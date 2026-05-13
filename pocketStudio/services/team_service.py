from __future__ import annotations

import json

from pocketStudio.core.config import Settings
from pocketStudio.core.database import Database
from pocketStudio.core.json_store import read_json_object, write_json_object
from pocketStudio.models import Team, TeamCreate


class TeamService:
    def __init__(self, db: Database, settings: Settings | None = None) -> None:
        self.db = db
        self.settings = settings

    def create(self, payload: TeamCreate) -> Team:
        leader_agent = payload.leader_agent or (payload.agent_ids[0] if payload.agent_ids else "")
        self.db.execute(
            """
            INSERT INTO teams (id, name, mode, agent_ids, leader_agent, max_rounds, stop_when_idle)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              name = excluded.name,
              mode = excluded.mode,
              agent_ids = excluded.agent_ids,
              leader_agent = excluded.leader_agent,
              max_rounds = excluded.max_rounds,
              stop_when_idle = excluded.stop_when_idle,
              updated_at = CURRENT_TIMESTAMP
            """,
            (
                payload.id,
                payload.name,
                payload.mode.value,
                json.dumps(payload.agent_ids),
                leader_agent,
                payload.max_rounds,
                int(payload.stop_when_idle),
            ),
        )
        team = self.get(payload.id)
        self._sync_team_settings(team)
        return team

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
        self._remove_team_settings(team_id)

    def add_member(self, team_id: str, agent_id: str) -> Team:
        team = self.get(team_id)
        agent_ids = list(team.agent_ids)
        if agent_id not in agent_ids:
            agent_ids.append(agent_id)
        return self.create(
            TeamCreate(
                id=team.id,
                name=team.name,
                mode=team.mode,
                agent_ids=agent_ids,
                leader_agent=team.leader_agent or agent_ids[0],
                max_rounds=team.max_rounds,
                stop_when_idle=team.stop_when_idle,
            )
        )

    def remove_member(self, team_id: str, agent_id: str) -> Team:
        team = self.get(team_id)
        agent_ids = [existing for existing in team.agent_ids if existing != agent_id]
        leader_agent = team.leader_agent
        if leader_agent == agent_id:
            leader_agent = agent_ids[0] if agent_ids else ""
        return self.create(
            TeamCreate(
                id=team.id,
                name=team.name,
                mode=team.mode,
                agent_ids=agent_ids,
                leader_agent=leader_agent,
                max_rounds=team.max_rounds,
                stop_when_idle=team.stop_when_idle,
            )
        )

    def set_leader(self, team_id: str, agent_id: str) -> Team:
        team = self.get(team_id)
        agent_ids = list(team.agent_ids)
        if agent_id not in agent_ids:
            agent_ids.append(agent_id)
        return self.create(
            TeamCreate(
                id=team.id,
                name=team.name,
                mode=team.mode,
                agent_ids=agent_ids,
                leader_agent=agent_id,
                max_rounds=team.max_rounds,
                stop_when_idle=team.stop_when_idle,
            )
        )

    def _sync_team_settings(self, team: Team) -> None:
        if self.settings is None:
            return
        data = read_json_object(self.settings.settings_path)
        teams = data.setdefault("teams", {})
        teams[team.id] = {
            "name": team.name,
            "agents": team.agent_ids,
            "leader_agent": team.leader_agent or (team.agent_ids[0] if team.agent_ids else ""),
            "mode": team.mode,
            "max_rounds": team.max_rounds,
            "stop_when_idle": team.stop_when_idle,
        }
        write_json_object(self.settings.settings_path, data)

    def _remove_team_settings(self, team_id: str) -> None:
        if self.settings is None:
            return
        data = read_json_object(self.settings.settings_path)
        teams = data.get("teams")
        if isinstance(teams, dict) and team_id in teams:
            teams.pop(team_id, None)
            write_json_object(self.settings.settings_path, data)

    @staticmethod
    def _to_team(row) -> Team:
        return Team(
            id=row["id"],
            name=row["name"],
            mode=row["mode"],
            agent_ids=json.loads(row["agent_ids"]),
            leader_agent=row["leader_agent"] or "",
            max_rounds=row["max_rounds"],
            stop_when_idle=bool(row["stop_when_idle"]),
        )
