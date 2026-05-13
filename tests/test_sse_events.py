from pathlib import Path
from uuid import uuid4

from pocketStudio.core.config import Settings
from pocketStudio.core.database import Database
from pocketStudio.services.event_service import EventService


def build_events() -> EventService:
    home = Path(".pytest-local") / f"events-home-{uuid4().hex[:8]}"
    settings = Settings(pocketStudio_home=home)
    db = Database(settings.database_path)
    db.initialize()
    return EventService(db, settings)


def test_office_event_maps_queue_agent_response_and_team_events() -> None:
    events = build_events()

    queued = events.office_event(
        events.emit("message.queued", {"message_id": 1, "target": "@agent:a", "content": "hello", "sender": "Web"})
    )
    running = events.office_event(events.emit("message.running", {"message_id": 1}))
    failed = events.office_event(events.emit("message.failed", {"message_id": 1, "status": "failed", "error": "boom"}))
    started = events.office_event(events.emit("agent.started", {"agent_id": "a", "provider": "local"}))
    process = events.office_event(events.emit("agent.process", {"agent_id": "a", "process": {"pid": 123}}))
    progress = events.office_event(
        events.emit(
            "agent.progress",
            {
                "agent_id": "a",
                "provider": "codex",
                "providerEventType": "item.started",
                "summary": "running command",
                "content": "stdout",
                "tool": "shell",
                "raw": {"type": "item.started"},
            },
        )
    )
    completed = events.office_event(events.emit("agent.completed", {"agent_id": "a", "content": "done"}))
    response = events.office_event(
        events.emit(
            "response.queued",
            {"response_id": 7, "message_id": "1-0", "channel": "web", "sender": "Web", "sender_id": "web-1", "agent": "a", "status": "pending"},
        )
    )
    chatroom = events.office_event(events.emit("team.chatroom", {"team_id": "dev", "from_agent": "a", "delivered": 2}))

    assert queued[0] == "message:incoming"
    assert queued[1]["messageId"] == "1"
    assert queued[1]["target"] == "@agent:a"
    assert running[0] == "message:processing"
    assert failed[0] == "message:failed"
    assert failed[1]["error"] == "boom"
    assert started[0] == "agent:invoke"
    assert process[0] == "agent:progress"
    assert process[1]["process"]["pid"] == 123
    assert progress[0] == "agent:progress"
    assert progress[1]["provider"] == "codex"
    assert progress[1]["providerEventType"] == "item.started"
    assert progress[1]["summary"] == "running command"
    assert progress[1]["content"] == "stdout"
    assert progress[1]["tool"] == "shell"
    assert completed[0] == "agent:response"
    assert response[0] == "response:queued"
    assert response[1]["senderId"] == "web-1"
    assert response[1]["agent"] == "a"
    assert chatroom[0] == "team:chatroom"
    assert chatroom[1]["delivered"] == 2
    assert all("timestamp" in item[1] and "eventId" in item[1] for item in [queued, running, failed, started, process, completed])


def test_event_listeners_can_be_added_and_removed() -> None:
    events = build_events()
    seen = []

    def listener(event):
        seen.append(event.type)

    events.add_listener(listener)
    events.emit("message.queued", {"message_id": 1})
    events.remove_listener(listener)
    events.emit("message.done", {"message_id": 1})

    assert seen == ["message.queued"]
