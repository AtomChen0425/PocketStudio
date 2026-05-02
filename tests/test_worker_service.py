import time
import uuid

from fastapi.testclient import TestClient

from pocketStudio.main import app


def test_background_worker_processes_queued_messages() -> None:
    agent_id = f"worker-agent-{uuid.uuid4().hex[:8]}"

    with TestClient(app) as client:
        agent_response = client.post(
            "/api/agents",
            json={"id": agent_id, "name": "Worker Agent", "role": "Processes queue items", "provider": "local"},
        )
        assert agent_response.status_code == 200

        message_response = client.post(
            "/api/messages",
            json={"target": f"@agent:{agent_id}", "content": "Process me automatically", "sender": "test"},
        )
        assert message_response.status_code == 200
        message_id = message_response.json()["id"]

        deadline = time.time() + 5
        message = None
        while time.time() < deadline:
            message = client.get(f"/api/queue/{message_id}").json()
            if message["status"] == "done":
                break
            time.sleep(0.1)

        assert message is not None
        assert message["status"] == "done"

        worker_status = client.get("/api/worker/status")
        assert worker_status.status_code == 200
        assert worker_status.json()["processed"] >= 1
        assert worker_status.json()["health"] in {"idle", "busy"}
        assert worker_status.json()["lastProcessedAt"] is not None
        assert worker_status.json()["queue"]["outgoing"] >= 1


def test_worker_maintenance_recovers_and_prunes_queue_items() -> None:
    agent_id = f"maintenance-agent-{uuid.uuid4().hex[:8]}"

    with TestClient(app) as client:
        client.post("/api/worker/stop")
        client.post("/api/agents", json={"id": agent_id, "name": "Maintenance Agent", "role": "Maintains", "provider": "local"})
        message_id = client.post(
            "/api/messages",
            json={"target": f"@agent:{agent_id}", "content": "old complete", "sender": "test"},
        ).json()["id"]
        client.post(f"/api/messages/{message_id}/process")
        response = client.get("/api/responses?limit=10").json()[0]
        client.post(f"/api/responses/{response['id']}/ack")

        maintenance = client.post("/api/worker/maintenance?older_than_ms=0&stale_threshold_seconds=1")

        assert maintenance.status_code == 200
        body = maintenance.json()
        assert body["ok"] is True
        assert body["prunedMessages"] >= 1
        assert body["prunedResponses"] >= 1
        assert "queue" in body["worker"]


def test_worker_pause_blocks_processing_until_resume_or_forced_tick() -> None:
    agent_id = f"pause-agent-{uuid.uuid4().hex[:8]}"

    with TestClient(app) as client:
        client.post("/api/worker/stop")
        client.post("/api/agents", json={"id": agent_id, "name": "Pause Agent", "role": "Waits", "provider": "local"})
        message_id = client.post(
            "/api/messages",
            json={"target": f"@agent:{agent_id}", "content": "hold this", "sender": "test"},
        ).json()["id"]

        paused = client.post("/api/worker/pause")
        tick = client.post("/api/worker/tick")
        still_queued = client.get(f"/api/queue/{message_id}").json()
        forced = client.post("/api/worker/tick?force=true")
        processed = client.get(f"/api/queue/{message_id}").json()
        resumed = client.post("/api/worker/resume")

        assert paused.status_code == 200
        assert paused.json()["worker"]["paused"] is True
        assert paused.json()["worker"]["health"] == "paused"
        assert tick.json()["processed"] is False
        assert tick.json()["worker"]["paused"] is True
        assert still_queued["status"] == "queued"
        assert forced.json()["processed"] is True
        assert processed["status"] == "done"
        assert resumed.json()["resumed"] is True
        assert resumed.json()["worker"]["paused"] is False
