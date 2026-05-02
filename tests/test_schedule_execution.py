import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from pocketStudio.core.config import Settings
from pocketStudio.core.database import Database
from pocketStudio.main import app
from pocketStudio.models import ScheduleCreate
from pocketStudio.services.event_service import EventService
from pocketStudio.services.schedule_service import ScheduleService


def test_worker_fires_due_one_time_schedule() -> None:
    agent_id = f"scheduled-agent-{uuid.uuid4().hex[:8]}"
    run_at = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()

    with TestClient(app) as client:
        agent_response = client.post(
            "/api/agents",
            json={"id": agent_id, "name": "Scheduled Agent", "role": "Runs scheduled work", "provider": "local"},
        )
        assert agent_response.status_code == 200

        schedule_response = client.post(
            "/api/schedules",
            json={"agentId": agent_id, "message": "scheduled check", "runAt": run_at, "label": f"one-shot-{agent_id}"},
        )
        assert schedule_response.status_code == 200
        schedule_id = schedule_response.json()["schedule"]["id"]

        deadline = time.time() + 5
        schedule = None
        messages = []
        while time.time() < deadline:
            schedule = next(item for item in client.get(f"/api/schedules?agent={agent_id}").json() if item["id"] == schedule_id)
            messages = [
                item
                for item in client.get("/api/queue").json()
                if item["target"] == f"@agent:{agent_id}" and item["content"] == "scheduled check"
            ]
            if schedule["enabled"] is False and schedule["lastFiredAt"] and any(item["status"] == "done" for item in messages):
                break
            time.sleep(0.1)

        assert schedule is not None
        assert schedule["enabled"] is False
        assert schedule["lastFiredAt"]
        assert any(item["status"] == "done" for item in messages)


def test_schedule_payload_includes_next_fire_preview() -> None:
    agent_id = f"preview-agent-{uuid.uuid4().hex[:8]}"
    run_at = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()

    with TestClient(app) as client:
        client.post("/api/agents", json={"id": agent_id, "name": "Preview Agent", "role": "Previews", "provider": "local"})
        created = client.post(
            "/api/schedules",
            json={"agentId": agent_id, "message": "future check", "runAt": run_at, "label": f"preview-{agent_id}"},
        )

        assert created.status_code == 200
        schedule = created.json()["schedule"]
        assert schedule["nextFireAt"] is not None
        assert schedule["dueInMs"] > 0
        assert schedule["due"] is False


def test_cron_schedule_preview_finds_next_matching_minute() -> None:
    settings = Settings(pocketStudio_home=Path(".pytest-local") / f"schedule-home-{uuid.uuid4().hex[:8]}")
    db = Database(settings.database_path)
    db.initialize()
    schedules = ScheduleService(db, EventService(db, settings))
    schedule = schedules.create(
        ScheduleCreate(agentId="agent", message="cron check", cron="*/15 * * * *", label="Quarter hour")
    )
    now = datetime(2026, 5, 2, 10, 7, 30, tzinfo=timezone.utc)

    status = schedules.schedule_status(schedule, now)

    assert status["nextFireAt"] == int(datetime(2026, 5, 2, 10, 15, tzinfo=timezone.utc).timestamp() * 1000)
    assert status["due"] is False
