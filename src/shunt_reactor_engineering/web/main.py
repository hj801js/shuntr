from __future__ import annotations

from contextlib import asynccontextmanager
import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from starlette.background import BackgroundTask

from ..cables import CABLE_LIBRARY, get_cable_spec
from ..reporting import ReportGenerationError
from .forms import StudyInputForm, default_form, validation_errors_as_dict
from .services import cleanup_workspace, compute_study, ensure_server_storage, generate_report_for_download

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "pages"
STATIC_DIR = BASE_DIR / "shared" / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_server_storage()
    yield


app = FastAPI(title="Shunt Reactor Engineering Web", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def cable_options() -> list[dict[str, str | float]]:
    return [
        {
            "code": spec.code,
            "label": spec.label,
            "capacitance": spec.capacitance_uf_per_km,
            "selected_value": spec.code,
        }
        for spec in CABLE_LIBRARY
    ]


def template_context(request: Request, **extra: object) -> dict[str, object]:
    context: dict[str, object] = {
        "request": request,
        "cable_options": cable_options(),
    }
    context.update(extra)
    return context


def resolve_selected_cable(code: str):
    try:
        return get_cable_spec(code)
    except KeyError:
        return CABLE_LIBRARY[0]


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    form = default_form()
    return templates.TemplateResponse(
        request,
        "home/templates/index.html",
        template_context(request, form=form, errors={}, selected_cable=get_cable_spec(form.cable_code)),
    )


@app.post("/analyze", response_class=HTMLResponse)
async def analyze(request: Request) -> HTMLResponse:
    form_data = await request.form()
    try:
        form = StudyInputForm.from_form_data({key: str(value) for key, value in form_data.multi_items()})
        computation = compute_study(form.to_study_input())
    except ValidationError as exc:
        fallback_form = default_form()
        merged = fallback_form.model_copy(update={k: str(v) for k, v in form_data.multi_items() if k in StudyInputForm.model_fields})
        selected_label = str(form_data.get("cable_code") or fallback_form.cable_code)
        return templates.TemplateResponse(
            request,
            "home/templates/index.html",
            template_context(
                request,
                form=merged,
                errors=validation_errors_as_dict(exc),
                selected_cable=resolve_selected_cable(selected_label),
            ),
            status_code=400,
        )

    return templates.TemplateResponse(
        request,
        "result/templates/result.html",
        template_context(
            request,
            form=form,
            result=computation.study_result,
            selected_cable=get_cable_spec(form.cable_code),
        ),
    )


@app.post("/report", response_model=None)
async def report(request: Request):
    form_data = await request.form()
    try:
        form = StudyInputForm.from_form_data({key: str(value) for key, value in form_data.multi_items()})
        report_result, workspace = generate_report_for_download(form.to_study_input())
    except ValidationError as exc:
        fallback_form = default_form()
        merged = fallback_form.model_copy(update={k: str(v) for k, v in form_data.multi_items() if k in StudyInputForm.model_fields})
        selected_label = str(form_data.get("cable_code") or fallback_form.cable_code)
        return templates.TemplateResponse(
            request,
            "home/templates/index.html",
            template_context(
                request,
                form=merged,
                errors=validation_errors_as_dict(exc),
                selected_cable=resolve_selected_cable(selected_label),
            ),
            status_code=400,
        )
    except ReportGenerationError as exc:
        form = StudyInputForm.from_form_data({key: str(value) for key, value in form_data.multi_items()})
        computation = compute_study(form.to_study_input())
        return templates.TemplateResponse(
            request,
            "result/templates/result.html",
            template_context(
                request,
                form=form,
                result=computation.study_result,
                selected_cable=get_cable_spec(form.cable_code),
                report_error=str(exc),
            ),
            status_code=500,
        )

    background = BackgroundTask(cleanup_workspace, workspace)
    return FileResponse(
        path=report_result.pdf_path,
        filename=report_result.pdf_path.name,
        media_type="application/pdf",
        background=background,
    )


def run() -> None:
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(
        "shunt_reactor_engineering.web.main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
    )


if __name__ == "__main__":
    run()
