from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from pocketStudio.api.errors import not_found
from pocketStudio.core.dependencies import (
    get_agent_service,
    get_database,
    get_heartbeat_service,
    get_orchestrator,
    get_project_service,
    get_queue_service,
    get_schedule_service,
    get_task_service,
    get_team_service,
    get_worker_service,
    get_provider_registry,
)
from pocketStudio.core.database import Database
from pocketStudio.models import (
    AgentCreate,
    MessageCreate,
    MessageStatus,
    ProjectCreate,
    ScheduleCreate,
    TaskCommentCreate,
    TeamCreate,
)
from pocketStudio.services.agent_service import AgentService
from pocketStudio.services.heartbeat_service import HeartbeatService
from pocketStudio.services.orchestrator import Orchestrator
from pocketStudio.services.project_service import ProjectService
from pocketStudio.services.queue_service import QueueService
from pocketStudio.services.schedule_service import ScheduleService
from pocketStudio.services.task_service import TaskService
from pocketStudio.services.team_service import TeamService
from pocketStudio.services.worker_service import WorkerService
from pocketStudio.providers.registry import ProviderRegistry

router = APIRouter(tags=["tinyagi-compat"])


def _agent_config(agent) -> dict:
    return {
        "name": agent.name,
        "provider": agent.provider,
        "model": agent.model or "",
        "working_directory": str(agent.workspace),
        "system_prompt": agent.system_prompt or agent.role,
        "heartbeat": {"enabled": agent.heartbeat_enabled, "interval": agent.heartbeat_interval},
    }


def _team_config(team) -> dict:
    return {
        "name": team.name,
        "agents": team.agent_ids,
        "leader_agent": team.agent_ids[0] if team.agent_ids else "",
    }


def _task_payload(task, comment_count: int = 0) -> dict:
    return {
        "id": str(task.id),
        "number": task.id,
        "identifier": f"PS-{task.id}",
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "assignee": task.assignee or "",
        "assigneeType": task.assignee_type or ("agent" if task.assignee else ""),
        "projectId": task.project_id,
        "createdAt": int(time.time() * 1000),
        "updatedAt": int(time.time() * 1000),
        "commentCount": comment_count,
    }


def _project_payload(project) -> dict:
    now = int(time.time() * 1000)
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "prefix": project.prefix,
        "color": project.color,
        "status": project.status,
        "createdAt": now,
        "updatedAt": now,
    }


def _schedule_payload(schedule) -> dict:
    return {
        "id": schedule.id,
        "label": schedule.label,
        "cron": schedule.cron,
        "runAt": schedule.run_at,
        "agentId": schedule.agent_id,
        "message": schedule.message,
        "channel": schedule.channel,
        "sender": schedule.sender,
        "enabled": schedule.enabled,
        "lastFiredAt": schedule.last_fired_at,
        "lastFireKey": schedule.last_fire_key,
        "createdAt": int(time.time() * 1000),
    }


def _custom_providers(db: Database) -> dict:
    rows = db.fetch_all("SELECT * FROM custom_providers ORDER BY id")
    providers = {
        row["id"]: {
            "name": row["name"],
            "harness": row["harness"],
            "base_url": row["base_url"],
            "api_key": row["api_key"],
            "model": row["model"],
        }
        for row in rows
    }
    providers.setdefault("local", {"name": "Local dry-run", "harness": "openai", "base_url": "", "api_key": "", "model": "local"})
    return providers


