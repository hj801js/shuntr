from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from importlib import resources
from pathlib import Path

from jinja2 import Environment

from .paths import (
    ensure_runtime_dirs,
    latex_build_dir,
    reports_dir,
    resolve_tectonic_executable,
    resolve_xelatex_executable,
)
from .studies import ChargingCurrentStudyInput, ChargingCurrentStudyResult, evaluate_study


@dataclass(frozen=True, slots=True)
class GeneratedReport:
    study_result: ChargingCurrentStudyResult
    created_at: datetime
    requested_stem: str
    filename_stem: str
    tex_path: Path
    pdf_path: Path


class ReportGenerationError(RuntimeError):
    pass


def generate_report(
    study_input: ChargingCurrentStudyInput,
    filename_stem: str | None = None,
    output_directory: Path | None = None,
    build_directory: Path | None = None,
) -> GeneratedReport:
    ensure_runtime_dirs()
    study_result = evaluate_study(study_input)
    created_at = datetime.now()
    target_output_dir = (output_directory or reports_dir()).expanduser().resolve(strict=False)
    target_output_dir.mkdir(parents=True, exist_ok=True)
    target_build_dir = (build_directory or latex_build_dir()).expanduser().resolve(strict=False)
    target_build_dir.mkdir(parents=True, exist_ok=True)
    requested_stem = sanitize_report_filename(filename_stem or default_report_filename(study_input.project_name))
    actual_stem = make_unique_report_stem(requested_stem, target_output_dir, target_build_dir)

    job_dir = target_build_dir / actual_stem
    job_dir.mkdir(parents=True, exist_ok=True)

    tex_filename = f"{actual_stem}.tex"
    tex_path = job_dir / tex_filename
    public_tex_path = target_output_dir / tex_filename
    pdf_path = target_output_dir / f"{actual_stem}.pdf"

    tex_content = render_report_tex(study_result, created_at)
    tex_path.write_text(tex_content, encoding="utf-8")
    public_tex_path.write_text(tex_content, encoding="utf-8")

    compile_pdf(tex_path=tex_path, output_dir=target_output_dir)

    if not pdf_path.exists():
        raise ReportGenerationError(f"expected PDF was not created: {pdf_path}")

    return GeneratedReport(
        study_result=study_result,
        created_at=created_at,
        requested_stem=requested_stem,
        filename_stem=actual_stem,
        tex_path=public_tex_path,
        pdf_path=pdf_path,
    )


def render_report_tex(study_result: ChargingCurrentStudyResult, created_at: datetime) -> str:
    environment = Environment(
        autoescape=False,
        block_start_string=r"\BLOCK{",
        block_end_string="}",
        variable_start_string=r"\VAR{",
        variable_end_string="}",
        comment_start_string=r"\#{",
        comment_end_string="}",
        trim_blocks=True,
        lstrip_blocks=True,
    )
    environment.filters["latex"] = latex_escape
    template_text = (
        resources.files("shunt_reactor_engineering")
        .joinpath("resources", "latex", "report_template.tex.jinja")
        .read_text(encoding="utf-8")
    )
    template = environment.from_string(template_text)

    study_input = study_result.study_input
    switching_conclusion = "만족." if not study_result.switching_limit_exceeded else "불만족."

    return template.render(
        created_date=created_at.strftime("%Y-%m-%d"),
        project_name=study_input.project_name,
        cable_name=study_input.cable_name,
        line_voltage_kv=format_number(study_input.line_voltage_kv, 1),
        frequency_hz=format_number(study_input.frequency_hz, 1),
        capacitance_uf_per_km=format_number(study_input.capacitance_uf_per_km, 3),
        route_length_km=format_number(study_input.route_length_km, 3),
        circuit_count=study_input.circuit_count,
        switching_limit_a=format_number(study_input.switching_limit_a, 1),
        total_length_km=format_number(study_result.total_length_km, 3),
        charging_current_per_km_a=format_number(study_result.charging_current_per_km_a, 3),
        charging_current_a=format_number(study_result.charging_current_a, 3),
        reactive_power_mvar=format_number(study_result.reactive_power_mvar, 3),
        recommended_compensation_mvar=format_number(study_result.recommended_compensation_mvar, 3),
        switching_margin_a=format_number(study_result.switching_margin_a, 3),
        switching_utilization_pct=format_number(study_result.switching_utilization_pct, 2),
        max_total_length_km=format_number(study_result.max_total_length_km, 3),
        max_route_length_per_circuit_km=format_number(study_result.max_route_length_per_circuit_km, 3),
        switching_conclusion=switching_conclusion,
    )


def compile_pdf(tex_path: Path, output_dir: Path) -> None:
    engine_name, command = build_latex_command(tex_path=tex_path, output_dir=output_dir)
    result = subprocess.run(
        command,
        cwd=tex_path.parent,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        output = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part)
        raise ReportGenerationError(output or f"{engine_name} failed without an error message")

    if engine_name == "xelatex":
        cleanup_xelatex_files(output_dir=output_dir, stem=tex_path.stem)


def build_latex_command(tex_path: Path, output_dir: Path) -> tuple[str, list[str]]:
    try:
        tectonic = resolve_tectonic_executable()
    except FileNotFoundError:
        tectonic = None

    try:
        xelatex = resolve_xelatex_executable()
    except FileNotFoundError:
        xelatex = None

    if tectonic and Path(tectonic).parent.name.lower() == "tools":
        return (
            "tectonic",
            [
                tectonic,
                "--chatter=minimal",
                "--outdir",
                str(output_dir),
                str(tex_path),
            ],
        )

    if xelatex:
        return (
            "xelatex",
            [
                xelatex,
                "-interaction=nonstopmode",
                "-halt-on-error",
                f"-output-directory={output_dir}",
                str(tex_path),
            ],
        )

    if tectonic:
        return (
            "tectonic",
            [
                tectonic,
                "--chatter=minimal",
                "--outdir",
                str(output_dir),
                str(tex_path),
            ],
        )

    raise ReportGenerationError(
        "No LaTeX engine was found. Install tectonic or xelatex, or place the executable in tools/."
    )


def default_report_filename(project_name: str) -> str:
    return sanitize_report_filename(f"{project_name} 검토서")


def sanitize_report_filename(value: str) -> str:
    candidate = re.sub(r"\.pdf$", "", value.strip(), flags=re.IGNORECASE)
    candidate = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", candidate)
    candidate = re.sub(r"\s+", " ", candidate).strip().rstrip(".")
    return candidate or "shunt-reactor-report"


def make_unique_report_stem(base_stem: str, report_directory: Path, build_directory: Path) -> str:
    candidate = base_stem
    index = 2
    while _report_name_exists(candidate, report_directory, build_directory):
        candidate = f"{base_stem} ({index})"
        index += 1
    return candidate


def _report_name_exists(candidate: str, report_directory: Path, build_directory: Path) -> bool:
    return any(
        (
            (report_directory / f"{candidate}.pdf").exists(),
            (report_directory / f"{candidate}.tex").exists(),
            (build_directory / candidate).exists(),
        )
    )


def format_number(value: float, digits: int) -> str:
    formatted = f"{value:.{digits}f}"
    return re.sub(r"(\.\d*?[1-9])0+$", r"\1", re.sub(r"\.0+$", "", formatted))


def latex_escape(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(character, character) for character in value)


def cleanup_xelatex_files(output_dir: Path, stem: str) -> None:
    for suffix in (".aux", ".log", ".out", ".xdv"):
        candidate = output_dir / f"{stem}{suffix}"
        if candidate.exists():
            candidate.unlink()
