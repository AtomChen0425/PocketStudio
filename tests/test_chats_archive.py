from uuid import uuid4

from fastapi.testclient import TestClient

from pocketStudio.main import app


def test_chat_archives_list_and_read_team_history() -> None:
    team_id = f"chat-team-{uuid4().hex[:8]}"

    with TestClient(app) as client:
        posted = client.post(f"/api/chatroom/{team_id}", json={"sender": "tester", "message": "hello archive"})
        assert posted.status_code == 200
        client.post(f"/api/chatroom/{team_id}", json={"sender": "agent", "message": "second archived note"})

        archives = client.get("/api/chats")
        assert archives.status_code == 200
        archive = next(item for item in archives.json() if item["teamId"] == team_id)
        assert archive["count"] >= 1
        assert archive["file"] == f"{team_id}.sqlite"
        assert archive["lastSender"] == "agent"
        assert archive["lastMessage"] == "second archived note"

        detail = client.get(f"/api/chats/{team_id}")
        assert detail.status_code == 200
        assert detail.json()["teamId"] == team_id
        assert any(message["message"] == "hello archive" for message in detail.json()["messages"])

        filtered = client.get(f"/api/chats/{team_id}?sender=tester&q=hello")
        assert filtered.status_code == 200
        assert [message["message"] for message in filtered.json()["messages"]] == ["hello archive"]


def test_worker_maintenance_can_prune_chat_archives() -> None:
    team_id = f"prune-chat-{uuid4().hex[:8]}"

    with TestClient(app) as client:
        client.post(f"/api/chatroom/{team_id}", json={"sender": "tester", "message": "old chat"})
        pruned = client.post("/api/worker/maintenance?older_than_ms=0&prune_chats=true")

        assert pruned.status_code == 200
        assert pruned.json()["prunedChatMessages"] >= 1
        detail = client.get(f"/api/chats/{team_id}")
        assert detail.status_code == 200
        assert detail.json()["messages"] == []
