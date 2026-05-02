from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from pocketStudio.api.errors import not_found
from pocketStudio.core.dependencies import (
    get_agent_service,
    get_channel_service,
    get_chat_service,
    get_database,
    get_event_service,
    get_heartbeat_service,
    get_orchestrator,
    get_plugin_service,
    get_project_service,
    get_queue_service,
    get_schedule_service,
    get_settings_service,
    get_task_service,
    get_team_service,
    get_worker_service,
    get_provider_registry,
)
from pocketStudio.core.database import Database
from pocketStudio.core.runtime import uptime_seconds
from pocketStudio.models import (
    AgentCreate,
    MessageCreate,
    ProjectCreate,
    ScheduleCreate,
    TaskCommentCreate,
    TeamCreate,
)
from pocketStudio.services.agent_service import AgentService
from pocketStudio.services.channel_service import ChannelService
from pocketStudio.services.chat_service import ChatService
from pocketStudio.services.event_service import EventService
from pocketStudio.services.heartbeat_service import HeartbeatService
from pocketStudio.services.orchestrator import Orchestrator
from pocketStudio.services.project_service import ProjectService
from pocketStudio.services.plugin_service import PluginService
from pocketStudio.services.queue_service import QueueService
from pocketStudio.services.schedule_service import ScheduleService
from pocketStudio.services.settings_service import SettingsService, SettingsValidationError
from pocketStudio.services.task_service import TaskService
from pocketStudio.services.team_service import TeamService
from pocketStudio.services.worker_service import WorkerService
from pocketStudio.providers.registry import ProviderRegistry

router = APIRouter(tags=["tinyagi-compat"])


def _millis(value: str | int | float | None) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    if not value:
        return int(time.time() * 1000)
    parsed = value.replace("Z", "+00:00")
    try:
        return int(datetime.fromisoformat(parsed).timestamp() * 1000)
    except ValueError:
        return int(time.time() * 1000)


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
        "leader_agent": team.leader_agent or (team.agent_ids[0] if team.agent_ids else ""),
        "max_rounds": team.max_rounds,
        "stop_when_idle": team.stop_when_idle,
    }


def _task_payload(task, comment_count: int = 0) -> dict:
    return {
        "id": str(task.id),
        "number": task.number,
        "identifier": task.identifier,
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "assignee": task.assignee or "",
        "assigneeType": task.assignee_type or ("agent" if task.assignee else ""),
        "projectId": task.project_id,
        "sortOrder": task.position,
        "createdAt": _millis(task.created_at),
        "updatedAt": _millis(task.updated_at),
        "commentCount": comment_count,
    }


def _project_payload(project, task_count: int | None = None) -> dict:
    payload = {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "prefix": project.prefix,
        "color": project.color,
        "status": project.status,
        "createdAt": _millis(project.created_at),
        "updatedAt": _millis(project.updated_at),
    }
    if task_count is not None:
        payload["taskCount"] = task_count
    return payload


def _schedule_payload(schedule) -> dict:
    payload = {
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
    return payload


def _schedule_payload_with_status(schedule, schedules: ScheduleService) -> dict:
    payload = _schedule_payload(schedule)
    payload.update(schedules.schedule_status(schedule))
    return payload


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


def _target_agent_id(target: str) -> str:
    if target.startswith("@agent:"):
        return target.split(":", 1)[1]
    if target.startswith("@"):
        return target[1:]
    return target


@router.get("/settings")
def get_settings_snapshot(
    agents: AgentService = Depends(get_agent_service),
    teams: TeamService = Depends(get_team_service),
    db: Database = Depends(get_database),
    settings_service: SettingsService = Depends(get_settings_service),
) -> dict:
    custom_providers = _custom_providers(db)
    settings = settings_service.snapshot()
    settings["models"] = {**settings.get("models", {}), "custom_providers": custom_providers}
    settings["agents"] = {agent.id: _agent_config(agent) for agent in agents.list()}
    settings["teams"] = {team.id: _team_config(team) for team in teams.list()}
    return settings


@router.get("/settings/export")
def export_settings_snapshot(
    agents: AgentService = Depends(get_agent_service),
    teams: TeamService = Depends(get_team_service),
    db: Database = Depends(get_database),
    settings_service: SettingsService = Depends(get_settings_service),
) -> dict:
    return {"ok": True, "settings": get_settings_snapshot(agents, teams, db, settings_service)}


@router.post("/settings/validate")
def validate_settings_snapshot(
    payload: dict[str, Any],
    settings_service: SettingsService = Depends(get_settings_service),
) -> dict:
    settings_payload = payload.get("settings") if "settings" in payload else payload
    if not isinstance(settings_payload, dict):
        raise HTTPException(status_code=422, detail="settings payload must be an object")
    try:
        settings_service.validate(settings_payload)
    except SettingsValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"ok": True}


