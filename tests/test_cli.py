import argparse
from pathlib import Path
from uuid import uuid4

from pocketStudio import cli


class FakeClient:
    def __init__(self) -> None:
        self.calls = []

    def get(self, path):
        self.calls.append(("GET", path, None))
        return {"path": path}

    def post(self, path, payload=None):
        self.calls.append(("POST", path, payload))
        return {"path": path, "payload": payload}

    def put(self, path, payload):
        self.calls.append(("PUT", path, payload))
        return {"path": path, "payload": payload}

    def delete(self, path):
        self.calls.append(("DELETE", path, None))
        return {"path": path}


def test_cli_send_maps_to_message_endpoint(capsys) -> None:
    client = FakeClient()

    assert cli.main(["send", "@agent hello", "--channel", "web", "--sender", "Tester"], client=client) == 0

    assert client.calls == [
        ("POST", "/api/message", {"message": "@agent hello", "agent": None, "channel": "web", "sender": "Tester"})
    ]
    assert "/api/message" in capsys.readouterr().out


def test_cli_agent_add_maps_to_agent_endpoint() -> None:
    client = FakeClient()

    cli.main(["agent", "add", "coder", "--name", "Coder", "--role", "Writes code", "--provider", "codex"], client=client)

    method, path, payload = client.calls[0]
    assert method == "POST"
    assert path == "/api/agents"
    assert payload["id"] == "coder"
    assert payload["provider"] == "codex"


def test_cli_agent_reset_maps_to_reset_endpoint() -> None:
    client = FakeClient()

    cli.main(["agent", "reset", "coder"], client=client)

    assert client.calls == [("POST", "/api/agents/coder/reset", {})]


def test_cli_team_member_commands_map_to_team_endpoints() -> None:
    client = FakeClient()

    cli.main(["team", "add-member", "dev", "coder"], client=client)
    cli.main(["team", "remove-member", "dev", "coder"], client=client)
    cli.main(["team", "set-leader", "dev", "reviewer"], client=client)

    assert client.calls == [
        ("POST", "/api/teams/dev/members/coder", {}),
        ("DELETE", "/api/teams/dev/members/coder", None),
        ("PUT", "/api/teams/dev/leader/reviewer", {}),
    ]


def test_cli_team_add_includes_iteration_controls() -> None:
    client = FakeClient()

    cli.main(["team", "add", "dev", "--name", "Dev", "--agent", "lead", "--max-rounds", "3", "--keep-alive"], client=client)

    assert client.calls == [
        (
            "POST",
            "/api/teams",
            {
                "id": "dev",
                "name": "Dev",
                "mode": "chain",
                "agent_ids": ["lead"],
                "leaderAgent": "",
                "maxRounds": 3,
                "stopWhenIdle": False,
            },
        )
    ]


def test_cli_provider_save_maps_to_custom_provider_endpoint() -> None:
    client = FakeClient()

    cli.main(
        [
            "provider",
            "save",
            "proxy",
            "--name",
            "Proxy",
            "--harness",
            "openai",
            "--base-url",
            "https://example.test/v1",
            "--api-key",
            "secret",
            "--model",
            "model-x",
        ],
        client=client,
    )

    method, path, payload = client.calls[0]
    assert method == "PUT"
    assert path == "/api/custom-providers/proxy"
    assert payload["model"] == "model-x"


def test_cli_logs_maps_to_logs_endpoint() -> None:
    client = FakeClient()

    cli.main(["logs", "--limit", "5", "--event-type", "message.queued", "--contains", "hello world"], client=client)

    assert client.calls == [("GET", "/api/logs?limit=5&event_type=message.queued&contains=hello%20world", None)]


def test_cli_settings_get_maps_to_settings_endpoint() -> None:
    client = FakeClient()

    cli.main(["settings", "get"], client=client)

    assert client.calls == [("GET", "/api/settings", None)]


def test_cli_settings_backup_maps_to_backup_endpoint() -> None:
    client = FakeClient()

    cli.main(["settings", "backup"], client=client)

    assert client.calls == [("GET", "/api/settings/backup", None)]


def test_cli_settings_restore_backup_maps_to_restore_endpoint() -> None:
    client = FakeClient()

    cli.main(["settings", "restore-backup"], client=client)

    assert client.calls == [("POST", "/api/settings/restore-backup", {})]


def test_cli_settings_import_posts_settings_file() -> None:
    client = FakeClient()
    temp_dir = Path(".pytest-tmp")
    temp_dir.mkdir(exist_ok=True)
    settings_file = temp_dir / f"settings-{uuid4().hex}.json"
    settings_file.write_text('{"monitoring": {"heartbeat_interval": 42}}', encoding="utf-8")

    cli.main(["settings", "import", str(settings_file)], client=client)
    try:
        settings_file.unlink(missing_ok=True)
    except PermissionError:
        pass

    assert client.calls == [
        ("POST", "/api/settings/import", {"settings": {"monitoring": {"heartbeat_interval": 42}}})
    ]


def test_cli_settings_validate_posts_settings_file_without_importing() -> None:
    client = FakeClient()
    temp_dir = Path(".pytest-tmp")
    temp_dir.mkdir(exist_ok=True)
    settings_file = temp_dir / f"settings-{uuid4().hex}.json"
    settings_file.write_text('{"channels": {"enabled": ["web"]}}', encoding="utf-8")

    cli.main(["settings", "validate", str(settings_file)], client=client)
    try:
        settings_file.unlink(missing_ok=True)
    except PermissionError:
        pass

    assert client.calls == [
        ("POST", "/api/settings/validate", {"settings": {"channels": {"enabled": ["web"]}}})
    ]


