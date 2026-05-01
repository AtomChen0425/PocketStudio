from __future__ import annotations

from pocketStudio.core.database import Database
from pocketStudio.providers.base import AgentProvider
from pocketStudio.providers.local import LocalEchoProvider
from pocketStudio.providers.openai_compatible import OpenAICompatibleProvider


class ProviderRegistry:
    def __init__(self, db: Database | None = None) -> None:
        self.db = db
        self._providers: dict[str, AgentProvider] = {
            "local": LocalEchoProvider(),
            "openai": OpenAICompatibleProvider(),
        }
        self.reload_custom()

    def register(self, provider: AgentProvider) -> None:
        self._providers[provider.name] = provider

    def reload_custom(self) -> None:
        for key in list(self._providers):
            if key not in {"local", "openai"}:
                del self._providers[key]
        if self.db is None:
            return
        rows = self.db.fetch_all("SELECT * FROM custom_providers ORDER BY id")
        for row in rows:
            if row["harness"] in {"openai", "codex", "claude"}:
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
