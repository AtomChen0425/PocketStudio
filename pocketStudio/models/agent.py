from pathlib import Path
from pydantic import BaseModel, Field

class AgentCreate(BaseModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]+$")
    name: str
    role: str
    system_prompt: str = ""
    provider: str = "local"
    model: str | None = None
    workspace: Path | None = None
    enabled: bool = True
    heartbeat_enabled: bool = True
    heartbeat_interval: int | None = None

class Agent(AgentCreate):
    workspace: Path

class AgentMessage(BaseModel):
    id: int
    agent_id: str
    role: str
    channel: str
    sender: str
    message_id: str
    content: str
    created_at: int