def test_cli_process_commands_map_to_process_endpoints() -> None:
    client = FakeClient()

    cli.main(["process", "list"], client=client)
    cli.main(["process", "kill", "agent 1"], client=client)

    assert client.calls == [
        ("GET", "/api/processes", None),
        ("POST", "/api/processes/agent%201/kill", {}),
    ]


def test_cli_project_add_maps_to_projects_endpoint() -> None:
    client = FakeClient()

    cli.main(["project", "add", "System Design", "--description", "Planning", "--prefix", "SYS"], client=client)

    assert client.calls == [
        ("POST", "/api/projects", {"name": "System Design", "description": "Planning", "prefix": "SYS", "color": ""})
    ]


def test_cli_project_update_maps_to_projects_endpoint() -> None:
    client = FakeClient()

    cli.main(["project", "update", "proj-1", "--name", "Renamed", "--status", "archived"], client=client)

    assert client.calls == [("PUT", "/api/projects/proj-1", {"name": "Renamed", "status": "archived"})]


def test_cli_task_add_maps_to_tasks_endpoint() -> None:
    client = FakeClient()

    cli.main(["task", "add", "Wire backend", "--project", "proj-1", "--assignee", "coder", "--assignee-type", "agent"], client=client)

    assert client.calls == [
        (
            "POST",
            "/api/tasks",
            {
                "title": "Wire backend",
                "description": "",
                "status": "todo",
                "assignee": "coder",
                "assigneeType": "agent",
                "projectId": "proj-1",
            },
        )
    ]


def test_cli_task_update_comment_and_reorder_commands() -> None:
    client = FakeClient()

    cli.main(["task", "update", "12", "--status", "review", "--assignee", "coder"], client=client)
    cli.main(["task", "comments", "12"], client=client)
    cli.main(["task", "comment", "12", "Looks ready", "--author", "Tester"], client=client)
    cli.main(["task", "reorder", "done", "12", "13"], client=client)

    assert client.calls == [
        ("PUT", "/api/tasks/12", {"status": "review", "assignee": "coder"}),
        ("GET", "/api/tasks/12/comments", None),
        ("POST", "/api/tasks/12/comments", {"author": "Tester", "authorType": "user", "content": "Looks ready"}),
        ("PUT", "/api/tasks/reorder", {"columns": {"done": ["12", "13"]}}),
    ]


class FakeDaemon:
    def __init__(self) -> None:
        self.calls = []

    def status(self):
        self.calls.append("status")
        return {"running": False}

    def start(self):
        self.calls.append("start")
        return {"started": True}

    def stop(self):
        self.calls.append("stop")
        return {"stopped": True}

    def restart(self):
        self.calls.append("restart")
        return {"ok": True}

    def open(self):
        self.calls.append("open")
        return {"opened": True}


def test_cli_daemon_commands_dispatch_to_manager() -> None:
    manager = FakeDaemon()

    cli.run_daemon(argparse.Namespace(daemon_command="status", host="127.0.0.1", port=3777), manager=manager)
    cli.run_daemon(argparse.Namespace(daemon_command="start", host="127.0.0.1", port=3777), manager=manager)
    cli.run_daemon(argparse.Namespace(daemon_command="stop", host="127.0.0.1", port=3777), manager=manager)
    cli.run_daemon(argparse.Namespace(daemon_command="restart", host="127.0.0.1", port=3777), manager=manager)
    cli.run_daemon(argparse.Namespace(daemon_command="open", host="127.0.0.1", port=3777), manager=manager)

    assert manager.calls == ["status", "start", "stop", "restart", "open"]


def test_cli_version_does_not_call_api(capsys) -> None:
    client = FakeClient()

    assert cli.main(["version"], client=client) == 0

    assert client.calls == []
    output = capsys.readouterr().out
    assert '"name": "pocketstudio"' in output
    assert '"version":' in output


def test_cli_worker_maintenance_maps_to_worker_endpoint() -> None:
    client = FakeClient()

    cli.main(
        [
            "worker",
            "maintenance",
            "--older-than-ms",
            "0",
            "--stale-threshold-seconds",
            "3",
            "--prune-chats",
        ],
        client=client,
    )

    assert client.calls == [
        ("POST", "/api/worker/maintenance?older_than_ms=0&stale_threshold_seconds=3&prune_chats=true", {})
    ]


def test_cli_worker_pause_and_resume_map_to_worker_endpoints() -> None:
    client = FakeClient()

    cli.main(["worker", "pause"], client=client)
    cli.main(["worker", "resume"], client=client)

    assert client.calls == [
        ("POST", "/api/worker/pause", {}),
        ("POST", "/api/worker/resume", {}),
    ]


def test_cli_channel_commands_map_to_service_channel_endpoints() -> None:
    client = FakeClient()

    cli.main(["channel", "status", "telegram"], client=client)
    cli.main(["channel", "tick", "telegram"], client=client)

    assert client.calls == [
        ("POST", "/api/services/channel/telegram/status", {}),
        ("POST", "/api/services/channel/telegram/tick", {}),
    ]
