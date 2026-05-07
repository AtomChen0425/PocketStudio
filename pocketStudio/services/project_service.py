from __future__ import annotations

from pathlib import Path

from pocketStudio.core.database import Database
from pocketStudio.core.ids import prefixed_id
from pocketStudio.models import Project, ProjectCreate, TaskComment, TaskCommentCreate
from pocketStudio.services.event_service import EventService


class ProjectService:
    PROJECT_COLORS = [
        "#6366f1",
        "#8b5cf6",
        "#ec4899",
        "#f43f5e",
        "#ef4444",
        "#f97316",
        "#eab308",
        "#22c55e",
        "#14b8a6",
        "#06b6d4",
        "#3b82f6",
        "#a855f7",
    ]

    def __init__(self, db: Database, events: EventService) -> None:
        self.db = db
        self.events = events

    def list_projects(self) -> list[Project]:
        rows = self.db.fetch_all("SELECT * FROM projects ORDER BY updated_at DESC")
        return [self._to_project(row) for row in rows]

    def create_project(self, payload: ProjectCreate) -> Project:
        project_id = self._project_id(payload.name)
        count_row = self.db.fetch_one("SELECT COUNT(*) AS count FROM projects")
        project_count = int(count_row["count"]) if count_row else 0
        prefix = payload.prefix or self.generate_prefix(payload.name)
        color = payload.color or self.PROJECT_COLORS[project_count % len(self.PROJECT_COLORS)]
        workspace = self._workspace_path(project_id, payload.workspace)
        self.ensure_workspace(workspace)
        self.db.execute(
            """
            INSERT INTO projects (id, name, description, prefix, color, workspace, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (project_id, payload.name, payload.description, prefix, color, str(workspace), payload.status),
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
        existing = self.get_project(project_id)
        prefix = payload.prefix or existing.prefix or self.generate_prefix(payload.name)
        color = payload.color or existing.color or self.PROJECT_COLORS[0]
        workspace = self._workspace_path(project_id, payload.workspace or existing.workspace)
        self.ensure_workspace(workspace)
        self.db.execute(
            """
            UPDATE projects
            SET name = ?, description = ?, prefix = ?, color = ?, workspace = ?, status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (payload.name, payload.description, prefix, color, str(workspace), payload.status, project_id),
        )
        project = self.get_project(project_id)
        self.events.emit("project.updated", {"project_id": project.id})
        return project

    def project_agent_workspace(self, project_id: str, agent_id: str) -> Path:
        project = self.get_project(project_id)
        workspace = Path(project.workspace) if project.workspace else self._workspace_path(project.id, None)
        path = workspace / ".pocketStudio" / "agents" / agent_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def workspace_status(self, project_id: str, repair: bool = False) -> dict:
        project = self.get_project(project_id)
        workspace = Path(project.workspace) if project.workspace else self._workspace_path(project.id, None)
        before = self._workspace_checks(workspace)
        repaired = [item["path"] for item in before if not item["ok"]]
        if repair and repaired:
            self.ensure_workspace(workspace)
        after = self._workspace_checks(workspace)
        return {
            "ok": all(item["ok"] for item in after),
            "projectId": project.id,
            "workspace": str(workspace),
            "repaired": repaired if repair else [],
            "checks": after,
            "before": before if repair else None,
        }

    @staticmethod
    def ensure_workspace(path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        (path / ".pocketStudio" / "agents").mkdir(parents=True, exist_ok=True)
        (path / ".pocketStudio" / "tasks").mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _workspace_checks(workspace: Path) -> list[dict]:
        checks = [
            ("directory", workspace),
            ("directory", workspace / ".pocketStudio"),
            ("directory", workspace / ".pocketStudio" / "agents"),
            ("directory", workspace / ".pocketStudio" / "tasks"),
        ]
        result = []
        for kind, path in checks:
            result.append(
                {
                    "path": str(path),
                    "relativePath": path.relative_to(workspace).as_posix() if path != workspace else ".",
                    "kind": kind,
                    "ok": path.is_dir(),
                }
            )
        return result

    def delete_project(self, project_id: str) -> None:
        task_rows = self.db.fetch_all("SELECT id FROM tasks WHERE project_id = ? ORDER BY id ASC", (project_id,))
        for row in task_rows:
            next_number = self._next_global_task_number()
            self.db.execute(
                """
                UPDATE tasks
                SET project_id = NULL,
                    number = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (next_number, row["id"]),
            )
        self.db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        self.events.emit("project.deleted", {"project_id": project_id, "detached_tasks": len(task_rows)})

    def task_count(self, project_id: str) -> int:
        row = self.db.fetch_one("SELECT COUNT(*) AS count FROM tasks WHERE project_id = ?", (project_id,))
        return int(row["count"]) if row else 0

    def list_comments(self, task_id: int) -> list[TaskComment]:
        rows = self.db.fetch_all("SELECT * FROM task_comments WHERE task_id = ? ORDER BY created_at", (task_id,))
        return [self._to_comment(row) for row in rows]

    def create_comment(self, task_id: int, payload: TaskCommentCreate) -> TaskComment:
        comment_id = prefixed_id("comment")
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
        return prefixed_id(slug or "project")

    @staticmethod
    def _workspace_path(project_id: str, workspace: str | None) -> Path:
        if workspace:
            return Path(workspace).expanduser()
        return Path(".pocketStudio") / "projects" / project_id

    @staticmethod
    def generate_prefix(name: str) -> str:
        words = [word for word in name.strip().split() if word]
        if not words:
            return "T"
        if len(words) == 1:
            return words[0][:3].upper()
        return "".join(word[0].upper() for word in words[:3])

    def _next_global_task_number(self) -> int:
        row = self.db.fetch_one("SELECT COALESCE(MAX(number), 0) + 1 AS next_number FROM tasks WHERE project_id IS NULL")
        return int(row["next_number"]) if row else 1

    @staticmethod
    def _to_project(row) -> Project:
        return Project(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            prefix=row["prefix"],
            color=row["color"],
            workspace=row["workspace"],
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
