from pydantic import BaseModel

class Event(BaseModel):
    id: int
    type: str
    payload: dict
    created_at: str