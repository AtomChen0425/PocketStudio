from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel

from pocketStudio.models import Agent


class ProviderRequest(BaseModel):
    agent: Agent
    input: str
    context: list[str] = []


class ProviderResponse(BaseModel):
    text: str
    raw: dict | None = None


class AgentProvider(ABC):
    name: str

    @abstractmethod
    async def run(self, request: ProviderRequest) -> ProviderResponse:
        """Execute an agent turn."""

