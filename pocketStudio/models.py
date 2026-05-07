from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


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
    heartbeat_enabled: bool = True
    heartbeat_interval: int | None = None


class Agent(AgentCreate):
    workspace: Path


class TeamCreate(BaseModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]+$")
    name: str
    mode: TeamMode = TeamMode.chain
    agent_ids: list[str] = Field(default_factory=list)
    leader_agent: str = Field(default="", alias="leaderAgent")
    max_rounds: int = Field(default=1, ge=1, le=20, alias="maxRounds")
    stop_when_idle: bool = Field(default=True, alias="stopWhenIdle")

    model_config = ConfigDict(populate_by_name=True)


class Team(TeamCreate):
    pass


class MessageCreate(BaseModel):
    target: str = Field(description="@agent:id, @team:id, or a bare agent/team id")
    content: str
    sender: str = "api"
    metadata: dict = Field(default_factory=dict)


class QueueMessage(BaseModel):
    id: int
    target: str
    content: str
    sender: str
    metadata: dict = Field(default_factory=dict)
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
    assignee_type: str = Field(default="", alias="assigneeType")
    project_id: str | None = Field(default=None, alias="projectId")
    position: int = 0

    model_config = ConfigDict(populate_by_name=True)


class Task(TaskCreate):
    id: int
    number: int = 0
    identifier: str = ""
    created_at: str
    updated_at: str


class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    prefix: str = ""
    color: str = ""
    status: str = "active"


class Project(ProjectCreate):
    id: str
    created_at: str
    updated_at: str


class TaskCommentCreate(BaseModel):
    author: str = "Web"
    author_type: str = Field(default="user", alias="authorType")
    content: str

    model_config = ConfigDict(populate_by_name=True)


class TaskComment(TaskCommentCreate):
    id: str
    task_id: int
    created_at: str


class ScheduleCreate(BaseModel):
    label: str | None = None
    cron: str = ""
    run_at: str | None = Field(default=None, alias="runAt")
    agent_id: str = Field(alias="agentId")
    message: str
    channel: str = "web"
    sender: str = "Web"
    enabled: bool = True

    model_config = ConfigDict(populate_by_name=True)


class Schedule(BaseModel):
    id: str
    label: str
    cron: str
    run_at: str | None = None
    agent_id: str
    message: str
    channel: str
    sender: str
    enabled: bool
    last_fired_at: int | None = None
    last_fire_key: str | None = None
    created_at: str
    updated_at: str


class AgentMessage(BaseModel):
    id: int
    agent_id: str
    role: str
    channel: str
    sender: str
    message_id: str
    content: str
    created_at: int


class QueueStatus(BaseModel):
    incoming: int
    queued: int
    processing: int
    outgoing: int
    activeConversations: int
    pending: int = 0
    completed: int = 0
    dead: int = 0
    failed: int = 0
    responsesPending: int = 0


class ResponseJob(BaseModel):
    id: int
    message_id: str
    channel: str
    sender: str
    sender_id: str | None = None
    message: str
    original_message: str
    agent: str | None = None
    files: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    status: str
    created_at: int
    acked_at: int | None = None


class Event(BaseModel):
    id: int
    type: str
    payload: dict
    created_at: str
