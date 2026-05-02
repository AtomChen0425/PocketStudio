import uuid

from fastapi.testclient import TestClient

from pocketStudio.main import app


def test_external_channel_requires_pairing_before_enqueue() -> None:
    sender_id = f"telegram-user-{uuid.uuid4().hex[:8]}"

    with TestClient(app) as client:
        response = client.post(
            "/api/message",
            json={"channel": "telegram", "senderId": sender_id, "sender": "Ada", "message": "@agent-x hello"},
        )
        assert response.status_code == 200
        assert response.json()["ok"] is False
        assert response.json()["pairingRequired"] is True
        code = response.json()["code"]

        state = client.get("/api/pairing").json()
        assert any(item["code"] == code and item["senderId"] == sender_id for item in state["pending"])

        approved = client.post("/api/pairing/approve", json={"code": code})
        assert approved.status_code == 200
        assert approved.json()["ok"] is True

        queued = client.post(
            "/api/message",
            json={"channel": "telegram", "senderId": sender_id, "sender": "Ada", "message": "@agent-x hello"},
        )
        assert queued.status_code == 200
        assert queued.json()["ok"] is True
        assert queued.json()["messageId"]


def test_channel_default_target_routes_followup_messages() -> None:
    agent_id = f"default-agent-{uuid.uuid4().hex[:8]}"
    sender_id = f"discord-user-{uuid.uuid4().hex[:8]}"

    with TestClient(app) as client:
        client.post(
            "/api/agents",
            json={"id": agent_id, "name": "Default Agent", "role": "Handles followups", "provider": "local"},
        )
        first = client.post(
            "/api/message",
            json={"channel": "discord", "senderId": sender_id, "sender": "Grace", "message": f"@{agent_id}"},
        )
        code = first.json()["code"]
        client.post("/api/pairing/approve", json={"code": code})

        switch = client.post(
            "/api/message",
            json={"channel": "discord", "senderId": sender_id, "sender": "Grace", "message": f"@{agent_id}"},
        )
        assert switch.json()["ok"] is True
        assert switch.json()["messageId"] is None
        assert "switchNotification" in switch.json()

        followup = client.post(
            "/api/message",
            json={"channel": "discord", "senderId": sender_id, "sender": "Grace", "message": "follow up"},
        )
        assert followup.json()["ok"] is True
        message = client.get(f"/api/queue/{followup.json()['messageId']}").json()
        assert message["target"] == f"@agent:{agent_id}"
        assert message["content"] == "follow up"
