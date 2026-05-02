from __future__ import annotations

from pocketStudio.core.database import Database
from pocketStudio.models import ChatMessage, ChatMessageCreate
from pocketStudio.services.event_service import EventService


class ChatService:
    def __init__(self, db: Database, events: EventService) -> None:
        self.db = db
        self.events = events

    def post(self, team_id: str, payload: ChatMessageCreate) -> ChatMessage:
        cursor = self.db.execute(
            "INSERT INTO chat_messages (team_id, sender, message) VALUES (?, ?, ?)",
            (team_id, payload.sender, payload.message),
        )
        message = self.get(cursor.lastrowid)
        self.events.emit("chat.posted", {"team_id": team_id, "message_id": message.id, "sender": payload.sender})
        return message

    def get(self, message_id: int) -> ChatMessage:
        row = self.db.fetch_one("SELECT * FROM chat_messages WHERE id = ?", (message_id,))
        if row is None:
            raise KeyError(f"Chat message '{message_id}' not found")
        return self._to_message(row)

    def list(self, team_id: str, limit: int = 100, since: int = 0) -> list[ChatMessage]:
        rows = self.db.fetch_all(
            """
            SELECT * FROM chat_messages
            WHERE team_id = ? AND id > ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (team_id, since, limit),
        )
        return [self._to_message(row) for row in rows]

    def archives(self) -> list[dict]:
        rows = self.db.fetch_all(
            """
            SELECT team_id, COUNT(*) AS count, MAX(created_at) AS last_time, MAX(id) AS last_message_id
            FROM chat_messages
            GROUP BY team_id
            ORDER BY last_time DESC
            """
        )
        return [
            {
                "teamId": row["team_id"],
                "file": f"{row['team_id']}.sqlite",
                "time": row["last_time"],
                "count": row["count"],
                "lastMessageId": row["last_message_id"],
            }
            for row in rows
        ]

    @staticmethod
    def _to_message(row) -> ChatMessage:
        return ChatMessage(
            id=row["id"],
            team_id=row["team_id"],
            sender=row["sender"],
            message=row["message"],
            created_at=row["created_at"],
        )
