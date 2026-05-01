from fastapi import APIRouter, Depends

from pocketStudio.api.errors import not_found
from pocketStudio.core.dependencies import get_agent_service
from pocketStudio.models import Agent, AgentCreate
from pocketStudio.services.agent_service import AgentService

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("", response_model=list[Agent])
def list_agents(service: AgentService = Depends(get_agent_service)) -> list[Agent]:
    return service.list()


@router.post("", response_model=Agent)
def upsert_agent(payload: AgentCreate, service: AgentService = Depends(get_agent_service)) -> Agent:
    return service.create(payload)


@router.get("/{agent_id}", response_model=Agent)
def get_agent(agent_id: str, service: AgentService = Depends(get_agent_service)) -> Agent:
    try:
        return service.get(agent_id)
    except KeyError as exc:
        raise not_found(exc) from exc


@router.delete("/{agent_id}", status_code=204)
def delete_agent(agent_id: str, service: AgentService = Depends(get_agent_service)) -> None:
    service.delete(agent_id)

