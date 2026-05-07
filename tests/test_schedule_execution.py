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


def test_manual_schedule_fire_enqueues_message_and_updates_state() -> None:
    agent_id = f"manual-schedule-agent-{uuid.uuid4().hex[:8]}"
    run_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()

    with TestClient(app) as client:
        client.post("/api/agents", json={"id": agent_id, "name": "Manual Schedule Agent", "role": "Runs on demand", "provider": "local"})
        created = client.post(
            "/api/schedules",
            json={"agentId": agent_id, "message": "manual fire check", "runAt": run_at, "label": f"manual-{agent_id}"},
        )
        schedule_id = created.json()["schedule"]["id"]

        fired = client.post(f"/api/schedules/{schedule_id}/fire")

        assert fired.status_code == 200
        payload = fired.json()
        assert payload["ok"] is True
        assert payload["message"]["target"] == f"@agent:{agent_id}"
        assert payload["message"]["content"] == "manual fire check"
        assert payload["schedule"]["enabled"] is False
        assert payload["schedule"]["lastFiredAt"] is not None

        queued = client.get("/api/queue").json()
        assert any(item["id"] == payload["messageId"] for item in queued)


def test_manual_schedule_fire_requires_enabled_unless_forced() -> None:
    agent_id = f"disabled-schedule-agent-{uuid.uuid4().hex[:8]}"

    with TestClient(app) as client:
        client.post("/api/agents", json={"id": agent_id, "name": "Disabled Schedule Agent", "role": "Runs when forced", "provider": "local"})
        created = client.post(
            "/api/schedules",
            json={
                "agentId": agent_id,
                "message": "forced fire check",
                "cron": "0 * * * *",
                "label": f"disabled-{agent_id}",
                "enabled": False,
            },
        )
        schedule_id = created.json()["schedule"]["id"]

        blocked = client.post(f"/api/schedules/{schedule_id}/fire")
        forced = client.post(f"/api/schedules/{schedule_id}/fire", json={"force": True})

        assert blocked.status_code == 409
        assert forced.status_code == 200
        assert forced.json()["message"]["content"] == "forced fire check"


def test_invalid_cron_is_rejected_before_persisting() -> None:
    agent_id = f"invalid-cron-agent-{uuid.uuid4().hex[:8]}"

    with TestClient(app) as client:
        client.post("/api/agents", json={"id": agent_id, "name": "Invalid Cron Agent", "role": "Validates cron", "provider": "local"})

        created = client.post(
            "/api/schedules",
            json={"agentId": agent_id, "message": "bad cron", "cron": "99 * * * *", "label": f"invalid-{agent_id}"},
        )
        validated = client.post(
            "/api/schedules/validate",
            json={"agentId": agent_id, "message": "bad cron", "cron": "* * * * 9", "label": f"invalid-preview-{agent_id}"},
        )

        assert created.status_code == 422
        assert "outside supported range" in created.json()["detail"]
        assert validated.status_code == 200
        assert validated.json()["ok"] is False
        assert client.get(f"/api/schedules?agent={agent_id}").json() == []


def test_schedule_label_is_unique_and_can_delete_by_label() -> None:
    agent_id = f"label-schedule-agent-{uuid.uuid4().hex[:8]}"
    label = f"unique-label-{agent_id}"

    with TestClient(app) as client:
        client.post("/api/agents", json={"id": agent_id, "name": "Label Schedule Agent", "role": "Uses labels", "provider": "local"})
        first = client.post("/api/schedules", json={"agentId": agent_id, "message": "first", "cron": "0 * * * *", "label": label})
        duplicate = client.post("/api/schedules", json={"agentId": agent_id, "message": "second", "cron": "5 * * * *", "label": label})

        assert first.status_code == 200
        assert duplicate.status_code == 422
        assert "already exists" in duplicate.json()["detail"]

        deleted = client.delete(f"/api/schedules/{label}")

        assert deleted.status_code == 200
        assert client.get(f"/api/schedules?agent={agent_id}").json() == []


def test_schedule_validate_returns_preview_without_persisting() -> None:
    agent_id = f"validate-schedule-agent-{uuid.uuid4().hex[:8]}"
    run_at = (datetime.now(timezone.utc) + timedelta(minutes=3)).isoformat()

    with TestClient(app) as client:
        client.post("/api/agents", json={"id": agent_id, "name": "Validate Schedule Agent", "role": "Previews validation", "provider": "local"})

        validated = client.post(
            "/api/schedules/validate",
            json={"agentId": agent_id, "message": "preview only", "runAt": run_at, "label": f"validate-{agent_id}"},
        )

        assert validated.status_code == 200
        assert validated.json()["ok"] is True
        assert validated.json()["nextFireAt"] is not None
        assert client.get(f"/api/schedules?agent={agent_id}").json() == []


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
