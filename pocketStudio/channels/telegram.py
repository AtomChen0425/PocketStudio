from __future__ import annotations

import asyncio
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from pocketStudio.core.config import Settings
from pocketStudio.core.database import Database
from pocketStudio.models import MessageCreate, ResponseJob
from pocketStudio.services.channel_service import ChannelService
from pocketStudio.services.event_service import EventService
from pocketStudio.services.queue_service import QueueService
from pocketStudio.services.settings_service import SettingsService


TELEGRAM_CHANNEL_ID = "telegram"
TELEGRAM_MESSAGE_LIMIT = 4096


class TelegramApiError(RuntimeError):
    pass


class TelegramChannelService:
    def __init__(
        self,
        db: Database,
        settings: Settings,
        settings_service: SettingsService,
        channels: ChannelService,
        queue: QueueService,
        events: EventService,
    ) -> None:
        self.db = db
        self.settings = settings
        self.settings_service = settings_service
        self.channels = channels
        self.queue = queue
        self.events = events
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._last_error: str | None = None
        self._started_at: float | None = None

    def configured_token(self) -> str | None:
        if os.environ.get("TELEGRAM_BOT_TOKEN"):
            return os.environ["TELEGRAM_BOT_TOKEN"]
        telegram_settings = ((self.settings_service.snapshot().get("channels") or {}).get("telegram") or {})
        token = telegram_settings.get("bot_token") or telegram_settings.get("token")
        return str(token) if token else None

    def status(self) -> dict:
        token = self.configured_token()
        return {
            "id": TELEGRAM_CHANNEL_ID,
            "implemented": True,
            "configured": bool(token),
            "running": bool(self._task and not self._task.done()),
            "status": self._status_label(bool(token)),
            "startedAt": int(self._started_at * 1000) if self._started_at else None,
            "lastError": self._last_error,
            "offset": self._load_offset(),
        }

    def start(self) -> bool:
        if self._task and not self._task.done():
            return False
        if not self.configured_token():
            self._last_error = "TELEGRAM_BOT_TOKEN or channels.telegram.bot_token is required"
            return False
        self._stop = asyncio.Event()
        self._started_at = time.time()
        self._last_error = None
        self._task = asyncio.create_task(self._run(), name="pocketstudio-telegram-channel")
        self.events.emit("channel.started", {"channel": TELEGRAM_CHANNEL_ID})
        return True

    async def stop(self) -> bool:
        if not self._task:
            return False
        self._stop.set()
        try:
            await asyncio.wait_for(self._task, timeout=5)
        except TimeoutError:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
        finally:
            self._task = None
            self.events.emit("channel.stopped", {"channel": TELEGRAM_CHANNEL_ID})
        return True

    async def restart(self) -> bool:
        await self.stop()
        return self.start()

    async def tick(self) -> dict:
        try:
            inbound = await asyncio.to_thread(self.poll_once)
            outbound = await asyncio.to_thread(self.deliver_pending)
        except Exception as exc:
            self._last_error = str(exc)
            self.events.emit("channel.error", {"channel": TELEGRAM_CHANNEL_ID, "error": str(exc)})
            return {
                "ok": False,
                "error": str(exc),
                "inbound": {"handled": 0, "queued": 0, "pairingRequired": 0, "updates": 0},
                "outbound": {"delivered": 0, "failed": 0},
                "telegram": self.status(),
            }
        return {"ok": True, "inbound": inbound, "outbound": outbound, "telegram": self.status()}

    def poll_once(self, limit: int = 20, timeout: int = 0) -> dict:
        token = self._require_token()
        offset = self._load_offset()
        params: dict[str, Any] = {"limit": limit, "timeout": timeout, "allowed_updates": json.dumps(["message"])}
        if offset is not None:
            params["offset"] = offset
        updates = self._api_call(token, "getUpdates", params).get("result") or []
        handled = 0
        queued = 0
        pairing_required = 0
        for update in updates:
            update_id = int(update.get("update_id", 0))
            if update_id:
                self._save_offset(update_id + 1)
            result = self._handle_update(update, token)
            if result["handled"]:
                handled += 1
            if result["queued"]:
                queued += 1
            if result["pairingRequired"]:
                pairing_required += 1
        return {"handled": handled, "queued": queued, "pairingRequired": pairing_required, "updates": len(updates)}

    def deliver_pending(self) -> dict:
        token = self._require_token()
        delivered = 0
        failed = 0
        for response in self.queue.get_responses_for_channel(TELEGRAM_CHANNEL_ID):
            try:
                if not response.sender_id:
                    self.queue.ack_response(response.id)
                    continue
                self._send_response(token, response)
                self.queue.ack_response(response.id)
                delivered += 1
            except Exception as exc:
                failed += 1
                self._last_error = str(exc)
                self.events.emit("channel.error", {"channel": TELEGRAM_CHANNEL_ID, "error": str(exc)})
        return {"delivered": delivered, "failed": failed}

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                await asyncio.to_thread(self.poll_once, 20, 20)
                await asyncio.to_thread(self.deliver_pending)
                self._last_error = None
            except Exception as exc:
                self._last_error = str(exc)
                self.events.emit("channel.error", {"channel": TELEGRAM_CHANNEL_ID, "error": str(exc)})
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=5)
                except TimeoutError:
                    continue
        self.events.emit("channel.exited", {"channel": TELEGRAM_CHANNEL_ID})

    def _handle_update(self, update: dict, token: str) -> dict:
        message = update.get("message") or {}
        chat = message.get("chat") or {}
        if chat.get("type") != "private":
            return {"handled": False, "queued": False, "pairingRequired": False}
        text = (message.get("text") or message.get("caption") or "").strip()
        if not text:
            return {"handled": False, "queued": False, "pairingRequired": False}

        sender_id = str(chat.get("id"))
        sender = self._sender_name(message)
        message_id = str(message.get("message_id") or update.get("update_id"))
        pairing = self.channels.ensure_sender_paired(TELEGRAM_CHANNEL_ID, sender_id, sender)
        if not pairing.approved:
            if pairing.is_new_pending and pairing.code:
                self._send_message(token, sender_id, self._pairing_message(pairing.code), reply_to=message.get("message_id"))
            return {"handled": True, "queued": False, "pairingRequired": True}

        command_response = self._handle_command(text, token, sender_id, message.get("message_id"))
        if command_response:
            return {"handled": True, "queued": False, "pairingRequired": False}

        routed = self.channels.route_message(TELEGRAM_CHANNEL_ID, sender_id, text)
        if routed.switch_notification:
            self._send_message(token, sender_id, routed.switch_notification)
        if not routed.target or not routed.content:
            return {"handled": True, "queued": False, "pairingRequired": False}

        queued = self.queue.enqueue(
            MessageCreate(
                target=routed.target,
                content=routed.content,
                sender=sender,
                metadata={
                    "channel": TELEGRAM_CHANNEL_ID,
                    "senderId": sender_id,
                    "telegramMessageId": message_id,
                    "clientMessageId": f"telegram-{sender_id}-{message_id}",
                },
            )
        )
        self._send_chat_action(token, sender_id)
        self.events.emit("channel.message", {"channel": TELEGRAM_CHANNEL_ID, "message_id": queued.id, "sender_id": sender_id})
        return {"handled": True, "queued": True, "pairingRequired": False}

    def _handle_command(self, text: str, token: str, chat_id: str, reply_to: int | None) -> bool:
        normalized = text.strip().lower()
        if normalized in {"/agent", "!agent"}:
            agents = self.channels.agents.list_agents()
            body = "No agents configured." if not agents else "Available Agents:\n" + "\n".join(f"@{agent.id} - {agent.name}" for agent in agents)
            self._send_message(token, chat_id, body, reply_to=reply_to)
            return True
        if normalized in {"/team", "!team"}:
            teams = self.channels.teams.list_teams()
            body = "No teams configured." if not teams else "Available Teams:\n" + "\n".join(f"@{team.id} - {team.name}" for team in teams)
            self._send_message(token, chat_id, body, reply_to=reply_to)
            return True
        return False

    def _send_response(self, token: str, response: ResponseJob) -> None:
        for chunk in self._split_message(response.message):
            self._send_message(token, response.sender_id or "", chunk)
        if response.files:
            notice = "\n".join(f"[file: {path}]" for path in response.files)
            self._send_message(token, response.sender_id or "", notice)

    def _api_call(self, token: str, method: str, payload: dict[str, Any]) -> dict:
        url = f"https://api.telegram.org/bot{token}/{method}"
        data = urllib.parse.urlencode(payload).encode("utf-8")
        request = urllib.request.Request(url, data=data, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise TelegramApiError(str(exc.reason)) from exc
        if not body.get("ok"):
            raise TelegramApiError(str(body))
        return body

    def _send_message(self, token: str, chat_id: str, text: str, reply_to: int | None = None) -> None:
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if reply_to:
            payload["reply_to_message_id"] = reply_to
        self._api_call(token, "sendMessage", payload)

    def _send_chat_action(self, token: str, chat_id: str) -> None:
        try:
            self._api_call(token, "sendChatAction", {"chat_id": chat_id, "action": "typing"})
        except TelegramApiError:
            pass

    def _require_token(self) -> str:
        token = self.configured_token()
        if not token:
            raise TelegramApiError("TELEGRAM_BOT_TOKEN or channels.telegram.bot_token is required")
        return token

    def _load_offset(self) -> int | None:
        path = self._offset_path()
        if not path.exists():
            return None
        try:
            return int(json.loads(path.read_text(encoding="utf-8")).get("offset"))
        except (TypeError, ValueError, json.JSONDecodeError, OSError):
            return None

    def _save_offset(self, offset: int) -> None:
        path = self._offset_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"offset": offset}), encoding="utf-8")

    def _offset_path(self):
        return self.settings.pocketStudio_home / "channels" / "telegram_state.json"

    def _status_label(self, configured: bool) -> str:
        if not configured:
            return "missing-token"
        if self._task and not self._task.done():
            return "running"
        if self._last_error:
            return "error"
        return "stopped"

    @staticmethod
    def _sender_name(message: dict) -> str:
        user = message.get("from") or {}
        parts = [user.get("first_name"), user.get("last_name")]
        return " ".join(part for part in parts if part) or user.get("username") or "Telegram"

    @staticmethod
    def _pairing_message(code: str) -> str:
        return "\n".join(
            [
                "This Telegram sender is not paired yet.",
                f"Pairing code: {code}",
                "Approve it with:",
                f"pocketstudio pairing approve {code}",
            ]
        )

    @staticmethod
    def _split_message(text: str) -> list[str]:
        if len(text) <= TELEGRAM_MESSAGE_LIMIT:
            return [text]
        chunks = []
        remaining = text
        while remaining:
            if len(remaining) <= TELEGRAM_MESSAGE_LIMIT:
                chunks.append(remaining)
                break
            split_at = remaining.rfind("\n", 0, TELEGRAM_MESSAGE_LIMIT)
            if split_at <= 0:
                split_at = remaining.rfind(" ", 0, TELEGRAM_MESSAGE_LIMIT)
            if split_at <= 0:
                split_at = TELEGRAM_MESSAGE_LIMIT
            chunks.append(remaining[:split_at])
            remaining = remaining[split_at:].lstrip()
        return chunks
