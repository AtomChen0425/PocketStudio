from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from pocketStudio.api.errors import not_found
from pocketStudio.core.dependencies import get_workflow_service
from pocketStudio.models import TeamWorkflow, TeamWorkflowCreate, TeamWorkflowUpdate, WorkflowDefinition
from pocketStudio.services.workflow_service import WorkflowService

router = APIRouter(prefix="/teams/{team_id}/workflows", tags=["team-workflows"])


@router.get("", response_model=list[TeamWorkflow])
def list_workflows(team_id: str, service: WorkflowService = Depends(get_workflow_service)) -> list[TeamWorkflow]:
    try:
        return service.list(team_id)
    except KeyError as exc:
        raise not_found(exc) from exc


@router.post("", response_model=TeamWorkflow)
def upsert_workflow(
    team_id: str,
    payload: TeamWorkflowCreate,
    service: WorkflowService = Depends(get_workflow_service),
) -> TeamWorkflow:
    try:
        return service.create(team_id, payload)
    except KeyError as exc:
        raise not_found(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/validate")
def validate_workflow(
    team_id: str,
    definition: WorkflowDefinition,
    service: WorkflowService = Depends(get_workflow_service),
) -> dict:
    try:
        return service.validate(team_id, definition)
    except KeyError as exc:
        raise not_found(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/import", response_model=TeamWorkflow)
def import_workflow(
    team_id: str,
    payload: dict[str, Any],
    service: WorkflowService = Depends(get_workflow_service),
) -> TeamWorkflow:
    try:
        return service.import_json(team_id, payload)
    except KeyError as exc:
        raise not_found(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{workflow_id}", response_model=TeamWorkflow)
def get_workflow(
    team_id: str,
    workflow_id: str,
    service: WorkflowService = Depends(get_workflow_service),
) -> TeamWorkflow:
    try:
        return service.get(team_id, workflow_id)
    except KeyError as exc:
        raise not_found(exc) from exc


@router.get("/{workflow_id}/export")
def export_workflow(
    team_id: str,
    workflow_id: str,
    service: WorkflowService = Depends(get_workflow_service),
) -> dict[str, Any]:
    try:
        return service.export_json(team_id, workflow_id)
    except KeyError as exc:
        raise not_found(exc) from exc


@router.put("/{workflow_id}", response_model=TeamWorkflow)
def update_workflow(
    team_id: str,
    workflow_id: str,
    payload: TeamWorkflowUpdate,
    service: WorkflowService = Depends(get_workflow_service),
) -> TeamWorkflow:
    try:
        return service.update(team_id, workflow_id, payload)
    except KeyError as exc:
        raise not_found(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/{workflow_id}")
def delete_workflow(
    team_id: str,
    workflow_id: str,
    service: WorkflowService = Depends(get_workflow_service),
) -> dict:
    service.delete(team_id, workflow_id)
    return {"ok": True}
