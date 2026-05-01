import uuid

from fastapi.testclient import TestClient

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
