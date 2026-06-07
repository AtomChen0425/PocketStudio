from pydantic import BaseModel, Field, ConfigDict
from pocketStudio.models.enums import TeamMode

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