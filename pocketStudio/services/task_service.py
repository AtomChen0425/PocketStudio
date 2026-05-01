from __future__ import annotations

from pocketStudio.core.database import Database
from pocketStudio.models import Task, TaskCreate
from pocketStudio.services.event_service import EventService


class TaskService:
    def __init__(self, db: Database, events: EventService) -> None:
        self.db = db
        self.events = events

    def create(self, payload: TaskCreate) -> Task:
        cursor = self.db.execute(
            """
            INSERT INTO tasks (title, description, status, assignee, assignee_type, project_id, position)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.title,
                payload.description,
                payload.status,
                payload.assignee,
                payload.assignee_type,
                payload.project_id,
                payload.position,
            ),
        )
        task = self.get(cursor.lastrowid)
        self.events.emit("task.created", {"task_id": task.id, "title": task.title})
        return task

    def get(self, task_id: int) -> Task:
        row = self.db.fetch_one("SELECT * FROM tasks WHERE id = ?", (task_id,))
        if row is None:
            raise KeyError(f"Task '{task_id}' not found")
        return self._to_task(row)

    def list(self) -> list[Task]:
        rows = self.db.fetch_all("SELECT * FROM tasks ORDER BY id DESC")
        return [self._to_task(row) for row in rows]

    def update(self, task_id: int, payload: TaskCreate) -> Task:
        self.db.execute(
            """
            UPDATE tasks
            SET title = ?, description = ?, status = ?, assignee = ?,
                assignee_type = ?, project_id = ?, position = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                payload.title,
                payload.description,
                payload.status,
                payload.assignee,
                payload.assignee_type,
                payload.project_id,
                payload.position,
                task_id,
            ),
        )
        task = self.get(task_id)
        self.events.emit("task.updated", {"task_id": task.id, "status": task.status})
        return task

    def update_status(self, task_id: int, status: str) -> Task:
        self.db.execute(
            "UPDATE tasks SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, task_id),
        )
        task = self.get(task_id)
        self.events.emit("task.updated", {"task_id": task.id, "status": task.status})
        return task

    def delete(self, task_id: int) -> None:
        self.db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        self.events.emit("task.deleted", {"task_id": task_id})

    @staticmethod
    def _to_task(row) -> Task:
        return Task(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            status=row["status"],
            assignee=row["assignee"],
            assignee_type=row["assignee_type"],
            project_id=row["project_id"],
            position=row["position"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
