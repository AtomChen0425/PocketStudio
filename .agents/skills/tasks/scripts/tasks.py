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


def get_agent_id() -> str:
    return os.getenv("POCKETSTUDIO_AGENT_ID") or os.getenv("TINYAGI_AGENT_ID") or ""


def get_agent_name() -> str:
    return os.getenv("POCKETSTUDIO_AGENT_NAME") or get_agent_id() or "Agent"


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


def print_json(value: Any) -> int:
    print(json.dumps(value, indent=2, ensure_ascii=False))
    return 0


def normalize_error_body(body: str) -> str:
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return body.strip()
    return json.dumps(parsed, indent=2, ensure_ascii=False)


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


def build_task_payload(
    *,
    title: str = "",
    description: str = "",
    status: str = "",
    assignee: str = "",
    assignee_type: str = "",
    project: str = "",
    clear_assignee: bool = False,
    clear_project: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if title:
        payload["title"] = title
    if description:
        payload["description"] = description
    if status:
        payload["status"] = status
    if clear_assignee:
        payload["assignee"] = None
        payload["assigneeType"] = ""
    elif assignee:
        payload["assignee"] = assignee
        if assignee_type:
            payload["assigneeType"] = assignee_type
    elif assignee_type:
        payload["assigneeType"] = assignee_type
    if clear_project:
        payload["projectId"] = None
    elif project:
        payload["projectId"] = project
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="tasks.py",
        description="Manage pocketStudio tasks through the local REST API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--api-base", default=None, help="API base URL, defaults to POCKETSTUDIO_API_BASE or http://127.0.0.1:3777/api")
    sub = parser.add_subparsers(dest="command", required=True)

    list_cmd = sub.add_parser("list", help="List tasks")
    list_cmd.add_argument("--mine", action="store_true")
    list_cmd.add_argument("--status")
    list_cmd.add_argument("--assignee")
    list_cmd.add_argument("--project", "--project-id", dest="project")
    list_cmd.add_argument("--query", "-q")

    get_cmd = sub.add_parser("get", help="Get a task")
    get_cmd.add_argument("task_id")

    create_cmd = sub.add_parser("create", help="Create a task")
    create_cmd.add_argument("--title", required=True)
    create_cmd.add_argument("--description", default="")
    create_cmd.add_argument("--status", default="todo")
    create_cmd.add_argument("--assignee")
    create_cmd.add_argument("--assignee-type", "--assigneeType", dest="assignee_type", default="agent")
    create_cmd.add_argument("--project", "--project-id", "--projectId", dest="project", default="")

    update_cmd = sub.add_parser("update", help="Update a task")
    update_cmd.add_argument("task_id")
    update_cmd.add_argument("--title", default="")
    update_cmd.add_argument("--description", default="")
    update_cmd.add_argument("--status", default="")
    update_cmd.add_argument("--assignee", default="")
    update_cmd.add_argument("--assignee-type", "--assigneeType", dest="assignee_type", default="")
    update_cmd.add_argument("--project", "--project-id", "--projectId", dest="project", default="")
    update_cmd.add_argument("--clear-assignee", action="store_true")
    update_cmd.add_argument("--clear-project", action="store_true")

    status_cmd = sub.add_parser("status", help="Update task status")
    status_cmd.add_argument("task_id")
    status_cmd.add_argument("status")

    delete_cmd = sub.add_parser("delete", help="Delete a task")
    delete_cmd.add_argument("task_id")

    comment_cmd = sub.add_parser("comment", help="Add a task comment")
    comment_cmd.add_argument("task_id")
    comment_cmd.add_argument("--content", required=True)
    comment_cmd.add_argument("--author", default=get_agent_name())
    comment_cmd.add_argument("--author-type", "--authorType", dest="author_type", default="agent" if get_agent_id() else "user")

    comments_cmd = sub.add_parser("comments", help="List task comments")
    comments_cmd.add_argument("task_id")

    delete_comment_cmd = sub.add_parser("delete-comment", help="Delete a comment")
    delete_comment_cmd.add_argument("comment_id")

    reorder_cmd = sub.add_parser("reorder", help="Reorder tasks by column JSON")
    reorder_cmd.add_argument("columns_json")

    return parser.parse_args(argv)


def run(args: argparse.Namespace, client: ApiClient) -> int:
    if args.command == "list":
        params = []
        if args.mine:
            agent_id = get_agent_id()
            if not agent_id:
                die("--mine requires POCKETSTUDIO_AGENT_ID or TINYAGI_AGENT_ID")
            args.assignee = agent_id
        if args.status:
            params.append(("status", args.status))
        if args.assignee:
            params.append(("assignee", args.assignee))
        if args.project:
            params.append(("projectId", args.project))
        if args.query:
            params.append(("q", args.query))
        query = f"?{urllib.parse.urlencode(params)}" if params else ""
        tasks = client.get(f"/tasks{query}") or []
        if not isinstance(tasks, list):
            return print_json(tasks)
        for task in tasks:
            print(
                f"[{task.get('status', '-')}] {task.get('id')} {task.get('identifier', '')}  "
                f"{task.get('title', '')}  project={task.get('projectId', '-') or '-'} "
                f"assignee={task.get('assignee', '-') or '-'} comments={task.get('commentCount', 0)}"
            )
        print("---")
        print(f"{len(tasks)} task(s)")
        return 0

    if args.command == "get":
        return print_json(client.get(f"/tasks/{args.task_id}"))

    if args.command == "create":
        payload = build_task_payload(
            title=args.title,
            description=args.description,
            status=args.status,
            assignee=args.assignee or get_agent_id(),
            assignee_type=args.assignee_type or ("agent" if args.assignee or get_agent_id() else ""),
            project=args.project,
        )
        return print_json(client.post("/tasks", payload))

    if args.command == "update":
        payload = build_task_payload(
            title=args.title,
            description=args.description,
            status=args.status,
            assignee=args.assignee,
            assignee_type=args.assignee_type,
            project=args.project,
            clear_assignee=args.clear_assignee,
            clear_project=args.clear_project,
        )
        return print_json(client.put(f"/tasks/{args.task_id}", payload))

    if args.command == "status":
        return print_json(client.patch(f"/tasks/{args.task_id}/status/{urllib.parse.quote(args.status)}"))

    if args.command == "delete":
        return print_json(client.delete(f"/tasks/{args.task_id}"))

    if args.command == "comment":
        payload = {"author": args.author, "authorType": args.author_type, "content": args.content}
        return print_json(client.post(f"/tasks/{args.task_id}/comments", payload))

    if args.command == "comments":
        return print_json(client.get(f"/tasks/{args.task_id}/comments"))

    if args.command == "delete-comment":
        return print_json(client.delete(f"/comments/{args.comment_id}"))

    if args.command == "reorder":
        columns = read_json_input(args.columns_json)
        if not isinstance(columns, dict):
            die("Reorder payload must be a JSON object mapping status columns to task id lists")
        return print_json(client.put("/tasks/reorder", columns))

    die(f"Unknown command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return run(args, ApiClient(args.api_base))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
