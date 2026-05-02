import shutil
import uuid
from pathlib import Path

from pocketStudio.core.config import Settings
from pocketStudio.core.database import Database
from pocketStudio.services.settings_service import SettingsService


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