def _save_custom_provider_row(provider_id: str, payload: dict[str, Any], db: Database) -> None:
    db.execute(
        """
        INSERT OR REPLACE INTO custom_providers (id, name, harness, base_url, api_key, model)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            provider_id,
            payload.get("name") or provider_id,
            payload.get("harness") or "openai",
            payload.get("base_url") or "",
            payload.get("api_key") or "",
            payload.get("model"),
        ),
    )


@router.get("/settings")
def get_settings_snapshot(
    agents: AgentService = Depends(get_agent_service),
    teams: TeamService = Depends(get_team_service),
    db: Database = Depends(get_database),
) -> dict:
    custom_providers = _custom_providers(db)
    return {
        "workspace": {"name": "pocketStudio", "path": ".pocketStudio/workspace"},
        "channels": {"enabled": ["web"]},
        "models": {
            "provider": "local",
            "openai": {"model": "gpt-4o-mini"},
            "custom_providers": custom_providers,
        },
        "agents": {agent.id: _agent_config(agent) for agent in agents.list()},
        "teams": {team.id: _team_config(team) for team in teams.list()},
        "monitoring": {"heartbeat_interval": 3600},
    }


@router.put("/settings")
def update_settings_snapshot(
    payload: dict[str, Any],
    agents: AgentService = Depends(get_agent_service),
    teams: TeamService = Depends(get_team_service),
    db: Database = Depends(get_database),
    registry: ProviderRegistry = Depends(get_provider_registry),
) -> dict:
    for provider_id, provider in (payload.get("models") or {}).get("custom_providers", {}).items():
        _save_custom_provider_row(provider_id, provider, db)
    for agent_id, config in (payload.get("agents") or {}).items():
        agents.create(
            AgentCreate(
                id=agent_id,
                name=config.get("name") or agent_id,
                role=config.get("system_prompt") or config.get("name") or agent_id,
                system_prompt=config.get("system_prompt") or "",
                provider=config.get("provider") or "local",
                model=config.get("model") or None,
                workspace=config.get("working_directory") or None,
                heartbeat_enabled=(config.get("heartbeat") or {}).get("enabled", True),
                heartbeat_interval=(config.get("heartbeat") or {}).get("interval"),
            )
        )
    for team_id, config in (payload.get("teams") or {}).items():
        teams.create(
            TeamCreate(
                id=team_id,
                name=config.get("name") or team_id,
                mode="chain",
                agent_ids=config.get("agents") or [],
            )
        )
    registry.reload_custom()
    return {"ok": True, "settings": get_settings_snapshot(agents, teams, db)}


@router.post("/setup")
def run_setup(payload: dict[str, Any]) -> dict:
    return {"ok": True, "settings": payload}


@router.post("/message")
def enqueue_legacy_message(payload: dict[str, Any], orchestrator: Orchestrator = Depends(get_orchestrator)) -> dict:
    text = payload.get("message") or ""
    agent = payload.get("agent")
    target = f"@agent:{agent}" if agent else "@agent:pocketstudio"
    if text.startswith("@team:"):
        target, _, text = text.partition(" ")
    elif text.startswith("@"):
        mention, _, text = text.partition(" ")
        target = f"@agent:{mention[1:]}"
    message = orchestrator.enqueue(
        MessageCreate(target=target, content=text.strip() or payload.get("message", ""), sender=payload.get("sender") or "api")
    )
    return {"ok": True, "messageId": str(message.id)}


@router.get("/queue/status")
def queue_status(queue: QueueService = Depends(get_queue_service)) -> dict:
    return queue.status().model_dump()


@router.get("/queue/agents")
def queue_agent_status(queue: QueueService = Depends(get_queue_service)) -> list[dict]:
    return queue.agent_status()


@router.get("/queue/dead")
def queue_dead(
    limit: int = Query(default=100, ge=1, le=500),
    queue: QueueService = Depends(get_queue_service),
) -> list[dict]:
    return [message.model_dump() for message in queue.list_dead(limit)]


@router.post("/queue/dead/{message_id}/retry")
def queue_dead_retry(message_id: int, queue: QueueService = Depends(get_queue_service)) -> dict:
    return {"ok": queue.retry_dead(message_id)}


@router.delete("/queue/dead/{message_id}")
def queue_dead_delete(message_id: int, queue: QueueService = Depends(get_queue_service)) -> dict:
    return {"ok": queue.delete_dead(message_id)}


@router.post("/queue/recover-stale")
def queue_recover_stale(
    threshold_seconds: int | None = None,
    queue: QueueService = Depends(get_queue_service),
) -> dict:
    return {"ok": True, "recovered": queue.recover_stale_messages(threshold_seconds)}


@router.get("/queue/processing")
def queue_processing(queue: QueueService = Depends(get_queue_service)) -> list[dict]:
    items = queue.list(limit=100, status=MessageStatus.running)
    now = int(time.time() * 1000)
    return [
        {
            "id": item.id,
            "messageId": str(item.id),
            "channel": "web",
            "sender": item.sender,
            "message": item.content,
            "agent": item.target,
            "status": "processing",
            "processAlive": True,
            "startedAt": now,
            "duration": 0,
        }
        for item in items
    ]


@router.post("/queue/processing/{message_id}/kill")
def kill_processing(message_id: int) -> dict:
    return {"ok": True, "agent": str(message_id), "processKilled": False}


@router.get("/responses")
def responses(limit: int = Query(default=20, ge=1, le=200), queue: QueueService = Depends(get_queue_service)) -> list[dict]:
    return queue.recent_responses(limit)


@router.get("/responses/channel/{channel}")
def responses_for_channel(channel: str, queue: QueueService = Depends(get_queue_service)) -> list[dict]:
    return [queue._response_api_payload(response) for response in queue.get_responses_for_channel(channel)]


@router.post("/responses/{response_id}/ack")
def ack_response(response_id: int, queue: QueueService = Depends(get_queue_service)) -> dict:
    return {"ok": queue.ack_response(response_id)}


@router.post("/responses/prune")
def prune_responses(
    older_than_ms: int = 86_400_000,
    queue: QueueService = Depends(get_queue_service),
) -> dict:
    return {"ok": True, "pruned": queue.prune_acked_responses(older_than_ms)}


@router.post("/queue/prune-completed")
def prune_completed_messages(
    older_than_ms: int = 86_400_000,
    queue: QueueService = Depends(get_queue_service),
) -> dict:
    return {"ok": True, "pruned": queue.prune_completed_messages(older_than_ms)}


@router.get("/logs")
def logs(limit: int = Query(default=100, ge=1, le=500), db: Database = Depends(get_database)) -> dict:
    rows = db.fetch_all("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,))
    return {"lines": [f"{row['created_at']} {row['type']} {row['payload']}" for row in rows]}


@router.get("/agents/{agent_id}/messages")
def agent_messages(
    agent_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    since_id: int = Query(default=0, ge=0),
    queue: QueueService = Depends(get_queue_service),
) -> list[dict]:
    return [message.model_dump() for message in queue.get_agent_messages(agent_id, limit, since_id)]


@router.get("/agents/{agent_id}/system-prompt")
def get_agent_system_prompt(agent_id: str, agents: AgentService = Depends(get_agent_service)) -> dict:
    try:
        return agents.get_system_prompt_file(agent_id)
    except KeyError as exc:
        raise not_found(exc) from exc


@router.put("/agents/{agent_id}/system-prompt")
def save_agent_system_prompt(
    agent_id: str,
    payload: dict[str, str],
    agents: AgentService = Depends(get_agent_service),
) -> dict:
    try:
        agents.save_system_prompt_file(agent_id, payload.get("content") or "")
    except KeyError as exc:
        raise not_found(exc) from exc
    return {"ok": True}


@router.get("/agents/{agent_id}/memory")
def get_agent_memory(agent_id: str, agents: AgentService = Depends(get_agent_service)) -> dict:
    try:
        return agents.list_memory_files(agent_id)
    except KeyError as exc:
        raise not_found(exc) from exc


@router.get("/agents/{agent_id}/heartbeat")
def get_agent_heartbeat(agent_id: str, agents: AgentService = Depends(get_agent_service)) -> dict:
    try:
        return agents.get_heartbeat_file(agent_id)
    except KeyError as exc:
        raise not_found(exc) from exc


@router.put("/agents/{agent_id}/heartbeat")
def save_agent_heartbeat(agent_id: str, payload: dict[str, Any], agents: AgentService = Depends(get_agent_service)) -> dict:
    try:
        heartbeat = agents.save_heartbeat_file(
            agent_id,
            content=payload.get("content") if "content" in payload else None,
            enabled=payload.get("enabled") if "enabled" in payload else None,
            interval=payload.get("interval") if "interval" in payload else None,
        )
    except KeyError as exc:
        raise not_found(exc) from exc
    return {"ok": True, **heartbeat}


@router.get("/agents/{agent_id}/skills")
def list_agent_skills(agent_id: str, agents: AgentService = Depends(get_agent_service)) -> list[dict]:
    try:
        return agents.list_skills(agent_id)
    except KeyError as exc:
        raise not_found(exc) from exc


@router.get("/agents/{agent_id}/skills/registry")
def search_agent_skills(agent_id: str, query: str = "", agents: AgentService = Depends(get_agent_service)) -> dict:
    try:
        agents.get(agent_id)
    except KeyError as exc:
        raise not_found(exc) from exc
    return {"results": [], "raw": f"No skill registry is configured for query: {query}"}


@router.post("/agents/{agent_id}/skills/install")
def install_agent_skill(agent_id: str, payload: dict[str, str], agents: AgentService = Depends(get_agent_service)) -> dict:
    try:
        agents.get(agent_id)
    except KeyError as exc:
        raise not_found(exc) from exc
    ref = payload.get("ref") or "skill"
    skill_path = agents.install_skill_placeholder(agent_id, ref)
    return {"ok": True, "output": f"Installed {ref} at {skill_path}"}


@router.get("/projects")
def list_projects(projects: ProjectService = Depends(get_project_service)) -> list[dict]:
    return [_project_payload(project) for project in projects.list_projects()]


@router.post("/projects")
def create_project(payload: ProjectCreate, projects: ProjectService = Depends(get_project_service)) -> dict:
    return {"ok": True, "project": _project_payload(projects.create_project(payload))}


@router.put("/projects/{project_id}")
def update_project(project_id: str, payload: ProjectCreate, projects: ProjectService = Depends(get_project_service)) -> dict:
    try:
        return {"ok": True, "project": _project_payload(projects.update_project(project_id, payload))}
    except KeyError as exc:
        raise not_found(exc) from exc


@router.delete("/projects/{project_id}")
def delete_project(project_id: str, projects: ProjectService = Depends(get_project_service)) -> dict:
    projects.delete_project(project_id)
    return {"ok": True}


@router.put("/tasks/reorder")
def reorder_tasks(payload: dict[str, Any]) -> dict:
    return {"ok": True}


@router.get("/tasks/{task_id}/comments")
def list_task_comments(task_id: int, projects: ProjectService = Depends(get_project_service)) -> list[dict]:
    return [
        {
            "id": comment.id,
            "taskId": str(comment.task_id),
            "author": comment.author,
            "authorType": comment.author_type,
            "content": comment.content,
            "createdAt": int(time.time() * 1000),
        }
        for comment in projects.list_comments(task_id)
    ]


@router.post("/tasks/{task_id}/comments")
def create_task_comment(
    task_id: int,
    payload: TaskCommentCreate,
    projects: ProjectService = Depends(get_project_service),
) -> dict:
    comment = projects.create_comment(task_id, payload)
    return {
        "ok": True,
        "comment": {
            "id": comment.id,
            "taskId": str(comment.task_id),
            "author": comment.author,
            "authorType": comment.author_type,
            "content": comment.content,
            "createdAt": int(time.time() * 1000),
        },
    }


@router.delete("/comments/{comment_id}")
def delete_comment(comment_id: str, projects: ProjectService = Depends(get_project_service)) -> dict:
    projects.delete_comment(comment_id)
    return {"ok": True}


@router.get("/schedules")
def list_schedules(
    agent: str | None = None,
    schedules: ScheduleService = Depends(get_schedule_service),
) -> list[dict]:
    return [_schedule_payload(schedule) for schedule in schedules.list(agent)]


@router.post("/schedules")
def create_schedule(payload: dict[str, Any], schedules: ScheduleService = Depends(get_schedule_service)) -> dict:
    try:
        schedule = schedules.create(
            ScheduleCreate(
                label=payload.get("label"),
                cron=payload.get("cron") or "",
                run_at=payload.get("runAt") or payload.get("run_at"),
                agent_id=payload.get("agentId") or payload.get("agent_id"),
                message=payload.get("message") or "",
                channel=payload.get("channel") or "web",
                sender=payload.get("sender") or "Web",
                enabled=payload.get("enabled", True),
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"ok": True, "schedule": _schedule_payload(schedule)}


@router.put("/schedules/{schedule_id}")
def update_schedule(schedule_id: str, payload: dict[str, Any], schedules: ScheduleService = Depends(get_schedule_service)) -> dict:
    try:
        schedule = schedules.update(
            schedule_id,
            ScheduleCreate(
                label=payload.get("label"),
                cron=payload.get("cron") or "",
                run_at=payload.get("runAt") or payload.get("run_at"),
                agent_id=payload.get("agentId") or payload.get("agent_id"),
                message=payload.get("message") or "",
                channel=payload.get("channel") or "web",
                sender=payload.get("sender") or "Web",
                enabled=payload.get("enabled", True),
            ),
        )
    except KeyError as exc:
        raise not_found(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"ok": True, "schedule": _schedule_payload(schedule)}


@router.delete("/schedules/{schedule_id}")
def delete_schedule(schedule_id: str, schedules: ScheduleService = Depends(get_schedule_service)) -> dict:
    schedules.delete(schedule_id)
    return {"ok": True}


@router.get("/status")
def system_status(
    worker: WorkerService = Depends(get_worker_service),
    heartbeat: HeartbeatService = Depends(get_heartbeat_service),
) -> dict:
    return {
        "ok": True,
        "uptime": 0,
        "server": {"running": True, "port": 3777},
        "channels": {"web": {"running": True}},
        "heartbeat": heartbeat.snapshot(),
        "worker": worker.snapshot(),
    }


@router.get("/heartbeat/status")
def heartbeat_status(heartbeat: HeartbeatService = Depends(get_heartbeat_service)) -> dict:
    return heartbeat.snapshot()


@router.get("/worker/status")
def worker_status(worker: WorkerService = Depends(get_worker_service)) -> dict:
    return worker.snapshot()


@router.post("/worker/start")
def worker_start(worker: WorkerService = Depends(get_worker_service)) -> dict:
    started = worker.start()
    return {"ok": True, "started": started, "worker": worker.snapshot()}


@router.post("/worker/stop")
async def worker_stop(worker: WorkerService = Depends(get_worker_service)) -> dict:
    stopped = await worker.stop()
    return {"ok": True, "stopped": stopped, "worker": worker.snapshot()}


@router.post("/worker/restart")
async def worker_restart(worker: WorkerService = Depends(get_worker_service)) -> dict:
    await worker.restart()
    return {"ok": True, "worker": worker.snapshot()}


@router.post("/worker/tick")
async def worker_tick(worker: WorkerService = Depends(get_worker_service)) -> dict:
    processed = await worker.process_once()
    return {"ok": True, "processed": processed, "worker": worker.snapshot()}

@router.post("/services/apply")
def apply_services(worker: WorkerService = Depends(get_worker_service)) -> dict:
    worker.start()
    return {"ok": True, "started": ["web", "worker"], "heartbeat": True}


@router.post("/services/restart")
async def restart_service(worker: WorkerService = Depends(get_worker_service)) -> dict:
    await worker.restart()
    return {"ok": True, "action": "worker-restart"}


@router.post("/services/channel/{channel_id}/{action}")
def channel_action(channel_id: str, action: str) -> dict:
    return {"ok": True, "channel": channel_id, "action": action}


@router.get("/pairing")
def get_pairings(db: Database = Depends(get_database)) -> dict:
    pending = db.fetch_all("SELECT * FROM pairing_pending ORDER BY created_at DESC")
    approved = db.fetch_all("SELECT * FROM pairing_approved ORDER BY approved_at DESC")
    return {
        "pending": [
            {
                "channel": row["channel"],
                "senderId": row["sender_id"],
                "sender": row["sender"],
                "code": row["code"],
                "createdAt": row["created_at"],
                "lastSeenAt": row["last_seen_at"],
            }
            for row in pending
        ],
        "approved": [
            {
                "channel": row["channel"],
                "senderId": row["sender_id"],
                "sender": row["sender"],
                "approvedAt": row["approved_at"],
                "approvedCode": row["approved_code"],
            }
            for row in approved
        ],
    }


@router.post("/pairing/approve")
def approve_pairing(payload: dict[str, str], db: Database = Depends(get_database)) -> dict:
    code = payload.get("code")
    row = db.fetch_one("SELECT * FROM pairing_pending WHERE code = ?", (code,))
    if row is None:
        return {"ok": False}
    now = int(time.time() * 1000)
    db.execute(
        """
        INSERT OR REPLACE INTO pairing_approved (channel, sender_id, sender, approved_at, approved_code)
        VALUES (?, ?, ?, ?, ?)
        """,
        (row["channel"], row["sender_id"], row["sender"], now, code),
    )
    db.execute("DELETE FROM pairing_pending WHERE code = ?", (code,))
    return {
        "ok": True,
        "entry": {
            "channel": row["channel"],
            "senderId": row["sender_id"],
            "sender": row["sender"],
            "approvedAt": now,
            "approvedCode": code,
        },
    }


@router.delete("/pairing/{channel}/{sender_id}")
def revoke_pairing(channel: str, sender_id: str, db: Database = Depends(get_database)) -> dict:
    db.execute("DELETE FROM pairing_approved WHERE channel = ? AND sender_id = ?", (channel, sender_id))
    return {"ok": True}


@router.delete("/pairing/pending/{code}")
def dismiss_pairing(code: str, db: Database = Depends(get_database)) -> dict:
    db.execute("DELETE FROM pairing_pending WHERE code = ?", (code,))
    return {"ok": True}


@router.get("/custom-providers")
def list_custom_providers(db: Database = Depends(get_database)) -> dict:
    return _custom_providers(db)


@router.put("/custom-providers/{provider_id}")
def save_custom_provider(
    provider_id: str,
    payload: dict[str, Any],
    db: Database = Depends(get_database),
    registry: ProviderRegistry = Depends(get_provider_registry),
) -> dict:
    _save_custom_provider_row(provider_id, payload, db)
    registry.reload_custom()
    return {"ok": True, "providers": _custom_providers(db)}


@router.delete("/custom-providers/{provider_id}")
def delete_custom_provider(
    provider_id: str,
    db: Database = Depends(get_database),
    registry: ProviderRegistry = Depends(get_provider_registry),
) -> dict:
    db.execute("DELETE FROM custom_providers WHERE id = ?", (provider_id,))
    registry.reload_custom()
    return {"ok": True, "providers": _custom_providers(db)}
