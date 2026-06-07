from pydantic import BaseModel, Field, ConfigDict

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

class TaskCommentCreate(BaseModel):
    author: str = "Web"
    author_type: str = Field(default="user", alias="authorType")
    content: str

    model_config = ConfigDict(populate_by_name=True)

class TaskComment(TaskCommentCreate):
    id: str
    task_id: int
    created_at: str