#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_API_BASE = "http://127.0.0.1:3777/api"


def die(message: str, code: int = 1) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(code)


def get_api_base() -> str:
    return os.getenv("POCKETSTUDIO_API_BASE", DEFAULT_API_BASE).rstrip("/")


def read_json_input(value: str) -> Any:
    if value == "-":
        raw = sys.stdin.read()
    elif value.startswith("@"):
        raw = Path(value[1:]).read_text(encoding="utf-8")
    else:
        raw = value
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        die(f"Invalid JSON input: {exc}")


def pretty_json(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False)


def print_json(value: Any) -> int:
    print(pretty_json(value))
    return 0


def normalize_error_body(body: str) -> str:
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return body.strip()
    return pretty_json(parsed)


class ApiClient:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or get_api_base()).rstrip("/")

    def request(self, method: str, path: str, payload: Any | None = None) -> Any:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise SystemExit(f"HTTP {exc.code}: {normalize_error_body(body)}") from exc
        except urllib.error.URLError as exc:
            raise SystemExit(f"Could not reach pocketStudio API at {self.base_url}: {exc.reason}") from exc
        if not body:
            return None
        return json.loads(body)

    def get(self, path: str) -> Any:
        return self.request("GET", path)

    def post(self, path: str, payload: Any | None = None) -> Any:
        return self.request("POST", path, payload)

    def put(self, path: str, payload: Any | None = None) -> Any:
        return self.request("PUT", path, payload)

    def patch(self, path: str, payload: Any | None = None) -> Any:
        return self.request("PATCH", path, payload)

    def delete(self, path: str) -> Any:
        return self.request("DELETE", path)


def check_api(client: ApiClient) -> None:
    try:
        client.get("/health")
    except SystemExit as exc:
        die(str(exc))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ps_api.py",
        description="PocketStudio API wrapper for admin and maintenance tasks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--api-base", default=None, help="API base URL, defaults to POCKETSTUDIO_API_BASE or http://127.0.0.1:3777/api")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Show health, system, and queue status")

    agents = sub.add_parser("agents", help="Agent operations")
    agents_sub = agents.add_subparsers(dest="agents_command", required=True)
    agents_sub.add_parser("list")
    agents_get = agents_sub.add_parser("get")
    agents_get.add_argument("agent_id")
    agents_create = agents_sub.add_parser("create")
    agents_create.add_argument("payload")
    agents_put = agents_sub.add_parser("put")
    agents_put.add_argument("agent_id")
    agents_put.add_argument("payload")
    agents_delete = agents_sub.add_parser("delete")
    agents_delete.add_argument("agent_id")

    teams = sub.add_parser("teams", help="Team operations")
    teams_sub = teams.add_subparsers(dest="teams_command", required=True)
    teams_sub.add_parser("list")
    teams_get = teams_sub.add_parser("get")
    teams_get.add_argument("team_id")
    teams_create = teams_sub.add_parser("create")
    teams_create.add_argument("payload")
    teams_put = teams_sub.add_parser("put")
    teams_put.add_argument("team_id")
    teams_put.add_argument("payload")
    teams_delete = teams_sub.add_parser("delete")
    teams_delete.add_argument("team_id")

    settings = sub.add_parser("settings", help="Settings operations")
    settings_sub = settings.add_subparsers(dest="settings_command", required=True)
    settings_sub.add_parser("get")
    settings_update = settings_sub.add_parser("update")
    settings_update.add_argument("payload")
    settings_preview = settings_sub.add_parser("preview")
    settings_preview.add_argument("payload")
    settings_validate = settings_sub.add_parser("validate")
    settings_validate.add_argument("payload")
    settings_import = settings_sub.add_parser("import")
    settings_import.add_argument("payload")
    settings_sub.add_parser("backup")
    settings_sub.add_parser("restore-backup")
    settings_export = settings_sub.add_parser("export")
    settings_export.add_argument("path")

    message = sub.add_parser("message", help="Enqueue a legacy message")
    message.add_argument("payload")

    tasks = sub.add_parser("tasks", help="Task operations")
    tasks_sub = tasks.add_subparsers(dest="tasks_command", required=True)
    tasks_sub.add_parser("list")
    tasks_create = tasks_sub.add_parser("create")
    tasks_create.add_argument("payload")
    tasks_put = tasks_sub.add_parser("update")
    tasks_put.add_argument("task_id")
    tasks_put.add_argument("payload")
    tasks_delete = tasks_sub.add_parser("delete")
    tasks_delete.add_argument("task_id")

    projects = sub.add_parser("projects", help="Project operations")
    projects_sub = projects.add_subparsers(dest="projects_command", required=True)
    projects_sub.add_parser("list")
    projects_create = projects_sub.add_parser("create")
    projects_create.add_argument("payload")
    projects_put = projects_sub.add_parser("update")
    projects_put.add_argument("project_id")
    projects_put.add_argument("payload")
    projects_delete = projects_sub.add_parser("delete")
    projects_delete.add_argument("project_id")

    queue = sub.add_parser("queue", help="Queue operations")
    queue_sub = queue.add_subparsers(dest="queue_command", required=True)
    queue_sub.add_parser("status")
    queue_sub.add_parser("dead")
    queue_sub.add_parser("processing")
    queue_sub.add_parser("recover-stale")

    worker = sub.add_parser("worker", help="Worker operations")
    worker_sub = worker.add_subparsers(dest="worker_command", required=True)
    for command in ("status", "start", "stop", "pause", "resume", "restart", "tick"):
        worker_sub.add_parser(command)

    logs = sub.add_parser("logs", help="Show recent logs")
    logs.add_argument("limit", nargs="?", type=int, default=50)

    return parser.parse_args(argv)


