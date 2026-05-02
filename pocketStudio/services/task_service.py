from __future__ import annotations

from pocketStudio.core.database import Database
from pocketStudio.models import Task, TaskCreate
from pocketStudio.services.event_service import EventService


class TaskService:
    def __init__(self, db: Database, events: EventService) -> None:
        self.db = db
        self.events = events

    def create(self, payload: TaskCreate) -> Task:
        number = self._next_number(payload.project_id)
        position = payload.position if payload.position else self._next_position(payload.status)
        cursor = self.db.execute(
            """
            INSERT INTO tasks (number, title, description, status, assignee, assignee_type, project_id, position)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                number,
                payload.title,
                payload.description,
                payload.status,
                payload.assignee,
                payload.assignee_type,
                payload.project_id,
                position,
            ),
        )
        task = self.get(cursor.lastrowid)
        self.events.emit("task.created", {"task_id": task.id, "title": task.title})
        return task

    def get(self, task_id: int) -> Task:
        row = self.db.fetch_one(
            """
            SELECT tasks.*, projects.prefix AS project_prefix
            FROM tasks
            LEFT JOIN projects ON tasks.project_id = projects.id
            WHERE tasks.id = ?
            """,
            (task_id,),
        )
        if row is None:
            raise KeyError(f"Task '{task_id}' not found")
        return self._to_task(row)

    def list(
        self,
        project_id: str | None = None,
        status: str | None = None,
        assignee: str | None = None,
        query: str | None = None,
    ) -> list[Task]:
        filters = []
        params: list[str] = []
        if project_id:
            filters.append("tasks.project_id = ?")
            params.append(project_id)
        if status:
            filters.append("tasks.status = ?")
            params.append(status)
        if assignee:
            filters.append("tasks.assignee = ?")
            params.append(assignee)
        if query:
            filters.append("(tasks.title LIKE ? OR tasks.description LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%"])
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        rows = self.db.fetch_all(
            f"""
            SELECT tasks.*, projects.prefix AS project_prefix
            FROM tasks
            LEFT JOIN projects ON tasks.project_id = projects.id
            {where}
            ORDER BY tasks.status ASC, tasks.position ASC, tasks.id ASC
            """,
            params,
        )
        return [self._to_task(row) for row in rows]

    def update(self, task_id: int, payload: TaskCreate) -> Task:
        current = self.get(task_id)
        number = current.number if payload.project_id == current.project_id else self._next_number(payload.project_id)
        self.db.execute(
            """
            UPDATE tasks
            SET number = ?, title = ?, description = ?, status = ?, assignee = ?,
                assignee_type = ?, project_id = ?, position = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                number,
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

    def reorder(self, columns: dict[str, list[str]]) -> int:
        updated = 0
        for status, task_ids in columns.items():
            for position, raw_task_id in enumerate(task_ids):
                try:
                    task_id = int(raw_task_id)
                except (TypeError, ValueError):
                    continue
                self.db.execute(
                    """
                    UPDATE tasks
                    SET status = ?, position = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (status, position, task_id),
                )
                updated += 1
        if updated:
            self.events.emit("tasks.reordered", {"count": updated})
        return updated

    def delete(self, task_id: int) -> None:
        self.db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        self.events.emit("task.deleted", {"task_id": task_id})

    @staticmethod
    def _to_task(row) -> Task:
        number = row["number"] or row["id"]
        prefix = row["project_prefix"] if "project_prefix" in row.keys() else None
        return Task(
            id=row["id"],
            number=number,
            identifier=f"{prefix or 'T'}-{number}",
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

    def _next_number(self, project_id: str | None) -> int:
        if project_id:
            row = self.db.fetch_one(
                "SELECT COALESCE(MAX(number), 0) + 1 AS next_number FROM tasks WHERE project_id = ?",
                (project_id,),
            )
        else:
            row = self.db.fetch_one("SELECT COALESCE(MAX(number), 0) + 1 AS next_number FROM tasks WHERE project_id IS NULL")
        return int(row["next_number"]) if row else 1

    def _next_position(self, status: str) -> int:
        row = self.db.fetch_one(
            "SELECT COALESCE(MAX(position), -1) + 1 AS next_position FROM tasks WHERE status = ?",
            (status,),
        )
        return int(row["next_position"]) if row else 0
