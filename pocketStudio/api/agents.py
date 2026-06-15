from fastapi import APIRouter, Depends

from pocketStudio.api.errors import not_found
from pocketStudio.api.payloads import agent_config
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


@router.put("/{agent_id}")
def update_agent(agent_id: str, payload: dict, service: AgentService = Depends(get_agent_service)) -> dict:
    try:
        current = service.get(agent_id)
        is_new = False
    except KeyError:
        current = None
        is_new = True

    heartbeat = payload.get("heartbeat") or {}
    system_prompt = payload.get("system_prompt")
    role = payload.get("role") or system_prompt or (current.role if current else payload.get("name") or agent_id)
    agent = service.create(
        AgentCreate(
            id=agent_id,
            name=payload.get("name") or (current.name if current else agent_id),
            role=role,
            system_prompt=system_prompt if system_prompt is not None else (current.system_prompt if current else ""),
            provider=payload.get("provider") or (current.provider if current else "local"),
            model=payload.get("model") if "model" in payload else (current.model if current else None),
            model_provider=payload.get("model_provider")
            if "model_provider" in payload
            else (current.model_provider if current else ""),
            api_key=payload.get("api_key") if "api_key" in payload else (current.api_key if current else ""),
            workspace=payload.get("working_directory") or payload.get("workspace") or (current.workspace if current else None),
            enabled=payload.get("enabled", current.enabled if current else True),
            heartbeat_enabled=heartbeat.get("enabled", payload.get("heartbeat_enabled", current.heartbeat_enabled if current else True)),
            heartbeat_interval=heartbeat.get(
                "interval",
                payload.get("heartbeat_interval", current.heartbeat_interval if current else None),
            ),
        )
    )
    if system_prompt is not None:
        service.save_system_prompt_file(agent_id, system_prompt)
    return {"ok": True, "agent": agent_config(agent), "provisioned": is_new}


@router.get("/{agent_id}", response_model=Agent)
def get_agent(agent_id: str, service: AgentService = Depends(get_agent_service)) -> Agent:
    try:
        return service.get(agent_id)
    except KeyError as exc:
        raise not_found(exc) from exc


@router.delete("/{agent_id}")
def delete_agent(agent_id: str, service: AgentService = Depends(get_agent_service)) -> dict:
    service.delete(agent_id)
    return {"ok": True}
