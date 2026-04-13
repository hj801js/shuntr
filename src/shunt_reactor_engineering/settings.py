from __future__ import annotations

import json
import os
import secrets
from dataclasses import asdict, dataclass
from pathlib import Path

from .cables import CABLE_LIBRARY, CableSpec
from .paths import config_dir, project_root, writable_root

DEFAULT_LOGO_PATH = "data/uptec_logo.jpg"
DEFAULT_ADMIN_USERNAME = os.environ.get("SHUNT_REACTOR_ADMIN_USER", "admin")
DEFAULT_ADMIN_PASSWORD = os.environ.get("SHUNT_REACTOR_ADMIN_PASSWORD", "59119580")
LEGACY_ADMIN_PASSWORD = "uptec"


@dataclass(frozen=True, slots=True)
class AppSettings:
    logo_path: str = DEFAULT_LOGO_PATH
    cables: tuple[CableSpec, ...] = CABLE_LIBRARY


def default_settings() -> AppSettings:
    return AppSettings()


def settings_file_path() -> Path:
    return config_dir() / "app_settings.json"


def load_settings() -> AppSettings:
    path = settings_file_path()
    if not path.exists():
        return default_settings()

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default_settings()

    logo_path = str(payload.get("logo_path") or DEFAULT_LOGO_PATH)
    cables = _deserialize_cables(payload.get("cables"))
    return AppSettings(logo_path=logo_path, cables=cables)


def save_settings(settings: AppSettings) -> None:
    path = settings_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "logo_path": settings.logo_path,
        "cables": [asdict(spec) for spec in settings.cables],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def resolve_logo_path(settings: AppSettings) -> Path | None:
    return resolve_path_value(settings.logo_path)


def resolve_path_value(path_value: str | None) -> Path | None:
    if path_value is None:
        return None

    trimmed = path_value.strip()
    if not trimmed:
        return None

    raw_path = Path(trimmed).expanduser()
    candidates = [raw_path] if raw_path.is_absolute() else [writable_root() / raw_path, project_root() / raw_path]

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def normalize_path_for_storage(path_value: str) -> str:
    resolved = Path(path_value).expanduser().resolve(strict=False)
    for root in (writable_root(), project_root()):
        try:
            return str(resolved.relative_to(root))
        except ValueError:
            continue
    return str(resolved)


def verify_admin_credentials(username: str, password: str) -> bool:
    if not secrets.compare_digest(username, DEFAULT_ADMIN_USERNAME):
        return False
    return secrets.compare_digest(password, DEFAULT_ADMIN_PASSWORD) or secrets.compare_digest(
        password,
        LEGACY_ADMIN_PASSWORD,
    )


def _deserialize_cables(raw_cables: object) -> tuple[CableSpec, ...]:
    if not isinstance(raw_cables, list):
        return CABLE_LIBRARY

    loaded: list[CableSpec] = []
    for spec in raw_cables:
        if not isinstance(spec, dict):
            continue

        code = spec.get("code")
        label = spec.get("label")
        capacitance = spec.get("capacitance_uf_per_km")
        if not isinstance(code, str) or not isinstance(label, str):
            continue

        try:
            loaded.append(CableSpec(code=code, label=label, capacitance_uf_per_km=float(capacitance)))
        except (TypeError, ValueError):
            continue

    return tuple(loaded) if loaded else CABLE_LIBRARY
