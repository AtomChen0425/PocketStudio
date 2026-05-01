from fastapi import APIRouter, Depends

from pocketStudio.api.errors import not_found
from pocketStudio.core.dependencies import get_task_service
from pocketStudio.models import Task, TaskCreate
from pocketStudio.services.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=list[Task])
def list_tasks(service: TaskService = Depends(get_task_service)) -> list[Task]:
    return service.list()


@router.post("", response_model=Task)
def create_task(payload: TaskCreate, service: TaskService = Depends(get_task_service)) -> Task:
    return service.create(payload)


@router.get("/{task_id}", response_model=Task)
def get_task(task_id: int, service: TaskService = Depends(get_task_service)) -> Task:
    try:
        return service.get(task_id)
    except KeyError as exc:
        raise not_found(exc) from exc


@router.put("/{task_id}", response_model=Task)
def update_task(task_id: int, payload: TaskCreate, service: TaskService = Depends(get_task_service)) -> Task:
    try:
        return service.update(task_id, payload)
    except KeyError as exc:
        raise not_found(exc) from exc


@router.patch("/{task_id}/status/{status}", response_model=Task)
def update_task_status(task_id: int, status: str, service: TaskService = Depends(get_task_service)) -> Task:
    try:
        return service.update_status(task_id, status)
    except KeyError as exc:
        raise not_found(exc) from exc


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: int, service: TaskService = Depends(get_task_service)) -> None:
    service.delete(task_id)
