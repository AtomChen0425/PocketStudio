from __future__ import annotations

import secrets
import time
from dataclasses import dataclass

from pocketStudio.core.database import Database
from pocketStudio.services.agent_service import AgentService
from pocketStudio.services.team_service import TeamService


PAIRING_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


@dataclass
class PairingResult:
    approved: bool
    code: str | None = None
    is_new_pending: bool = False


@dataclass
class RoutedChannelMessage:
    target: str | None
    content: str | None
    switch_notification: str | None = None


class ChannelService:
    def __init__(self, db: Database, agents: AgentService, teams: TeamService) -> None:
        self.db = db
        self.agents = agents
        self.teams = teams

    def pairing_state(self) -> dict:
        pending = self.db.fetch_all("SELECT * FROM pairing_pending ORDER BY created_at DESC")
        approved = self.db.fetch_all("SELECT * FROM pairing_approved ORDER BY approved_at DESC")
        return {
            "pending": [
                {
                    "channel": row["channel"],
                    "senderId": row["sender_id"],
                    "sender": row["sender"],
                    "code": row["code"],
                    "createdAt": row["created_at"],
                    "lastSeenAt": row["last_seen_at"],
                }
                for row in pending
            ],
            "approved": [
                {
                    "channel": row["channel"],
                    "senderId": row["sender_id"],
                    "sender": row["sender"],
                    "approvedAt": row["approved_at"],
                    "approvedCode": row["approved_code"],
                }
                for row in approved
            ],
        }

    def ensure_sender_paired(self, channel: str, sender_id: str, sender: str) -> PairingResult:
        approved = self.db.fetch_one(
            "SELECT * FROM pairing_approved WHERE channel = ? AND sender_id = ?",
            (channel, sender_id),
        )
        if approved:
            if approved["sender"] != sender:
                self.db.execute(
                    "UPDATE pairing_approved SET sender = ? WHERE channel = ? AND sender_id = ?",
                    (sender, channel, sender_id),
                )
            return PairingResult(approved=True)

        now = int(time.time() * 1000)
        pending = self.db.fetch_one(
            "SELECT * FROM pairing_pending WHERE channel = ? AND sender_id = ?",
            (channel, sender_id),
        )
        if pending:
            self.db.execute(
                """
                UPDATE pairing_pending
                SET sender = ?, last_seen_at = ?
                WHERE channel = ? AND sender_id = ?
                """,
                (sender, now, channel, sender_id),
            )
            return PairingResult(approved=False, code=pending["code"], is_new_pending=False)

        code = self._unique_pairing_code()
        self.db.execute(
            """
            INSERT INTO pairing_pending (code, channel, sender_id, sender, created_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (code, channel, sender_id, sender, now, now),
        )
        return PairingResult(approved=False, code=code, is_new_pending=True)

    def approve(self, code: str | None) -> dict:
        normalized = (code or "").strip().upper()
        if not normalized:
            return {"ok": False, "error": "code is required"}
        row = self.db.fetch_one("SELECT * FROM pairing_pending WHERE code = ?", (normalized,))
        if row is None:
            return {"ok": False, "error": f"Pairing code not found: {normalized}"}
        now = int(time.time() * 1000)
        self.db.execute(
            """
            INSERT OR REPLACE INTO pairing_approved (channel, sender_id, sender, approved_at, approved_code)
            VALUES (?, ?, ?, ?, ?)
            """,
            (row["channel"], row["sender_id"], row["sender"], now, normalized),
        )
        self.db.execute("DELETE FROM pairing_pending WHERE code = ?", (normalized,))
        return {
            "ok": True,
            "entry": {
                "channel": row["channel"],
                "senderId": row["sender_id"],
                "sender": row["sender"],
                "approvedAt": now,
                "approvedCode": normalized,
            },
        }

    def revoke(self, channel: str, sender_id: str) -> bool:
        self.db.execute("DELETE FROM pairing_approved WHERE channel = ? AND sender_id = ?", (channel, sender_id))
        self.db.execute("DELETE FROM channel_defaults WHERE channel = ? AND sender_id = ?", (channel, sender_id))
        return True

    def dismiss_pending(self, code: str) -> bool:
        self.db.execute("DELETE FROM pairing_pending WHERE code = ?", (code.strip().upper(),))
        return True

    def route_message(self, channel: str, sender_id: str, text: str, explicit_agent: str | None = None) -> RoutedChannelMessage:
        stripped = text.strip()
        if explicit_agent:
            return RoutedChannelMessage(target=f"@agent:{explicit_agent}", content=stripped)

        if stripped.startswith("@"):
            mention, _, body = stripped.partition(" ")
            tag = mention[1:]
            if tag.lower() == "default":
                had_default = self.clear_default(channel, sender_id)
                return RoutedChannelMessage(
                    target=None,
                    content=None,
                    switch_notification="Cleared default agent." if had_default else "No default agent was set.",
                )

            target = self.resolve_target(tag)
            if target:
                previous = self.get_default(channel, sender_id)
                if previous != target:
                    self.save_default(channel, sender_id, target)
                notification = (
                    f"Switched default target to {target}. Future messages will route there. Send @default to clear."
                    if previous != target
                    else None
                )
                if not body.strip():
                    return RoutedChannelMessage(target=None, content=None, switch_notification=notification)
                return RoutedChannelMessage(target=target, content=body.strip(), switch_notification=notification)
            return RoutedChannelMessage(target=f"@agent:{tag}", content=body.strip() or stripped)

        default = self.get_default(channel, sender_id)
        if default:
            return RoutedChannelMessage(target=default, content=stripped)
        return RoutedChannelMessage(target="@agent:pocketstudio", content=stripped)

    def resolve_target(self, tag: str) -> str | None:
        normalized = tag.strip()
        if not normalized:
            return None
        if normalized.startswith("team:"):
            team_id = normalized.split(":", 1)[1]
            try:
                self.teams.get(team_id)
                return f"@team:{team_id}"
            except KeyError:
                return None
        if normalized.startswith("agent:"):
            normalized = normalized.split(":", 1)[1]
        try:
            self.agents.get(normalized)
            return f"@agent:{normalized}"
        except KeyError:
            pass
        try:
            self.teams.get(normalized)
            return f"@team:{normalized}"
        except KeyError:
            return None

    def get_default(self, channel: str, sender_id: str) -> str | None:
        row = self.db.fetch_one(
            "SELECT target FROM channel_defaults WHERE channel = ? AND sender_id = ?",
            (channel, sender_id),
        )
        return row["target"] if row else None

    def save_default(self, channel: str, sender_id: str, target: str) -> None:
        self.db.execute(
            """
            INSERT OR REPLACE INTO channel_defaults (channel, sender_id, target, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (channel, sender_id, target, int(time.time() * 1000)),
        )

    def clear_default(self, channel: str, sender_id: str) -> bool:
        existed = self.get_default(channel, sender_id) is not None
        self.db.execute("DELETE FROM channel_defaults WHERE channel = ? AND sender_id = ?", (channel, sender_id))
        return existed

    def _unique_pairing_code(self) -> str:
        existing = {
            row["code"].upper()
            for row in self.db.fetch_all("SELECT code FROM pairing_pending")
        }
        existing.update(
            row["approved_code"].upper()
            for row in self.db.fetch_all("SELECT approved_code FROM pairing_approved WHERE approved_code IS NOT NULL")
        )
        for _ in range(20):
            code = "".join(secrets.choice(PAIRING_ALPHABET) for _ in range(8))
            if code not in existing:
                return code
        return str(int(time.time()))[-8:].rjust(8, "A")
