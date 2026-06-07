from pydantic import BaseModel

class AgentRun(BaseModel):
    agent_id: str
    input: str
    output: str

class OrchestrationResult(BaseModel):
    message_id: int
    target: str
    runs: list[AgentRun]
    output: str