@router.get("/settings/backup")
def settings_backup_info(settings_service: SettingsService = Depends(get_settings_service)) -> dict:
    return {"ok": True, "backup": settings_service.backup_info()}


@router.post("/settings/restore-backup")
def restore_settings_backup(
    agents: AgentService = Depends(get_agent_service),
    teams: TeamService = Depends(get_team_service),
    db: Database = Depends(get_database),
    settings_service: SettingsService = Depends(get_settings_service),
) -> dict:
    try:
        settings_service.restore_backup()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SettingsValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"ok": True, "settings": get_settings_snapshot(agents, teams, db, settings_service)}


@router.put("/settings")
def update_settings_snapshot(
    payload: dict[str, Any],
    agents: AgentService = Depends(get_agent_service),
    teams: TeamService = Depends(get_team_service),
    db: Database = Depends(get_database),
    registry: ProviderRegistry = Depends(get_provider_registry),
    settings_service: SettingsService = Depends(get_settings_service),
) -> dict:
    try:
        settings_service.update(payload)
    except SettingsValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
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
                leader_agent=config.get("leader_agent") or "",
                max_rounds=config.get("max_rounds") or config.get("maxRounds") or 1,
                stop_when_idle=config.get("stop_when_idle", config.get("stopWhenIdle", True)),
            )
        )
    registry.reload_custom()
    return {"ok": True, "settings": get_settings_snapshot(agents, teams, db, settings_service)}


@router.post("/settings/import")
def import_settings_snapshot(
    payload: dict[str, Any],
    agents: AgentService = Depends(get_agent_service),
    teams: TeamService = Depends(get_team_service),
    db: Database = Depends(get_database),
    registry: ProviderRegistry = Depends(get_provider_registry),
    settings_service: SettingsService = Depends(get_settings_service),
) -> dict:
    settings_payload = payload.get("settings") if "settings" in payload else payload
    if not isinstance(settings_payload, dict):
        raise HTTPException(status_code=422, detail="settings payload must be an object")
    return update_settings_snapshot(settings_payload, agents, teams, db, registry, settings_service)


@router.post("/setup")
def run_setup(
    payload: dict[str, Any],
    agents: AgentService = Depends(get_agent_service),
    teams: TeamService = Depends(get_team_service),
    db: Database = Depends(get_database),
    registry: ProviderRegistry = Depends(get_provider_registry),
    settings_service: SettingsService = Depends(get_settings_service),
) -> dict:
    result = update_settings_snapshot(payload, agents, teams, db, registry, settings_service)["settings"]
    settings_service.ensure_setup_dirs(result)
    return {"ok": True, "settings": result}


@router.post("/message")
def enqueue_legacy_message(
    payload: dict[str, Any],
    orchestrator: Orchestrator = Depends(get_orchestrator),
    channels: ChannelService = Depends(get_channel_service),
) -> dict:
    text = payload.get("message") or ""
    channel = payload.get("channel") or "web"
    sender = payload.get("sender") or "api"
    sender_id = payload.get("senderId") or payload.get("sender_id") or sender
    if channel != "web" and sender_id:
        pairing = channels.ensure_sender_paired(channel, sender_id, sender)
        if not pairing.approved:
            return {
                "ok": False,
                "pairingRequired": True,
                "code": pairing.code,
                "isNewPending": pairing.is_new_pending,
                "message": f"Pair this sender with code {pairing.code}",
            }
    agent = payload.get("agent")
    routed = channels.route_message(channel, sender_id, text, explicit_agent=agent)
    if routed.target is None:
        return {"ok": True, "messageId": None, "switchNotification": routed.switch_notification}
    message = orchestrator.enqueue(MessageCreate(target=routed.target, content=routed.content or text, sender=sender))
    response = {"ok": True, "messageId": str(message.id)}
    if routed.switch_notification:
        response["switchNotification"] = routed.switch_notification
    return response


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
def queue_processing(
    queue: QueueService = Depends(get_queue_service),
    registry: ProviderRegistry = Depends(get_provider_registry),
) -> list[dict]:
    items = queue.processing_payloads()
    for item in items:
        item["processAlive"] = registry.agent_process_alive(_target_agent_id(item["target"]))
    return items


@router.get("/processes")
def active_processes(registry: ProviderRegistry = Depends(get_provider_registry)) -> dict:
    return {"processes": registry.active_processes()}


@router.post("/processes/{agent_id}/kill")
async def kill_agent_process(
    agent_id: str,
    registry: ProviderRegistry = Depends(get_provider_registry),
) -> dict:
    return {"ok": True, "agent": agent_id, "processKilled": await registry.kill_agent(agent_id)}


