from datetime import datetime

from shunt_reactor_engineering import ChargingCurrentStudyInput, evaluate_study, render_report_tex
from shunt_reactor_engineering.reporting import (
    default_report_filename,
    generate_report,
    make_unique_report_stem,
    sanitize_report_filename,
)


def test_render_report_tex_contains_requested_sections() -> None:
    study_input = ChargingCurrentStudyInput()
    study_result = evaluate_study(study_input)

    rendered = render_report_tex(study_result, datetime(2026, 3, 11, 12, 0))

    assert "충전전류 계산" in rendered
    assert "무효전력 계산" in rendered
    assert "개폐전류 및 개폐선로 길이 검토" in rendered
    assert "개폐선로 실제 길이" in rendered
    assert "허용 개폐선로 길이 환산값" in rendered
    assert r"\item 개폐전류 검토: \textbf{만족.}" in rendered
    assert "재생에너지 연계 변전소" in rendered
    assert "mm²" in rendered
    assert r"D_{\mathrm{total}}" in rendered
    assert "작성일자" not in rendered
    assert "최종" not in rendered
    assert "결론" not in rendered
    assert "판정:" not in rendered
    assert "산정식 적용." not in rendered
    assert "환산식 적용." not in rendered


def test_render_report_tex_uses_manual_compensation_value() -> None:
    study_input = ChargingCurrentStudyInput(compensation_mvar=3.25)
    study_result = evaluate_study(study_input)

    rendered = render_report_tex(study_result, datetime(2026, 3, 11, 12, 0))

    assert r"\item 보상용량: \textbf{3.25 MVar}" in rendered
    assert "보상용량 & 3.25 MVar" in rendered


def test_sanitize_report_filename_removes_invalid_characters() -> None:
    assert sanitize_report_filename("재생에너지:연계/변전소?.pdf") == "재생에너지_연계_변전소_"


def test_default_report_filename_uses_project_name() -> None:
    assert default_report_filename("재생에너지 연계 변전소") == "재생에너지 연계 변전소 검토서"


def test_make_unique_report_stem_appends_counter(tmp_path) -> None:
    report_dir = tmp_path / "reports"
    build_dir = tmp_path / "build"
    report_dir.mkdir()
    build_dir.mkdir()
    (report_dir / "재생에너지 연계 변전소 검토서.pdf").write_text("x", encoding="utf-8")
    (report_dir / "재생에너지 연계 변전소 검토서.tex").write_text("x", encoding="utf-8")

    unique_name = make_unique_report_stem("재생에너지 연계 변전소 검토서", report_dir, build_dir)

    assert unique_name == "재생에너지 연계 변전소 검토서 (2)"


def test_generate_report_uses_custom_build_directory(tmp_path, monkeypatch) -> None:
    output_dir = tmp_path / "reports"
    build_dir = tmp_path / "build"
    output_dir.mkdir()
    build_dir.mkdir()

    def fake_compile_pdf(tex_path, output_dir):
        (output_dir / f"{tex_path.stem}.pdf").write_bytes(b"%PDF-1.4\n%mock\n")

    monkeypatch.setattr("shunt_reactor_engineering.reporting.compile_pdf", fake_compile_pdf)

    report = generate_report(
        ChargingCurrentStudyInput(),
        output_directory=output_dir,
        build_directory=build_dir,
    )

    assert report.pdf_path.parent == output_dir
    assert report.tex_path.parent == output_dir
    assert (build_dir / report.filename_stem / f"{report.filename_stem}.tex").exists()
