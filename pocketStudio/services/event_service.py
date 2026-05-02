from __future__ import annotations

import json
from datetime import datetime, timezone

from pocketStudio.core.config import Settings
from pocketStudio.core.database import Database
from pocketStudio.models import Event


class EventService:
    def __init__(self, db: Database, settings: Settings | None = None) -> None:
        self.db = db
        self.settings = settings

    def emit(self, event_type: str, payload: dict) -> Event:
        payload_json = json.dumps(payload)
        cursor = self.db.execute(
            "INSERT INTO events (type, payload) VALUES (?, ?)",
            (event_type, payload_json),
        )
        row = self.db.fetch_one("SELECT * FROM events WHERE id = ?", (cursor.lastrowid,))
        event = self._to_event(row)
        self._append_log(event.type, payload_json, event.created_at)
        return event

    def list(self, limit: int = 100, since: int = 0) -> list[Event]:
        rows = self.db.fetch_all(
            "SELECT * FROM events WHERE id > ? ORDER BY id DESC LIMIT ?",
            (since, limit),
        )
        return [self._to_event(row) for row in rows]

    def log_lines(self, limit: int = 100) -> list[str]:
        if self.settings is None or not self.settings.log_file_path.exists():
            return []
        lines = self.settings.log_file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        return lines[-limit:]

    def _append_log(self, event_type: str, payload_json: str, created_at: str | None = None) -> None:
        if self.settings is None:
            return
        self.settings.logs_path.mkdir(parents=True, exist_ok=True)
        timestamp = created_at or datetime.now(timezone.utc).isoformat()
        line = f"[{timestamp}] [EVENT] {event_type} {payload_json}\n"
        with self.settings.log_file_path.open("a", encoding="utf-8") as handle:
            handle.write(line)

    @staticmethod
    def _to_event(row) -> Event:
        return Event(
            id=row["id"],
            type=row["type"],
            payload=json.loads(row["payload"]),
            created_at=row["created_at"],
        )
