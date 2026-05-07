from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Callable

from pocketStudio.core.config import Settings
from pocketStudio.core.database import Database
from pocketStudio.models import Event


class EventService:
    def __init__(self, db: Database, settings: Settings | None = None) -> None:
        self.db = db
        self.settings = settings
        self._listeners: list[Callable[[Event], None]] = []

    def emit(self, event_type: str, payload: dict) -> Event:
        payload_json = json.dumps(payload)
        cursor = self.db.execute(
            "INSERT INTO events (type, payload) VALUES (?, ?)",
            (event_type, payload_json),
        )
        row = self.db.fetch_one("SELECT * FROM events WHERE id = ?", (cursor.lastrowid,))
        event = self._to_event(row)
        self._append_log(event.type, payload_json, event.created_at)
        self._notify(event)
        return event

    def add_listener(self, listener: Callable[[Event], None]) -> None:
        if listener not in self._listeners:
            self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[Event], None]) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

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

    def log_records(
        self,
        limit: int = 100,
        event_type: str | None = None,
        contains: str | None = None,
    ) -> list[dict]:
        records = []
        for line in self.log_lines(limit=5000):
            if contains and contains not in line:
                continue
            record = self._parse_log_line(line)
            if event_type and record.get("type") != event_type:
                continue
            records.append(record)
        return records[-limit:]

    def office_event(self, event: Event) -> tuple[str, dict]:
        payload = event.payload
        timestamp = self._event_timestamp_ms(event.created_at)
        base = {"timestamp": timestamp, "eventId": event.id}
        if event.type == "message.queued":
            data = {
                **base,
                "type": "message:incoming",
                "messageId": str(payload.get("message_id", "")),
                "target": payload.get("target", ""),
                "message": payload.get("content", ""),
                "sender": payload.get("sender", "Web"),
                "metadata": payload.get("metadata", {}),
            }
            return data["type"], data
        if event.type == "message.running":
            data = {**base, "type": "message:processing", "messageId": str(payload.get("message_id", ""))}
            return data["type"], data
        if event.type == "message.done":
            data = {**base, "type": "message:done", "messageId": str(payload.get("message_id", ""))}
            return data["type"], data
        if event.type == "message.failed":
            data = {
                **base,
                "type": "message:failed",
                "messageId": str(payload.get("message_id", "")),
                "status": payload.get("status", "failed"),
                "error": payload.get("error", ""),
            }
            return data["type"], data
        if event.type == "agent.started":
            data = {
                **base,
                "type": "agent:invoke",
                "agentId": payload.get("agent_id", ""),
                "provider": payload.get("provider", ""),
            }
            return data["type"], data
        if event.type == "agent.process":
            data = {
                **base,
                "type": "agent:progress",
                "agentId": payload.get("agent_id", ""),
                "provider": payload.get("provider", ""),
                "process": payload.get("process", {}),
            }
            return data["type"], data
        if event.type == "agent.completed":
            data = {
                **base,
                "type": "agent:response",
                "agentId": payload.get("agent_id", ""),
                "content": payload.get("content", "Completed"),
            }
            return data["type"], data
        if event.type == "agent.mention":
            data = {
                **base,
                "type": "agent:mention",
                "teamId": payload.get("team_id", ""),
                "fromAgent": payload.get("from_agent", ""),
                "toAgent": payload.get("to_agent", ""),
            }
            return data["type"], data
        if event.type == "response.queued":
            data = {
                **base,
                "type": "response:queued",
                "responseId": payload.get("response_id"),
                "messageId": str(payload.get("message_id", "")),
                "channel": payload.get("channel", ""),
                "sender": payload.get("sender", ""),
                "senderId": payload.get("sender_id"),
                "agent": payload.get("agent"),
                "status": payload.get("status"),
            }
            return data["type"], data
        if event.type == "team.chatroom":
            data = {
                **base,
                "type": "team:chatroom",
                "teamId": payload.get("team_id", ""),
                "fromAgent": payload.get("from_agent", ""),
                "delivered": payload.get("delivered", 0),
            }
            return data["type"], data
        event_type = event.type.replace(".", ":")
        return event_type, {**base, "type": event_type, **payload}

    def _append_log(self, event_type: str, payload_json: str, created_at: str | None = None) -> None:
        if self.settings is None:
            return
        self.settings.logs_path.mkdir(parents=True, exist_ok=True)
        timestamp = created_at or datetime.now(timezone.utc).isoformat()
        line = f"[{timestamp}] [EVENT] {event_type} {payload_json}\n"
        with self.settings.log_file_path.open("a", encoding="utf-8") as handle:
            handle.write(line)

    def _notify(self, event: Event) -> None:
        for listener in list(self._listeners):
            try:
                listener(event)
            except Exception:
                continue

    @staticmethod
    def _parse_log_line(line: str) -> dict:
        match = re.match(r"^\[(?P<timestamp>[^\]]+)\]\s+\[(?P<level>[^\]]+)\]\s+(?P<type>\S+)\s+(?P<payload>.*)$", line)
        if not match:
            return {"line": line, "timestamp": None, "level": None, "type": None, "payload": None}
        payload_text = match.group("payload")
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError:
            payload = payload_text
        return {
            "line": line,
            "timestamp": match.group("timestamp"),
            "level": match.group("level"),
            "type": match.group("type"),
            "payload": payload,
        }

    @staticmethod
    def _event_timestamp_ms(value: str) -> int:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return int(datetime.now(timezone.utc).timestamp() * 1000)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return int(parsed.timestamp() * 1000)

    @staticmethod
    def _to_event(row) -> Event:
        return Event(
            id=row["id"],
            type=row["type"],
            payload=json.loads(row["payload"]),
            created_at=row["created_at"],
        )
