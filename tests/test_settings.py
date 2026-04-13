from pathlib import Path

from shunt_reactor_engineering.cables import CABLE_LIBRARY
from shunt_reactor_engineering.settings import (
    AppSettings,
    load_settings,
    normalize_path_for_storage,
    resolve_logo_path,
    save_settings,
    verify_admin_credentials,
)


def test_settings_round_trip(tmp_path, monkeypatch) -> None:
    config_file = tmp_path / "output" / "config" / "app_settings.json"
    monkeypatch.setattr("shunt_reactor_engineering.settings.settings_file_path", lambda: config_file)

    settings = AppSettings(logo_path="data/uptec_logo.jpg", cables=(CABLE_LIBRARY[0],))

    save_settings(settings)
    loaded = load_settings()

    assert loaded.logo_path == "data/uptec_logo.jpg"
    assert loaded.cables[0].label == CABLE_LIBRARY[0].label


def test_resolve_logo_path_returns_none_when_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("shunt_reactor_engineering.settings.writable_root", lambda: tmp_path)
    monkeypatch.setattr("shunt_reactor_engineering.settings.project_root", lambda: tmp_path)

    resolved = resolve_logo_path(AppSettings(logo_path="data/missing_logo.jpg", cables=CABLE_LIBRARY))

    assert resolved is None


def test_normalize_path_for_storage_prefers_relative_workspace_path(tmp_path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    logo_path = workspace / "data" / "uptec_logo.jpg"
    logo_path.parent.mkdir(parents=True)
    logo_path.write_bytes(b"logo")

    monkeypatch.setattr("shunt_reactor_engineering.settings.writable_root", lambda: workspace)
    monkeypatch.setattr("shunt_reactor_engineering.settings.project_root", lambda: workspace)

    normalized = normalize_path_for_storage(str(logo_path))

    assert normalized == str(Path("data") / "uptec_logo.jpg")


def test_verify_admin_credentials_accepts_current_and_legacy_passwords() -> None:
    assert verify_admin_credentials("admin", "59119580") is True
    assert verify_admin_credentials("admin", "uptec") is True
    assert verify_admin_credentials("admin", "wrong-password") is False
