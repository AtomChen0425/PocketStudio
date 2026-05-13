from typing import Any

from fastapi import APIRouter, Depends

from pocketStudio.api.errors import not_found
from pocketStudio.core.dependencies import get_project_service, get_task_service
from pocketStudio.models import Task, TaskCreate
from pocketStudio.services.project_service import ProjectService
from pocketStudio.services.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=list[Task])
def list_tasks(
    projectId: str | None = None,
    status: str | None = None,
    assignee: str | None = None,
    q: str | None = None,
    service: TaskService = Depends(get_task_service),
) -> list[Task]:
    return service.list(project_id=projectId, status=status, assignee=assignee, query=q)


@router.post("")
def create_task(
    payload: TaskCreate,
    service: TaskService = Depends(get_task_service),
    projects: ProjectService = Depends(get_project_service),
) -> dict:
    return _task_response(service.create(payload), projects)


@router.get("/{task_id}")
def get_task(
    task_id: int,
    service: TaskService = Depends(get_task_service),
    projects: ProjectService = Depends(get_project_service),
) -> dict:
    try:
        return _task_payload(service.get(task_id), projects)
    except KeyError as exc:
        raise not_found(exc) from exc


@router.put("/{task_id}")
def update_task(
    task_id: int,
    payload: dict[str, Any],
    service: TaskService = Depends(get_task_service),
    projects: ProjectService = Depends(get_project_service),
) -> dict:
    try:
        current = service.get(task_id)
        merged = current.model_dump()
        if "assigneeType" in payload and "assignee_type" not in payload:
            payload["assignee_type"] = payload.pop("assigneeType")
        if "projectId" in payload and "project_id" not in payload:
            payload["project_id"] = payload.pop("projectId")
        merged.update(payload)
        return _task_response(service.update(task_id, TaskCreate(**merged)), projects)
    except KeyError as exc:
        raise not_found(exc) from exc


@router.patch("/{task_id}/status/{status}", response_model=Task)
def update_task_status(task_id: int, status: str, service: TaskService = Depends(get_task_service)) -> Task:
    try:
        return service.update_status(task_id, status)
    except KeyError as exc:
        raise not_found(exc) from exc


@router.delete("/{task_id}")
def delete_task(task_id: int, service: TaskService = Depends(get_task_service)) -> dict:
    try:
        service.delete(task_id)
    except KeyError as exc:
        raise not_found(exc) from exc
    return {"ok": True}


def _task_response(task: Task, projects: ProjectService) -> dict:
    payload = _task_payload(task, projects)
    return {**payload, "ok": True, "task": payload}


def _task_payload(task: Task, projects: ProjectService) -> dict:
    payload = task.model_dump(mode="json")
    payload["assigneeType"] = task.assignee_type or ("agent" if task.assignee else "")
    payload["projectId"] = task.project_id
    payload["sortOrder"] = task.position
    payload["commentCount"] = projects.comment_count(task.id)
    return payload
