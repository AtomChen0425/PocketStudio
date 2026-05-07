from __future__ import annotations

import json
import time
from datetime import datetime, timezone

from pocketStudio.core.config import Settings
from pocketStudio.core.database import Database
from pocketStudio.models import AgentMessage, MessageCreate, MessageStatus, QueueMessage, QueueStatus, ResponseJob
from pocketStudio.services.event_service import EventService
from pocketStudio.services.plugin_service import PluginService
from pocketStudio.services.response_service import ResponseService
from pocketStudio.services.team_routing import convert_tags_to_readable


class QueueService:
    def __init__(
        self,
        db: Database,
        events: EventService,
        settings: Settings,
        responses: ResponseService | None = None,
        plugins: PluginService | None = None,
    ) -> None:
        self.db = db
        self.events = events
        self.settings = settings
        self.responses = responses or ResponseService(settings)
        self.plugins = plugins

    def enqueue(self, payload: MessageCreate) -> QueueMessage:
        content = payload.content
        if self.plugins:
            hooked = self.plugins.run_incoming_hooks(
                content,
                {"channel": payload.metadata.get("channel", "web"), "sender": payload.sender, "target": payload.target},
            )
            content = hooked.text
        cursor = self.db.execute(
            "INSERT INTO messages (target, content, sender, metadata) VALUES (?, ?, ?, ?)",
            (payload.target, content, payload.sender, json.dumps(payload.metadata)),
        )
        message = self.get(cursor.lastrowid)
        self.events.emit(
            "message.queued",
            {
                "message_id": message.id,
                "target": message.target,
                "content": message.content,
                "sender": message.sender,
                "metadata": message.metadata,
            },
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

    def grouped_chatroom_messages(
        self,
        limit: int = 100,
        status: MessageStatus | None = None,
    ) -> dict:
        messages = list(reversed(self.list(limit=limit, status=status)))
        grouped: list[dict] = []
        message_ids: list[list[int]] = []
        pending: list[QueueMessage] = []

        def flush() -> None:
            nonlocal pending
            if not pending:
                return
            grouped.append(self._combined_chatroom_payload(pending))
            message_ids.append([message.id for message in pending])
            pending = []

        for message in messages:
            if self._is_chatroom_message(message):
                pending.append(message)
                continue
            flush()
            grouped.append(message.model_dump())
            message_ids.append([message.id])
        flush()
        return {"messages": grouped, "messageIds": message_ids}

    def status(self) -> QueueStatus:
        rows = self.db.fetch_all("SELECT status, COUNT(*) AS count FROM messages GROUP BY status")
        counts = {row["status"]: row["count"] for row in rows}
        queued = counts.get("queued", 0) + counts.get("failed", 0)
        running = counts.get("running", 0)
        done = counts.get("done", 0)
        dead = counts.get("dead", 0)
        failed = counts.get("failed", 0)
        responses_pending = self._pending_response_count()
        return QueueStatus(
            incoming=queued,
            queued=queued,
            processing=running,
            outgoing=responses_pending,
            activeConversations=queued + running,
            pending=queued,
            completed=done,
            dead=dead,
            failed=failed,
            responsesPending=responses_pending,
        )

    def diagnostics(self, stale_threshold_seconds: int | None = None) -> dict:
        stale_threshold = stale_threshold_seconds or self.settings.stale_processing_seconds
        status = self.status().model_dump()
        oldest_queued = self.db.fetch_one(
            """
            SELECT *
            FROM messages
            WHERE status IN ('queued', 'failed') AND attempts < ?
            ORDER BY created_at ASC, id ASC
            LIMIT 1
            """,
            (self.settings.queue_max_attempts,),
        )
        oldest_running = self.db.fetch_one(
            """
            SELECT *
            FROM messages
            WHERE status = 'running'
            ORDER BY updated_at ASC, id ASC
            LIMIT 1
            """
        )
        retryable_row = self.db.fetch_one(
            "SELECT COUNT(*) AS count FROM messages WHERE status IN ('failed', 'dead')"
        )
        exhausted_row = self.db.fetch_one(
            "SELECT COUNT(*) AS count FROM messages WHERE attempts >= ? AND status != 'done'",
            (self.settings.queue_max_attempts,),
        )
        stale_row = self.db.fetch_one(
            """
            SELECT COUNT(*) AS count
            FROM messages
            WHERE status = 'running'
              AND updated_at <= datetime('now', ?)
            """,
            (f"-{stale_threshold} seconds",),
        )
        now_ms = int(time.time() * 1000)
        oldest_queued_at = self._timestamp_ms(oldest_queued["created_at"]) if oldest_queued else None
        oldest_running_at = self._timestamp_ms(oldest_running["updated_at"]) if oldest_running else None
        return {
            "status": status,
            "maxAttempts": self.settings.queue_max_attempts,
            "staleThresholdSeconds": stale_threshold,
            "retryable": retryable_row["count"] if retryable_row else 0,
            "exhausted": exhausted_row["count"] if exhausted_row else 0,
            "staleProcessing": stale_row["count"] if stale_row else 0,
            "oldestQueued": self._message_summary(oldest_queued) if oldest_queued else None,
            "oldestQueuedAt": oldest_queued_at,
            "oldestQueuedAgeMs": max(0, now_ms - oldest_queued_at) if oldest_queued_at is not None else None,
            "oldestRunning": self._message_summary(oldest_running) if oldest_running else None,
            "oldestRunningAt": oldest_running_at,
            "oldestRunningAgeMs": max(0, now_ms - oldest_running_at) if oldest_running_at is not None else None,
        }

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
        message = self.get(message_id)
        if message.status not in {MessageStatus.queued, MessageStatus.failed}:
            raise ValueError(f"Message '{message_id}' is not processable from status '{message.status}'")
        if message.attempts >= self.settings.queue_max_attempts:
            self.db.execute(
                """
                UPDATE messages
                SET status = 'dead', error = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                ("Maximum attempts exceeded", message_id),
            )
            self.events.emit("message.dead", {"message_id": message_id, "reason": "maximum attempts exceeded"})
            raise ValueError(f"Message '{message_id}' exceeded maximum attempts")
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

    def dead_payloads(self, limit: int = 100) -> list[dict]:
        return [self._dead_payload(message) for message in self.list_dead(limit)]

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

    def retry_message(self, message_id: int) -> QueueMessage:
        message = self.get(message_id)
        if message.status not in {MessageStatus.failed, MessageStatus.dead}:
            raise ValueError(f"Message '{message_id}' is not retryable from status '{message.status}'")
        self.db.execute(
            """
            UPDATE messages
            SET status = 'queued', attempts = 0, error = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (message_id,),
        )
        self.events.emit("message.retry", {"message_id": message_id, "from_status": message.status.value})
        return self.get(message_id)

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

    def reset_agent(self, agent_id: str) -> dict:
        message_rows = self.db.fetch_all("SELECT id FROM agent_messages WHERE agent_id = ?", (agent_id,))
        response_rows = self.db.fetch_all("SELECT id FROM responses WHERE agent = ?", (agent_id,))
        self.db.execute("DELETE FROM agent_messages WHERE agent_id = ?", (agent_id,))
        self.db.execute("DELETE FROM responses WHERE agent = ?", (agent_id,))
        self.events.emit(
            "agent.reset",
            {"agent_id": agent_id, "messages": len(message_rows), "responses": len(response_rows)},
        )
        return {"messages": len(message_rows), "responses": len(response_rows)}

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
        self.events.emit(
            "response.queued",
            {
                "response_id": response.id,
                "message_id": message_id,
                "channel": channel,
                "sender": sender,
                "sender_id": sender_id,
                "agent": agent,
                "status": response.status,
            },
        )
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
            response_text, team_metadata = self._prepare_team_response_text(run)
            prepared = self.responses.prepare(
                response_text,
                context={
                    "channel": "web",
                    "sender": message.sender,
                    "messageId": f"{message.id}-{index}",
                    "originalMessage": message.content,
                    "agentId": run.get("agent_id"),
                },
            )
            metadata = {"queue_message_id": message.id, **team_metadata, **prepared.metadata}
            responses.append(
                self.enqueue_response(
                    message_id=f"{message.id}-{index}",
                    channel="web",
                    sender=message.sender,
                    message=prepared.message,
                    original_message=message.content,
                    agent=run.get("agent_id"),
                    files=prepared.files,
                    metadata=metadata,
                )
            )
        return responses

    def processing_payloads(self) -> list[dict]:
        rows = self.db.fetch_all(
            """
            SELECT *
            FROM messages
            WHERE status = 'running'
            ORDER BY updated_at ASC, id ASC
            """
        )
        now_ms = int(time.time() * 1000)
        payloads = []
        for row in rows:
            message = self._to_message(row)
            started_at = self._timestamp_ms(message.updated_at)
            payloads.append(
                {
                    "id": message.id,
                    "messageId": str(message.id),
                    "channel": message.metadata.get("channel", "web"),
                    "sender": message.sender,
                    "senderId": message.metadata.get("senderId") or message.metadata.get("sender_id"),
                    "message": message.content,
                    "agent": self._target_label(message.target),
                    "target": message.target,
                    "status": "processing",
                    "attempts": message.attempts,
                    "startedAt": started_at,
                    "duration": max(0, now_ms - started_at),
                    "metadata": message.metadata,
                }
            )
        return payloads

    @staticmethod
    def _dead_payload(message: QueueMessage) -> dict:
        channel = message.metadata.get("channel", "web")
        sender_id = message.metadata.get("senderId") or message.metadata.get("sender_id")
        payload = message.model_dump()
        payload.update(
            {
                "data": {
                    "channel": channel,
                    "sender": message.sender,
                    "senderId": sender_id,
                    "message": message.content,
                    "messageId": str(message.id),
                    "agent": QueueService._target_label(message.target),
                    "target": message.target,
                    "metadata": message.metadata,
                },
                "failedReason": message.error,
                "attemptsMade": message.attempts,
                "timestamp": QueueService._timestamp_ms(message.created_at),
            }
        )
        return payload

    @staticmethod
    def _target_label(target: str) -> str:
        if target.startswith("@agent:") or target.startswith("@team:"):
            return target.split(":", 1)[1]
        if target.startswith("@"):
            return target[1:]
        return target

    @staticmethod
    def _is_chatroom_message(message: QueueMessage) -> bool:
        return message.metadata.get("kind") == "chatroom" or message.sender.startswith("chatroom:")

    @staticmethod
    def _combined_chatroom_payload(messages: list[QueueMessage]) -> dict:
        first = messages[0].model_dump()
        first["id"] = messages[0].id
        first["content"] = "\n\n".join(message.content for message in messages)
        metadata = dict(first.get("metadata") or {})
        metadata["groupedMessageIds"] = [message.id for message in messages]
        metadata["groupedCount"] = len(messages)
        first["metadata"] = metadata
        return first

    def _pending_response_count(self) -> int:
        row = self.db.fetch_one("SELECT COUNT(*) AS count FROM responses WHERE status = 'pending'")
        return row["count"] if row else 0

    @staticmethod
    def _message_summary(row) -> dict:
        metadata = json.loads(row["metadata"] or "{}")
        return {
            "id": row["id"],
            "target": row["target"],
            "agent": QueueService._target_label(row["target"]),
            "sender": row["sender"],
            "status": row["status"],
            "attempts": row["attempts"],
            "channel": metadata.get("channel", "web"),
            "createdAt": QueueService._timestamp_ms(row["created_at"]),
            "updatedAt": QueueService._timestamp_ms(row["updated_at"]),
        }

    @staticmethod
    def _timestamp_ms(value: str) -> int:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return int(time.time() * 1000)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return int(parsed.timestamp() * 1000)

    @staticmethod
    def _to_message(row) -> QueueMessage:
        return QueueMessage(
            id=row["id"],
            target=row["target"],
            content=row["content"],
            sender=row["sender"],
            metadata=json.loads(row["metadata"] or "{}"),
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

    @staticmethod
    def _prepare_team_response_text(run: dict) -> tuple[str, dict]:
        output = run.get("output", "") or ""
        agent_id = run.get("agent_id")
        readable = convert_tags_to_readable(output, str(agent_id) if agent_id else None)
        if readable == output:
            return output, {}
        return readable, {"teamTagsConverted": True}
