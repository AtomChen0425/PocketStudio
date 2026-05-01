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

