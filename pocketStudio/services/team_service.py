from __future__ import annotations

import json

from pocketStudio.core.config import Settings
from pocketStudio.core.database import Database
from pocketStudio.core.json_store import read_json_object, write_json_object
from pocketStudio.models import Agent, AgentRun, Team, TeamCreate
from pocketStudio.utils.tag_parser import extract_tags, split_candidate_ids, strip_tags


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
                json.dumps(payload.agent_ids, ensure_ascii=False),
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

    def for_agent(self, agent_id: str) -> list[Team]:
        return [team for team in self.list() if agent_id in team.agent_ids]

    @staticmethod
    def order_agents_for_team(team: Team, agents: list[Agent]) -> list[Agent]:
        if not team.leader_agent:
            return agents
        leaders = [agent for agent in agents if agent.id == team.leader_agent]
        others = [agent for agent in agents if agent.id != team.leader_agent]
        return leaders + others if leaders else agents

    @staticmethod
    def resolve_team_context_for_agent(agent_id: str, teams: list[Team]) -> Team | None:
        for team in teams:
            if team.leader_agent == agent_id and agent_id in team.agent_ids:
                return team
        return teams[0] if teams else None

    @staticmethod
    def resolve_team_for_tag(team_id: str, teams: list[Team], agent_id: str) -> Team | None:
        lookup = team_id.lower()
        for team in teams:
            if team.id.lower() == lookup and agent_id in team.agent_ids:
                return team
        return None

    @staticmethod
    def agent_lookup(agents: list[Agent]) -> dict[str, str]:
        return {agent.id.lower(): agent.id for agent in agents}

    def mentions_from_runs(self, runs: list[AgentRun], agents: list[Agent]) -> list[tuple[str, str, str]]:
        agent_by_lookup = self.agent_lookup(agents)
        mentions: list[tuple[str, str, str]] = []
        for run in runs:
            shared_context = strip_tags(run.output, "@")
            seen: set[str] = set()
            for raw_ids, content in extract_tags(run.output, "@"):
                for candidate_id in split_candidate_ids(raw_ids):
                    teammate_id = agent_by_lookup.get(candidate_id)
                    if teammate_id is None or teammate_id in seen or teammate_id == run.agent_id:
                        continue
                    seen.add(teammate_id)
                    routed_content = f"{shared_context}\n\n------\n\nDirected to you:\n{content}" if shared_context else content
                    mentions.append((run.agent_id, teammate_id, routed_content))
        return mentions

    def member_chain_input(
        self,
        team: Team,
        original_request: str,
        leader_run: AgentRun,
        previous_member_runs: list[AgentRun],
        member_id: str,
    ) -> str:
        shared_context = strip_tags(leader_run.output, "@")
        directed = [
            content
            for raw_ids, content in extract_tags(leader_run.output, "@")
            for candidate_id in split_candidate_ids(raw_ids)
            if candidate_id.lower() == member_id.lower()
        ]
        chunks = [
            f"Team #{team.id} request:\n{original_request}",
            f"Team leader @{leader_run.agent_id} context:\n{shared_context or leader_run.output}",
        ]
        if directed:
            chunks.append("Directed to you:\n" + "\n\n".join(directed))
        else:
            chunks.append("Directed to you:\nContribute your part based on the team leader context above.")
        if previous_member_runs:
            chunks.append("Previous teammate results:\n" + self.format_runs(previous_member_runs))
        return "\n\n------\n\n".join(chunks)

    def leader_summary_input(
        self,
        team: Team,
        original_request: str,
        leader_run: AgentRun,
        member_runs: list[AgentRun],
    ) -> str:
        return "\n\n------\n\n".join(
            [
                f"Team #{team.id} original request:\n{original_request}",
                f"Your initial team direction:\n{leader_run.output}",
                "Teammate results:\n" + self.format_runs(member_runs),
                "Produce the final team response for the user. Synthesize the teammate results, keep important details, and call out any unresolved work.",
            ]
        )

    @staticmethod
    def format_runs(runs: list[AgentRun]) -> str:
        return "\n\n".join(f"## @{run.agent_id}\n{run.output}" for run in runs)

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
