from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field


class TeamMode(StrEnum):
    chain = "chain"
    fanout = "fanout"


class MessageStatus(StrEnum):
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"
    dead = "dead"


class AgentCreate(BaseModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]+$")
    name: str
    role: str
    system_prompt: str = ""
    provider: str = "local"
    model: str | None = None
    workspace: Path | None = None
    enabled: bool = True


class Agent(AgentCreate):
    workspace: Path


class TeamCreate(BaseModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]+$")
    name: str
    mode: TeamMode = TeamMode.chain
    agent_ids: list[str] = Field(default_factory=list)


class Team(TeamCreate):
    pass


class MessageCreate(BaseModel):
    target: str = Field(description="@agent:id, @team:id, or a bare agent/team id")
    content: str
    sender: str = "api"


class QueueMessage(BaseModel):
    id: int
    target: str
    content: str
    sender: str
    status: MessageStatus
    attempts: int
    error: str | None = None
    result: str | None = None
    created_at: str
    updated_at: str


class AgentRun(BaseModel):
    agent_id: str
    input: str
    output: str


class OrchestrationResult(BaseModel):
    message_id: int
    target: str
    runs: list[AgentRun]
    output: str


class ChatMessageCreate(BaseModel):
    message: str
    sender: str = "api"


class ChatMessage(BaseModel):
    id: int
    team_id: str
    sender: str
    message: str
    created_at: str


class TaskCreate(BaseModel):
    title: str
    description: str = ""
    status: str = "todo"
    assignee: str | None = None


class Task(TaskCreate):
    id: int
    created_at: str
    updated_at: str


class Event(BaseModel):
    id: int
    type: str
    payload: dict
    created_at: str

