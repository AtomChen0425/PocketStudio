from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from pocketStudio.core.database import Database
from pocketStudio.models import Agent, ChatMessage, ChatMessageCreate, MessageCreate, QueueMessage, Team
from pocketStudio.services.event_service import EventService
from pocketStudio.utils.tag_parser import strip_tags

if TYPE_CHECKING:
    from pocketStudio.services.queue_service import QueueService


class ChatService:
    def __init__(self, db: Database, events: EventService) -> None:
        self.db = db
        self.events = events

    def post(
        self,
        team_id: str,
        payload: ChatMessageCreate,
        conn: sqlite3.Connection | None = None,
        *,
        emit_event: bool = True,
    ) -> ChatMessage:
        if payload.client_message_id:
            existing = self.find_by_client_message_id(team_id, payload.client_message_id, conn=conn)
            if existing is not None:
                return existing
        columns = ["team_id", "sender", "message"]
        values: list[object] = [team_id, payload.sender, payload.message]
        if payload.client_message_id:
            columns.append("client_message_id")
            values.append(payload.client_message_id)
        query = f"INSERT INTO chat_messages ({', '.join(columns)}) VALUES ({', '.join(['?'] * len(columns))})"
        try:
            if conn is None:
                cursor = self.db.execute(query, values)
                message_id = cursor.lastrowid
            else:
                cursor = conn.execute(query, values)
                message_id = cursor.lastrowid
        except sqlite3.IntegrityError:
            if payload.client_message_id:
                existing = self.find_by_client_message_id(team_id, payload.client_message_id, conn=conn)
                if existing is not None:
                    return existing
            raise
        if conn is None:
            message = self.get(message_id)
        else:
            row = conn.execute("SELECT * FROM chat_messages WHERE id = ?", (message_id,)).fetchone()
            if row is None:
                raise KeyError(f"Chat message '{message_id}' not found")
            message = self._annotate_dispatch(self._to_message(row))
        if emit_event:
            self.events.emit("chat.posted", {"team_id": team_id, "message_id": message.id, "sender": payload.sender})
        return message

    def get(self, message_id: int, conn: sqlite3.Connection | None = None) -> ChatMessage:
        row = (
            conn.execute("SELECT * FROM chat_messages WHERE id = ?", (message_id,)).fetchone()
            if conn is not None
            else self.db.fetch_one("SELECT * FROM chat_messages WHERE id = ?", (message_id,))
        )
        if row is None:
            raise KeyError(f"Chat message '{message_id}' not found")
        return self._annotate_dispatch(self._to_message(row), conn=conn)

    def find_by_client_message_id(self, team_id: str, client_message_id: str, conn: sqlite3.Connection | None = None) -> ChatMessage | None:
        row = (
            conn.execute("SELECT * FROM chat_messages WHERE team_id = ? AND client_message_id = ?", (team_id, client_message_id)).fetchone()
            if conn is not None
            else self.db.fetch_one(
                "SELECT * FROM chat_messages WHERE team_id = ? AND client_message_id = ?",
                (team_id, client_message_id),
            )
        )
        return self._annotate_dispatch(self._to_message(row), conn=conn) if row is not None else None

    def get_dispatch(self, chat_message_id: int, conn: sqlite3.Connection | None = None) -> dict | None:
        row = (
            conn.execute("SELECT * FROM chat_dispatches WHERE chat_message_id = ?", (chat_message_id,)).fetchone()
            if conn is not None
            else self.db.fetch_one("SELECT * FROM chat_dispatches WHERE chat_message_id = ?", (chat_message_id,))
        )
        if row is None:
            return None
        return {
            "chat_message_id": row["chat_message_id"],
            "team_id": row["team_id"],
            "client_message_id": row["client_message_id"],
            "queued_count": row["queued_count"],
            "message_ids": json.loads(row["message_ids"] or "[]"),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _annotate_dispatch(self, message: ChatMessage, conn: sqlite3.Connection | None = None) -> ChatMessage:
        dispatch = self.get_dispatch(message.id, conn=conn)
        if dispatch is None:
            return message
        return message.model_copy(
            update={
                "dispatch_status": "dispatched",
                "dispatch_queued_count": dispatch["queued_count"],
                "dispatch_message_ids": dispatch["message_ids"],
            }
        )

    def record_dispatch(
        self,
        *,
        chat_message_id: int,
        team_id: str,
        client_message_id: str | None,
        queued_count: int,
        message_ids: list[int],
        conn: sqlite3.Connection | None = None,
    ) -> dict:
        sql = """
            INSERT INTO chat_dispatches (
                chat_message_id, team_id, client_message_id, queued_count, message_ids, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(chat_message_id) DO UPDATE SET
                team_id = excluded.team_id,
                client_message_id = excluded.client_message_id,
                queued_count = excluded.queued_count,
                message_ids = excluded.message_ids,
                updated_at = CURRENT_TIMESTAMP
        """
        params = (chat_message_id, team_id, client_message_id, queued_count, json.dumps(message_ids, ensure_ascii=False))
        if conn is None:
            self.db.execute(sql, params)
        else:
            conn.execute(sql, params)
        dispatch = self.get_dispatch(chat_message_id, conn=conn)
        assert dispatch is not None
        return dispatch

    def broadcast_chatroom(
        self,
        queue: "QueueService",
        team: Team,
        from_agent: str,
        content: str,
        agents: list[Agent],
        parent: QueueMessage,
    ) -> int:
        delivered = 0
        agent_ids = {agent.id for agent in agents}
        chat_message = f"[Chat room #{team.id} - @{from_agent}]:\n{content}"
        for teammate_id in team.agent_ids:
            if teammate_id == from_agent or teammate_id not in agent_ids:
                continue
            queue.enqueue(
                MessageCreate(
                    target=f"@agent:{teammate_id}",
                    content=chat_message,
                    sender=f"chatroom:{team.id}:{from_agent}",
                    metadata=self.team_child_metadata(
                        parent,
                        team=team,
                        from_agent=from_agent,
                        kind="chatroom",
                        to_agent=teammate_id,
                    ),
                )
            )
            delivered += 1
        return delivered

    def dispatch_team_message(
        self,
        queue: "QueueService",
        team: Team,
        message: str,
        *,
        sender: str = "user",
        chat_message_id: int | None = None,
        conn: sqlite3.Connection | None = None,
        emit_event: bool = True,
    ) -> dict:
        chat_message = f"[Chat room #{team.id} - @{sender}]:\n{message}"
        delivered = 0
        message_ids: list[int] = []
        queued_messages: list[dict] = []
        for teammate_id in team.agent_ids:
            if sender in team.agent_ids and teammate_id == sender:
                continue
            metadata = self.team_child_metadata(
                None,
                team=team,
                from_agent=sender,
                kind="chatroom",
                to_agent=teammate_id,
            )
            metadata["channel"] = "chatroom"
            if chat_message_id is not None:
                metadata["parentMessageId"] = f"chat:{chat_message_id}"
            queued = queue.enqueue(
                MessageCreate(
                    target=f"@agent:{teammate_id}",
                    content=chat_message,
                    sender=sender,
                    metadata=metadata,
                ),
                conn=conn,
                emit_event=False if conn is not None else True,
            )
            message_ids.append(queued.id)
            queued_messages.append(queued.model_dump())
            delivered += 1
        if emit_event:
            self.events.emit(
                "team.dispatch",
                {
                    "team_id": team.id,
                    "from_agent": sender,
                    "delivered": delivered,
                    "message_id": chat_message_id,
                    "message_ids": message_ids,
                },
            )
        return {"ok": True, "teamId": team.id, "queued": delivered, "messageIds": message_ids, "queuedMessages": queued_messages}

    def post_chatroom_run_outputs(self, team: Team, runs: list) -> None:
        for run in runs:
            message = strip_tags(run.output, "#").strip()
            if message:
                self.post(team.id, ChatMessageCreate(sender=run.agent_id, message=message))

    @staticmethod
    def is_chatroom_origin(message: QueueMessage) -> bool:
        return message.metadata.get("channel") == "chatroom" or message.metadata.get("teamId")

    @staticmethod
    def team_child_metadata(
        parent: QueueMessage | None,
        *,
        team: Team,
        from_agent: str,
        kind: str,
        to_agent: str,
    ) -> dict:
        parent_metadata = parent.metadata if parent else {}
        metadata = {
            "kind": kind,
            "teamId": team.id,
            "fromAgent": from_agent,
            "toAgent": to_agent,
            "parentMessageId": str(parent.id) if parent else None,
            "parentTarget": parent.target if parent else None,
            "channel": parent_metadata.get("channel", "team"),
            "sender": parent.sender if parent else "",
            "senderId": parent_metadata.get("senderId") or parent_metadata.get("sender_id"),
            "projectId": parent_metadata.get("projectId") or parent_metadata.get("project_id"),
        }
        return {key: value for key, value in metadata.items() if value is not None}

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
        return list(reversed([self._annotate_dispatch(self._to_message(row)) for row in rows]))

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
            client_message_id=row["client_message_id"] if "client_message_id" in row.keys() else None,
            created_at=row["created_at"],
        )
