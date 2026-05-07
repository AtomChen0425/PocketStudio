from __future__ import annotations

import json
import re
import shutil
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


class SettingsValidationError(ValueError):
    pass


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
        self.validate(payload)
        current = self.snapshot()
        next_settings = self._merge(current, payload)
        self.write(next_settings)
        return self.snapshot()

    def preview_update(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.validate(payload)
        current = self.snapshot()
        next_settings = self._merge(current, payload)
        return {
            "ok": True,
            "changed": current != next_settings,
            "changes": self._diff(current, next_settings),
            "settings": next_settings,
        }

    def validate(self, payload: dict[str, Any]) -> None:
        if not isinstance(payload, dict):
            raise SettingsValidationError("settings payload must be an object")
        allowed = {"workspace", "channels", "models", "monitoring", "agents", "teams"}
        unknown = sorted(set(payload) - allowed)
        if unknown:
            raise SettingsValidationError(f"unknown settings section(s): {', '.join(unknown)}")
        self._validate_object(payload, "workspace")
        self._validate_object(payload, "channels")
        self._validate_object(payload, "models")
        self._validate_object(payload, "monitoring")
        self._validate_mapping(payload, "agents")
        self._validate_mapping(payload, "teams")

        workspace = payload.get("workspace") or {}
        if "name" in workspace and not isinstance(workspace["name"], str):
            raise SettingsValidationError("workspace.name must be a string")
        if "path" in workspace and not isinstance(workspace["path"], str):
            raise SettingsValidationError("workspace.path must be a string")

        channels = payload.get("channels") or {}
        if "enabled" in channels:
            enabled = channels["enabled"]
            if not isinstance(enabled, list) or not all(isinstance(item, str) and item for item in enabled):
                raise SettingsValidationError("channels.enabled must be a list of non-empty strings")
        if "defaults" in channels and not isinstance(channels["defaults"], dict):
            raise SettingsValidationError("channels.defaults must be an object")

        monitoring = payload.get("monitoring") or {}
        if "heartbeat_interval" in monitoring:
            interval = monitoring["heartbeat_interval"]
            if not isinstance(interval, int) or interval <= 0:
                raise SettingsValidationError("monitoring.heartbeat_interval must be a positive integer")

        models = payload.get("models") or {}
        if "provider" in models and not isinstance(models["provider"], str):
            raise SettingsValidationError("models.provider must be a string")
        if "custom_providers" in models and not isinstance(models["custom_providers"], dict):
            raise SettingsValidationError("models.custom_providers must be an object")

    @staticmethod
    def _validate_object(payload: dict[str, Any], key: str) -> None:
        if key in payload and not isinstance(payload[key], dict):
            raise SettingsValidationError(f"{key} must be an object")

    @staticmethod
    def _validate_mapping(payload: dict[str, Any], key: str) -> None:
        if key not in payload:
            return
        value = payload[key]
        if not isinstance(value, dict):
            raise SettingsValidationError(f"{key} must be an object")
        if not all(isinstance(item_key, str) and item_key for item_key in value):
            raise SettingsValidationError(f"{key} keys must be non-empty strings")

    def write(self, settings: dict[str, Any]) -> None:
        self.settings.pocketStudio_home.mkdir(parents=True, exist_ok=True)
        self._backup_current_settings()
        serialized = json.dumps(settings, ensure_ascii=False, indent=2) + "\n"
        self.settings.settings_path.write_text(serialized, encoding="utf-8")
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

    def backup_info(self) -> dict[str, Any]:
        backup = self.backup_path
        return {
            "exists": backup.exists(),
            "path": str(backup),
            "size": backup.stat().st_size if backup.exists() else 0,
            "modifiedAt": int(backup.stat().st_mtime * 1000) if backup.exists() else None,
        }

    def restore_backup(self) -> dict[str, Any]:
        backup = self.backup_path
        if not backup.exists():
            raise FileNotFoundError(f"Settings backup '{backup}' not found")
        raw = backup.read_text(encoding="utf-8")
        try:
            restored = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SettingsValidationError(f"settings backup is not valid JSON: {exc.msg}") from exc
        self.validate(restored)
        self.write(restored)
        return self.snapshot()

    @property
    def backup_path(self) -> Path:
        return self.settings.settings_path.with_suffix(self.settings.settings_path.suffix + ".bak")

    def _backup_current_settings(self) -> None:
        path = self.settings.settings_path
        if not path.exists():
            return
        shutil.copyfile(path, self.backup_path)

    @classmethod
    def _merge(cls, current: Any, update: Any) -> Any:
        if isinstance(current, dict) and isinstance(update, dict):
            merged = dict(current)
            for key, value in update.items():
                merged[key] = cls._merge(merged.get(key), value)
            return merged
        return update

    @classmethod
    def _diff(cls, current: Any, next_value: Any, prefix: str = "") -> list[dict[str, Any]]:
        if isinstance(current, dict) and isinstance(next_value, dict):
            changes: list[dict[str, Any]] = []
            for key in sorted(set(current) | set(next_value)):
                path = f"{prefix}.{key}" if prefix else key
                if key not in current:
                    changes.append({"path": path, "type": "added", "before": None, "after": next_value[key]})
                elif key not in next_value:
                    changes.append({"path": path, "type": "removed", "before": current[key], "after": None})
                else:
                    changes.extend(cls._diff(current[key], next_value[key], path))
            return changes
        if current != next_value:
            return [{"path": prefix, "type": "changed", "before": current, "after": next_value}]
        return []

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
