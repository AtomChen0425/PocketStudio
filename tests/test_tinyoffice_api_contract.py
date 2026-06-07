import uuid

from fastapi.testclient import TestClient

from pocketStudio.main import app


def unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def test_tinyoffice_core_api_contracts_return_expected_shapes() -> None:
    client = TestClient(app)
    agent_id = unique("office-agent")
    team_id = unique("office-team")

    agent = client.post(
        "/api/agents",
        json={
            "id": agent_id,
            "name": "Office Agent",
            "role": "Handles office calls",
            "system_prompt": "Be concise.",
            "provider": "local",
            "model": None,
            "heartbeat_enabled": False,
        },
    )
    assert agent.status_code == 200
    assert {"id", "name", "role", "provider", "workspace"} <= set(agent.json())

    team = client.post(
        "/api/teams",
        json={"id": team_id, "name": "Office Team", "mode": "chain", "agent_ids": [agent_id], "leaderAgent": agent_id},
    )
    assert team.status_code == 200
    assert (team.json().get("leader_agent") or team.json().get("leaderAgent")) == agent_id

    settings = client.get("/api/settings")
    assert settings.status_code == 200
    assert agent_id in settings.json()["agents"]
    assert team_id in settings.json()["teams"]

    message = client.post(
        "/api/messages",
        json={"target": f"@agent:{agent_id}", "content": "hello office", "sender": "Web"},
    )
    assert message.status_code == 200
    message_id = message.json()["id"]

    assert client.get("/api/queue/status").status_code == 200
    assert client.get("/api/queue/processing").status_code == 200

    processed = client.post(f"/api/messages/{message_id}/process")
    assert processed.status_code == 200
    assert processed.json()["runs"][0]["agent_id"] == agent_id

    responses = client.get("/api/responses?limit=5")
    assert responses.status_code == 200
    response = next(item for item in responses.json() if item.get("agent") == agent_id)
    assert {"channel", "sender", "message", "originalMessage", "timestamp", "messageId"} <= set(response)

    history = client.get(f"/api/agents/{agent_id}/messages")
    assert history.status_code == 200
    assert {item["role"] for item in history.json()} == {"user", "assistant"}

    assert client.get(f"/api/agents/{agent_id}/skills").status_code == 200
    assert client.get(f"/api/agents/{agent_id}/system-prompt").status_code == 200
    assert client.get(f"/api/agents/{agent_id}/memory").status_code == 200
    assert client.get(f"/api/agents/{agent_id}/heartbeat").status_code == 200

    status = client.get("/api/status")
    assert status.status_code == 200
    assert {"ok", "uptime", "server", "channels", "heartbeat"} <= set(status.json())
    assert "interval" in status.json()["heartbeat"]

    logs = client.get("/api/logs?limit=10")
    assert logs.status_code == 200
    assert "lines" in logs.json()

    assert client.delete(f"/api/teams/{team_id}").json() == {"ok": True}
    assert client.delete(f"/api/agents/{agent_id}").json() == {"ok": True}


def test_team_workflow_import_export_api_accepts_json_artifacts() -> None:
    client = TestClient(app)
    planner_id = unique("workflow-planner")
    coder_id = unique("workflow-coder")
    team_id = unique("workflow-team")
    client.post("/api/agents", json={"id": planner_id, "name": "Planner", "role": "Plans", "provider": "local"})
    client.post("/api/agents", json={"id": coder_id, "name": "Coder", "role": "Codes", "provider": "local"})
    client.post(
        "/api/teams",
        json={"id": team_id, "name": "Workflow Team", "mode": "chain", "agent_ids": [planner_id, coder_id]},
    )
    artifact = {
        "format": "pocketstudio.team.workflow",
        "formatVersion": 1,
        "workflow": {
            "id": "delivery",
            "name": "Delivery",
            "definition": {
                "entrypoint": "plan",
                "outputNode": "build",
                "nodes": [
                    {"id": "plan", "agentId": planner_id, "prompt": "Plan it"},
                    {"id": "build", "agentId": coder_id},
                ],
                "edges": [{"source": "plan", "target": "build"}],
            },
        },
    }

    imported = client.post(f"/api/teams/{team_id}/workflows/import", json=artifact)
    exported = client.get(f"/api/teams/{team_id}/workflows/delivery/export")

    assert imported.status_code == 200
    assert imported.json()["id"] == "delivery"
    assert exported.status_code == 200
    assert exported.json()["workflow"]["definition"]["outputNode"] == "build"

    assert client.delete(f"/api/teams/{team_id}").json() == {"ok": True}
    assert client.delete(f"/api/agents/{planner_id}").json() == {"ok": True}
    assert client.delete(f"/api/agents/{coder_id}").json() == {"ok": True}


def test_tinyoffice_task_project_comment_delete_contracts_return_ok() -> None:
    client = TestClient(app)

    project = client.post("/api/projects", json={"name": unique("Office Project"), "description": "Frontend contract"})
    assert project.status_code == 200
    project_id = project.json()["project"]["id"]

    task = client.post("/api/tasks", json={"title": "Office task", "status": "todo", "projectId": project_id})
    assert task.status_code == 200
    task_id = task.json()["id"]

    comment = client.post(
        f"/api/tasks/{task_id}/comments",
        json={"author": "Web", "authorType": "user", "content": "Frontend comment"},
    )
    assert comment.status_code == 200
    comment_id = comment.json()["comment"]["id"]

    updated = client.put(f"/api/tasks/{task_id}", json={"title": "Office task updated", "status": "review"})
    assert updated.status_code == 200
    assert updated.json()["title"] == "Office task updated"
    assert updated.json()["status"] == "review"

    assert client.get(f"/api/tasks/{task_id}/comments").status_code == 200
    assert client.delete(f"/api/comments/{comment_id}").json() == {"ok": True}
    assert client.delete(f"/api/tasks/{task_id}").json() == {"ok": True}
    assert client.delete(f"/api/projects/{project_id}").json() == {"ok": True}
