from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def writable_root() -> Path:
    onefile_directory = os.environ.get("NUITKA_ONEFILE_DIRECTORY")
    if onefile_directory:
        return Path(onefile_directory).resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    if "__compiled__" in globals():
        return Path(sys.argv[0]).resolve().parent
    return project_root()


def output_root() -> Path:
    override = os.environ.get("SHUNT_REACTOR_OUTPUT_DIR")
    if override:
        return Path(override).expanduser().resolve(strict=False)
    return writable_root() / "output"


def config_dir() -> Path:
    return output_root() / "config"


def reports_dir() -> Path:
    return output_root() / "reports"


def runtime_dir() -> Path:
    override = os.environ.get("SHUNT_REACTOR_RUNTIME_DIR")
    if override:
        return Path(override).expanduser().resolve(strict=False)
    return output_root() / "runtime"


def latex_build_dir() -> Path:
    return runtime_dir() / "latex"


def tools_dir() -> Path:
    return writable_root() / "tools"


def ensure_runtime_dirs() -> None:
    config_dir().mkdir(parents=True, exist_ok=True)
    reports_dir().mkdir(parents=True, exist_ok=True)
    latex_build_dir().mkdir(parents=True, exist_ok=True)


def resolve_tectonic_executable() -> str:
    candidates = [
        tools_dir() / "tectonic.exe",
        writable_root() / "tectonic.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    found = shutil.which("tectonic")
    if found:
        return found

    raise FileNotFoundError(
        "tectonic executable was not found. Install it into the current environment or place tectonic.exe in tools/."
    )


def resolve_xelatex_executable() -> str:
    candidates = [
        tools_dir() / "xelatex.exe",
        writable_root() / "xelatex.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    found = shutil.which("xelatex")
    if found:
        return found

    raise FileNotFoundError(
        "xelatex executable was not found. Install TeX Live/MiKTeX or place xelatex.exe in tools/."
    )
