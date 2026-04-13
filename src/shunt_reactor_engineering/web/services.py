from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from ..paths import output_root, runtime_dir
from ..reporting import GeneratedReport, generate_report
from ..studies import ChargingCurrentStudyInput, ChargingCurrentStudyResult, evaluate_study


@dataclass(frozen=True, slots=True)
class StudyComputation:
    study_input: ChargingCurrentStudyInput
    study_result: ChargingCurrentStudyResult


def compute_study(study_input: ChargingCurrentStudyInput) -> StudyComputation:
    return StudyComputation(study_input=study_input, study_result=evaluate_study(study_input))


def create_request_workspace() -> Path:
    root = runtime_dir() / "web-jobs"
    root.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="job-", dir=root))


def cleanup_workspace(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)


def generate_report_for_download(study_input: ChargingCurrentStudyInput) -> tuple[GeneratedReport, Path]:
    workspace = create_request_workspace()
    output_directory = workspace / "reports"
    build_directory = workspace / "latex"
    output_directory.mkdir(parents=True, exist_ok=True)
    build_directory.mkdir(parents=True, exist_ok=True)
    report = generate_report(
        study_input=study_input,
        output_directory=output_directory,
        build_directory=build_directory,
    )
    return report, workspace


def ensure_server_storage() -> None:
    output_root().mkdir(parents=True, exist_ok=True)
    runtime_dir().mkdir(parents=True, exist_ok=True)
