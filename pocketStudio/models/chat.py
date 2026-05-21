from pydantic import BaseModel

class ChatMessageCreate(BaseModel):
    message: str
    sender: str = "api"

class ChatMessage(BaseModel):
    id: int
    team_id: str
    sender: str
    message: str
    created_at: str