import json
import os
import uuid
import urllib.parse
import urllib.error
import urllib.request

import pytest
from fastapi.testclient import TestClient

from pocketStudio.main import app


class FakeTelegramResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class FakeTelegramApi:
    def __init__(self, updates: list[dict]) -> None:
        self.updates = updates
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, request: urllib.request.Request, timeout: int = 30):
        method = request.full_url.rsplit("/", 1)[-1]
        payload = dict(urllib.parse.parse_qsl((request.data or b"").decode("utf-8")))
        self.calls.append((method, payload))
        if method == "getUpdates":
            updates = self.updates
            self.updates = []
            return FakeTelegramResponse({"ok": True, "result": updates})
        return FakeTelegramResponse({"ok": True, "result": {"message_id": 1}})


def _telegram_update(text: str, chat_id: int, update_id: int = 100, message_id: int = 10) -> dict:
    return {
        "update_id": update_id,
        "message": {
            "message_id": message_id,
            "chat": {"id": chat_id, "type": "private"},
            "from": {"id": chat_id, "first_name": "Ada", "last_name": "Lovelace"},
            "text": text,
        },
    }


def test_telegram_tick_pairs_sender_then_queues_approved_message(monkeypatch) -> None:
    chat_id = int("7" + uuid.uuid4().hex[:8], 16)
    agent_id = f"telegram-agent-{uuid.uuid4().hex[:8]}"
    fake_api = FakeTelegramApi([_telegram_update(f"@{agent_id} hello", chat_id)])
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setattr(urllib.request, "urlopen", fake_api)

    with TestClient(app) as client:
        client.post("/api/agents", json={"id": agent_id, "name": "Telegram Agent", "role": "Handles Telegram", "provider": "local"})
        first = client.post("/api/services/channel/telegram/tick")

        assert first.status_code == 200
        assert first.json()["inbound"]["pairingRequired"] == 1
        assert any(method == "sendMessage" and "Pairing code" in payload["text"] for method, payload in fake_api.calls)

        pending = client.get("/api/pairing").json()["pending"]
        code = next(item["code"] for item in pending if item["channel"] == "telegram" and item["senderId"] == str(chat_id))
        client.post("/api/pairing/approve", json={"code": code})

        fake_api.updates = [_telegram_update(f"@{agent_id} hello again", chat_id, update_id=101, message_id=11)]
        second = client.post("/api/services/channel/telegram/tick")

        assert second.status_code == 200
        assert second.json()["inbound"]["queued"] == 1
        queued = [item for item in client.get("/api/queue").json() if item["metadata"].get("channel") == "telegram"]
        assert any(item["target"] == f"@agent:{agent_id}" and item["metadata"]["senderId"] == str(chat_id) for item in queued)


def test_telegram_channel_response_inherits_channel_and_is_delivered(monkeypatch) -> None:
    chat_id = str(int("8" + uuid.uuid4().hex[:8], 16))
    agent_id = f"telegram-response-agent-{uuid.uuid4().hex[:8]}"
    fake_api = FakeTelegramApi([])
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setattr(urllib.request, "urlopen", fake_api)

    with TestClient(app) as client:
        client.post("/api/agents", json={"id": agent_id, "name": "Telegram Response", "role": "Replies", "provider": "local"})
        pairing = client.post("/api/message", json={"channel": "telegram", "senderId": chat_id, "sender": "Ada", "message": f"@{agent_id} hello"})
        client.post("/api/pairing/approve", json={"code": pairing.json()["code"]})
        queued = client.post(
            "/api/message",
            json={"channel": "telegram", "senderId": chat_id, "sender": "Ada", "message": f"@{agent_id} hello"},
        )
        client.post(f"/api/messages/{queued.json()['messageId']}/process")

        pending = [
            item
            for item in client.get("/api/responses/pending?channel=telegram").json()
            if item["senderId"] == chat_id
        ]
        assert pending
        assert pending[0]["senderId"] == chat_id

        tick = client.post("/api/services/channel/telegram/tick")

        assert tick.status_code == 200
        assert tick.json()["outbound"]["delivered"] >= 1
        assert any(method == "sendMessage" and "Configure an OpenAI-compatible provider" in payload["text"] for method, payload in fake_api.calls)
        assert client.get("/api/responses/pending?channel=telegram").json() == []


def test_telegram_tick_returns_structured_error_when_api_is_unreachable(monkeypatch) -> None:
    def fail_urlopen(request: urllib.request.Request, timeout: int = 30):
        raise urllib.error.URLError(ConnectionRefusedError("telegram unavailable"))

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setattr(urllib.request, "urlopen", fail_urlopen)

    with TestClient(app) as client:
        tick = client.post("/api/services/channel/telegram/tick")

        assert tick.status_code == 200
        body = tick.json()
        assert body["ok"] is False
        assert "telegram unavailable" in body["error"]
        assert body["telegram"]["configured"] is True
        assert body["telegram"]["lastError"]


@pytest.mark.skipif(
    os.environ.get("RUN_TELEGRAM_INTEGRATION") != "1" or not os.environ.get("TELEGRAM_BOT_TOKEN"),
    reason="Set RUN_TELEGRAM_INTEGRATION=1 and TELEGRAM_BOT_TOKEN to call the real Telegram Bot API.",
)
def test_real_telegram_token_can_tick_against_bot_api() -> None:
    with TestClient(app) as client:
        status = client.post("/api/services/channel/telegram/status")
        tick = client.post("/api/services/channel/telegram/tick")

        assert status.status_code == 200
        assert status.json()["telegram"]["configured"] is True
        assert tick.status_code == 200
        assert tick.json()["ok"] is True
        assert "updates" in tick.json()["inbound"]
