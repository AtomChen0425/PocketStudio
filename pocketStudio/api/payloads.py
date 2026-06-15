from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from pocketStudio.models import Agent, Project, Schedule, Task, Team
from pocketStudio.services.schedule_service import ScheduleService


def timestamp_millis(value: str | int | float | None) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    if not value:
        return int(time.time() * 1000)
    try:
        return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)
    except ValueError:
        return int(time.time() * 1000)


def agent_config(agent: Agent) -> dict[str, Any]:
    return {
        "name": agent.name,
        "provider": agent.provider,
        "model": agent.model or "",
        "model_provider": agent.model_provider,
        "api_key": agent.api_key,
        "working_directory": str(agent.workspace),
        "system_prompt": agent.system_prompt or agent.role,
        "heartbeat": {"enabled": agent.heartbeat_enabled, "interval": agent.heartbeat_interval},
    }


def team_config(team: Team) -> dict[str, Any]:
    return {
        "name": team.name,
        "agents": team.agent_ids,
        "leader_agent": team.leader_agent or (team.agent_ids[0] if team.agent_ids else ""),
        "max_rounds": team.max_rounds,
        "stop_when_idle": team.stop_when_idle,
    }


def task_payload(task: Task, comment_count: int = 0) -> dict[str, Any]:
    payload = task.model_dump(mode="json")
    payload["assigneeType"] = task.assignee_type or ("agent" if task.assignee else "")
    payload["projectId"] = task.project_id
    payload["sortOrder"] = task.position
    payload["commentCount"] = comment_count
    return payload


def task_response(task: Task, comment_count: int = 0) -> dict[str, Any]:
    payload = task_payload(task, comment_count)
    return {**payload, "ok": True, "task": payload}


def project_payload(project: Project, task_count: int | None = None) -> dict[str, Any]:
    payload = {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "prefix": project.prefix,
        "color": project.color,
        "workspace": project.workspace,
        "status": project.status,
        "createdAt": timestamp_millis(project.created_at),
        "updatedAt": timestamp_millis(project.updated_at),
    }
    if task_count is not None:
        payload["taskCount"] = task_count
    return payload


def schedule_payload(schedule: Schedule) -> dict[str, Any]:
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


def schedule_payload_with_status(schedule: Schedule, schedules: ScheduleService) -> dict[str, Any]:
    payload = schedule_payload(schedule)
    payload.update(schedules.schedule_status(schedule))
    return payload
