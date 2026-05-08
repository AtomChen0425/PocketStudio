from fastapi import APIRouter, Depends, Query

from pocketStudio.core.dependencies import get_chat_service, get_queue_service, get_team_service
from pocketStudio.models import ChatMessage, ChatMessageCreate, MessageCreate
from pocketStudio.services.chat_service import ChatService
from pocketStudio.services.queue_service import QueueService
from pocketStudio.services.team_service import TeamService

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
    queue: QueueService = Depends(get_queue_service),
    teams: TeamService = Depends(get_team_service),
) -> ChatMessage:
    sender = "user" if payload.sender == "api" else payload.sender
    chat_payload = ChatMessageCreate(sender=sender, message=payload.message)
    message = service.post(team_id, chat_payload)
    if sender != "user":
        return message
    try:
        team = teams.get(team_id)
    except KeyError:
        return message
    chat_content = f"[Chat room #{team_id} - @user]:\n{payload.message}"
    for agent_id in team.agent_ids:
        queue.enqueue(
            MessageCreate(
                target=f"@agent:{agent_id}",
                content=chat_content,
                sender="user",
                metadata={
                    "channel": "chatroom",
                    "teamId": team_id,
                    "fromAgent": "user",
                    "toAgent": agent_id,
                    "kind": "chatroom",
                    "parentMessageId": f"chat:{message.id}",
                },
            )
        )
    return message
