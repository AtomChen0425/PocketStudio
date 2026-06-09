from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable

from pydantic import BaseModel, ConfigDict, Field
from pathlib import Path
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
    def setup_workspace(self, workspace: Path) -> None:
        """Set up the workspace for the provider."""
        pass
    async def reset_agent(self, agent_id: str) -> bool:
        """Reset any provider-side session/process state for an agent."""
        return False
    @abstractmethod
    async def run(self, request: ProviderRequest) -> ProviderResponse:
        """Execute an agent turn."""
