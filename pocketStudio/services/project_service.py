from __future__ import annotations

import time
from uuid import uuid4

from pocketStudio.core.database import Database
from pocketStudio.models import Project, ProjectCreate, TaskComment, TaskCommentCreate
from pocketStudio.services.event_service import EventService


class ProjectService:
    def __init__(self, db: Database, events: EventService) -> None:
        self.db = db
        self.events = events

    def list_projects(self) -> list[Project]:
        rows = self.db.fetch_all("SELECT * FROM projects ORDER BY updated_at DESC")
        return [self._to_project(row) for row in rows]

    def create_project(self, payload: ProjectCreate) -> Project:
        project_id = self._project_id(payload.name)
        self.db.execute(
            """
            INSERT INTO projects (id, name, description, prefix, color, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (project_id, payload.name, payload.description, payload.prefix, payload.color, payload.status),
        )
        project = self.get_project(project_id)
        self.events.emit("project.created", {"project_id": project.id, "name": project.name})
        return project

    def get_project(self, project_id: str) -> Project:
        row = self.db.fetch_one("SELECT * FROM projects WHERE id = ?", (project_id,))
        if row is None:
            raise KeyError(f"Project '{project_id}' not found")
        return self._to_project(row)

    def update_project(self, project_id: str, payload: ProjectCreate) -> Project:
        self.db.execute(
            """
            UPDATE projects
            SET name = ?, description = ?, prefix = ?, color = ?, status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (payload.name, payload.description, payload.prefix, payload.color, payload.status, project_id),
        )
        project = self.get_project(project_id)
        self.events.emit("project.updated", {"project_id": project.id})
        return project

    def delete_project(self, project_id: str) -> None:
        self.db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        self.events.emit("project.deleted", {"project_id": project_id})

    def list_comments(self, task_id: int) -> list[TaskComment]:
        rows = self.db.fetch_all("SELECT * FROM task_comments WHERE task_id = ? ORDER BY created_at", (task_id,))
        return [self._to_comment(row) for row in rows]

    def create_comment(self, task_id: int, payload: TaskCommentCreate) -> TaskComment:
        comment_id = f"comment-{uuid4().hex[:12]}"
        self.db.execute(
            """
            INSERT INTO task_comments (id, task_id, author, author_type, content)
            VALUES (?, ?, ?, ?, ?)
            """,
            (comment_id, task_id, payload.author, payload.author_type, payload.content),
        )
        row = self.db.fetch_one("SELECT * FROM task_comments WHERE id = ?", (comment_id,))
        comment = self._to_comment(row)
        self.events.emit("task.comment.created", {"task_id": task_id, "comment_id": comment_id})
        return comment

    def delete_comment(self, comment_id: str) -> None:
        self.db.execute("DELETE FROM task_comments WHERE id = ?", (comment_id,))
        self.events.emit("task.comment.deleted", {"comment_id": comment_id})

    @staticmethod
    def _project_id(name: str) -> str:
        slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in name).strip("-")
        return f"{slug or 'project'}-{int(time.time() * 1000)}"

    @staticmethod
    def _to_project(row) -> Project:
        return Project(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            prefix=row["prefix"],
            color=row["color"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _to_comment(row) -> TaskComment:
        return TaskComment(
            id=row["id"],
            task_id=row["task_id"],
            author=row["author"],
            author_type=row["author_type"],
            content=row["content"],
            created_at=row["created_at"],
        )

