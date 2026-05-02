from fastapi import APIRouter, Depends, Query

from pocketStudio.core.dependencies import get_chat_service
from pocketStudio.models import ChatMessage, ChatMessageCreate
from pocketStudio.services.chat_service import ChatService

router = APIRouter(prefix="/chatroom", tags=["chatroom"])


@router.get("/{team_id}", response_model=list[ChatMessage])
def list_chat(
    team_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    since: int = Query(default=0, ge=0),
    sender: str | None = None,
    q: str | None = None,
    service: ChatService = Depends(get_chat_service),
) -> list[ChatMessage]:
    return service.list(team_id=team_id, limit=limit, since=since, sender=sender, query=q)


@router.post("/{team_id}", response_model=ChatMessage)
def post_chat(
    team_id: str,
    payload: ChatMessageCreate,
    service: ChatService = Depends(get_chat_service),
) -> ChatMessage:
    return service.post(team_id, payload)
