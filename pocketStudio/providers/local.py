from __future__ import annotations

from pocketStudio.providers.base import AgentProvider, ProviderRequest, ProviderResponse


class LocalEchoProvider(AgentProvider):
    name = "local"

    async def run(self, request: ProviderRequest) -> ProviderResponse:
        agent = request.agent
        text = (
            f"{agent.name} ({agent.role}) received: {request.input}\n\n"
            "Configure an OpenAI-compatible provider to replace this local dry-run response."
        )
        return ProviderResponse(text=text, raw={"provider": self.name})

