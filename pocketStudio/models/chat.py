from pydantic import BaseModel, ConfigDict, Field

class ChatMessageCreate(BaseModel):
    message: str
    sender: str = "api"
    client_message_id: str | None = Field(default=None, alias="clientMessageId")

    model_config = ConfigDict(populate_by_name=True)

class ChatMessage(BaseModel):
    id: int
    team_id: str
    sender: str
    message: str
    client_message_id: str | None = None
    dispatch_status: str | None = None
    dispatch_queued_count: int | None = None
    dispatch_message_ids: list[int] = Field(default_factory=list)
    created_at: str