def run(args: argparse.Namespace, client: ApiClient) -> int:
    check_api(client)

    if args.command == "status":
        print("=== Health ===")
        print_json(client.get("/health"))
        print("=== System ===")
        print_json(client.get("/status"))
        print("=== Queue ===")
        print_json(client.get("/queue/status"))
        return 0

    if args.command == "agents":
        if args.agents_command == "list":
            return print_json(client.get("/agents"))
        if args.agents_command == "get":
            return print_json(client.get(f"/agents/{urllib.parse.quote(args.agent_id)}"))
        if args.agents_command == "create":
            return print_json(client.post("/agents", read_json_input(args.payload)))
        if args.agents_command == "put":
            return print_json(client.put(f"/agents/{urllib.parse.quote(args.agent_id)}", read_json_input(args.payload)))
        if args.agents_command == "delete":
            return print_json(client.delete(f"/agents/{urllib.parse.quote(args.agent_id)}"))

    if args.command == "teams":
        if args.teams_command == "list":
            return print_json(client.get("/teams"))
        if args.teams_command == "get":
            return print_json(client.get(f"/teams/{urllib.parse.quote(args.team_id)}"))
        if args.teams_command == "create":
            return print_json(client.post("/teams", read_json_input(args.payload)))
        if args.teams_command == "put":
            return print_json(client.put(f"/teams/{urllib.parse.quote(args.team_id)}", read_json_input(args.payload)))
        if args.teams_command == "delete":
            return print_json(client.delete(f"/teams/{urllib.parse.quote(args.team_id)}"))

    if args.command == "settings":
        if args.settings_command == "get":
            return print_json(client.get("/settings"))
        if args.settings_command == "update":
            return print_json(client.put("/settings", read_json_input(args.payload)))
        if args.settings_command == "preview":
            return print_json(client.post("/settings/preview", read_json_input(args.payload)))
        if args.settings_command == "validate":
            return print_json(client.post("/settings/validate", read_json_input(args.payload)))
        if args.settings_command == "import":
            return print_json(client.post("/settings/import", read_json_input(args.payload)))
        if args.settings_command == "backup":
            return print_json(client.get("/settings/backup"))
        if args.settings_command == "restore-backup":
            return print_json(client.post("/settings/restore-backup", {}))
        if args.settings_command == "export":
            snapshot = client.get("/settings/export")
            Path(args.path).write_text(json.dumps(snapshot.get("settings", snapshot), indent=2, ensure_ascii=False), encoding="utf-8")
            return print_json({"ok": True, "path": args.path})

    if args.command == "message":
        return print_json(client.post("/message", read_json_input(args.payload)))

    if args.command == "tasks":
        if args.tasks_command == "list":
            return print_json(client.get("/tasks"))
        if args.tasks_command == "create":
            return print_json(client.post("/tasks", read_json_input(args.payload)))
        if args.tasks_command == "update":
            return print_json(client.put(f"/tasks/{args.task_id}", read_json_input(args.payload)))
        if args.tasks_command == "delete":
            return print_json(client.delete(f"/tasks/{args.task_id}"))

    if args.command == "projects":
        if args.projects_command == "list":
            return print_json(client.get("/projects"))
        if args.projects_command == "create":
            return print_json(client.post("/projects", read_json_input(args.payload)))
        if args.projects_command == "update":
            return print_json(client.put(f"/projects/{args.project_id}", read_json_input(args.payload)))
        if args.projects_command == "delete":
            return print_json(client.delete(f"/projects/{args.project_id}"))

    if args.command == "queue":
        if args.queue_command == "status":
            return print_json(client.get("/queue/status"))
        if args.queue_command == "dead":
            return print_json(client.get("/queue/dead"))
        if args.queue_command == "processing":
            return print_json(client.get("/queue/processing"))
        if args.queue_command == "recover-stale":
            return print_json(client.post("/queue/recover-stale", {}))

    if args.command == "worker":
        if args.worker_command == "status":
            return print_json(client.get("/worker/status"))
        if args.worker_command in {"start", "stop", "pause", "resume", "restart", "tick"}:
            return print_json(client.post(f"/worker/{args.worker_command}", {}))

    if args.command == "logs":
        return print_json(client.get(f"/logs?{urllib.parse.urlencode({'limit': args.limit})}"))

    die(f"Unknown command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return run(args, ApiClient(args.api_base))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