@router.post("/queue/processing/{message_id}/kill")
async def kill_processing(
    message_id: int,
    queue: QueueService = Depends(get_queue_service),
    registry: ProviderRegistry = Depends(get_provider_registry),
) -> dict:
    try:
        message = queue.get(message_id)
    except KeyError:
        return {"ok": False, "agent": str(message_id), "processKilled": False}
    agent_id = _target_agent_id(message.target)
    killed = await registry.kill_agent(agent_id)
    if killed:
        queue.mark_failed(message_id, "Killed by user")
    return {"ok": True, "agent": agent_id, "processKilled": killed}


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
def logs(
    limit: int = Query(default=100, ge=1, le=500),
    event_type: str | None = None,
    contains: str | None = None,
    events: EventService = Depends(get_event_service),
) -> dict:
    records = events.log_records(limit=limit, event_type=event_type, contains=contains)
    return {"lines": [record["line"] for record in records], "records": records}


@router.get("/chats")
def list_chats(chat: ChatService = Depends(get_chat_service)) -> list[dict]:
    return chat.archives()


@router.get("/chats/{team_id}")
def read_chat_archive(
    team_id: str,
    limit: int = Query(default=500, ge=1, le=2000),
    sender: str | None = None,
    q: str | None = None,
    chat: ChatService = Depends(get_chat_service),
) -> dict:
    messages = chat.list(team_id=team_id, limit=limit, sender=sender, query=q)
    return {
        "teamId": team_id,
        "messages": [message.model_dump() for message in messages],
    }


@router.get("/agents/{agent_id}/messages")
def agent_messages(
    agent_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    since_id: int = Query(default=0, ge=0),
    queue: QueueService = Depends(get_queue_service),
) -> list[dict]:
    return [message.model_dump() for message in queue.get_agent_messages(agent_id, limit, since_id)]


@router.post("/agents/{agent_id}/reset")
def reset_agent_runtime(
    agent_id: str,
    agents: AgentService = Depends(get_agent_service),
    queue: QueueService = Depends(get_queue_service),
) -> dict:
    try:
        agents.get(agent_id)
    except KeyError as exc:
        raise not_found(exc) from exc
    return {"ok": True, "agentId": agent_id, "cleared": queue.reset_agent(agent_id)}


@router.get("/plugins")
def list_plugins(plugins: PluginService = Depends(get_plugin_service)) -> dict:
    return {"plugins": plugins.list_plugins()}


@router.post("/plugins/reload")
def reload_plugins(plugins: PluginService = Depends(get_plugin_service)) -> dict:
    return {"ok": True, "plugins": plugins.list_plugins(reload=True)}


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
def list_projects(status: str | None = None, projects: ProjectService = Depends(get_project_service)) -> list[dict]:
    all_projects = projects.list_projects()
    if status:
        all_projects = [project for project in all_projects if project.status == status]
    return [_project_payload(project, projects.task_count(project.id)) for project in all_projects]


@router.post("/projects")
def create_project(payload: ProjectCreate, projects: ProjectService = Depends(get_project_service)) -> dict:
    project = projects.create_project(payload)
    return {"ok": True, "project": _project_payload(project, projects.task_count(project.id))}


@router.get("/projects/{project_id}")
def get_project(project_id: str, projects: ProjectService = Depends(get_project_service)) -> dict:
    try:
        return _project_payload(projects.get_project(project_id), projects.task_count(project_id))
    except KeyError as exc:
        raise not_found(exc) from exc


@router.put("/projects/{project_id}")
def update_project(project_id: str, payload: dict[str, Any], projects: ProjectService = Depends(get_project_service)) -> dict:
    try:
        current = projects.get_project(project_id)
        merged = current.model_dump()
        merged.update(payload)
        project = projects.update_project(project_id, ProjectCreate(**merged))
        return {"ok": True, "project": _project_payload(project, projects.task_count(project.id))}
    except KeyError as exc:
        raise not_found(exc) from exc


@router.delete("/projects/{project_id}")
def delete_project(project_id: str, projects: ProjectService = Depends(get_project_service)) -> dict:
    projects.delete_project(project_id)
    return {"ok": True}


@router.put("/tasks/reorder")
def reorder_tasks(payload: dict[str, Any], tasks: TaskService = Depends(get_task_service)) -> dict:
    columns = payload.get("columns") if "columns" in payload else payload
    if not isinstance(columns, dict):
        return {"ok": False, "updated": 0}
    updated = tasks.reorder({str(status): [str(task_id) for task_id in task_ids] for status, task_ids in columns.items()})
    return {"ok": True, "updated": updated}


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
    return [_schedule_payload_with_status(schedule, schedules) for schedule in schedules.list(agent)]


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
    return {"ok": True, "schedule": _schedule_payload_with_status(schedule, schedules)}


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
    return {"ok": True, "schedule": _schedule_payload_with_status(schedule, schedules)}


