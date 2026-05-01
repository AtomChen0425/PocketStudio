import time
import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from pocketStudio.main import app


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
