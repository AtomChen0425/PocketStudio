import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from pocketStudio.core.config import Settings
from pocketStudio.core.database import Database
from pocketStudio.core.dependencies import get_database
from pocketStudio.main import app
from pocketStudio.models import MessageCreate
from pocketStudio.services.event_service import EventService
from pocketStudio.services.queue_service import QueueService


def test_dead_letter_retry_delete_and_agent_status() -> None:
    with TestClient(app) as client:
        client.post("/api/worker/stop")
        message_response = client.post(
            "/api/messages",
            json={"target": f"@agent:missing-{uuid.uuid4().hex[:8]}", "content": "fail please", "sender": "test"},
        )
        assert message_response.status_code == 200
        message_id = message_response.json()["id"]

        for _ in range(6):
            client.post(f"/api/messages/{message_id}/process")

        dead_response = client.get("/api/queue/dead")
        assert dead_response.status_code == 200
        assert any(item["id"] == message_id for item in dead_response.json())

        agent_status = client.get("/api/queue/agents")
        assert agent_status.status_code == 200
        assert any(item["pending"] >= 0 for item in agent_status.json())

        retry_response = client.post(f"/api/queue/dead/{message_id}/retry")
        assert retry_response.status_code == 200
        assert retry_response.json()["ok"] is True
        assert client.get(f"/api/queue/{message_id}").json()["status"] == "queued"

        for _ in range(6):
            client.post(f"/api/messages/{message_id}/process")

        delete_response = client.delete(f"/api/queue/dead/{message_id}")
        assert delete_response.status_code == 200
        assert delete_response.json()["ok"] is True


def test_recover_stale_running_message() -> None:
    settings = Settings(pocketStudio_home=Path(".pytest-local") / f"stale-home-{uuid.uuid4().hex[:8]}")
    db = Database(settings.database_path)
    db.initialize()
    queue = QueueService(db, EventService(db, settings), settings)
    message = queue.enqueue(MessageCreate(target="@agent:stale", content="recover me", sender="test"))
    db.execute(
        """
        UPDATE messages
        SET status = 'running', attempts = 1, updated_at = datetime('now', '-20 minutes')
        WHERE id = ?
        """,
        (message.id,),
    )

    assert queue.recover_stale_messages(threshold_seconds=1) == 1
    assert queue.get(message.id).status == "failed"
