import uuid
import json
from pathlib import Path

from fastapi.testclient import TestClient

from pocketStudio.core.dependencies import get_provider_registry, get_settings
from pocketStudio.main import app


def unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


class FakeProcess:
    pid = 4321
    returncode = None

    def __init__(self) -> None:
        self.killed = False

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9

    async def wait(self) -> int:
        return self.returncode or 0


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

    all_history_response = client.get("/api/agent-messages?limit=10")
    assert all_history_response.status_code == 200
    all_history = all_history_response.json()
    assert any(item["agent_id"] == agent_id and item["role"] == "user" for item in all_history)
    assert any(item["agent_id"] == agent_id and item["role"] == "assistant" for item in all_history)

    newest_seen = max(item["id"] for item in all_history)
    filtered_history = client.get(f"/api/agent-messages?since_id={newest_seen}")
    assert filtered_history.status_code == 200
    assert all(item["id"] > newest_seen for item in filtered_history.json())

    responses_response = client.get("/api/responses?limit=10")
    assert responses_response.status_code == 200
    assert any(item.get("agent") == agent_id for item in responses_response.json())


def test_api_message_rejects_duplicate_client_message_id_without_changing_queue_id_contract() -> None:
    client = TestClient(app)
    agent_id = unique("idempotent-agent")
    client.post("/api/agents", json={"id": agent_id, "name": "Idempotent", "role": "Dedupes", "provider": "local"})
    client_message_id = unique("client-msg")

    first = client.post(
        "/api/message",
        json={
            "message": f"@{agent_id} hello once",
            "sender": "Tester",
            "channel": "web",
            "messageId": client_message_id,
        },
    )
    second = client.post(
        "/api/message",
        json={
            "message": f"@{agent_id} hello again",
            "sender": "Tester",
            "channel": "web",
            "messageId": client_message_id,
        },
    )

    assert first.status_code == 200
    assert first.json()["clientMessageId"] == client_message_id
    assert first.json()["messageId"] == str(first.json()["queueId"])
    queued = client.get(f"/api/queue/{first.json()['messageId']}").json()
    assert queued["metadata"]["clientMessageId"] == client_message_id
    assert queued["metadata"]["messageId"] == client_message_id
    assert second.status_code == 409
    assert second.json() == {"error": "duplicate messageId", "messageId": client_message_id}


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
        json={"agentId": agent_id, "message": "daily check", "cron": "0 9 * * *", "label": unique("Daily check")},
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


def test_custom_provider_cannot_shadow_builtin_local_provider() -> None:
    client = TestClient(app)
    save_response = client.put(
        "/api/custom-providers/local",
        json={
            "name": "Shadow Local",
            "harness": "openai",
            "base_url": "https://example.invalid/v1",
            "api_key": "",
            "model": "shadow-model",
        },
    )
    assert save_response.status_code == 200

    agent_id = unique("shadow-local")
    client.post("/api/agents", json={"id": agent_id, "name": "Shadow Local", "role": "Dry run", "provider": "local"})
    message_id = client.post(
        "/api/messages",
        json={"target": f"@agent:{agent_id}", "content": "use builtin local", "sender": "test"},
    ).json()["id"]
    processed = client.post(f"/api/messages/{message_id}/process")

    assert processed.status_code == 200
    assert "Configure an OpenAI-compatible provider" in processed.json()["output"]


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


def test_task_routes_keep_top_level_shape_and_add_upstream_envelope() -> None:
    client = TestClient(app)
    created = client.post(
        "/api/tasks",
        json={"title": unique("Envelope task"), "description": "shape", "status": "todo"},
    )
    task_id = created.json()["id"]
    comment = client.post(
        f"/api/tasks/{task_id}/comments",
        json={"author": "Tester", "authorType": "user", "content": "shape comment"},
    )
    updated = client.put(
        f"/api/tasks/{task_id}",
        json={"title": "Envelope task updated", "assignee": "agent-a", "assigneeType": "agent"},
    )
    fetched = client.get(f"/api/tasks/{task_id}")

    assert created.status_code == 200
    assert created.json()["ok"] is True
    assert created.json()["task"]["id"] == task_id
    assert created.json()["title"] == created.json()["task"]["title"]
    assert comment.status_code == 200
    assert updated.status_code == 200
    assert updated.json()["ok"] is True
    assert updated.json()["task"]["assigneeType"] == "agent"
    assert updated.json()["assignee_type"] == "agent"
    assert fetched.status_code == 200
    assert fetched.json()["id"] == task_id
    assert fetched.json()["commentCount"] == 1


