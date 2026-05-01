import uuid

from fastapi.testclient import TestClient

from pocketStudio.core.dependencies import get_database
from pocketStudio.main import app


def test_dead_letter_retry_delete_and_agent_status() -> None:
    with TestClient(app) as client:
        client.post("/api/worker/stop")
        message_response = client.post(
            "/api/messages",
            json={"target": f"@agent:missing-{uuid.uuid4().hex[:8]}", "content": "fail please", "sender": "test"},
        )
        assert message_response.status_code == 200
        message_id = message_response.json()["id"]

        for _ in range(6):
            client.post("/api/worker/tick")

        dead_response = client.get("/api/queue/dead")
        assert dead_response.status_code == 200
        assert any(item["id"] == message_id for item in dead_response.json())

        agent_status = client.get("/api/queue/agents")
        assert agent_status.status_code == 200
        assert any(item["pending"] >= 0 for item in agent_status.json())

        retry_response = client.post(f"/api/queue/dead/{message_id}/retry")
        assert retry_response.status_code == 200
        assert retry_response.json()["ok"] is True
        assert client.get(f"/api/queue/{message_id}").json()["status"] == "queued"

        for _ in range(6):
            client.post("/api/worker/tick")

        delete_response = client.delete(f"/api/queue/dead/{message_id}")
        assert delete_response.status_code == 200
        assert delete_response.json()["ok"] is True


def test_recover_stale_running_message() -> None:
    with TestClient(app) as client:
        client.post("/api/worker/stop")
        agent_id = f"stale-agent-{uuid.uuid4().hex[:8]}"
        client.post("/api/agents", json={"id": agent_id, "name": "Stale Agent", "role": "Recovers", "provider": "local"})
        message_response = client.post(
            "/api/messages",
            json={"target": f"@agent:{agent_id}", "content": "recover me", "sender": "test"},
        )
        message_id = message_response.json()["id"]
        db = get_database()
        db.execute(
            """
            UPDATE messages
            SET status = 'running', attempts = 1, updated_at = datetime('now', '-20 minutes')
            WHERE id = ?
            """,
            (message_id,),
        )

        recover_response = client.post("/api/queue/recover-stale?threshold_seconds=1")

        assert recover_response.status_code == 200
        assert recover_response.json()["recovered"] >= 1
        assert client.get(f"/api/queue/{message_id}").json()["status"] == "failed"

