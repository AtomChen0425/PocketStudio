from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from pocketStudio.core.config import Settings
from pocketStudio.services.event_service import EventService
from pocketStudio.services.heartbeat_service import HeartbeatService
from pocketStudio.services.orchestrator import Orchestrator
from pocketStudio.services.schedule_service import ScheduleService


@dataclass
class WorkerState:
    running: bool = False
    paused: bool = False
    processed: int = 0
    failures: int = 0
    started_at: float | None = None
    last_tick_at: float | None = None
    last_processed_at: float | None = None
    last_error: str | None = None


class WorkerService:
    def __init__(
        self,
        orchestrator: Orchestrator,
        schedules: ScheduleService,
        heartbeat: HeartbeatService,
        events: EventService,
        settings: Settings,
    ) -> None:
        self.orchestrator = orchestrator
        self.schedules = schedules
        self.heartbeat = heartbeat
        self.events = events
        self.settings = settings
        self.state = WorkerState()
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._lock = asyncio.Lock()

    def start(self) -> bool:
        if self._task and not self._task.done():
            return False
        self._stop = asyncio.Event()
        self.state.running = True
        self.state.paused = False
        self.state.started_at = time.time()
        self.state.last_error = None
        self._task = asyncio.create_task(self._run(), name="pocketstudio-worker")
        self.events.emit("worker.started", {"interval": self.settings.worker_poll_interval})
        return True

    async def stop(self) -> bool:
        if not self._task:
            self.state.running = False
            return False
        self._stop.set()
        try:
            await asyncio.wait_for(self._task, timeout=5)
        except TimeoutError:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
        finally:
            self.state.running = False
            self._task = None
            self.events.emit("worker.stopped", {})
        return True

    def pause(self) -> bool:
        if self.state.paused:
            return False
        self.state.paused = True
        self.events.emit("worker.paused", {})
        return True

    def resume(self) -> bool:
        if not self.state.paused:
            return False
        self.state.paused = False
        self.events.emit("worker.resumed", {})
        return True

    async def restart(self) -> None:
        await self.stop()
        self.start()

    async def process_once(self, force: bool = False) -> bool:
        async with self._lock:
            self.state.last_tick_at = time.time()
            if self.state.paused and not force:
                return False
            try:
                self.orchestrator.queue.recover_stale_messages()
                self.schedules.fire_due(self.orchestrator.queue)
                self.heartbeat.fire_due(self.orchestrator.queue)
                result = await self.orchestrator.process_one()
            except Exception as exc:
                self.state.failures += 1
                self.state.last_error = str(exc)
                self.events.emit("worker.error", {"error": str(exc)})
                return False
            if result is None:
                return False
            self.state.processed += 1
            self.state.last_processed_at = time.time()
            self.state.last_error = None
            return True

    def snapshot(self) -> dict:
        queue_diagnostics = self.orchestrator.queue.diagnostics()
        queue_status = queue_diagnostics["status"]
        return {
            "running": self.state.running,
            "paused": self.state.paused,
            "health": self._health(queue_status),
            "processed": self.state.processed,
            "failures": self.state.failures,
            "startedAt": int(self.state.started_at * 1000) if self.state.started_at else None,
            "lastTickAt": int(self.state.last_tick_at * 1000) if self.state.last_tick_at else None,
            "lastProcessedAt": int(self.state.last_processed_at * 1000) if self.state.last_processed_at else None,
            "lastError": self.state.last_error,
            "pollInterval": self.settings.worker_poll_interval,
            "queue": queue_status,
            "queueDiagnostics": queue_diagnostics,
        }

    def maintenance(
        self,
        older_than_ms: int = 86_400_000,
        stale_threshold_seconds: int | None = None,
        prune_chats: bool = False,
    ) -> dict:
        recovered = self.orchestrator.queue.recover_stale_messages(stale_threshold_seconds)
        pruned_responses = self.orchestrator.queue.prune_acked_responses(older_than_ms)
        pruned_messages = self.orchestrator.queue.prune_completed_messages(older_than_ms)
        pruned_chat_messages = self.orchestrator.chat.prune(older_than_ms) if prune_chats else 0
        result = {
            "recovered": recovered,
            "prunedResponses": pruned_responses,
            "prunedMessages": pruned_messages,
            "prunedChatMessages": pruned_chat_messages,
            "worker": self.snapshot(),
        }
        self.events.emit("worker.maintenance", result)
        return result

    def _health(self, queue_status: dict) -> str:
        if self.state.last_error:
            return "degraded"
        if self.state.paused:
            return "paused"
        if queue_status.get("processing", 0) > 0 and not self.state.running:
            return "degraded"
        if not self.state.running:
            return "stopped"
        if queue_status.get("incoming", 0) > 0:
            return "busy"
        return "idle"

    async def _run(self) -> None:
        while not self._stop.is_set():
            if self.state.paused:
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=self.settings.worker_poll_interval)
                except TimeoutError:
                    continue
                continue
            processed = await self.process_once()
            sleep_for = 0 if processed else self.settings.worker_poll_interval
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=sleep_for)
            except TimeoutError:
                continue
        self.state.running = False
