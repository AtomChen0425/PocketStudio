from __future__ import annotations

import json

from pocketStudio.core.database import Database
from pocketStudio.models import Event


class EventService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def emit(self, event_type: str, payload: dict) -> Event:
        cursor = self.db.execute(
            "INSERT INTO events (type, payload) VALUES (?, ?)",
            (event_type, json.dumps(payload)),
        )
        row = self.db.fetch_one("SELECT * FROM events WHERE id = ?", (cursor.lastrowid,))
        return self._to_event(row)

    def list(self, limit: int = 100, since: int = 0) -> list[Event]:
        rows = self.db.fetch_all(
            "SELECT * FROM events WHERE id > ? ORDER BY id DESC LIMIT ?",
            (since, limit),
        )
        return [self._to_event(row) for row in rows]

    @staticmethod
    def _to_event(row) -> Event:
        return Event(
            id=row["id"],
            type=row["type"],
            payload=json.loads(row["payload"]),
            created_at=row["created_at"],
        )

