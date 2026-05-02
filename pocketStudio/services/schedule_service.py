from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pocketStudio.core.database import Database
from pocketStudio.core.ids import prefixed_id
from pocketStudio.models import MessageCreate, QueueMessage, Schedule, ScheduleCreate
from pocketStudio.services.event_service import EventService
from pocketStudio.services.queue_service import QueueService


class ScheduleService:
    def __init__(self, db: Database, events: EventService) -> None:
        self.db = db
        self.events = events

    def list(self, agent_id: str | None = None) -> list[Schedule]:
        if agent_id:
            rows = self.db.fetch_all("SELECT * FROM schedules WHERE agent_id = ? ORDER BY created_at DESC", (agent_id,))
        else:
            rows = self.db.fetch_all("SELECT * FROM schedules ORDER BY created_at DESC")
        return [self._to_schedule(row) for row in rows]

    def schedule_status(self, schedule: Schedule, now: datetime | None = None) -> dict:
        now = now or datetime.now(timezone.utc)
        next_fire_at = self.next_fire_at(schedule, now)
        next_fire_ms = self._epoch_ms(next_fire_at) if next_fire_at else None
        now_ms = self._epoch_ms(now)
        return {
            "nextFireAt": next_fire_ms,
            "dueInMs": max(0, next_fire_ms - now_ms) if next_fire_ms is not None else None,
            "due": bool(schedule.enabled and next_fire_ms is not None and next_fire_ms <= now_ms),
        }

    def next_fire_at(self, schedule: Schedule, now: datetime | None = None) -> datetime | None:
        now = now or datetime.now(timezone.utc)
        if not schedule.enabled:
            return None
        if schedule.run_at:
            run_at = self._parse_datetime(schedule.run_at)
            if run_at is None:
                return None
            return run_at
        if not schedule.cron:
            return None
        cursor = now.replace(second=0, microsecond=0)
        if now.second or now.microsecond:
            cursor += timedelta(minutes=1)
        for _ in range(366 * 24 * 60):
            fire_key = cursor.strftime("%Y-%m-%dT%H:%M")
            if schedule.last_fire_key != fire_key and self._cron_matches(schedule.cron, cursor):
                return cursor
            cursor += timedelta(minutes=1)
        return None

    def create(self, payload: ScheduleCreate) -> Schedule:
        self._validate_payload(payload)
        schedule_id = prefixed_id("schedule")
        label = payload.label or payload.cron or payload.run_at or f"Message {payload.agent_id}"
        self.db.execute(
            """
            INSERT INTO schedules (id, label, cron, run_at, agent_id, message, channel, sender, enabled)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                schedule_id,
                label,
                payload.cron,
                payload.run_at,
                payload.agent_id,
                payload.message,
                payload.channel,
                payload.sender,
                int(payload.enabled),
            ),
        )
        schedule = self.get(schedule_id)
        self.events.emit("schedule.created", {"schedule_id": schedule.id, "agent_id": schedule.agent_id})
        return schedule

    def get(self, schedule_id: str) -> Schedule:
        row = self.db.fetch_one("SELECT * FROM schedules WHERE id = ?", (schedule_id,))
        if row is None:
            raise KeyError(f"Schedule '{schedule_id}' not found")
        return self._to_schedule(row)

    def update(self, schedule_id: str, payload: ScheduleCreate) -> Schedule:
        self._validate_payload(payload)
        self.db.execute(
            """
            UPDATE schedules
            SET label = ?, cron = ?, run_at = ?, agent_id = ?, message = ?,
                channel = ?, sender = ?, enabled = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                payload.label or payload.cron or payload.run_at or f"Message {payload.agent_id}",
                payload.cron,
                payload.run_at,
                payload.agent_id,
                payload.message,
                payload.channel,
                payload.sender,
                int(payload.enabled),
                schedule_id,
            ),
        )
        schedule = self.get(schedule_id)
        self.events.emit("schedule.updated", {"schedule_id": schedule.id})
        return schedule

    def delete(self, schedule_id: str) -> None:
        self.db.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
        self.events.emit("schedule.deleted", {"schedule_id": schedule_id})

    def fire_due(self, queue: QueueService, now: datetime | None = None) -> list[QueueMessage]:
        now = now or datetime.now(timezone.utc)
        rows = self.db.fetch_all("SELECT * FROM schedules WHERE enabled = 1 ORDER BY created_at ASC")
        fired: list[QueueMessage] = []
        for row in rows:
            schedule = self._to_schedule(row)
            if schedule.run_at:
                run_at = self._parse_datetime(schedule.run_at)
                if run_at and run_at <= now:
                    fired.append(self._fire(queue, schedule, now))
                    self.db.execute(
                        """
                        UPDATE schedules
                        SET enabled = 0, last_fired_at = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (self._epoch_ms(now), schedule.id),
                    )
                continue

            fire_key = now.strftime("%Y-%m-%dT%H:%M")
            if schedule.cron and schedule.last_fire_key != fire_key and self._cron_matches(schedule.cron, now):
                fired.append(self._fire(queue, schedule, now))
                self.db.execute(
                    """
                    UPDATE schedules
                    SET last_fired_at = ?, last_fire_key = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (self._epoch_ms(now), fire_key, schedule.id),
                )
        return fired

    def _fire(self, queue: QueueService, schedule: Schedule, now: datetime) -> QueueMessage:
        message = queue.enqueue(
            MessageCreate(
                target=f"@agent:{schedule.agent_id}",
                content=schedule.message,
                sender=schedule.sender,
            )
        )
        self.events.emit(
            "schedule.fired",
            {
                "schedule_id": schedule.id,
                "agent_id": schedule.agent_id,
                "message_id": message.id,
                "channel": schedule.channel,
                "fired_at": self._epoch_ms(now),
            },
        )
        return message

    def _validate_payload(self, payload: ScheduleCreate) -> None:
        if not payload.cron and not payload.run_at:
            raise ValueError("Either cron or runAt is required")
        if payload.run_at and self._parse_datetime(payload.run_at) is None:
            raise ValueError("runAt must be a valid ISO datetime")
        if payload.cron:
            parts = payload.cron.split()
            if len(parts) != 5:
                raise ValueError("cron must use five fields: minute hour day month weekday")

    @staticmethod
    def _parse_datetime(value: str) -> datetime | None:
        normalized = value.strip()
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _cron_matches(expression: str, now: datetime) -> bool:
        fields = expression.split()
        if len(fields) != 5:
            return False
        minute, hour, day, month, weekday = fields
        cron_weekday = (now.weekday() + 1) % 7
        return (
            ScheduleService._field_matches(minute, now.minute, 0, 59)
            and ScheduleService._field_matches(hour, now.hour, 0, 23)
            and ScheduleService._field_matches(day, now.day, 1, 31)
            and ScheduleService._field_matches(month, now.month, 1, 12)
            and ScheduleService._field_matches(weekday, cron_weekday, 0, 6)
        )

    @staticmethod
    def _field_matches(field: str, value: int, minimum: int, maximum: int) -> bool:
        for item in field.split(","):
            item = item.strip()
            if not item:
                continue
            if "/" in item:
                base, step_text = item.split("/", 1)
                try:
                    step = int(step_text)
                except ValueError:
                    return False
                if step <= 0:
                    return False
                start, end = (minimum, maximum) if base == "*" else ScheduleService._range(base)
                if start is None or end is None:
                    return False
                if start <= value <= end and (value - start) % step == 0:
                    return True
                continue
            if item == "*":
                return True
            start, end = ScheduleService._range(item)
            if start is None or end is None:
                return False
            if start <= value <= end:
                return True
        return False

    @staticmethod
    def _range(value: str) -> tuple[int | None, int | None]:
        if "-" not in value:
            try:
                parsed = int(value)
            except ValueError:
                return None, None
            return parsed, parsed
        start_text, end_text = value.split("-", 1)
        try:
            return int(start_text), int(end_text)
        except ValueError:
            return None, None

    @staticmethod
    def _epoch_ms(value: datetime) -> int:
        return int(value.timestamp() * 1000)

    @staticmethod
    def _to_schedule(row) -> Schedule:
        return Schedule(
            id=row["id"],
            label=row["label"],
            cron=row["cron"],
            run_at=row["run_at"],
            agent_id=row["agent_id"],
            message=row["message"],
            channel=row["channel"],
            sender=row["sender"],
            enabled=bool(row["enabled"]),
            last_fired_at=row["last_fired_at"],
            last_fire_key=row["last_fire_key"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
