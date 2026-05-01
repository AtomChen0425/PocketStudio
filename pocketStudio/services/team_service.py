from __future__ import annotations

import json

from pocketStudio.core.database import Database
from pocketStudio.models import Team, TeamCreate


class TeamService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create(self, payload: TeamCreate) -> Team:
        self.db.execute(
            """
            INSERT INTO teams (id, name, mode, agent_ids)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              name = excluded.name,
              mode = excluded.mode,
              agent_ids = excluded.agent_ids,
              updated_at = CURRENT_TIMESTAMP
            """,
            (payload.id, payload.name, payload.mode.value, json.dumps(payload.agent_ids)),
        )
        return self.get(payload.id)

    def get(self, team_id: str) -> Team:
        row = self.db.fetch_one("SELECT * FROM teams WHERE id = ?", (team_id,))
        if row is None:
            raise KeyError(f"Team '{team_id}' not found")
        return self._to_team(row)

    def list(self) -> list[Team]:
        rows = self.db.fetch_all("SELECT * FROM teams ORDER BY id")
        return [self._to_team(row) for row in rows]

    def delete(self, team_id: str) -> None:
        self.db.execute("DELETE FROM teams WHERE id = ?", (team_id,))

    @staticmethod
    def _to_team(row) -> Team:
        return Team(
            id=row["id"],
            name=row["name"],
            mode=row["mode"],
            agent_ids=json.loads(row["agent_ids"]),
        )

