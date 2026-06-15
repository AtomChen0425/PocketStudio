import uuid

from pocketStudio.core.dependencies import get_agent_service, get_heartbeat_service, get_queue_service
from pocketStudio.models import AgentCreate


def test_heartbeat_reads_agent_file_and_respects_interval() -> None:
    agent_id = f"heartbeat-agent-{uuid.uuid4().hex[:8]}"
    agents = get_agent_service()
    queue = get_queue_service()
    heartbeat = get_heartbeat_service()

    agent = agents.create(AgentCreate(id=agent_id, name="Heartbeat", role="Checks in", provider="local", heartbeat_interval=10))
    (agent.workspace / "heartbeat.md").write_text("Custom heartbeat prompt", encoding="utf-8")

    now_ms = int(__import__("time").time() * 1000)
    first = heartbeat.fire_due(queue, now_ms=now_ms)
    second = heartbeat.fire_due(queue, now_ms=now_ms + 11_000)

    assert first == []
    message = next(item for item in second if item.target == f"@agent:{agent_id}")
    assert message.content == "Custom heartbeat prompt"

    snapshot = heartbeat.snapshot(now_ms=now_ms + 11_000)
    assert snapshot["lastSent"][agent_id] == now_ms + 11_000
    assert snapshot["lastMessageIds"][agent_id] == message.id
    assert snapshot["agents"][agent_id]["lastSentAt"] == now_ms + 11_000
    assert snapshot["agents"][agent_id]["lastMessageId"] == message.id
    assert snapshot["agents"][agent_id]["nextDueAt"] > now_ms + 11_000
    assert snapshot["agents"][agent_id]["due"] is False
    assert snapshot["enabledCount"] >= 1
    assert snapshot["dueCount"] >= 0
    assert snapshot["baseInterval"] >= 10


def test_heartbeat_tick_force_and_clear_state() -> None:
    from fastapi.testclient import TestClient

    from pocketStudio.main import app

    agent_id = f"heartbeat-tick-{uuid.uuid4().hex[:8]}"
    with TestClient(app) as client:
        client.post(
            "/api/agents",
            json={"id": agent_id, "name": "Heartbeat Tick", "role": "Ticks manually", "provider": "local", "heartbeat_interval": 3600},
        )

        first = client.post("/api/heartbeat/tick", json={"agentId": agent_id, "force": True})
        second = client.post("/api/heartbeat/tick", json={"agentId": agent_id})
        cleared = client.delete(f"/api/heartbeat/state?agent={agent_id}")
        third = client.post("/api/heartbeat/tick", json={"agentId": agent_id})

        assert first.status_code == 200
        assert first.json()["queued"] == 1
        assert second.status_code == 200
        assert second.json()["queued"] == 0
        assert cleared.status_code == 200
        assert cleared.json()["cleared"] == 1
        assert third.status_code == 200
        assert third.json()["queued"] == 1

        messages = [
            item
            for item in client.get("/api/queue").json()
            if item["target"] == f"@agent:{agent_id}" and item["metadata"].get("channel") == "heartbeat"
        ]
        assert len(messages) >= 2


def test_heartbeat_tick_returns_404_for_unknown_agent() -> None:
    from fastapi.testclient import TestClient

    from pocketStudio.main import app

    with TestClient(app) as client:
        response = client.post("/api/heartbeat/tick", json={"agentId": f"missing-{uuid.uuid4().hex[:8]}", "force": True})

        assert response.status_code == 404


def test_agent_heartbeat_api_updates_runtime_config() -> None:
    from fastapi.testclient import TestClient

    from pocketStudio.main import app

    agent_id = f"heartbeat-config-{uuid.uuid4().hex[:8]}"
    with TestClient(app) as client:
        created = client.post(
            "/api/agents",
            json={
                "id": agent_id,
                "name": "Heartbeat Config",
                "role": "Checks settings",
                "provider": "local",
                "heartbeat_enabled": False,
                "heartbeat_interval": 30,
            },
        )
        assert created.status_code == 200

        heartbeat = client.get(f"/api/agents/{agent_id}/heartbeat")
        assert heartbeat.status_code == 200
        assert heartbeat.json()["enabled"] is False
        assert heartbeat.json()["interval"] == 30

        saved = client.put(
            f"/api/agents/{agent_id}/heartbeat",
            json={"content": "API heartbeat prompt", "enabled": True, "interval": 15},
        )
        assert saved.status_code == 200
        assert saved.json()["enabled"] is True
        assert saved.json()["interval"] == 15
        assert saved.json()["content"] == "API heartbeat prompt"

        settings = client.get("/api/settings").json()
        assert settings["agents"][agent_id]["heartbeat"] == {"enabled": True, "interval": 15}


def test_new_agent_gets_default_heartbeat_interval_from_monitoring_settings() -> None:
    from fastapi.testclient import TestClient

    from pocketStudio.main import app

    agent_id = f"heartbeat-default-{uuid.uuid4().hex[:8]}"
    with TestClient(app) as client:
        client.put("/api/settings", json={"monitoring": {"heartbeat_interval": 77}})
        created = client.post(
            "/api/agents",
            json={"id": agent_id, "name": "Default Heartbeat", "role": "Checks defaults", "provider": "local"},
        )

        assert created.status_code == 200
        assert created.json()["heartbeat_interval"] == 77
        heartbeat = client.get(f"/api/agents/{agent_id}/heartbeat")
        assert heartbeat.json()["interval"] == 77
        settings = client.get("/api/settings").json()
        assert settings["agents"][agent_id]["heartbeat"] == {"enabled": True, "interval": 77}


def test_new_agent_does_not_fire_heartbeat_immediately() -> None:
    agents = get_agent_service()
    queue = get_queue_service()
    heartbeat = get_heartbeat_service()

    agent_id = f"heartbeat-cooldown-{uuid.uuid4().hex[:8]}"
    agent = agents.create(AgentCreate(id=agent_id, name="Heartbeat Cooldown", role="Waits before first ping", provider="local", heartbeat_interval=3600))

    assert heartbeat.fire_due(queue, now_ms=1_000_000) == []
    snapshot = heartbeat.snapshot(now_ms=1_000_000)
    assert snapshot["agents"][agent.id]["lastSentAt"] is not None
    assert snapshot["agents"][agent.id]["due"] is False
