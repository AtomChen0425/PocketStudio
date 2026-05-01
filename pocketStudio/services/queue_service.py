from __future__ import annotations

import json
import time

from pocketStudio.core.config import Settings
from pocketStudio.core.database import Database
from pocketStudio.models import AgentMessage, MessageCreate, MessageStatus, QueueMessage, QueueStatus, ResponseJob
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

    def status(self) -> QueueStatus:
        rows = self.db.fetch_all("SELECT status, COUNT(*) AS count FROM messages GROUP BY status")
        counts = {row["status"]: row["count"] for row in rows}
        queued = counts.get("queued", 0) + counts.get("failed", 0)
        running = counts.get("running", 0)
        done = counts.get("done", 0)
        return QueueStatus(
            incoming=queued,
            queued=queued,
            processing=running,
            outgoing=self._pending_response_count(),
            activeConversations=queued + running,
        )

    def agent_status(self) -> list[dict]:
        rows = self.db.fetch_all(
            """
            SELECT target, status, COUNT(*) AS count
            FROM messages
            GROUP BY target, status
            ORDER BY target
            """
        )
        grouped: dict[str, dict] = {}
        for row in rows:
            agent = self._target_label(row["target"])
            entry = grouped.setdefault(agent, {"agent": agent, "pending": 0, "queued": 0, "processing": 0})
            status = row["status"]
            count = row["count"]
            if status in {"queued", "failed"}:
                entry["pending"] += count
                entry["queued"] += count
            elif status == "running":
                entry["processing"] += count
        return list(grouped.values())

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

    def recover_stale_messages(self, threshold_seconds: int | None = None) -> int:
        threshold = threshold_seconds or self.settings.stale_processing_seconds
        rows = self.db.fetch_all(
            """
            SELECT id, attempts
            FROM messages
            WHERE status = 'running'
              AND updated_at <= datetime('now', ?)
            """,
            (f"-{threshold} seconds",),
        )
        recovered = 0
        for row in rows:
            next_status = "dead" if row["attempts"] >= self.settings.queue_max_attempts else "failed"
            self.db.execute(
                """
                UPDATE messages
                SET status = ?, error = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (next_status, "Recovered stale running message", row["id"]),
            )
            recovered += 1
            self.events.emit("message.recovered", {"message_id": row["id"], "status": next_status})
        return recovered

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

    def list_dead(self, limit: int = 100) -> list[QueueMessage]:
        return self.list(limit=limit, status=MessageStatus.dead)

    def retry_dead(self, message_id: int) -> bool:
        row = self.db.fetch_one("SELECT id FROM messages WHERE id = ? AND status = 'dead'", (message_id,))
        if row is None:
            return False
        self.db.execute(
            """
            UPDATE messages
            SET status = 'queued', attempts = 0, error = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (message_id,),
        )
        self.events.emit("message.retry", {"message_id": message_id})
        return True

    def delete_dead(self, message_id: int) -> bool:
        row = self.db.fetch_one("SELECT id FROM messages WHERE id = ? AND status = 'dead'", (message_id,))
        if row is None:
            return False
        self.db.execute("DELETE FROM messages WHERE id = ?", (message_id,))
        self.events.emit("message.deleted", {"message_id": message_id})
        return True

    def insert_agent_message(
        self,
        agent_id: str,
        role: str,
        content: str,
        message_id: str,
        sender: str = "",
        channel: str = "web",
        created_at: int | None = None,
    ) -> AgentMessage:
        cursor = self.db.execute(
            """
            INSERT INTO agent_messages (agent_id, role, channel, sender, message_id, content, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (agent_id, role, channel, sender, message_id, content, created_at or int(time.time() * 1000)),
        )
        row = self.db.fetch_one("SELECT * FROM agent_messages WHERE id = ?", (cursor.lastrowid,))
        return self._to_agent_message(row)

    def get_agent_messages(self, agent_id: str, limit: int = 100, since_id: int = 0) -> list[AgentMessage]:
        rows = self.db.fetch_all(
            """
            SELECT * FROM agent_messages
            WHERE agent_id = ? AND id > ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (agent_id, since_id, limit),
        )
        return [self._to_agent_message(row) for row in reversed(rows)]

    def recent_responses(self, limit: int = 20) -> list[dict]:
        rows = self.db.fetch_all("SELECT * FROM responses ORDER BY created_at DESC LIMIT ?", (limit,))
        return [self._response_api_payload(self._to_response(row)) for row in rows]

    def enqueue_response(
        self,
        message_id: str,
        channel: str,
        sender: str,
        message: str,
        original_message: str,
        agent: str | None = None,
        sender_id: str | None = None,
        files: list[str] | None = None,
        metadata: dict | None = None,
    ) -> ResponseJob:
        cursor = self.db.execute(
            """
            INSERT INTO responses
              (message_id, channel, sender, sender_id, message, original_message, agent, files, metadata, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (
                message_id,
                channel,
                sender,
                sender_id,
                message,
                original_message,
                agent,
                json.dumps(files or []),
                json.dumps(metadata or {}),
                int(time.time() * 1000),
            ),
        )
        row = self.db.fetch_one("SELECT * FROM responses WHERE id = ?", (cursor.lastrowid,))
        response = self._to_response(row)
        self.events.emit("response.queued", {"response_id": response.id, "message_id": message_id, "channel": channel})
        return response

    def get_responses_for_channel(self, channel: str) -> list[ResponseJob]:
        rows = self.db.fetch_all(
            "SELECT * FROM responses WHERE channel = ? AND status = 'pending' ORDER BY created_at",
            (channel,),
        )
        return [self._to_response(row) for row in rows]

    def ack_response(self, response_id: int) -> bool:
        row = self.db.fetch_one("SELECT id FROM responses WHERE id = ?", (response_id,))
        if row is None:
            return False
        self.db.execute(
            "UPDATE responses SET status = 'acked', acked_at = ? WHERE id = ?",
            (int(time.time() * 1000), response_id),
        )
        self.events.emit("response.acked", {"response_id": response_id})
        return True

    def prune_acked_responses(self, older_than_ms: int = 86_400_000) -> int:
        cutoff = int(time.time() * 1000) - older_than_ms
        rows = self.db.fetch_all("SELECT id FROM responses WHERE status = 'acked' AND acked_at < ?", (cutoff,))
        for row in rows:
            self.db.execute("DELETE FROM responses WHERE id = ?", (row["id"],))
        if rows:
            self.events.emit("responses.pruned", {"count": len(rows)})
        return len(rows)

    def prune_completed_messages(self, older_than_ms: int = 86_400_000) -> int:
        cutoff_seconds = max(0, older_than_ms // 1000)
        rows = self.db.fetch_all(
            """
            SELECT id FROM messages
            WHERE status = 'done' AND updated_at <= datetime('now', ?)
            """,
            (f"-{cutoff_seconds} seconds",),
        )
        for row in rows:
            self.db.execute("DELETE FROM messages WHERE id = ?", (row["id"],))
        if rows:
            self.events.emit("messages.pruned", {"count": len(rows)})
        return len(rows)

    def enqueue_responses_from_message(self, message: QueueMessage) -> list[ResponseJob]:
        if not message.result:
            return []
        try:
            body = json.loads(message.result)
            runs = body.get("runs") or [{"agent_id": "orchestrator", "output": body.get("output", "")}]
        except Exception:
            runs = [{"agent_id": "orchestrator", "output": message.result}]
        responses = []
        for index, run in enumerate(runs):
            responses.append(
                self.enqueue_response(
                    message_id=f"{message.id}-{index}",
                    channel="web",
                    sender=message.sender,
                    message=run.get("output", ""),
                    original_message=message.content,
                    agent=run.get("agent_id"),
                    metadata={"queue_message_id": message.id},
                )
            )
        return responses

    @staticmethod
    def _target_label(target: str) -> str:
        if target.startswith("@agent:") or target.startswith("@team:"):
            return target.split(":", 1)[1]
        if target.startswith("@"):
            return target[1:]
        return target

    def _pending_response_count(self) -> int:
        row = self.db.fetch_one("SELECT COUNT(*) AS count FROM responses WHERE status = 'pending'")
        return row["count"] if row else 0

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

    @staticmethod
    def _to_agent_message(row) -> AgentMessage:
        return AgentMessage(
            id=row["id"],
            agent_id=row["agent_id"],
            role=row["role"],
            channel=row["channel"],
            sender=row["sender"],
            message_id=row["message_id"],
            content=row["content"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _to_response(row) -> ResponseJob:
        return ResponseJob(
            id=row["id"],
            message_id=row["message_id"],
            channel=row["channel"],
            sender=row["sender"],
            sender_id=row["sender_id"],
            message=row["message"],
            original_message=row["original_message"],
            agent=row["agent"],
            files=json.loads(row["files"] or "[]"),
            metadata=json.loads(row["metadata"] or "{}"),
            status=row["status"],
            created_at=row["created_at"],
            acked_at=row["acked_at"],
        )

    @staticmethod
    def _response_api_payload(response: ResponseJob) -> dict:
        return {
            "id": response.id,
            "channel": response.channel,
            "sender": response.sender,
            "senderId": response.sender_id,
            "message": response.message,
            "originalMessage": response.original_message,
            "timestamp": response.created_at,
            "messageId": response.message_id,
            "agent": response.agent,
            "files": response.files,
            "metadata": response.metadata,
            "status": response.status,
            "ackedAt": response.acked_at,
        }
