from typing import Any

from fastapi import APIRouter, Depends

from pocketStudio.api.errors import not_found
from pocketStudio.api.payloads import task_payload, task_response
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
    task = service.create(payload)
    return task_response(task, projects.comment_count(task.id))


@router.get("/{task_id}")
def get_task(
    task_id: int,
    service: TaskService = Depends(get_task_service),
    projects: ProjectService = Depends(get_project_service),
) -> dict:
    try:
        task = service.get(task_id)
        return task_payload(task, projects.comment_count(task.id))
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
        task = service.update(task_id, TaskCreate(**merged))
        return task_response(task, projects.comment_count(task.id))
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
