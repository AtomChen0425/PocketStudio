from __future__ import annotations

from pocketStudio.core.database import Database
from pocketStudio.providers.base import AgentProvider
from pocketStudio.providers.cli_agent import ClaudeProvider, OpenCodeProvider, provider_from_command
from pocketStudio.providers.codex import CodexProvider, codex_provider_from_command
from pocketStudio.providers.local import LocalEchoProvider
from pocketStudio.providers.openai_compatible import OpenAICompatibleProvider
from pocketStudio.providers.nanobot import NanobotProvider
from pocketStudio.providers.subprocess import ProcessRegistry


class ProviderRegistry:
    BUILTIN_PROVIDERS = {"local", "openai", "codex", "anthropic", "claude", "opencode", "nanobot"}

    def __init__(self, db: Database | None = None) -> None:
        self.db = db
        self.processes = ProcessRegistry()
        self._manual_provider_names: set[str] = set()
        codex_provider = CodexProvider(registry=self.processes)
        claude_provider = ClaudeProvider(registry=self.processes)
        self._providers: dict[str, AgentProvider] = {
            # "local": LocalEchoProvider(),
            # "openai": codex_provider,
            "codex": codex_provider,
            # "anthropic": claude_provider,
            # "claude": claude_provider,
            # "opencode": OpenCodeProvider(registry=self.processes),
            "nanobot": NanobotProvider(db=self.db),
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

    async def reset_agent(self, agent_id: str) -> bool:
        reset = False
        for provider in self._providers.values():
            handler = getattr(provider, "reset_agent", None)
            if handler and await handler(agent_id):
                reset = True
                continue
            kill = getattr(provider, "kill_agent", None)
            if kill and await kill(agent_id):
                reset = True
        return reset

    def agent_process_alive(self, agent_id: str) -> bool:
        return any(
            bool(is_alive(agent_id))
            for provider in self._providers.values()
            if (is_alive := getattr(provider, "is_alive", None))
        )

    def active_processes(self) -> list[dict]:
        return self.processes.snapshot()
