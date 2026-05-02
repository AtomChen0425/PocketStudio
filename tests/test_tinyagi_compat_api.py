import uuid
import json

from fastapi.testclient import TestClient

from pocketStudio.core.dependencies import get_settings
from pocketStudio.main import app


def unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def test_settings_queue_agent_messages_and_responses() -> None:
    client = TestClient(app)
    agent_id = unique("agent")

    agent_response = client.post(
        "/api/agents",
        json={"id": agent_id, "name": "Compat Agent", "role": "Tests compatibility", "provider": "local"},
    )
    assert agent_response.status_code == 200

    settings_response = client.get("/api/settings")
    assert settings_response.status_code == 200
    assert agent_id in settings_response.json()["agents"]

    message_response = client.post(
        "/api/message",
        json={"message": f"@{agent_id} hello from compat", "sender": "Tester", "channel": "web"},
    )
    assert message_response.status_code == 200
    message_id = message_response.json()["messageId"]

    queue_status = client.get("/api/queue/status")
    assert queue_status.status_code == 200
    assert queue_status.json()["queued"] >= 1

    process_response = client.post(f"/api/messages/{message_id}/process")
    assert process_response.status_code == 200

    history_response = client.get(f"/api/agents/{agent_id}/messages")
    assert history_response.status_code == 200
    history = history_response.json()
    assert {item["role"] for item in history} == {"user", "assistant"}

    responses_response = client.get("/api/responses?limit=10")
    assert responses_response.status_code == 200
    assert any(item.get("agent") == agent_id for item in responses_response.json())


def test_projects_comments_and_schedules() -> None:
    client = TestClient(app)
    agent_id = unique("schedule-agent")
    client.post("/api/agents", json={"id": agent_id, "name": "Scheduler", "role": "Runs schedules", "provider": "local"})

    project_response = client.post("/api/projects", json={"name": unique("Project"), "description": "Compat project"})
    assert project_response.status_code == 200
    project = project_response.json()["project"]

    task_response = client.post(
        "/api/tasks",
        json={
            "title": "Compat task",
            "description": "Task with a project and comment",
            "status": "todo",
            "projectId": project["id"],
            "assignee": agent_id,
            "assigneeType": "agent",
        },
    )
    assert task_response.status_code == 200
    task_id = task_response.json()["id"]

    comment_response = client.post(
        f"/api/tasks/{task_id}/comments",
        json={"author": "Tester", "authorType": "user", "content": "Looks useful."},
    )
    assert comment_response.status_code == 200
    assert comment_response.json()["comment"]["taskId"] == str(task_id)

    comments_response = client.get(f"/api/tasks/{task_id}/comments")
    assert comments_response.status_code == 200
    assert len(comments_response.json()) >= 1

    schedule_response = client.post(
        "/api/schedules",
        json={"agentId": agent_id, "message": "daily check", "cron": "0 9 * * *", "label": "Daily check"},
    )
    assert schedule_response.status_code == 200
    schedule = schedule_response.json()["schedule"]

    schedules_response = client.get(f"/api/schedules?agent={agent_id}")
    assert schedules_response.status_code == 200
    assert any(item["id"] == schedule["id"] for item in schedules_response.json())


def test_custom_providers_are_persisted_and_registered() -> None:
    client = TestClient(app)
    provider_id = unique("provider")

    save_response = client.put(
        f"/api/custom-providers/{provider_id}",
        json={
            "name": "Compat Provider",
            "harness": "openai",
            "base_url": "https://example.test/v1",
            "api_key": "test-key",
            "model": "test-model",
        },
    )
    assert save_response.status_code == 200

    providers_response = client.get("/api/custom-providers")
    assert providers_response.status_code == 200
    assert providers_response.json()[provider_id]["model"] == "test-model"

    registry_response = client.get("/api/providers")
    assert registry_response.status_code == 200
    assert provider_id in registry_response.json()

    settings_response = client.get("/api/settings")
    assert settings_response.status_code == 200
    assert provider_id in settings_response.json()["models"]["custom_providers"]


def test_task_reorder_persists_status_and_position() -> None:
    client = TestClient(app)
    first = client.post("/api/tasks", json={"title": unique("First"), "status": "todo"}).json()
    second = client.post("/api/tasks", json={"title": unique("Second"), "status": "todo"}).json()

    response = client.put(
        "/api/tasks/reorder",
        json={"columns": {"review": [str(second["id"]), str(first["id"])]}},
    )
    assert response.status_code == 200
    assert response.json()["updated"] == 2

    tasks = client.get("/api/tasks").json()
    reordered = [task for task in tasks if task["id"] in {first["id"], second["id"]}]
    assert [(task["id"], task["status"], task["position"]) for task in reordered] == [
        (second["id"], "review", 0),
        (first["id"], "review", 1),
    ]


