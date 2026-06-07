from pydantic import BaseModel, Field
from pocketStudio.models.enums import MessageStatus

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