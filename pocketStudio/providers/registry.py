from __future__ import annotations

from pocketStudio.core.database import Database
from pocketStudio.providers.base import AgentProvider
from pocketStudio.providers.codex import CodexProvider
from pocketStudio.providers.local import LocalEchoProvider
from pocketStudio.providers.openai_compatible import OpenAICompatibleProvider
from pocketStudio.providers.subprocess import ProcessRegistry


class ProviderRegistry:
    def __init__(self, db: Database | None = None) -> None:
        self.db = db
        self.processes = ProcessRegistry()
        self._providers: dict[str, AgentProvider] = {
            "local": LocalEchoProvider(),
            "openai": OpenAICompatibleProvider(),
            "codex": CodexProvider(registry=self.processes),
        }
        self.reload_custom()

    def register(self, provider: AgentProvider) -> None:
        self._providers[provider.name] = provider

    def reload_custom(self) -> None:
        for key in list(self._providers):
            if key not in {"local", "openai", "codex"}:
                del self._providers[key]
        if self.db is None:
            return
        rows = self.db.fetch_all("SELECT * FROM custom_providers ORDER BY id")
        for row in rows:
            if row["harness"] == "codex":
                provider = CodexProvider(registry=self.processes)
                provider.name = row["id"]
                self.register(provider)
            elif row["harness"] in {"openai", "claude"}:
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
