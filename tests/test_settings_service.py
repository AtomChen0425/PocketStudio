import json
import shutil
import uuid
from pathlib import Path

from pocketStudio.core.config import Settings
from pocketStudio.core.database import Database
import pytest

from pocketStudio.services.settings_service import SettingsService, SettingsValidationError


def temp_home() -> Path:
    root = Path(".pytest-tmp")
    root.mkdir(exist_ok=True)
    home = root / uuid.uuid4().hex
    home.mkdir()
    return home


def test_settings_json_is_primary_store_and_repairs_common_json_errors() -> None:
    home = temp_home()
    try:
        settings = Settings(pocketStudio_home=home)
        db = Database(settings.database_path, journal_mode=settings.sqlite_journal_mode)
        db.initialize()
        service = SettingsService(db, settings)

        settings.settings_path.write_text(
            "{'monitoring': {'heartbeat_interval': 45,}, 'channels': {'enabled': ['web',],},}",
            encoding="utf-8",
        )

        snapshot = service.snapshot()

        assert snapshot["monitoring"]["heartbeat_interval"] == 45
        assert snapshot["channels"]["enabled"] == ["web"]
        assert settings.settings_path.with_suffix(".json.bak").exists()
        assert settings.settings_path.read_text(encoding="utf-8").startswith("{\n")
    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_settings_write_backs_up_existing_file() -> None:
    home = temp_home()
    try:
        settings = Settings(pocketStudio_home=home)
        db = Database(settings.database_path, journal_mode=settings.sqlite_journal_mode)
        db.initialize()
        service = SettingsService(db, settings)

        settings.settings_path.write_text('{"workspace": {"name": "before"}}\n', encoding="utf-8")
        snapshot = service.update({"workspace": {"name": "after"}})

        assert snapshot["workspace"]["name"] == "after"
        assert settings.settings_path.with_suffix(".json.bak").read_text(encoding="utf-8") == '{"workspace": {"name": "before"}}\n'
        assert not settings.settings_path.with_suffix(".json.tmp").exists()
    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_settings_backup_can_be_inspected_and_restored() -> None:
    home = temp_home()
    try:
        settings = Settings(pocketStudio_home=home)
        db = Database(settings.database_path, journal_mode=settings.sqlite_journal_mode)
        db.initialize()
        service = SettingsService(db, settings)

        settings.settings_path.write_text('{"workspace": {"name": "before"}}\n', encoding="utf-8")
        service.update({"workspace": {"name": "after"}})

        backup = service.backup_info()

        assert backup["exists"] is True
        assert backup["path"] == str(settings.settings_path.with_suffix(".json.bak"))
        assert backup["size"] > 0
        assert backup["modifiedAt"] is not None

        restored = service.restore_backup()

        assert restored["workspace"]["name"] == "before"
        assert service.snapshot()["workspace"]["name"] == "before"
        assert json.loads(settings.settings_path.with_suffix(".json.bak").read_text(encoding="utf-8"))["workspace"]["name"] == "after"
    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_settings_validation_rejects_bad_sections_and_types() -> None:
    home = temp_home()
    try:
        settings = Settings(pocketStudio_home=home)
        db = Database(settings.database_path, journal_mode=settings.sqlite_journal_mode)
        db.initialize()
        service = SettingsService(db, settings)

        with pytest.raises(SettingsValidationError, match="unknown settings section"):
            service.update({"unknown": {}})
        with pytest.raises(SettingsValidationError, match="channels.enabled"):
            service.update({"channels": {"enabled": "web"}})
        with pytest.raises(SettingsValidationError, match="heartbeat_interval"):
            service.update({"monitoring": {"heartbeat_interval": 0}})
        with pytest.raises(SettingsValidationError, match="workspace.path"):
            service.update({"workspace": {"path": 123}})
    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_settings_preview_reports_diff_without_writing() -> None:
    home = temp_home()
    try:
        settings = Settings(pocketStudio_home=home)
        db = Database(settings.database_path, journal_mode=settings.sqlite_journal_mode)
        db.initialize()
        service = SettingsService(db, settings)
        service.update({"workspace": {"name": "before"}, "monitoring": {"heartbeat_interval": 30}})
        before = settings.settings_path.read_text(encoding="utf-8")

        preview = service.preview_update({"workspace": {"name": "after"}, "channels": {"enabled": ["web", "cli"]}})

        assert preview["ok"] is True
        assert preview["changed"] is True
        assert {"path": "workspace.name", "type": "changed", "before": "before", "after": "after"} in preview["changes"]
        assert {"path": "channels.enabled", "type": "changed", "before": ["web"], "after": ["web", "cli"]} in preview["changes"]
        assert service.snapshot()["workspace"]["name"] == "before"
        assert settings.settings_path.read_text(encoding="utf-8") == before
    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_settings_preview_api_validates_without_persisting() -> None:
    from fastapi.testclient import TestClient

    from pocketStudio.main import app

    with TestClient(app) as client:
        current = client.get("/api/settings").json()
        original_name = current["workspace"]["name"]
        preview = client.post("/api/settings/preview", json={"settings": {"workspace": {"name": f"preview-{uuid.uuid4().hex[:8]}"}}})
        invalid = client.post("/api/settings/preview", json={"settings": {"monitoring": {"heartbeat_interval": 0}}})
        after = client.get("/api/settings").json()

        assert preview.status_code == 200
        assert preview.json()["changed"] is True
        assert any(change["path"] == "workspace.name" for change in preview.json()["changes"])
        assert invalid.status_code == 422
        assert after["workspace"]["name"] == original_name
