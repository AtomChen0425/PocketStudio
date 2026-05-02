from fastapi import APIRouter, Depends, HTTPException, Query

from pocketStudio.api.errors import not_found
from pocketStudio.core.dependencies import get_orchestrator, get_queue_service
from pocketStudio.models import MessageCreate, MessageStatus, OrchestrationResult, QueueMessage
from pocketStudio.services.orchestrator import Orchestrator
from pocketStudio.services.queue_service import QueueService

router = APIRouter(tags=["messages"])


@router.post("/messages", response_model=QueueMessage)
def enqueue_message(payload: MessageCreate, orchestrator: Orchestrator = Depends(get_orchestrator)) -> QueueMessage:
    return orchestrator.enqueue(payload)


@router.post("/messages/{message_id}/process", response_model=OrchestrationResult)
async def process_message(message_id: int, orchestrator: Orchestrator = Depends(get_orchestrator)) -> OrchestrationResult:
    try:
        return await orchestrator.process_message(message_id)
    except KeyError as exc:
        raise not_found(exc) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/queue/process-next", response_model=OrchestrationResult | None)
async def process_next(orchestrator: Orchestrator = Depends(get_orchestrator)) -> OrchestrationResult | None:
    try:
        return await orchestrator.process_one()
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/queue", response_model=list[QueueMessage])
def list_queue(
    limit: int = Query(default=100, ge=1, le=500),
    status: MessageStatus | None = None,
    service: QueueService = Depends(get_queue_service),
) -> list[QueueMessage]:
    return service.list(limit=limit, status=status)


@router.get("/queue/{message_id}", response_model=QueueMessage)
def get_message(message_id: int, service: QueueService = Depends(get_queue_service)) -> QueueMessage:
    try:
        return service.get(message_id)
    except KeyError as exc:
        raise not_found(exc) from exc


@router.post("/queue/{message_id}/retry", response_model=QueueMessage)
def retry_message(message_id: int, service: QueueService = Depends(get_queue_service)) -> QueueMessage:
    try:
        return service.retry_message(message_id)
    except KeyError as exc:
        raise not_found(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
