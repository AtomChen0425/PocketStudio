from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from pocketStudio.core.config import Settings
from pocketStudio.core.database import Database
from pocketStudio.main import app
from pocketStudio.services.event_service import EventService


def test_event_service_writes_file_logs() -> None:
    home = Path(".pytest-local") / f"logs-home-{uuid4().hex[:8]}"
    settings = Settings(pocketStudio_home=home)
    db = Database(settings.database_path)
    db.initialize()
    events = EventService(db, settings)

    events.emit("test.event", {"value": 42})

    assert settings.log_file_path.exists()
    lines = events.log_lines()
    assert len(lines) == 1
    assert "test.event" in lines[0]
    assert '"value": 42' in lines[0]


def test_logs_route_returns_file_backed_lines() -> None:
    with TestClient(app) as client:
        agent_id = f"log-agent-{uuid4().hex[:8]}"
        client.post("/api/agents", json={"id": agent_id, "name": "Logger", "role": "Logs", "provider": "local"})

        response = client.get("/api/logs?limit=20")

        assert response.status_code == 200
        assert any("message.queued" in line or "agent" in line for line in response.json()["lines"])
