from fastapi import APIRouter, Depends, Query

from pocketStudio.core.dependencies import get_chat_service, get_orchestrator
from pocketStudio.models import ChatMessage, ChatMessageCreate
from pocketStudio.services.chat_service import ChatService
from pocketStudio.services.orchestrator import Orchestrator

router = APIRouter(prefix="/chatroom", tags=["chatroom"])


def _chatroom_payload(message: ChatMessage) -> dict:
    payload = message.model_dump()
    payload["from_agent"] = message.sender
    return payload


@router.get("/{team_id}")
def list_chat(
    team_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    since: int = Query(default=0, ge=0),
    sender: str | None = None,
    q: str | None = None,
    service: ChatService = Depends(get_chat_service),
) -> list[dict]:
    return [
        _chatroom_payload(message)
        for message in service.list(team_id=team_id, limit=limit, since=since, sender=sender, query=q)
    ]


@router.post("/{team_id}")
def post_chat(
    team_id: str,
    payload: ChatMessageCreate,
    service: ChatService = Depends(get_chat_service),
) -> dict:
    sender = "user" if payload.sender == "api" else payload.sender
    chat_payload = ChatMessageCreate(sender=sender, message=payload.message, client_message_id=payload.client_message_id)
    return _chatroom_payload(service.post(team_id, chat_payload))


@router.post("/{team_id}/send")
def send_chat(
    team_id: str,
    payload: ChatMessageCreate,
    service: ChatService = Depends(get_chat_service),
    orchestrator: Orchestrator = Depends(get_orchestrator),
) -> dict:
    sender = "user" if payload.sender == "api" else payload.sender
    chat_payload = ChatMessageCreate(
        sender=sender,
        message=payload.message,
        client_message_id=payload.client_message_id,
    )
    with service.db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            message = service.post(team_id, chat_payload, conn=conn, emit_event=False)
            if sender != "user":
                conn.commit()
                service.events.emit("chat.posted", {"team_id": team_id, "message_id": message.id, "sender": sender})
                return {"ok": True, "chatMessage": _chatroom_payload(service.get(message.id, conn=conn)), "dispatch": None}

            dispatch_result: dict | None = None
            existing_dispatch = service.get_dispatch(message.id, conn=conn)
            if existing_dispatch is None:
                dispatch_result = orchestrator.dispatch_team_message(
                    team_id,
                    payload.message,
                    sender=sender,
                    chat_message_id=message.id,
                    conn=conn,
                    emit_event=False,
                )
                existing_dispatch = service.record_dispatch(
                    chat_message_id=message.id,
                    team_id=team_id,
                    client_message_id=payload.client_message_id,
                    queued_count=dispatch_result["queued"],
                    message_ids=dispatch_result["messageIds"],
                    conn=conn,
                )

            final_message = service.get(message.id, conn=conn)
            conn.commit()
            service.events.emit("chat.posted", {"team_id": team_id, "message_id": message.id, "sender": sender})
            if dispatch_result is not None:
                service.events.emit(
                    "team.dispatch",
                    {
                        "team_id": team_id,
                        "from_agent": sender,
                        "delivered": dispatch_result["queued"],
                        "message_id": message.id,
                        "message_ids": dispatch_result["messageIds"],
                    },
                )
                for queued in dispatch_result["queuedMessages"]:
                    service.events.emit(
                        "message.queued",
                        {
                            "message_id": queued["id"],
                            "target": queued["target"],
                            "content": queued["content"],
                            "sender": queued["sender"],
                            "metadata": queued["metadata"],
                        },
                    )
            return {
                "ok": True,
                "chatMessage": _chatroom_payload(final_message),
                "dispatch": {
                    "teamId": team_id,
                    "chatMessageId": existing_dispatch["chat_message_id"],
                    "queued": existing_dispatch["queued_count"],
                    "messageIds": existing_dispatch["message_ids"],
                },
            }
        except Exception:
            conn.rollback()
            raise
