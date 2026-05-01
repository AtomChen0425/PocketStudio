from __future__ import annotations

from pocketStudio.core.config import Settings
from pocketStudio.core.database import Database
from pocketStudio.models import Agent, AgentCreate


class AgentService:
    def __init__(self, db: Database, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    def create(self, payload: AgentCreate) -> Agent:
        workspace = payload.workspace or self.settings.workspace_path / payload.id
        workspace.mkdir(parents=True, exist_ok=True)
        self.db.execute(
            """
            INSERT INTO agents (id, name, role, system_prompt, provider, model, workspace, enabled)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              name = excluded.name,
              role = excluded.role,
              system_prompt = excluded.system_prompt,
              provider = excluded.provider,
              model = excluded.model,
              workspace = excluded.workspace,
              enabled = excluded.enabled,
              updated_at = CURRENT_TIMESTAMP
            """,
            (
                payload.id,
                payload.name,
                payload.role,
                payload.system_prompt,
                payload.provider,
                payload.model,
                str(workspace),
                int(payload.enabled),
            ),
        )
        return self.get(payload.id)

    def get(self, agent_id: str) -> Agent:
        row = self.db.fetch_one("SELECT * FROM agents WHERE id = ?", (agent_id,))
        if row is None:
            raise KeyError(f"Agent '{agent_id}' not found")
        return self._to_agent(row)

    def list(self) -> list[Agent]:
        rows = self.db.fetch_all("SELECT * FROM agents ORDER BY id")
        return [self._to_agent(row) for row in rows]

    def delete(self, agent_id: str) -> None:
        self.db.execute("DELETE FROM agents WHERE id = ?", (agent_id,))

    @staticmethod
    def _to_agent(row) -> Agent:
        return Agent(
            id=row["id"],
            name=row["name"],
            role=row["role"],
            system_prompt=row["system_prompt"],
            provider=row["provider"],
            model=row["model"],
            workspace=row["workspace"],
            enabled=bool(row["enabled"]),
        )

