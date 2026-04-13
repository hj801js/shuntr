from pathlib import Path

from fastapi.testclient import TestClient

from shunt_reactor_engineering.web.main import app


client = TestClient(app)


def _default_payload() -> dict[str, str]:
    return {
        "project_name": "재생에너지 연계 변전소",
        "line_voltage_kv": "154.0",
        "frequency_hz": "60.0",
        "cable_code": "xlpe_1200",
        "capacitance_uf_per_km": "0.24",
        "route_length_km": "0.5",
        "circuit_count": "1",
        "switching_limit_a": "400.0",
        "compensation_mvar": "",
    }


def test_home_page_renders() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Shunt Reactor Engineering" in response.text
    assert "계산하기" in response.text


def test_healthz() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_analyze_renders_result() -> None:
    response = client.post("/analyze", data=_default_payload())
    assert response.status_code == 200
    assert "계산 결과" in response.text
    assert "PDF 다운로드" in response.text


def test_invalid_input_returns_400() -> None:
    payload = _default_payload()
    payload["route_length_km"] = "0"
    response = client.post("/analyze", data=payload)
    assert response.status_code == 400
    assert "greater than 0" in response.text or "입력값" in response.text


def test_invalid_cable_code_returns_400() -> None:
    payload = _default_payload()
    payload["cable_code"] = "bad"
    response = client.post("/analyze", data=payload)
    assert response.status_code == 400
    assert "지원하지 않는 케이블" in response.text


def test_report_invalid_cable_code_returns_400() -> None:
    payload = _default_payload()
    payload["cable_code"] = "bad"
    response = client.post("/report", data=payload)
    assert response.status_code == 400
    assert "지원하지 않는 케이블" in response.text


def test_report_download_streams_pdf(monkeypatch, tmp_path) -> None:
    from shunt_reactor_engineering.web import main as web_main

    workspace = tmp_path / "workspace"
    reports = workspace / "reports"
    reports.mkdir(parents=True)
    pdf_path = reports / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%mock\n")

    class DummyReport:
        def __init__(self, path: Path):
            self.pdf_path = path

    def fake_generate_report_for_download(_study_input):
        return DummyReport(pdf_path), workspace

    monkeypatch.setattr(web_main, "generate_report_for_download", fake_generate_report_for_download)

    response = client.post("/report", data=_default_payload())
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF-1.4")