def test_project_prefix_and_task_identifier_follow_tinyagi_shape() -> None:
    client = TestClient(app)
    workspace = f".pytest-local/project-workspace-{uuid.uuid4().hex[:8]}"
    project_response = client.post(
        "/api/projects",
        json={"name": unique("System Design"), "description": "Identifiers", "workspace": workspace},
    )
    assert project_response.status_code == 200
    project = project_response.json()["project"]
    assert project["prefix"].startswith("S")
    assert project["color"].startswith("#")
    assert Path(project["workspace"]) == Path(workspace)
    workspace_status = client.get(f"/api/projects/{project['id']}/workspace")
    assert workspace_status.status_code == 200
    assert workspace_status.json()["ok"] is True
    assert workspace_status.json()["purpose"] == "working_directory"
    assert not (Path(workspace) / ".pocketStudio").exists()

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


def test_project_without_workspace_reports_unconfigured_working_directory() -> None:
    client = TestClient(app)
    project_response = client.post(
        "/api/projects",
        json={"name": unique("No Workspace"), "description": "Uses agent workspace"},
    )
    assert project_response.status_code == 200
    project = project_response.json()["project"]
    assert project["workspace"] is None

    workspace_status = client.get(f"/api/projects/{project['id']}/workspace")
    assert workspace_status.status_code == 200
    assert workspace_status.json()["ok"] is True
    assert workspace_status.json()["configured"] is False
    assert workspace_status.json()["workspace"] is None
    assert workspace_status.json()["checks"] == []


def test_project_workspace_can_be_cleared_to_restore_agent_workspace_fallback() -> None:
    client = TestClient(app)
    workspace = f".pytest-local/project-clear-{uuid.uuid4().hex[:8]}"
    project_response = client.post(
        "/api/projects",
        json={"name": unique("Clear Workspace"), "description": "Clears cwd", "workspace": workspace},
    )
    assert project_response.status_code == 200
    project = project_response.json()["project"]
    assert Path(project["workspace"]) == Path(workspace)

    cleared = client.put(f"/api/projects/{project['id']}", json={"workspace": None})
    assert cleared.status_code == 200
    assert cleared.json()["project"]["workspace"] is None

    workspace_status = client.get(f"/api/projects/{project['id']}/workspace")
    assert workspace_status.status_code == 200
    assert workspace_status.json()["configured"] is False
    assert workspace_status.json()["workspace"] is None


def test_project_task_comment_deletes_return_404_for_missing_ids() -> None:
    client = TestClient(app)

    missing_project = client.delete("/api/projects/missing-project-id")
    missing_task = client.delete("/api/tasks/99999999")
    missing_comment = client.delete("/api/comments/missing-comment-id")

    assert missing_project.status_code == 404
    assert missing_task.status_code == 404
    assert missing_comment.status_code == 404


def test_project_delete_detaches_tasks_and_task_filters_search_server_side() -> None:
    client = TestClient(app)
    project_response = client.post("/api/projects", json={"name": unique("Detach Project"), "description": "Cleanup"})
    assert project_response.status_code == 200
    project = project_response.json()["project"]

    first = client.post(
        "/api/tasks",
        json={"title": unique("Alpha task"), "description": "Find me", "projectId": project["id"], "status": "todo"},
    ).json()
    second = client.post(
        "/api/tasks",
        json={"title": unique("Beta task"), "description": "Other", "projectId": project["id"], "status": "done"},
    ).json()

    projects = client.get("/api/projects").json()
    listed_project = next(item for item in projects if item["id"] == project["id"])
    assert listed_project["taskCount"] == 2

    searched = client.get(f"/api/tasks?projectId={project['id']}&status=todo&q=Find").json()
    assert [task["id"] for task in searched] == [first["id"]]

    delete_response = client.delete(f"/api/projects/{project['id']}")
    assert delete_response.status_code == 200

    detached_first = client.get(f"/api/tasks/{first['id']}").json()
    detached_second = client.get(f"/api/tasks/{second['id']}").json()
    assert detached_first["projectId"] is None
    assert detached_second["projectId"] is None
    assert detached_first["identifier"].startswith("T-")
    assert detached_second["identifier"].startswith("T-")
    assert client.get(f"/api/tasks?projectId={project['id']}").json() == []


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


