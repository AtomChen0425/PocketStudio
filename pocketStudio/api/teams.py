from fastapi import APIRouter, Depends

from pocketStudio.api.errors import not_found
from pocketStudio.core.dependencies import get_chat_service, get_orchestrator, get_team_service
from pocketStudio.models import Team, TeamCreate, TeamDispatchCreate
from pocketStudio.services.chat_service import ChatService
from pocketStudio.services.orchestrator import Orchestrator
from pocketStudio.services.team_service import TeamService

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("", response_model=list[Team])
def list_teams(service: TeamService = Depends(get_team_service)) -> list[Team]:
    return service.list()


@router.post("", response_model=Team)
def upsert_team(payload: TeamCreate, service: TeamService = Depends(get_team_service)) -> Team:
    return service.create(payload)


@router.put("/{team_id}")
def update_team(team_id: str, payload: dict, service: TeamService = Depends(get_team_service)) -> dict:
    try:
        current = service.get(team_id)
    except KeyError as exc:
        raise not_found(exc) from exc
    merged = current.model_dump()
    merged.update(
        {
            "id": team_id,
            "name": payload.get("name", current.name),
            "mode": payload.get("mode", current.mode),
            "agent_ids": payload.get("agent_ids") or payload.get("agents") or current.agent_ids,
            "leader_agent": payload.get("leader_agent") or payload.get("leaderAgent") or current.leader_agent,
            "max_rounds": payload.get("max_rounds") or payload.get("maxRounds") or current.max_rounds,
            "stop_when_idle": payload.get("stop_when_idle", payload.get("stopWhenIdle", current.stop_when_idle)),
        }
    )
    team = service.create(TeamCreate(**merged))
    return {"ok": True, "team": team.model_dump()}


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


@router.post("/{team_id}/dispatch")
def dispatch_team_message(
    team_id: str,
    payload: TeamDispatchCreate,
    chat: ChatService = Depends(get_chat_service),
    orchestrator: Orchestrator = Depends(get_orchestrator),
) -> dict:
    try:
        if payload.chat_message_id is not None:
            existing = chat.get_dispatch(payload.chat_message_id)
            if existing is not None:
                return {
                    "ok": True,
                    "teamId": team_id,
                    "queued": existing["queued_count"],
                    "messageIds": existing["message_ids"],
                    "chatMessageId": existing["chat_message_id"],
                }
        result = orchestrator.dispatch_team_message(
            team_id,
            payload.message,
            sender=payload.sender,
            chat_message_id=payload.chat_message_id,
        )
        if payload.chat_message_id is not None:
            recorded = chat.record_dispatch(
                chat_message_id=payload.chat_message_id,
                team_id=team_id,
                client_message_id=None,
                queued_count=result["queued"],
                message_ids=result["messageIds"],
            )
            return {
                "ok": True,
                "teamId": team_id,
                "queued": recorded["queued_count"],
                "messageIds": recorded["message_ids"],
                "chatMessageId": recorded["chat_message_id"],
            }
        return result
    except KeyError as exc:
        raise not_found(exc) from exc


@router.delete("/{team_id}")
def delete_team(team_id: str, service: TeamService = Depends(get_team_service)) -> dict:
    service.delete(team_id)
    return {"ok": True}
