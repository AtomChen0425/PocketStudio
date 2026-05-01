from __future__ import annotations

import time
from pathlib import Path

from pocketStudio.core.config import Settings
from pocketStudio.core.database import Database
from pocketStudio.models import MessageCreate, QueueMessage
from pocketStudio.services.agent_service import AgentService
from pocketStudio.services.event_service import EventService
from pocketStudio.services.queue_service import QueueService


DEFAULT_HEARTBEAT_PROMPT = "Quick status check: Any pending tasks? Keep response brief."


class HeartbeatService:
    def __init__(
        self,
        db: Database,
        agents: AgentService,
        events: EventService,
        settings: Settings,
    ) -> None:
        self.db = db
        self.agents = agents
        self.events = events
        self.settings = settings

    def fire_due(self, queue: QueueService, now_ms: int | None = None) -> list[QueueMessage]:
        if not self.settings.heartbeat_enabled:
            return []
        now_ms = now_ms or int(time.time() * 1000)
        fired: list[QueueMessage] = []
        for agent in self.agents.list():
            if not agent.enabled or not agent.heartbeat_enabled:
                continue
            interval_seconds = agent.heartbeat_interval or self.settings.heartbeat_interval_seconds
            interval_ms = max(10, interval_seconds) * 1000
            state = self.db.fetch_one("SELECT * FROM heartbeat_state WHERE agent_id = ?", (agent.id,))
            last_sent_at = state["last_sent_at"] if state else None
            if last_sent_at is not None and now_ms - last_sent_at < interval_ms:
                continue
            prompt = self._read_prompt(agent.workspace)
            message = queue.enqueue(MessageCreate(target=f"@agent:{agent.id}", content=prompt, sender="System"))
            self.db.execute(
                """
                INSERT INTO heartbeat_state (agent_id, last_sent_at, last_message_id)
                VALUES (?, ?, ?)
                ON CONFLICT(agent_id) DO UPDATE SET
                  last_sent_at = excluded.last_sent_at,
                  last_message_id = excluded.last_message_id
                """,
                (agent.id, now_ms, message.id),
            )
            self.events.emit("heartbeat.queued", {"agent_id": agent.id, "message_id": message.id})
            fired.append(message)
        return fired

    def snapshot(self) -> dict:
        rows = self.db.fetch_all("SELECT * FROM heartbeat_state ORDER BY agent_id")
        return {
            "running": self.settings.heartbeat_enabled,
            "interval": self.settings.heartbeat_interval_seconds,
            "lastSent": {row["agent_id"]: row["last_sent_at"] for row in rows},
            "lastMessageIds": {row["agent_id"]: row["last_message_id"] for row in rows},
        }

    @staticmethod
    def _read_prompt(workspace: Path) -> str:
        path = workspace / "heartbeat.md"
        if not path.exists():
            return DEFAULT_HEARTBEAT_PROMPT
        content = path.read_text(encoding="utf-8", errors="ignore").strip()
        return content or DEFAULT_HEARTBEAT_PROMPT
