from __future__ import annotations

import os

import httpx

from pocketStudio.providers.base import AgentProvider, ProviderRequest, ProviderResponse


class OpenAICompatibleProvider(AgentProvider):
    name = "openai"

    def __init__(
        self,
        name: str = "openai",
        base_url: str | None = None,
        api_key: str | None = None,
        default_model: str | None = None,
    ) -> None:
        self.name = name
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.default_model = default_model

    async def run(self, request: ProviderRequest) -> ProviderResponse:
        if not self.api_key:
            raise RuntimeError(f"An API key is required for the {self.name} provider")

        system_prompt = request.agent.system_prompt or request.agent.role
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend({"role": "assistant", "content": item} for item in request.context)
        messages.append({"role": "user", "content": request.input})

        payload = {
            "model": request.agent.model or self.default_model or os.getenv("OPENAI_MODEL") or "gpt-4o-mini",
            "messages": messages,
        }
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
            response.raise_for_status()
        body = response.json()
        text = body["choices"][0]["message"]["content"]
        return ProviderResponse(text=text, raw=body)
