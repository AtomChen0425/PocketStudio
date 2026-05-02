import uuid

from pocketStudio.core.dependencies import get_agent_service, get_heartbeat_service, get_queue_service
from pocketStudio.models import AgentCreate


def test_heartbeat_reads_agent_file_and_respects_interval() -> None:
    agent_id = f"heartbeat-agent-{uuid.uuid4().hex[:8]}"
    agents = get_agent_service()
    queue = get_queue_service()
    heartbeat = get_heartbeat_service()

    agent = agents.create(AgentCreate(id=agent_id, name="Heartbeat", role="Checks in", provider="local"))
    (agent.workspace / "heartbeat.md").write_text("Custom heartbeat prompt", encoding="utf-8")

    first = heartbeat.fire_due(queue, now_ms=1_000_000)
    second = heartbeat.fire_due(queue, now_ms=1_000_100)

    message = next(item for item in first if item.target == f"@agent:{agent_id}")
    assert message.content == "Custom heartbeat prompt"
    assert second == []

    snapshot = heartbeat.snapshot()
    assert snapshot["lastSent"][agent_id] == 1_000_000
    assert snapshot["lastMessageIds"][agent_id] == message.id


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