@router.delete("/schedules/{schedule_id}")
def delete_schedule(schedule_id: str, schedules: ScheduleService = Depends(get_schedule_service)) -> dict:
    schedules.delete(schedule_id)
    return {"ok": True}


@router.get("/status")
def system_status(
    worker: WorkerService = Depends(get_worker_service),
    heartbeat: HeartbeatService = Depends(get_heartbeat_service),
    settings_service: SettingsService = Depends(get_settings_service),
) -> dict:
    enabled_channels = (settings_service.snapshot().get("channels") or {}).get("enabled") or ["web"]
    return {
        "ok": True,
        "uptime": uptime_seconds(),
        "server": {"running": True, "port": 3777},
        "channels": {
            channel: {"running": channel == "web", "managed": channel == "web"}
            for channel in enabled_channels
        },
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
async def worker_start(worker: WorkerService = Depends(get_worker_service)) -> dict:
    started = worker.start()
    return {"ok": True, "started": started, "worker": worker.snapshot()}


@router.post("/worker/stop")
async def worker_stop(worker: WorkerService = Depends(get_worker_service)) -> dict:
    stopped = await worker.stop()
    return {"ok": True, "stopped": stopped, "worker": worker.snapshot()}


@router.post("/worker/pause")
async def worker_pause(worker: WorkerService = Depends(get_worker_service)) -> dict:
    paused = worker.pause()
    return {"ok": True, "paused": paused, "worker": worker.snapshot()}


@router.post("/worker/resume")
async def worker_resume(worker: WorkerService = Depends(get_worker_service)) -> dict:
    resumed = worker.resume()
    return {"ok": True, "resumed": resumed, "worker": worker.snapshot()}


@router.post("/worker/restart")
async def worker_restart(worker: WorkerService = Depends(get_worker_service)) -> dict:
    await worker.restart()
    return {"ok": True, "worker": worker.snapshot()}


@router.post("/worker/tick")
async def worker_tick(force: bool = False, worker: WorkerService = Depends(get_worker_service)) -> dict:
    processed = await worker.process_once(force=force)
    return {"ok": True, "processed": processed, "worker": worker.snapshot()}


@router.post("/worker/maintenance")
def worker_maintenance(
    older_than_ms: int = 86_400_000,
    stale_threshold_seconds: int | None = None,
    prune_chats: bool = False,
    worker: WorkerService = Depends(get_worker_service),
) -> dict:
    return {"ok": True, **worker.maintenance(older_than_ms, stale_threshold_seconds, prune_chats)}


@router.post("/services/apply")
async def apply_services(
    worker: WorkerService = Depends(get_worker_service),
    settings_service: SettingsService = Depends(get_settings_service),
) -> dict:
    worker.start()
    enabled_channels = (settings_service.snapshot().get("channels") or {}).get("enabled") or ["web"]
    started = ["worker"]
    errors = []
    for channel in enabled_channels:
        if channel == "web":
            started.append("web")
        else:
            errors.append(f"{channel}: channel process manager is not implemented")
    return {"ok": True, "started": started, "heartbeat": True, "errors": errors or None}


@router.post("/services/restart")
async def restart_service(worker: WorkerService = Depends(get_worker_service)) -> dict:
    await worker.restart()
    return {"ok": True, "action": "worker-restart"}


@router.post("/services/channel/{channel_id}/{action}")
def channel_action(channel_id: str, action: str) -> dict:
    if channel_id == "web" and action in {"start", "restart"}:
        return {"ok": True, "channel": channel_id, "action": "started"}
    if channel_id == "web" and action == "stop":
        return {"ok": False, "channel": channel_id, "error": "web channel is built into the API server"}
    return {"ok": False, "channel": channel_id, "error": "channel process manager is not implemented"}


@router.get("/pairing")
def get_pairings(channels: ChannelService = Depends(get_channel_service)) -> dict:
    return channels.pairing_state()


@router.post("/pairing/approve")
def approve_pairing(payload: dict[str, str], channels: ChannelService = Depends(get_channel_service)) -> dict:
    return channels.approve(payload.get("code"))


@router.delete("/pairing/{channel}/{sender_id}")
def revoke_pairing(channel: str, sender_id: str, channels: ChannelService = Depends(get_channel_service)) -> dict:
    return {"ok": channels.revoke(channel, sender_id)}


@router.delete("/pairing/pending/{code}")
def dismiss_pairing(code: str, channels: ChannelService = Depends(get_channel_service)) -> dict:
    return {"ok": channels.dismiss_pending(code)}


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
