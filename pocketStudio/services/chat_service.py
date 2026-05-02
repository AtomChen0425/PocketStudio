from __future__ import annotations

from datetime import datetime, timezone

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

    def list(
        self,
        team_id: str,
        limit: int = 100,
        since: int = 0,
        sender: str | None = None,
        query: str | None = None,
    ) -> list[ChatMessage]:
        filters = ["team_id = ?", "id > ?"]
        params: list[object] = [team_id, since]
        if sender:
            filters.append("sender = ?")
            params.append(sender)
        if query:
            filters.append("message LIKE ?")
            params.append(f"%{query}%")
        rows = self.db.fetch_all(
            f"""
            SELECT * FROM chat_messages
            WHERE {' AND '.join(filters)}
            ORDER BY id DESC
            LIMIT ?
            """,
            [*params, limit],
        )
        return list(reversed([self._to_message(row) for row in rows]))

    def archives(self) -> list[dict]:
        rows = self.db.fetch_all(
            """
            SELECT c.team_id,
                   COUNT(*) AS count,
                   MAX(c.created_at) AS last_time,
                   MAX(c.id) AS last_message_id,
                   latest.sender AS last_sender,
                   latest.message AS last_message
            FROM chat_messages c
            JOIN chat_messages latest
              ON latest.id = (
                  SELECT id FROM chat_messages
                  WHERE team_id = c.team_id
                  ORDER BY id DESC
                  LIMIT 1
              )
            GROUP BY c.team_id
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
                "lastSender": row["last_sender"],
                "lastMessage": row["last_message"],
            }
            for row in rows
        ]

    def prune(self, older_than_ms: int) -> int:
        cutoff = int(datetime.now(timezone.utc).timestamp() * 1000) - older_than_ms
        rows = self.db.fetch_all("SELECT id FROM chat_messages WHERE strftime('%s', created_at) * 1000 < ?", (cutoff,))
        for row in rows:
            self.db.execute("DELETE FROM chat_messages WHERE id = ?", (row["id"],))
        if rows:
            self.events.emit("chat.pruned", {"count": len(rows)})
        return len(rows)

    @staticmethod
    def _to_message(row) -> ChatMessage:
        return ChatMessage(
            id=row["id"],
            team_id=row["team_id"],
            sender=row["sender"],
            message=row["message"],
            created_at=row["created_at"],
        )
