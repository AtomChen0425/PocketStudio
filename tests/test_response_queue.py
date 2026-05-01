import uuid

from fastapi.testclient import TestClient

from pocketStudio.core.dependencies import get_database
from pocketStudio.main import app


def test_response_queue_channel_ack_and_prune() -> None:
    agent_id = f"response-agent-{uuid.uuid4().hex[:8]}"

    with TestClient(app) as client:
        client.post("/api/worker/stop")
        client.post("/api/agents", json={"id": agent_id, "name": "Responder", "role": "Responds", "provider": "local"})
        message_response = client.post(
            "/api/messages",
            json={"target": f"@agent:{agent_id}", "content": "create response", "sender": "test"},
        )
        message_id = message_response.json()["id"]

        process_response = client.post(f"/api/messages/{message_id}/process")
        assert process_response.status_code == 200

        channel_response = client.get("/api/responses/channel/web")
        assert channel_response.status_code == 200
        pending = channel_response.json()
        response = next(item for item in pending if item["metadata"].get("queue_message_id") == message_id)
        assert response["status"] == "pending"

        ack_response = client.post(f"/api/responses/{response['id']}/ack")
        assert ack_response.status_code == 200
        assert ack_response.json()["ok"] is True
        assert all(item["id"] != response["id"] for item in client.get("/api/responses/channel/web").json())

        db = get_database()
        db.execute("UPDATE responses SET acked_at = ? WHERE id = ?", (0, response["id"]))
        prune_response = client.post("/api/responses/prune?older_than_ms=1")
        assert prune_response.status_code == 200
        assert prune_response.json()["pruned"] >= 1


def test_prune_completed_messages() -> None:
    agent_id = f"prune-agent-{uuid.uuid4().hex[:8]}"

    with TestClient(app) as client:
        client.post("/api/worker/stop")
        client.post("/api/agents", json={"id": agent_id, "name": "Pruner", "role": "Prunes", "provider": "local"})
        message_response = client.post(
            "/api/messages",
            json={"target": f"@agent:{agent_id}", "content": "old done message", "sender": "test"},
        )
        message_id = message_response.json()["id"]
        client.post(f"/api/messages/{message_id}/process")
        db = get_database()
        db.execute("UPDATE messages SET updated_at = datetime('now', '-2 days') WHERE id = ?", (message_id,))

        prune_response = client.post("/api/queue/prune-completed?older_than_ms=1")

        assert prune_response.status_code == 200
        assert prune_response.json()["pruned"] >= 1
        assert client.get(f"/api/queue/{message_id}").status_code == 404

