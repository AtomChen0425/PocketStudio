from fastapi import APIRouter, Depends

from pocketStudio.api.errors import not_found
from pocketStudio.core.dependencies import get_team_service
from pocketStudio.models import Team, TeamCreate
from pocketStudio.services.team_service import TeamService

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("", response_model=list[Team])
def list_teams(service: TeamService = Depends(get_team_service)) -> list[Team]:
    return service.list()


@router.post("", response_model=Team)
def upsert_team(payload: TeamCreate, service: TeamService = Depends(get_team_service)) -> Team:
    return service.create(payload)


@router.get("/{team_id}", response_model=Team)
def get_team(team_id: str, service: TeamService = Depends(get_team_service)) -> Team:
    try:
        return service.get(team_id)
    except KeyError as exc:
        raise not_found(exc) from exc


@router.post("/{team_id}/members/{agent_id}", response_model=Team)
def add_team_member(team_id: str, agent_id: str, service: TeamService = Depends(get_team_service)) -> Team:
    try:
        return service.add_member(team_id, agent_id)
    except KeyError as exc:
        raise not_found(exc) from exc


@router.delete("/{team_id}/members/{agent_id}", response_model=Team)
def remove_team_member(team_id: str, agent_id: str, service: TeamService = Depends(get_team_service)) -> Team:
    try:
        return service.remove_member(team_id, agent_id)
    except KeyError as exc:
        raise not_found(exc) from exc


@router.put("/{team_id}/leader/{agent_id}", response_model=Team)
def set_team_leader(team_id: str, agent_id: str, service: TeamService = Depends(get_team_service)) -> Team:
    try:
        return service.set_leader(team_id, agent_id)
    except KeyError as exc:
        raise not_found(exc) from exc


@router.delete("/{team_id}", status_code=204)
def delete_team(team_id: str, service: TeamService = Depends(get_team_service)) -> None:
    service.delete(team_id)