def test_settings_import_rejects_invalid_payload_without_writing() -> None:
    client = TestClient(app)
    before = client.get("/api/settings").json()

    response = client.post("/api/settings/import", json={"settings": {"channels": {"enabled": "web"}}})

    assert response.status_code == 422
    assert "channels.enabled" in response.json()["detail"]
    after = client.get("/api/settings").json()
    assert after["channels"] == before["channels"]


def test_settings_import_rejects_invalid_runtime_sections_before_writing() -> None:
    client = TestClient(app)
    before = client.get("/api/settings").json()
    original_name = before["workspace"]["name"]
    attempted_name = unique("should-not-write")

    response = client.post(
        "/api/settings/import",
        json={
            "settings": {
                "workspace": {"name": attempted_name},
                "agents": {
                    "bad id with spaces": {
                        "name": "Bad Agent",
                        "provider": "local",
                    }
                },
            }
        },
    )
    validate = client.post(
        "/api/settings/validate",
        json={"settings": {"teams": {"bad team": {"name": "Bad Team", "maxRounds": 99}}}},
    )
    after = client.get("/api/settings").json()
    file_settings = json.loads(get_settings().settings_path.read_text(encoding="utf-8"))

    assert response.status_code == 422
    assert "bad id with spaces" in response.json()["detail"] or "String should match pattern" in response.json()["detail"]
    assert validate.status_code == 422
    assert after["workspace"]["name"] == original_name
    assert file_settings["workspace"]["name"] != attempted_name


def test_settings_validate_reports_validity_without_writing() -> None:
    client = TestClient(app)
    before = client.get("/api/settings").json()

    valid = client.post("/api/settings/validate", json={"settings": {"channels": {"enabled": ["web"]}}})
    invalid = client.post("/api/settings/validate", json={"settings": {"monitoring": {"heartbeat_interval": -1}}})

    assert valid.status_code == 200
    assert valid.json() == {"ok": True}
    assert invalid.status_code == 422
    assert "heartbeat_interval" in invalid.json()["detail"]
    after = client.get("/api/settings").json()
    assert after["channels"] == before["channels"]
    assert after["monitoring"] == before["monitoring"]


def test_settings_setup_expands_home_paths(monkeypatch) -> None:
    client = TestClient(app)
    fake_home = Path(".pytest-local/home-expand").resolve()
    monkeypatch.setenv("HOME", str(fake_home))
    agent_id = unique("home-agent")

    setup = client.post(
        "/api/setup",
        json={
            "workspace": {"name": "Expanded", "path": "$HOME/pocket-workspace"},
            "agents": {
                agent_id: {
                    "name": "Home Agent",
                    "provider": "local",
                    "working_directory": "~/agents/home-agent",
                }
            },
        },
    )

    assert setup.status_code == 200
    settings = setup.json()["settings"]
    assert Path(settings["workspace"]["path"]) == fake_home / "pocket-workspace"
    assert Path(settings["agents"][agent_id]["working_directory"]) == fake_home / "agents" / "home-agent"
    assert (fake_home / "pocket-workspace").is_dir()
    assert (fake_home / "agents" / "home-agent" / "AGENTS.md").is_file()


def test_settings_backup_info_and_restore_backup() -> None:
    client = TestClient(app)
    before_name = unique("settings-before")
    after_name = unique("settings-after")

    first = client.put("/api/settings", json={"workspace": {"name": before_name}})
    second = client.put("/api/settings", json={"workspace": {"name": after_name}})
    backup = client.get("/api/settings/backup")
    restored = client.post("/api/settings/restore-backup")

    assert first.status_code == 200
    assert second.status_code == 200
    assert backup.status_code == 200
    assert backup.json()["backup"]["exists"] is True
    assert restored.status_code == 200
    assert restored.json()["settings"]["workspace"]["name"] == before_name
    assert client.get("/api/settings").json()["workspace"]["name"] == before_name


def test_process_list_and_kill_routes_expose_active_agent_processes() -> None:
    client = TestClient(app)
    registry = get_provider_registry()
    agent_id = unique("proc-agent")
    process = FakeProcess()
    registry.processes.register(agent_id, process, {"command": "codex", "args": ["exec"], "cwd": "workspace"})
    try:
        listed = client.get("/api/processes")
        killed = client.post(f"/api/processes/{agent_id}/kill")

        assert listed.status_code == 200
        item = next(item for item in listed.json()["processes"] if item["agent"] == agent_id)
        assert item["pid"] == 4321
        assert item["alive"] is True
        assert item["command"] == "codex"
        assert item["args"] == ["exec"]
        assert item["cwd"] == "workspace"
        assert killed.status_code == 200
        assert killed.json() == {"ok": True, "agent": agent_id, "processKilled": True}
        assert process.killed is True
        assert all(item["agent"] != agent_id for item in client.get("/api/processes").json()["processes"])
    finally:
        registry.processes._processes.pop(agent_id, None)
        registry.processes._metadata.pop(agent_id, None)


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


