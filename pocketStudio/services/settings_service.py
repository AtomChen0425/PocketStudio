from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pocketStudio.core.config import Settings
from pocketStudio.core.database import Database


DEFAULT_SETTINGS = {
    "workspace": {"name": "pocketStudio", "path": ".pocketStudio/workspace"},
    "channels": {"enabled": ["web"]},
    "models": {"provider": "local", "openai": {"model": "gpt-4o-mini"}},
    "monitoring": {"heartbeat_interval": 3600},
}


class SettingsService:
    def __init__(self, db: Database, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    def snapshot(self) -> dict[str, Any]:
        result = json.loads(json.dumps(DEFAULT_SETTINGS))
        result = self._merge(result, self._legacy_db_settings())
        result = self._merge(result, self._file_settings())
        return result

    def update(self, payload: dict[str, Any]) -> dict[str, Any]:
        current = self.snapshot()
        next_settings = self._merge(current, payload)
        self.write(next_settings)
        return self.snapshot()

    def write(self, settings: dict[str, Any]) -> None:
        self.settings.pocketStudio_home.mkdir(parents=True, exist_ok=True)
        self.settings.settings_path.write_text(
            json.dumps(settings, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        for key in ("workspace", "channels", "models", "monitoring", "agents", "teams"):
            if key in settings:
                self.db.execute(
                    """
                    INSERT INTO app_settings (key, value, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(key) DO UPDATE SET
                      value = excluded.value,
                      updated_at = CURRENT_TIMESTAMP
                    """,
                    (key, json.dumps(settings[key], ensure_ascii=False)),
                )

    def _file_settings(self) -> dict[str, Any]:
        path = self.settings.settings_path
        if not path.exists():
            return {}
        raw = path.read_text(encoding="utf-8")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            backup = path.with_suffix(path.suffix + ".bak")
            backup.write_text(raw, encoding="utf-8")
            repaired = self._repair_json(raw)
            if repaired is None:
                return {}
            path.write_text(json.dumps(repaired, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return repaired

    def _legacy_db_settings(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        rows = self.db.fetch_all("SELECT key, value FROM app_settings")
        for row in rows:
            try:
                value = json.loads(row["value"])
            except json.JSONDecodeError:
                continue
            result[row["key"]] = self._merge(result.get(row["key"], {}), value)
        return result

    def ensure_setup_dirs(self, settings: dict[str, Any]) -> None:
        self.settings.pocketStudio_home.mkdir(parents=True, exist_ok=True)
        self.settings.logs_path.mkdir(parents=True, exist_ok=True)
        self.settings.files_path.mkdir(parents=True, exist_ok=True)
        workspace_path = (settings.get("workspace") or {}).get("path")
        if workspace_path:
            Path(workspace_path).expanduser().mkdir(parents=True, exist_ok=True)

    @classmethod
    def _merge(cls, current: Any, update: Any) -> Any:
        if isinstance(current, dict) and isinstance(update, dict):
            merged = dict(current)
            for key, value in update.items():
                merged[key] = cls._merge(merged.get(key), value)
            return merged
        return update

    @staticmethod
    def _repair_json(raw: str) -> dict[str, Any] | None:
        candidates = [
            raw,
            re.sub(r",\s*([}\]])", r"\1", raw),
            re.sub(r"'", '"', re.sub(r",\s*([}\]])", r"\1", raw)),
        ]
        for candidate in candidates:
            try:
                value = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            return value if isinstance(value, dict) else None
        return None
