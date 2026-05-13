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
        dead_item = next(item for item in dead_response.json() if item["id"] == message_id)
        assert dead_item["data"]["messageId"] == str(message_id)
        assert dead_item["data"]["target"] == message_response.json()["target"]
        assert dead_item["failedReason"]
        assert dead_item["attemptsMade"] >= 1
        assert dead_item["timestamp"] > 0

        agent_status = client.get("/api/queue/agents")
        assert agent_status.status_code == 200
        assert any(item["pending"] >= 0 for item in agent_status.json())

        queue_status = client.get("/api/queue/status")
        assert queue_status.status_code == 200
        assert {"incoming", "queued", "processing", "completed", "dead", "failed", "outgoing", "responsesPending"} <= set(queue_status.json())
        assert queue_status.json()["dead"] >= 1

        retry_response = client.post(f"/api/queue/dead/{message_id}/retry")
        assert retry_response.status_code == 200
        assert retry_response.json()["ok"] is True
        assert client.get(f"/api/queue/{message_id}").json()["status"] == "queued"

        for _ in range(6):
            client.post(f"/api/messages/{message_id}/process")

        delete_response = client.delete(f"/api/queue/dead/{message_id}")
        assert delete_response.status_code == 200
        assert delete_response.json()["ok"] is True


def test_dead_letter_retry_delete_return_404_for_missing_message() -> None:
    with TestClient(app) as client:
        retry_response = client.post("/api/queue/dead/99999999/retry")
        delete_response = client.delete("/api/queue/dead/99999999")

        assert retry_response.status_code == 404
        assert "dead message" in retry_response.json()["detail"]
        assert delete_response.status_code == 404
        assert "dead message" in delete_response.json()["detail"]


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


def test_done_messages_are_not_reprocessed_and_failed_messages_can_retry() -> None:
    with TestClient(app) as client:
        client.post("/api/worker/stop")
        agent_id = f"queue-agent-{uuid.uuid4().hex[:8]}"
        client.post("/api/agents", json={"id": agent_id, "name": "Queue Agent", "role": "Runs", "provider": "local"})
        message_id = client.post(
            "/api/messages",
            json={"target": f"@agent:{agent_id}", "content": "run once", "sender": "test"},
        ).json()["id"]

        first_process = client.post(f"/api/messages/{message_id}/process")
        second_process = client.post(f"/api/messages/{message_id}/process")

        assert first_process.status_code == 200
        assert second_process.status_code == 422
        assert "not processable" in second_process.json()["detail"]

        failed_id = client.post(
            "/api/messages",
            json={"target": f"@agent:missing-{uuid.uuid4().hex[:8]}", "content": "fail once", "sender": "test"},
        ).json()["id"]
        failed_process = client.post(f"/api/messages/{failed_id}/process")
        assert failed_process.status_code == 404
        assert client.get(f"/api/queue/{failed_id}").json()["status"] == "failed"

        retry_response = client.post(f"/api/queue/{failed_id}/retry")
        assert retry_response.status_code == 200
        retried = retry_response.json()
        assert retried["status"] == "queued"
        assert retried["attempts"] == 0


def test_processing_payload_uses_running_timestamp_and_metadata() -> None:
    settings = Settings(pocketStudio_home=Path(".pytest-local") / f"processing-home-{uuid.uuid4().hex[:8]}")
    db = Database(settings.database_path)
    db.initialize()
    queue = QueueService(db, EventService(db, settings), settings)
    message = queue.enqueue(
        MessageCreate(
            target="@agent:runner",
            content="still running",
            sender="test",
            metadata={"channel": "cli", "senderId": "tester-1"},
        )
    )
    db.execute(
        """
        UPDATE messages
        SET status = 'running', attempts = 2, updated_at = datetime('now', '-1 minute')
        WHERE id = ?
        """,
        (message.id,),
    )

    payload = queue.processing_payloads()[0]

    assert payload["messageId"] == str(message.id)
    assert payload["agent"] == "runner"
    assert payload["channel"] == "cli"
    assert payload["senderId"] == "tester-1"
    assert payload["attempts"] == 2
    assert payload["duration"] >= 0


def test_queue_diagnostics_reports_backlog_and_stale_processing() -> None:
    settings = Settings(pocketStudio_home=Path(".pytest-local") / f"diagnostics-home-{uuid.uuid4().hex[:8]}")
    db = Database(settings.database_path)
    db.initialize()
    queue = QueueService(db, EventService(db, settings), settings)
    queued = queue.enqueue(
        MessageCreate(
            target="@agent:queued",
            content="queued backlog",
            sender="test",
            metadata={"channel": "diagnostics"},
        )
    )
    running = queue.enqueue(MessageCreate(target="@agent:runner", content="stale runner", sender="test"))
    db.execute(
        """
        UPDATE messages
        SET status = 'running', attempts = 1, updated_at = datetime('now', '-20 minutes')
        WHERE id = ?
        """,
        (running.id,),
    )

    diagnostics = queue.diagnostics(stale_threshold_seconds=1)

    assert diagnostics["status"]["queued"] >= 1
    assert diagnostics["oldestQueued"]["id"] == queued.id
    assert diagnostics["oldestQueued"]["channel"] == "diagnostics"
    assert diagnostics["oldestQueuedAgeMs"] >= 0
    assert diagnostics["oldestRunning"]["id"] == running.id
    assert diagnostics["oldestRunningAgeMs"] >= 0
    assert diagnostics["staleProcessing"] == 1
    assert diagnostics["maxAttempts"] == settings.queue_max_attempts


def test_queue_diagnostics_api_and_worker_snapshot_include_runtime_details() -> None:
    agent_id = f"diagnostics-agent-{uuid.uuid4().hex[:8]}"

    with TestClient(app) as client:
        client.post("/api/worker/stop")
        client.post("/api/agents", json={"id": agent_id, "name": "Diagnostics Agent", "role": "Reports queue state", "provider": "local"})
        message_id = client.post(
            "/api/messages",
            json={"target": f"@agent:{agent_id}", "content": "inspect backlog", "sender": "test"},
        ).json()["id"]

        diagnostics = client.get("/api/queue/diagnostics?stale_threshold_seconds=1")
        worker = client.get("/api/worker/status")

        assert diagnostics.status_code == 200
        assert diagnostics.json()["status"]["queued"] >= 1
        assert diagnostics.json()["oldestQueued"]["id"] <= message_id
        assert diagnostics.json()["oldestQueuedAgeMs"] >= 0
        assert worker.status_code == 200
        assert "queueDiagnostics" in worker.json()
        assert worker.json()["queueDiagnostics"]["status"]["queued"] >= 1
