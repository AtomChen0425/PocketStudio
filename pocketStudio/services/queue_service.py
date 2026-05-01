from __future__ import annotations

from pocketStudio.core.config import Settings
from pocketStudio.core.database import Database
from pocketStudio.models import MessageCreate, MessageStatus, QueueMessage
from pocketStudio.services.event_service import EventService


class QueueService:
    def __init__(self, db: Database, events: EventService, settings: Settings) -> None:
        self.db = db
        self.events = events
        self.settings = settings

    def enqueue(self, payload: MessageCreate) -> QueueMessage:
        cursor = self.db.execute(
            "INSERT INTO messages (target, content, sender) VALUES (?, ?, ?)",
            (payload.target, payload.content, payload.sender),
        )
        message = self.get(cursor.lastrowid)
        self.events.emit(
            "message.queued",
            {"message_id": message.id, "target": message.target, "content": message.content, "sender": message.sender},
        )
        return message

    def get(self, message_id: int) -> QueueMessage:
        row = self.db.fetch_one("SELECT * FROM messages WHERE id = ?", (message_id,))
        if row is None:
            raise KeyError(f"Message '{message_id}' not found")
        return self._to_message(row)

    def list(self, limit: int = 100, status: MessageStatus | None = None) -> list[QueueMessage]:
        if status is None:
            rows = self.db.fetch_all("SELECT * FROM messages ORDER BY id DESC LIMIT ?", (limit,))
        else:
            rows = self.db.fetch_all(
                "SELECT * FROM messages WHERE status = ? ORDER BY id DESC LIMIT ?",
                (status.value, limit),
            )
        return [self._to_message(row) for row in rows]

    def next_queued(self) -> QueueMessage | None:
        row = self.db.fetch_one(
            """
            SELECT * FROM messages
            WHERE status IN ('queued', 'failed') AND attempts < ?
            ORDER BY id ASC
            LIMIT 1
            """,
            (self.settings.queue_max_attempts,),
        )
        return self._to_message(row) if row else None

    def mark_running(self, message_id: int) -> QueueMessage:
        self.db.execute(
            """
            UPDATE messages
            SET status = 'running', attempts = attempts + 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (message_id,),
        )
        self.events.emit("message.running", {"message_id": message_id})
        return self.get(message_id)

    def mark_done(self, message_id: int, result: str) -> QueueMessage:
        self.db.execute(
            """
            UPDATE messages
            SET status = 'done', result = ?, error = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (result, message_id),
        )
        self.events.emit("message.done", {"message_id": message_id})
        return self.get(message_id)

    def mark_failed(self, message_id: int, error: str) -> QueueMessage:
        message = self.get(message_id)
        status = MessageStatus.dead if message.attempts >= self.settings.queue_max_attempts else MessageStatus.failed
        self.db.execute(
            """
            UPDATE messages
            SET status = ?, error = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status.value, error, message_id),
        )
        self.events.emit("message.failed", {"message_id": message_id, "status": status.value, "error": error})
        return self.get(message_id)

    @staticmethod
    def _to_message(row) -> QueueMessage:
        return QueueMessage(
            id=row["id"],
            target=row["target"],
            content=row["content"],
            sender=row["sender"],
            status=row["status"],
            attempts=row["attempts"],
            error=row["error"],
            result=row["result"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
