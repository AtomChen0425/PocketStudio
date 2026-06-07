from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any
from urllib.parse import quote

from pocketStudio.visualizer import VisualizerClient, run_chatroom_viewer, run_team_visualizer


DEFAULT_API_URL = "http://127.0.0.1:3777"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 3777


class ApiClient:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or os.getenv("POCKETSTUDIO_API_URL") or DEFAULT_API_URL).rstrip("/")

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
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
            raise SystemExit(f"HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise SystemExit(f"Could not reach pocketStudio API at {self.base_url}: {exc.reason}") from exc
        return json.loads(body) if body else None

    def get(self, path: str) -> Any:
        return self.request("GET", path)

    def post(self, path: str, payload: dict[str, Any] | None = None) -> Any:
        return self.request("POST", path, payload)

    def put(self, path: str, payload: dict[str, Any]) -> Any:
        return self.request("PUT", path, payload)

    def delete(self, path: str) -> Any:
        return self.request("DELETE", path)


class DaemonManager:
    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, home: Path | None = None) -> None:
        self.host = host
        self.port = port
        self.home = home or Path(os.getenv("POCKETSTUDIO_HOME", ".pocketStudio"))
        self.pid_file = self.home / "pocketstudio.pid"
        self.log_dir = self.home / "logs"
        self.log_file = self.log_dir / "daemon.log"

    @property
    def api_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def status(self) -> dict[str, Any]:
        pid = self._read_pid()
        running = bool(pid and self._pid_alive(pid))
        if pid and not running:
            self._unlink_pid()
        api_status = self._fetch_status() if running else None
        return {
            "ok": True,
            "running": running,
            "pid": pid if running else None,
            "apiUrl": self.api_url,
            "logFile": str(self.log_file),
            "server": api_status,
        }

    def start(self) -> dict[str, Any]:
        current = self.status()
        if current["running"]:
            return {"ok": True, "started": False, **current}
        self.home.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        log_handle = self.log_file.open("ab")
        args = [
            sys.executable,
            "-m",
            "uvicorn",
            "pocketStudio.main:app",
            "--host",
            self.host,
            "--port",
            str(self.port),
        ]
        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        process = subprocess.Popen(
            args,
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=log_handle,
            close_fds=os.name != "nt",
            creationflags=creationflags,
        )
        log_handle.close()
        self.pid_file.write_text(str(process.pid), encoding="utf-8")
        status = self._wait_for_status()
        return {
            "ok": True,
            "started": True,
            "running": True,
            "pid": process.pid,
            "apiUrl": self.api_url,
            "logFile": str(self.log_file),
            "server": status,
        }

    def stop(self) -> dict[str, Any]:
        pid = self._read_pid()
        if not pid:
            return {"ok": True, "stopped": False, "running": False}
        try:
            os.kill(pid, signal.SIGTERM)
            stopped = True
        except OSError:
            stopped = False
        self._unlink_pid()
        return {"ok": True, "stopped": stopped, "running": False, "pid": pid}

    def restart(self) -> dict[str, Any]:
        stopped = self.stop()
        time.sleep(0.5)
        started = self.start()
        return {"ok": True, "stopped": stopped, "started": started}

    def open(self) -> dict[str, Any]:
        url = self.api_url
        opened = webbrowser.open(url)
        return {"ok": True, "opened": opened, "url": url}

    def _read_pid(self) -> int | None:
        if not self.pid_file.exists():
            return None
        try:
            return int(self.pid_file.read_text(encoding="utf-8").strip())
        except ValueError:
            self._unlink_pid()
            return None

    def _pid_alive(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except PermissionError:
            return True
        except OSError:
            return False

    def _unlink_pid(self) -> None:
        try:
            self.pid_file.unlink(missing_ok=True)
        except PermissionError:
            pass

    def _fetch_status(self) -> dict[str, Any] | None:
        try:
            with urllib.request.urlopen(f"{self.api_url}/api/status", timeout=1) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception:
            return None

    def _wait_for_status(self, timeout_seconds: float = 8.0) -> dict[str, Any] | None:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            status = self._fetch_status()
            if status:
                return status
            time.sleep(0.25)
        return None


def print_json(value: Any) -> int:
    print(json.dumps(value, indent=2, ensure_ascii=False))
    return 0


def package_version() -> str:
    try:
        return version("pocketstudio")
    except PackageNotFoundError:
        return "0.0.0+editable"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pocketstudio", description="pocketStudio command line control plane")
    parser.add_argument("--api-url", default=None, help="API base URL, defaults to POCKETSTUDIO_API_URL or http://127.0.0.1:3777")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Show system status")
    sub.add_parser("version", help="Show pocketStudio version")

    visualize = sub.add_parser("visualize", help="Show the live team visualizer")
    visualize.add_argument("--team", "-t")
    visualize.add_argument("--interval", type=float, default=1.0)
    visualize.add_argument("--events", type=int, default=80)
    visualize.add_argument("--no-clear", action="store_true")
    visualize.add_argument("--once", action="store_true")

    chatroom = sub.add_parser("chatroom", help="Watch or post to a team chatroom")
    chatroom.add_argument("team")
    chatroom.add_argument("--interval", type=float, default=1.0)
    chatroom.add_argument("--limit", type=int, default=50)
    chatroom.add_argument("--no-clear", action="store_true")
    chatroom.add_argument("--once", action="store_true")
    chatroom.add_argument("--send")
    chatroom.add_argument("--sender", default="user")

    daemon = sub.add_parser("daemon", help="Local API daemon process operations")
    daemon_sub = daemon.add_subparsers(dest="daemon_command", required=True)
    for name in ("start", "stop", "restart", "status", "open"):
        daemon_cmd = daemon_sub.add_parser(name)
        daemon_cmd.add_argument("--host", default=DEFAULT_HOST)
        daemon_cmd.add_argument("--port", type=int, default=DEFAULT_PORT)

    logs = sub.add_parser("logs", help="Show recent log lines")
    logs.add_argument("--limit", type=int, default=100)
    logs.add_argument("--event-type")
    logs.add_argument("--contains")

    settings = sub.add_parser("settings", help="Settings operations")
    settings_sub = settings.add_subparsers(dest="settings_command", required=True)
    settings_sub.add_parser("get")
    settings_sub.add_parser("backup")
    settings_sub.add_parser("restore-backup")
    export_settings = settings_sub.add_parser("export")
    export_settings.add_argument("path")
    import_settings = settings_sub.add_parser("import")
    import_settings.add_argument("path")
    validate_settings = settings_sub.add_parser("validate")
    validate_settings.add_argument("path")
    preview_settings = settings_sub.add_parser("preview")
    preview_settings.add_argument("path")

    send = sub.add_parser("send", help="Send a message")
    send.add_argument("message")
    send.add_argument("--agent")
    send.add_argument("--channel", default="cli")
    send.add_argument("--sender", default="CLI")
    send.add_argument("--sender-id")

    queue = sub.add_parser("queue", help="Queue operations")
    queue_sub = queue.add_subparsers(dest="queue_command", required=True)
    queue_sub.add_parser("status")
    queue_sub.add_parser("diagnostics")
    queue_sub.add_parser("dead")
    retry = queue_sub.add_parser("retry")
    retry.add_argument("message_id", type=int)
    delete = queue_sub.add_parser("delete-dead")
    delete.add_argument("message_id", type=int)

    process = sub.add_parser("process", help="Active agent process operations")
    process_sub = process.add_subparsers(dest="process_command", required=True)
    process_sub.add_parser("list")
    kill_process = process_sub.add_parser("kill")
    kill_process.add_argument("agent_id")

    worker = sub.add_parser("worker", help="Background worker operations")
    worker_sub = worker.add_subparsers(dest="worker_command", required=True)
    for name in ("status", "start", "stop", "pause", "resume", "restart", "tick"):
        worker_sub.add_parser(name)
    maintenance = worker_sub.add_parser("maintenance")
    maintenance.add_argument("--older-than-ms", type=int, default=86_400_000)
    maintenance.add_argument("--stale-threshold-seconds", type=int)
    maintenance.add_argument("--prune-chats", action="store_true")

    heartbeat = sub.add_parser("heartbeat", help="Heartbeat operations")
    heartbeat_sub = heartbeat.add_subparsers(dest="heartbeat_command", required=True)
    heartbeat_sub.add_parser("status")
    heartbeat_tick = heartbeat_sub.add_parser("tick")
    heartbeat_tick.add_argument("--agent")
    heartbeat_tick.add_argument("--force", action="store_true")
    heartbeat_clear = heartbeat_sub.add_parser("clear")
    heartbeat_clear.add_argument("--agent")

    channel = sub.add_parser("channel", help="Messaging channel operations")
    channel_sub = channel.add_subparsers(dest="channel_command", required=True)
    for name in ("status", "start", "stop", "restart", "tick"):
        channel_cmd = channel_sub.add_parser(name)
        channel_cmd.add_argument("channel")

    agent = sub.add_parser("agent", help="Agent operations")
    agent_sub = agent.add_subparsers(dest="agent_command", required=True)
    agent_sub.add_parser("list")
    add_agent = agent_sub.add_parser("add")
    add_agent.add_argument("id")
    add_agent.add_argument("--name", required=True)
    add_agent.add_argument("--role", required=True)
    add_agent.add_argument("--provider", default="local")
    add_agent.add_argument("--model")
    add_agent.add_argument("--workspace")
    show_agent = agent_sub.add_parser("show")
    show_agent.add_argument("id")
    workspace_agent = agent_sub.add_parser("workspace")
    workspace_agent.add_argument("id")
    repair_workspace_agent = agent_sub.add_parser("repair-workspace")
    repair_workspace_agent.add_argument("id")
    remove_agent = agent_sub.add_parser("remove")
    remove_agent.add_argument("id")
    reset_agent = agent_sub.add_parser("reset")
    reset_agent.add_argument("id")

    team = sub.add_parser("team", help="Team operations")
    team_sub = team.add_subparsers(dest="team_command", required=True)
    team_sub.add_parser("list")
    add_team = team_sub.add_parser("add")
    add_team.add_argument("id")
    add_team.add_argument("--name", required=True)
    add_team.add_argument("--mode", choices=["chain", "fanout"], default="chain")
    add_team.add_argument("--agent", action="append", default=[])
    add_team.add_argument("--leader")
    add_team.add_argument("--max-rounds", type=int, default=1)
    add_team.add_argument("--keep-alive", action="store_true")
    show_team = team_sub.add_parser("show")
    show_team.add_argument("id")
    add_team_member = team_sub.add_parser("add-member")
    add_team_member.add_argument("id")
    add_team_member.add_argument("agent")
    remove_team_member = team_sub.add_parser("remove-member")
    remove_team_member.add_argument("id")
    remove_team_member.add_argument("agent")
    set_team_leader = team_sub.add_parser("set-leader")
    set_team_leader.add_argument("id")
    set_team_leader.add_argument("agent")
    remove_team = team_sub.add_parser("remove")
    remove_team.add_argument("id")

    provider = sub.add_parser("provider", help="Provider operations")
    provider_sub = provider.add_subparsers(dest="provider_command", required=True)
    provider_sub.add_parser("list")
    provider_sub.add_parser("custom")
    save_provider = provider_sub.add_parser("save")
    save_provider.add_argument("id")
    save_provider.add_argument("--name", required=True)
    save_provider.add_argument("--harness", choices=["openai", "codex", "claude", "opencode"], default="openai")
    save_provider.add_argument("--base-url", default="")
    save_provider.add_argument("--api-key", default="")
    save_provider.add_argument("--model")
    remove_provider = provider_sub.add_parser("remove")
    remove_provider.add_argument("id")

    schedule = sub.add_parser("schedule", help="Schedule operations")
    schedule_sub = schedule.add_subparsers(dest="schedule_command", required=True)
    schedule_sub.add_parser("list")
    add_schedule = schedule_sub.add_parser("add")
    add_schedule.add_argument("--agent", required=True)
    add_schedule.add_argument("--message", required=True)
    add_schedule.add_argument("--cron", default="")
    add_schedule.add_argument("--run-at")
    add_schedule.add_argument("--label")
    remove_schedule = schedule_sub.add_parser("remove")
    remove_schedule.add_argument("id")
    fire_schedule = schedule_sub.add_parser("fire")
    fire_schedule.add_argument("id")
    fire_schedule.add_argument("--force", action="store_true")

    pairing = sub.add_parser("pairing", help="Pairing operations")
    pairing_sub = pairing.add_subparsers(dest="pairing_command", required=True)
    pairing_sub.add_parser("list")
    approve = pairing_sub.add_parser("approve")
    approve.add_argument("code")
    revoke = pairing_sub.add_parser("revoke")
    revoke.add_argument("channel")
    revoke.add_argument("sender_id")

    project = sub.add_parser("project", help="Project operations")
    project_sub = project.add_subparsers(dest="project_command", required=True)
    project_sub.add_parser("list")
    show_project = project_sub.add_parser("show")
    show_project.add_argument("id")
    add_project = project_sub.add_parser("add")
    add_project.add_argument("name")
    add_project.add_argument("--description", default="")
    add_project.add_argument("--prefix", default="")
    add_project.add_argument("--color", default="")
    add_project.add_argument("--workspace")
    update_project = project_sub.add_parser("update")
    update_project.add_argument("id")
    update_project.add_argument("--name")
    update_project.add_argument("--description")
    update_project.add_argument("--prefix")
    update_project.add_argument("--color")
    update_project.add_argument("--workspace")
    update_project.add_argument("--status", choices=["active", "archived"])
    project_workspace = project_sub.add_parser("workspace")
    project_workspace.add_argument("id")
    project_repair = project_sub.add_parser("repair-workspace")
    project_repair.add_argument("id")
    remove_project = project_sub.add_parser("remove")
    remove_project.add_argument("id")

    task = sub.add_parser("task", help="Task operations")
    task_sub = task.add_subparsers(dest="task_command", required=True)
    task_sub.add_parser("list")
    show_task = task_sub.add_parser("show")
    show_task.add_argument("id")
    add_task = task_sub.add_parser("add")
    add_task.add_argument("title")
    add_task.add_argument("--description", default="")
    add_task.add_argument("--status", default="todo")
    add_task.add_argument("--assignee")
    add_task.add_argument("--assignee-type", default="")
    add_task.add_argument("--project")
    update_task = task_sub.add_parser("update")
    update_task.add_argument("id")
    update_task.add_argument("--title")
    update_task.add_argument("--description")
    update_task.add_argument("--status")
    update_task.add_argument("--assignee")
    update_task.add_argument("--assignee-type")
    update_task.add_argument("--project")
    comments_task = task_sub.add_parser("comments")
    comments_task.add_argument("id")
    comment_task = task_sub.add_parser("comment")
    comment_task.add_argument("id")
    comment_task.add_argument("content")
    comment_task.add_argument("--author", default="CLI")
    comment_task.add_argument("--author-type", default="user")
    reorder_task = task_sub.add_parser("reorder")
    reorder_task.add_argument("status")
    reorder_task.add_argument("task_ids", nargs="+")
    remove_task = task_sub.add_parser("remove")
    remove_task.add_argument("id")

    return parser


def run(args: argparse.Namespace, client: ApiClient) -> int:
    if args.command == "status":
        return print_json(client.get("/api/status"))
    if args.command == "version":
        return print_json({"ok": True, "name": "pocketstudio", "version": package_version()})
    if args.command == "visualize":
        return run_team_visualizer(
            VisualizerClient(getattr(client, "base_url", None)),
            team_id=args.team,
            interval=args.interval,
            once=args.once,
            event_limit=args.events,
            clear_screen=not args.no_clear,
        )
    if args.command == "chatroom":
        return run_chatroom_viewer(
            VisualizerClient(getattr(client, "base_url", None)),
            team_id=args.team,
            interval=args.interval,
            once=args.once,
            send=args.send,
            sender=args.sender,
            limit=args.limit,
            clear_screen=not args.no_clear,
        )
    if args.command == "daemon":
        return run_daemon(args)
    if args.command == "logs":
        params = [f"limit={args.limit}"]
        if args.event_type:
            params.append(f"event_type={quote(args.event_type)}")
        if args.contains:
            params.append(f"contains={quote(args.contains)}")
        return print_json(client.get(f"/api/logs?{'&'.join(params)}"))
    if args.command == "settings":
        return run_settings(args, client)
    if args.command == "send":
        payload = {"message": args.message, "agent": args.agent, "channel": args.channel, "sender": args.sender}
        if args.sender_id:
            payload["senderId"] = args.sender_id
        return print_json(client.post("/api/message", payload))
    if args.command == "queue":
        if args.queue_command == "status":
            return print_json(client.get("/api/queue/status"))
        if args.queue_command == "diagnostics":
            return print_json(client.get("/api/queue/diagnostics"))
        if args.queue_command == "dead":
            return print_json(client.get("/api/queue/dead"))
        if args.queue_command == "retry":
            return print_json(client.post(f"/api/queue/dead/{args.message_id}/retry", {}))
        if args.queue_command == "delete-dead":
            return print_json(client.delete(f"/api/queue/dead/{args.message_id}"))
    if args.command == "process":
        if args.process_command == "list":
            return print_json(client.get("/api/processes"))
        if args.process_command == "kill":
            return print_json(client.post(f"/api/processes/{quote(args.agent_id)}/kill", {}))
    if args.command == "worker":
        if args.worker_command == "status":
            return print_json(client.get("/api/worker/status"))
        if args.worker_command == "maintenance":
            params = [f"older_than_ms={args.older_than_ms}"]
            if args.stale_threshold_seconds is not None:
                params.append(f"stale_threshold_seconds={args.stale_threshold_seconds}")
            if args.prune_chats:
                params.append("prune_chats=true")
            return print_json(client.post(f"/api/worker/maintenance?{'&'.join(params)}", {}))
        return print_json(client.post(f"/api/worker/{args.worker_command}", {}))
    if args.command == "heartbeat":
        if args.heartbeat_command == "status":
            return print_json(client.get("/api/heartbeat/status"))
        if args.heartbeat_command == "tick":
            return print_json(client.post("/api/heartbeat/tick", {"agentId": args.agent, "force": args.force}))
        if args.heartbeat_command == "clear":
            suffix = f"?agent={quote(args.agent)}" if args.agent else ""
            return print_json(client.delete(f"/api/heartbeat/state{suffix}"))
    if args.command == "channel":
        return print_json(client.post(f"/api/services/channel/{quote(args.channel)}/{args.channel_command}", {}))
    if args.command == "agent":
        return run_agent(args, client)
    if args.command == "team":
        return run_team(args, client)
    if args.command == "provider":
        return run_provider(args, client)
    if args.command == "schedule":
        return run_schedule(args, client)
    if args.command == "pairing":
        return run_pairing(args, client)
    if args.command == "project":
        return run_project(args, client)
    if args.command == "task":
        return run_task(args, client)
    raise SystemExit(f"Unknown command: {args.command}")


def run_agent(args: argparse.Namespace, client: ApiClient) -> int:
    if args.agent_command == "list":
        return print_json(client.get("/api/agents"))
    if args.agent_command == "show":
        return print_json(client.get(f"/api/agents/{args.id}"))
    if args.agent_command == "workspace":
        return print_json(client.get(f"/api/agents/{args.id}/workspace"))
    if args.agent_command == "repair-workspace":
        return print_json(client.post(f"/api/agents/{args.id}/workspace/repair", {}))
    if args.agent_command == "add":
        payload = {
            "id": args.id,
            "name": args.name,
            "role": args.role,
            "provider": args.provider,
            "model": args.model,
            "workspace": args.workspace,
        }
        return print_json(client.post("/api/agents", payload))
    if args.agent_command == "remove":
        return print_json(client.delete(f"/api/agents/{args.id}"))
    if args.agent_command == "reset":
        return print_json(client.post(f"/api/agents/{args.id}/reset", {}))
    raise SystemExit(f"Unknown agent command: {args.agent_command}")


def run_settings(args: argparse.Namespace, client: ApiClient) -> int:
    if args.settings_command == "get":
        return print_json(client.get("/api/settings"))
    if args.settings_command == "backup":
        return print_json(client.get("/api/settings/backup"))
    if args.settings_command == "restore-backup":
        return print_json(client.post("/api/settings/restore-backup", {}))
    if args.settings_command == "export":
        snapshot = client.get("/api/settings/export")
        Path(args.path).write_text(json.dumps(snapshot.get("settings", snapshot), ensure_ascii=False, indent=2), encoding="utf-8")
        return print_json({"ok": True, "path": args.path})
    if args.settings_command == "import":
        payload = json.loads(Path(args.path).read_text(encoding="utf-8"))
        return print_json(client.post("/api/settings/import", {"settings": payload}))
    if args.settings_command == "validate":
        payload = json.loads(Path(args.path).read_text(encoding="utf-8"))
        return print_json(client.post("/api/settings/validate", {"settings": payload}))
    if args.settings_command == "preview":
        payload = json.loads(Path(args.path).read_text(encoding="utf-8"))
        return print_json(client.post("/api/settings/preview", {"settings": payload}))
    raise SystemExit(f"Unknown settings command: {args.settings_command}")


def run_daemon(args: argparse.Namespace, manager: DaemonManager | None = None) -> int:
    daemon = manager or DaemonManager(host=args.host, port=args.port)
    if args.daemon_command == "status":
        return print_json(daemon.status())
    if args.daemon_command == "start":
        return print_json(daemon.start())
    if args.daemon_command == "stop":
        return print_json(daemon.stop())
    if args.daemon_command == "restart":
        return print_json(daemon.restart())
    if args.daemon_command == "open":
        return print_json(daemon.open())
    raise SystemExit(f"Unknown daemon command: {args.daemon_command}")


def run_team(args: argparse.Namespace, client: ApiClient) -> int:
    if args.team_command == "list":
        return print_json(client.get("/api/teams"))
    if args.team_command == "show":
        return print_json(client.get(f"/api/teams/{args.id}"))
    if args.team_command == "add":
        return print_json(
            client.post(
                "/api/teams",
                {
                    "id": args.id,
                    "name": args.name,
                    "mode": args.mode,
                    "agent_ids": args.agent,
                    "leaderAgent": args.leader or "",
                    "maxRounds": args.max_rounds,
                    "stopWhenIdle": not args.keep_alive,
                },
            )
        )
    if args.team_command == "add-member":
        return print_json(client.post(f"/api/teams/{args.id}/members/{args.agent}", {}))
    if args.team_command == "remove-member":
        return print_json(client.delete(f"/api/teams/{args.id}/members/{args.agent}"))
    if args.team_command == "set-leader":
        return print_json(client.put(f"/api/teams/{args.id}/leader/{args.agent}", {}))
    if args.team_command == "remove":
        return print_json(client.delete(f"/api/teams/{args.id}"))
    raise SystemExit(f"Unknown team command: {args.team_command}")


def run_provider(args: argparse.Namespace, client: ApiClient) -> int:
    if args.provider_command == "list":
        return print_json(client.get("/api/providers"))
    if args.provider_command == "custom":
        return print_json(client.get("/api/custom-providers"))
    if args.provider_command == "save":
        payload = {"name": args.name, "harness": args.harness, "base_url": args.base_url, "api_key": args.api_key, "model": args.model}
        return print_json(client.put(f"/api/custom-providers/{args.id}", payload))
    if args.provider_command == "remove":
        return print_json(client.delete(f"/api/custom-providers/{args.id}"))
    raise SystemExit(f"Unknown provider command: {args.provider_command}")


def run_schedule(args: argparse.Namespace, client: ApiClient) -> int:
    if args.schedule_command == "list":
        return print_json(client.get("/api/schedules"))
    if args.schedule_command == "add":
        payload = {"agentId": args.agent, "message": args.message, "cron": args.cron, "runAt": args.run_at, "label": args.label}
        return print_json(client.post("/api/schedules", payload))
    if args.schedule_command == "remove":
        return print_json(client.delete(f"/api/schedules/{args.id}"))
    if args.schedule_command == "fire":
        return print_json(client.post(f"/api/schedules/{args.id}/fire", {"force": args.force}))
    raise SystemExit(f"Unknown schedule command: {args.schedule_command}")


def run_pairing(args: argparse.Namespace, client: ApiClient) -> int:
    if args.pairing_command == "list":
        return print_json(client.get("/api/pairing"))
    if args.pairing_command == "approve":
        return print_json(client.post("/api/pairing/approve", {"code": args.code}))
    if args.pairing_command == "revoke":
        return print_json(client.delete(f"/api/pairing/{args.channel}/{args.sender_id}"))
    raise SystemExit(f"Unknown pairing command: {args.pairing_command}")


def run_project(args: argparse.Namespace, client: ApiClient) -> int:
    if args.project_command == "list":
        return print_json(client.get("/api/projects"))
    if args.project_command == "show":
        return print_json(client.get(f"/api/projects/{args.id}"))
    if args.project_command == "workspace":
        return print_json(client.get(f"/api/projects/{args.id}/workspace"))
    if args.project_command == "repair-workspace":
        return print_json(client.post(f"/api/projects/{args.id}/workspace/repair", {}))
    if args.project_command == "add":
        payload = {"name": args.name, "description": args.description, "prefix": args.prefix, "color": args.color}
        if args.workspace:
            payload["workspace"] = args.workspace
        return print_json(client.post("/api/projects", payload))
    if args.project_command == "update":
        payload = {
            key: value
            for key, value in {
                "name": args.name,
                "description": args.description,
                "prefix": args.prefix,
                "color": args.color,
                "workspace": args.workspace,
                "status": args.status,
            }.items()
            if value is not None
        }
        return print_json(client.put(f"/api/projects/{args.id}", payload))
    if args.project_command == "remove":
        return print_json(client.delete(f"/api/projects/{args.id}"))
    raise SystemExit(f"Unknown project command: {args.project_command}")


def run_task(args: argparse.Namespace, client: ApiClient) -> int:
    if args.task_command == "list":
        return print_json(client.get("/api/tasks"))
    if args.task_command == "show":
        return print_json(client.get(f"/api/tasks/{args.id}"))
    if args.task_command == "add":
        payload = {
            "title": args.title,
            "description": args.description,
            "status": args.status,
            "assignee": args.assignee,
            "assigneeType": args.assignee_type,
            "projectId": args.project,
        }
        return print_json(client.post("/api/tasks", payload))
    if args.task_command == "update":
        payload = {
            key: value
            for key, value in {
                "title": args.title,
                "description": args.description,
                "status": args.status,
                "assignee": args.assignee,
                "assigneeType": args.assignee_type,
                "projectId": args.project,
            }.items()
            if value is not None
        }
        return print_json(client.put(f"/api/tasks/{args.id}", payload))
    if args.task_command == "comments":
        return print_json(client.get(f"/api/tasks/{args.id}/comments"))
    if args.task_command == "comment":
        payload = {"author": args.author, "authorType": args.author_type, "content": args.content}
        return print_json(client.post(f"/api/tasks/{args.id}/comments", payload))
    if args.task_command == "reorder":
        return print_json(client.put("/api/tasks/reorder", {"columns": {args.status: args.task_ids}}))
    if args.task_command == "remove":
        return print_json(client.delete(f"/api/tasks/{args.id}"))
    raise SystemExit(f"Unknown task command: {args.task_command}")


def main(argv: list[str] | None = None, client: ApiClient | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run(args, client or ApiClient(args.api_url))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
