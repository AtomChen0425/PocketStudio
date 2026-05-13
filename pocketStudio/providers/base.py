from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable

from pydantic import BaseModel, ConfigDict, Field

from pocketStudio.models import Agent


class ProviderRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    agent: Agent
    input: str
    context: list[str] = []
    reset: bool = False
    progress: Callable[[dict], None] | None = Field(default=None, exclude=True)


class ProviderResponse(BaseModel):
    text: str
    raw: dict | None = None


class AgentProvider(ABC):
    name: str

    @abstractmethod
    async def run(self, request: ProviderRequest) -> ProviderResponse:
        """Execute an agent turn."""