def test_agent_put_updates_upstream_shape_workspace_prompt_and_settings_json() -> None:
    client = TestClient(app)
    agent_id = unique("put-agent")
    workspace = f".pytest-local/{agent_id}"

    created = client.put(
        f"/api/agents/{agent_id}",
        json={
            "name": "PUT Agent",
            "provider": "local",
            "model": "local-model",
            "working_directory": workspace,
            "system_prompt": "Use the PUT route.",
            "heartbeat": {"enabled": False, "interval": 321},
        },
    )
    updated = client.put(
        f"/api/agents/{agent_id}",
        json={
            "name": "Updated PUT Agent",
            "provider": "local",
            "model": "",
            "system_prompt": "Updated prompt.",
            "heartbeat": {"enabled": True, "interval": 654},
        },
    )

    assert created.status_code == 200
    assert created.json()["ok"] is True
    assert created.json()["provisioned"] is True
    assert Path(created.json()["agent"]["working_directory"]) == Path(workspace)
    assert updated.status_code == 200
    assert updated.json()["provisioned"] is False
    agent = updated.json()["agent"]
    assert agent["name"] == "Updated PUT Agent"
    assert agent["heartbeat"] == {"enabled": True, "interval": 654}
    assert Path(workspace, "AGENTS.md").read_text(encoding="utf-8") == "Updated prompt."
    file_settings = json.loads(get_settings().settings_path.read_text(encoding="utf-8"))
    assert file_settings["agents"][agent_id]["name"] == "Updated PUT Agent"
    assert Path(file_settings["agents"][agent_id]["working_directory"]) == Path(workspace)
    assert file_settings["agents"][agent_id]["heartbeat"] == {"enabled": True, "interval": 654}


def test_team_put_updates_upstream_shape_and_settings_json() -> None:
    client = TestClient(app)
    first_agent = unique("team-first")
    second_agent = unique("team-second")
    team_id = unique("put-team")
    client.post("/api/agents", json={"id": first_agent, "name": "First", "role": "First", "provider": "local"})
    client.post("/api/agents", json={"id": second_agent, "name": "Second", "role": "Second", "provider": "local"})
    client.post(
        "/api/teams",
        json={"id": team_id, "name": "Initial Team", "mode": "chain", "agent_ids": [first_agent]},
    )

    updated = client.put(
        f"/api/teams/{team_id}",
        json={
            "name": "Updated Team",
            "agents": [first_agent, second_agent],
            "leader_agent": second_agent,
            "maxRounds": 3,
            "stopWhenIdle": False,
        },
    )

    assert updated.status_code == 200
    assert updated.json()["ok"] is True
    team = updated.json()["team"]
    assert team["name"] == "Updated Team"
    assert team["agent_ids"] == [first_agent, second_agent]
    assert team["leader_agent"] == second_agent
    assert team["max_rounds"] == 3
    assert team["stop_when_idle"] is False
    file_settings = json.loads(get_settings().settings_path.read_text(encoding="utf-8"))
    assert file_settings["teams"][team_id]["agents"] == [first_agent, second_agent]
    assert file_settings["teams"][team_id]["leader_agent"] == second_agent


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


def test_services_status_start_and_stop_routes_report_worker_state() -> None:
    with TestClient(app) as client:
        client.put("/api/settings", json={"channels": {"enabled": ["web", "cli"]}})

        stopped = client.post("/api/services/stop")
        status = client.get("/api/services/status")
        started = client.post("/api/services/start")

        assert stopped.status_code == 200
        assert stopped.json()["stopped"]["worker"] in {True, False}
        assert stopped.json()["services"]["server"]["running"] is True
        assert status.status_code == 200
        assert status.json()["services"]["worker"]["running"] is False
        assert status.json()["channels"]["web"]["implemented"] is True
        assert status.json()["channels"]["cli"]["implemented"] is False
        assert started.status_code == 200
        assert started.json()["services"]["worker"]["running"] is True
