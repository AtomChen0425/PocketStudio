from __future__ import annotations

import os

import httpx

from pocketStudio.providers.base import AgentProvider, ProviderRequest, ProviderResponse


class OpenAICompatibleProvider(AgentProvider):
    name = "openai"

    def __init__(self, base_url: str | None = None, api_key: str | None = None) -> None:
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")

    async def run(self, request: ProviderRequest) -> ProviderResponse:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for the openai provider")

        messages = [{"role": "system", "content": request.agent.system_prompt or request.agent.role}]
        messages.extend({"role": "assistant", "content": item} for item in request.context)
        messages.append({"role": "user", "content": request.input})

        payload = {
            "model": request.agent.model or os.getenv("OPENAI_MODEL") or "gpt-4o-mini",
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

