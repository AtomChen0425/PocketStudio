from pydantic import BaseModel, Field, ConfigDict

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