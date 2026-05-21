from pydantic import BaseModel

class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    prefix: str = ""
    color: str = ""
    status: str = "active"
    workspace: str | None = None

class Project(ProjectCreate):
    id: str
    created_at: str
    updated_at: str