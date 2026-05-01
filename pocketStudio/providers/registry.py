from __future__ import annotations

from pocketStudio.providers.base import AgentProvider
from pocketStudio.providers.local import LocalEchoProvider
from pocketStudio.providers.openai_compatible import OpenAICompatibleProvider


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, AgentProvider] = {
            "local": LocalEchoProvider(),
            "openai": OpenAICompatibleProvider(),
        }

    def register(self, provider: AgentProvider) -> None:
        self._providers[provider.name] = provider

    def get(self, name: str) -> AgentProvider:
        try:
            return self._providers[name]
        except KeyError as exc:
            available = ", ".join(sorted(self._providers))
            raise ValueError(f"Unknown provider '{name}'. Available providers: {available}") from exc

    def list_names(self) -> list[str]:
        return sorted(self._providers)

