import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from pocketStudio.core.config import Settings, get_settings
from pocketStudio.core.dependencies import get_event_service, get_provider_registry
from pocketStudio.models import Event
from pocketStudio.providers.registry import ProviderRegistry
from pocketStudio.services.event_service import EventService

router = APIRouter(tags=["system"])


@router.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict:
    return {"status": "ok", "app": settings.app_name}


@router.get("/providers", response_model=list[str])
def providers(registry: ProviderRegistry = Depends(get_provider_registry)) -> list[str]:
    return registry.list_names()


@router.get("/events", response_model=list[Event])
def events(
    limit: int = Query(default=100, ge=1, le=500),
    since: int = Query(default=0, ge=0),
    service: EventService = Depends(get_event_service),
) -> list[Event]:
    return service.list(limit=limit, since=since)


def _tinyoffice_event(event: Event) -> tuple[str, dict]:
    payload = event.payload
    timestamp = int(__import__("datetime").datetime.fromisoformat(event.created_at.replace("Z", "+00:00")).timestamp() * 1000)
    if event.type == "message.queued":
        return "message:incoming", {
            "type": "message:incoming",
            "timestamp": timestamp,
            "messageId": str(payload.get("message_id", "")),
            "message": payload.get("content", ""),
            "sender": "Web",
        }
    if event.type == "agent.started":
        return "agent:invoke", {
            "type": "agent:invoke",
            "timestamp": timestamp,
            "agentId": payload.get("agent_id", ""),
        }
    if event.type == "agent.completed":
        return "agent:response", {
            "type": "agent:response",
            "timestamp": timestamp,
            "agentId": payload.get("agent_id", ""),
            "content": payload.get("content", "Completed"),
        }
    if event.type == "message.done":
        return "message:done", {
            "type": "message:done",
            "timestamp": timestamp,
            "messageId": str(payload.get("message_id", "")),
        }
    return event.type.replace(".", ":"), {"type": event.type.replace(".", ":"), "timestamp": timestamp, **payload}


@router.get("/events/stream", include_in_schema=False)
async def event_stream(service: EventService = Depends(get_event_service)) -> StreamingResponse:
    async def stream() -> AsyncIterator[str]:
        last_id = 0
        while True:
            events = list(reversed(service.list(limit=100, since=last_id)))
            for event in events:
                last_id = max(last_id, event.id)
                event_name, data = _tinyoffice_event(event)
                yield f"event: {event_name}\ndata: {json.dumps(data)}\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(stream(), media_type="text/event-stream")
