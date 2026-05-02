from uuid import uuid4

from fastapi.testclient import TestClient

from pocketStudio.main import app


def test_chat_archives_list_and_read_team_history() -> None:
    team_id = f"chat-team-{uuid4().hex[:8]}"

    with TestClient(app) as client:
        posted = client.post(f"/api/chatroom/{team_id}", json={"sender": "tester", "message": "hello archive"})
        assert posted.status_code == 200

        archives = client.get("/api/chats")
        assert archives.status_code == 200
        archive = next(item for item in archives.json() if item["teamId"] == team_id)
        assert archive["count"] >= 1
        assert archive["file"] == f"{team_id}.sqlite"

        detail = client.get(f"/api/chats/{team_id}")
        assert detail.status_code == 200
        assert detail.json()["teamId"] == team_id
        assert any(message["message"] == "hello archive" for message in detail.json()["messages"])