def test_project_prefix_and_task_identifier_follow_tinyagi_shape() -> None:
    client = TestClient(app)
    project_response = client.post("/api/projects", json={"name": unique("System Design"), "description": "Identifiers"})
    assert project_response.status_code == 200
    project = project_response.json()["project"]
    assert project["prefix"].startswith("S")
    assert project["color"].startswith("#")

    first = client.post("/api/tasks", json={"title": unique("Task"), "projectId": project["id"]}).json()
    second = client.post("/api/tasks", json={"title": unique("Task"), "projectId": project["id"]}).json()
    global_task = client.post("/api/tasks", json={"title": unique("Global task")}).json()

    assert first["number"] == 1
    assert second["number"] == 2
    assert first["identifier"] == f"{project['prefix']}-1"
    assert second["identifier"] == f"{project['prefix']}-2"
    assert global_task["identifier"].startswith("T-")

    filtered = client.get(f"/api/tasks?projectId={project['id']}").json()
    assert {task["id"] for task in filtered} >= {first["id"], second["id"]}


def test_settings_sections_are_persisted() -> None:
    client = TestClient(app)
    workspace_name = unique("workspace")

    update = client.put(
        "/api/settings",
        json={
            "workspace": {"name": workspace_name, "path": ".pocketStudio/custom-workspace"},
            "channels": {"enabled": ["web", "cli"], "defaults": {"cli::Tester": "@agent:coder"}},
            "monitoring": {"heartbeat_interval": 123},
            "models": {"provider": "codex", "openai": {"model": "test-model"}},
        },
    )
    assert update.status_code == 200

    settings = client.get("/api/settings").json()
    assert settings["workspace"]["name"] == workspace_name
    assert settings["workspace"]["path"] == ".pocketStudio/custom-workspace"
    assert settings["channels"]["enabled"] == ["web", "cli"]
    assert settings["channels"]["defaults"]["cli::Tester"] == "@agent:coder"
    assert settings["monitoring"]["heartbeat_interval"] == 123
    assert settings["models"]["provider"] == "codex"
    assert settings["models"]["openai"]["model"] == "test-model"

    file_settings = json.loads(get_settings().settings_path.read_text(encoding="utf-8"))
    assert file_settings["workspace"]["name"] == workspace_name
    assert file_settings["channels"]["enabled"] == ["web", "cli"]
    assert file_settings["monitoring"]["heartbeat_interval"] == 123


def test_agent_and_team_crud_sync_to_settings_json() -> None:
    client = TestClient(app)
    agent_id = unique("settings-agent")
    team_id = unique("settings-team")

    client.post("/api/agents", json={"id": agent_id, "name": "Settings Agent", "role": "In file", "provider": "local"})
    client.post(
        "/api/teams",
        json={"id": team_id, "name": "Settings Team", "mode": "chain", "agent_ids": [agent_id], "leaderAgent": agent_id},
    )

    file_settings = json.loads(get_settings().settings_path.read_text(encoding="utf-8"))
    assert file_settings["agents"][agent_id]["name"] == "Settings Agent"
    assert file_settings["teams"][team_id]["leader_agent"] == agent_id


def test_agent_reset_clears_history_and_responses() -> None:
    client = TestClient(app)
    agent_id = unique("reset-agent")
    client.post("/api/agents", json={"id": agent_id, "name": "Reset Agent", "role": "Resets", "provider": "local"})
    message_id = client.post(
        "/api/messages",
        json={"target": f"@agent:{agent_id}", "content": "remember this", "sender": "test"},
    ).json()["id"]
    client.post(f"/api/messages/{message_id}/process")

    assert client.get(f"/api/agents/{agent_id}/messages").json()
    assert any(item.get("agent") == agent_id for item in client.get("/api/responses").json())

    reset = client.post(f"/api/agents/{agent_id}/reset")
    assert reset.status_code == 200
    assert reset.json()["ok"] is True
    assert reset.json()["cleared"]["messages"] >= 2
    assert client.get(f"/api/agents/{agent_id}/messages").json() == []
    assert not any(item.get("agent") == agent_id for item in client.get("/api/responses").json())


def test_status_and_services_reflect_settings_channels() -> None:
    client = TestClient(app)
    client.put("/api/settings", json={"channels": {"enabled": ["web", "cli"]}})

    status = client.get("/api/status")
    assert status.status_code == 200
    assert status.json()["uptime"] >= 0
    assert status.json()["channels"]["web"]["running"] is True
    assert status.json()["channels"]["cli"]["running"] is False

    applied = client.post("/api/services/apply")
    assert applied.status_code == 200
    assert "worker" in applied.json()["started"]
    assert any("cli" in error for error in applied.json()["errors"])
