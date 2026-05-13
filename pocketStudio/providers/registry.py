from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from pocketStudio.core.database import Database
from pocketStudio.providers.base import AgentProvider
from pocketStudio.providers.cli_agent import ClaudeProvider, OpenCodeProvider, provider_from_command
from pocketStudio.providers.codex import CodexProvider, codex_provider_from_command
from pocketStudio.providers.local import LocalEchoProvider
from pocketStudio.providers.openai_compatible import OpenAICompatibleProvider
from pocketStudio.providers.subprocess import ProcessRegistry


class ProviderRegistry:
    BUILTIN_PROVIDERS = {"local", "openai", "codex", "anthropic", "claude", "opencode"}

    def __init__(self, db: Database | None = None) -> None:
        self.db = db
        self.processes = ProcessRegistry()
        self._manual_provider_names: set[str] = set()
        codex_provider = CodexProvider(registry=self.processes)
        claude_provider = ClaudeProvider(registry=self.processes)
        self._providers: dict[str, AgentProvider] = {
            "local": LocalEchoProvider(),
            "openai": codex_provider,
            "codex": codex_provider,
            "anthropic": claude_provider,
            "claude": claude_provider,
            "opencode": OpenCodeProvider(registry=self.processes),
        }
        self.reload_custom()

    def register(self, provider: AgentProvider) -> None:
        self._providers[provider.name] = provider
        if provider.name not in self.BUILTIN_PROVIDERS:
            self._manual_provider_names.add(provider.name)

    def reload_custom(self) -> None:
        for key in list(self._providers):
            if key not in self.BUILTIN_PROVIDERS and key not in self._manual_provider_names:
                del self._providers[key]
        if self.db is None:
            return
        rows = self.db.fetch_all("SELECT * FROM custom_providers ORDER BY id")
        for row in rows:
            if row["id"] in self.BUILTIN_PROVIDERS:
                continue
            if row["harness"] == "codex":
                command = row["base_url"] or ""
                provider = codex_provider_from_command(command, self.processes) if command else CodexProvider(registry=self.processes)
                provider.name = row["id"]
                self.register(provider)
            elif row["harness"] == "claude":
                command = row["base_url"] or ""
                provider = provider_from_command(row["id"], command, self.processes) if command else ClaudeProvider(registry=self.processes)
                provider.name = row["id"]
                self.register(provider)
            elif row["harness"] == "opencode":
                command = row["base_url"] or ""
                provider = provider_from_command(row["id"], command, self.processes) if command else OpenCodeProvider(registry=self.processes)
                provider.name = row["id"]
                self.register(provider)
            elif row["harness"] == "openai":
                self.register(
                    OpenAICompatibleProvider(
                        name=row["id"],
                        base_url=row["base_url"] or None,
                        api_key=row["api_key"] or None,
                        default_model=row["model"],
                    )
                )

    def get(self, name: str) -> AgentProvider:
        self.reload_custom()
        try:
            return self._providers[name]
        except KeyError as exc:
            available = ", ".join(sorted(self._providers))
            raise ValueError(f"Unknown provider '{name}'. Available providers: {available}") from exc

    def list_names(self) -> list[str]:
        self.reload_custom()
        return sorted(self._providers)

    async def kill_agent(self, agent_id: str) -> bool:
        killed = False
        for provider in self._providers.values():
            kill = getattr(provider, "kill_agent", None)
            if kill and await kill(agent_id):
                killed = True
        return killed

    def agent_process_alive(self, agent_id: str) -> bool:
        return any(
            bool(is_alive(agent_id))
            for provider in self._providers.values()
            if (is_alive := getattr(provider, "is_alive", None))
        )

    def active_processes(self) -> list[dict]:
        return self.processes.snapshot()

    def diagnostics(self) -> dict:
        providers = []
        for name in self.list_names():
            provider = self._providers[name]
            command = getattr(provider, "command", None)
            resolved_path = _resolved_command_path(command)
            harness = getattr(provider, "harness_name", None)
            provider_info = {
                "name": name,
                "providerName": getattr(provider, "name", name),
                "harness": harness,
                "class": provider.__class__.__name__,
                "builtin": name in self.BUILTIN_PROVIDERS,
                "command": command,
                "resolvedPath": resolved_path,
                "baseArgs": list(getattr(provider, "base_args", []) or []),
            }
            if harness == "codex" or isinstance(provider, CodexProvider):
                provider_info["codexHome"] = _codex_home_diagnostics(Path.home() / ".codex")
            provider_info["available"] = bool(resolved_path) if command else True
            providers.append(provider_info)
        return {
            "providers": providers,
            "activeProcesses": self.active_processes(),
            "windowsPowerShellFallback": bool(shutil.which("powershell.exe") or shutil.which("powershell")),
        }


def _codex_home_diagnostics(codex_home: Path) -> dict:
    sessions_dir = codex_home / "sessions"
    writable = _can_write(codex_home)
    sessions_writable = _can_write(sessions_dir)
    return {
        "path": str(codex_home),
        "exists": codex_home.exists(),
        "writable": writable,
        "sessionsPath": str(sessions_dir),
        "sessionsExists": sessions_dir.exists(),
        "sessionsWritable": sessions_writable,
    }


def _can_write(path: Path) -> bool:
    if not path.exists() or not path.is_dir():
        return False
    probe = path / f".pocketstudio-write-test-{uuid.uuid4().hex}.tmp"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def _resolved_command_path(command: str | None) -> str | None:
    if not command:
        return None
    return shutil.which(command)
