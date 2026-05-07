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


@router.get("/events/office")
def office_events(
    limit: int = Query(default=100, ge=1, le=500),
    since: int = Query(default=0, ge=0),
    service: EventService = Depends(get_event_service),
) -> list[dict]:
    mapped = []
    for event in reversed(service.list(limit=limit, since=since)):
        event_name, data = service.office_event(event)
        mapped.append({"event": event_name, "data": data})
    return mapped


def _sse_message(event_name: str, data: dict) -> str:
    return f"event: {event_name}\ndata: {json.dumps(data)}\n\n"


@router.get("/events/stream", include_in_schema=False)
async def event_stream(
    since: int = Query(default=0, ge=0),
    replay: bool = Query(default=True),
    service: EventService = Depends(get_event_service),
) -> StreamingResponse:
    async def stream() -> AsyncIterator[str]:
        queue: asyncio.Queue[Event | None] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def listener(event: Event) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, event)

        service.add_listener(listener)
        try:
            if replay:
                for event in reversed(service.list(limit=100, since=since)):
                    event_name, data = service.office_event(event)
                    yield _sse_message(event_name, data)
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                except TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                if event is None:
                    continue
                event_name, data = service.office_event(event)
                yield _sse_message(event_name, data)
        finally:
            service.remove_listener(listener)

    return StreamingResponse(stream(), media_type="text/event-stream")
