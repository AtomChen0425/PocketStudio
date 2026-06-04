from __future__ import annotations

import json
from collections import defaultdict, deque
from typing import Any

from pocketStudio.core.database import Database
from pocketStudio.core.ids import prefixed_id
from pocketStudio.models import TeamWorkflow, TeamWorkflowCreate, TeamWorkflowUpdate, WorkflowDefinition
from pocketStudio.services.team_service import TeamService


class WorkflowService:
    def __init__(self, db: Database, teams: TeamService) -> None:
        self.db = db
        self.teams = teams

    def create(self, team_id: str, payload: TeamWorkflowCreate) -> TeamWorkflow:
        self._validate_definition_for_team(team_id, payload.definition)
        if payload.enabled:
            self._disable_other_workflows(team_id, payload.id)
        self.db.execute(
            """
            INSERT INTO team_workflows (id, team_id, name, description, definition, enabled)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(team_id, id) DO UPDATE SET
              name = excluded.name,
              description = excluded.description,
              definition = excluded.definition,
              enabled = excluded.enabled,
              updated_at = CURRENT_TIMESTAMP
            """,
            (
                payload.id,
                team_id,
                payload.name,
                payload.description,
                payload.definition.model_dump_json(by_alias=True),
                int(payload.enabled),
            ),
        )
        return self.get(team_id, payload.id)

    def list(self, team_id: str) -> list[TeamWorkflow]:
        self.teams.get(team_id)
        rows = self.db.fetch_all(
            "SELECT * FROM team_workflows WHERE team_id = ? ORDER BY enabled DESC, id",
            (team_id,),
        )
        return [self._to_workflow(row) for row in rows]

    def get(self, team_id: str, workflow_id: str) -> TeamWorkflow:
        row = self.db.fetch_one(
            "SELECT * FROM team_workflows WHERE team_id = ? AND id = ?",
            (team_id, workflow_id),
        )
        if row is None:
            raise KeyError(f"Workflow '{workflow_id}' for team '{team_id}' not found")
        return self._to_workflow(row)

    def active_for_team(self, team_id: str) -> TeamWorkflow | None:
        row = self.db.fetch_one(
            """
            SELECT * FROM team_workflows
            WHERE team_id = ? AND enabled = 1
            ORDER BY updated_at DESC, id
            LIMIT 1
            """,
            (team_id,),
        )
        return self._to_workflow(row) if row else None

    def update(self, team_id: str, workflow_id: str, payload: TeamWorkflowUpdate) -> TeamWorkflow:
        current = self.get(team_id, workflow_id)
        definition = payload.definition or current.definition
        self._validate_definition_for_team(team_id, definition)
        enabled = current.enabled if payload.enabled is None else payload.enabled
        if enabled:
            self._disable_other_workflows(team_id, workflow_id)
        self.db.execute(
            """
            UPDATE team_workflows
            SET name = ?, description = ?, definition = ?, enabled = ?, updated_at = CURRENT_TIMESTAMP
            WHERE team_id = ? AND id = ?
            """,
            (
                payload.name if payload.name is not None else current.name,
                payload.description if payload.description is not None else current.description,
                definition.model_dump_json(by_alias=True),
                int(enabled),
                team_id,
                workflow_id,
            ),
        )
        return self.get(team_id, workflow_id)

    def delete(self, team_id: str, workflow_id: str) -> None:
        self.db.execute("DELETE FROM team_workflows WHERE team_id = ? AND id = ?", (team_id, workflow_id))

    def export_json(self, team_id: str, workflow_id: str) -> dict[str, Any]:
        workflow = self.get(team_id, workflow_id)
        return {
            "format": "pocketstudio.team.workflow",
            "formatVersion": 1,
            "sourceTeamId": team_id,
            "workflow": {
                "id": workflow.id,
                "name": workflow.name,
                "description": workflow.description,
                "enabled": workflow.enabled,
                "definition": workflow.definition.model_dump(by_alias=True, mode="json"),
            },
        }

    def import_json(self, team_id: str, payload: dict[str, Any]) -> TeamWorkflow:
        return self.create(team_id, self._payload_from_import_json(payload))

    def validate(self, team_id: str, definition: WorkflowDefinition) -> dict:
        order = self._validate_definition_for_team(team_id, definition)
        return {"ok": True, "order": order}

    @staticmethod
    def _payload_from_import_json(payload: dict[str, Any]) -> TeamWorkflowCreate:
        raw_workflow = payload.get("workflow") if isinstance(payload.get("workflow"), dict) else payload
        if "definition" in raw_workflow:
            definition_data = raw_workflow["definition"]
            workflow_id = raw_workflow.get("id") or prefixed_id("workflow")
            name = raw_workflow.get("name") or "Imported Workflow"
            description = raw_workflow.get("description", "")
            enabled = raw_workflow.get("enabled", True)
        elif "entrypoint" in payload and "nodes" in payload:
            definition_data = payload
            metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
            workflow_id = metadata.get("id") or prefixed_id("workflow")
            name = metadata.get("name") or "Imported Workflow"
            description = metadata.get("description", "")
            enabled = metadata.get("enabled", True)
        else:
            raise ValueError("Workflow import JSON must contain either 'workflow.definition', 'definition', or a workflow definition")
        return TeamWorkflowCreate(
            id=workflow_id,
            name=name,
            description=description,
            enabled=enabled,
            definition=WorkflowDefinition(**definition_data),
        )

    def _validate_definition_for_team(self, team_id: str, definition: WorkflowDefinition) -> list[str]:
        team = self.teams.get(team_id)
        team_agents = set(team.agent_ids)
        missing_agents = sorted(
            [node.agent_id for node in definition.nodes if node.type == "agent" and node.agent_id not in team_agents]
        )
        if missing_agents:
            raise ValueError(f"Workflow references agents outside team'{team_id}': {', '.join(missing_agents)}")
        normal_sources = {edge.source for edge in definition.edges}
        conditional_sources = {edge.source for edge in definition.conditional_edges}
        overlapping_sources = sorted(normal_sources & conditional_sources)
        if overlapping_sources:
            raise ValueError(
                "Workflow nodes cannot mix normal and conditional outgoing edges: "
                + ", ".join(overlapping_sources)
            )
        conditional_sources = {edge.source for edge in definition.conditional_edges}
        routing_function_sources = sorted(
            node.id for node in definition.nodes if node.routing_function is not None and node.id not in conditional_sources
        )
        if routing_function_sources:
            raise ValueError(
                "Workflow routingFunction can only be set on conditional source nodes: "
                + ", ".join(routing_function_sources)
            )
        return self._topological_order(definition)

    @staticmethod
    def graph_io(definition: WorkflowDefinition) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
        node_ids = {node.id for node in definition.nodes}
        outgoing: dict[str, list[str]] = defaultdict(list)
        predecessors: dict[str, list[str]] = defaultdict(list)
        for node_id in node_ids:
            outgoing[node_id] = []
            predecessors[node_id] = []
        for edge in definition.edges:
            outgoing[edge.source].append(edge.target)
            predecessors[edge.target].append(edge.source)
        for conditional_edge in definition.conditional_edges:
            targets = [route.target for route in conditional_edge.routes]
            if conditional_edge.default_target:
                targets.append(conditional_edge.default_target)
            for target in sorted(set(targets)):
                outgoing[conditional_edge.source].append(target)
                predecessors[target].append(conditional_edge.source)
        return dict(outgoing), dict(predecessors)

    @staticmethod
    def terminal_nodes(definition: WorkflowDefinition) -> list[str]:
        outgoing, _predecessors = WorkflowService.graph_io(definition)
        return [node.id for node in definition.nodes if not outgoing.get(node.id)]

    @staticmethod
    def _topological_order(definition: WorkflowDefinition) -> list[str]:
        node_ids = {node.id for node in definition.nodes}
        outgoing, _predecessors = WorkflowService.graph_io(definition)

        queue = deque([definition.entrypoint])
        visited: list[str] = []
        seen: set[str] = set()
        while queue:
            node_id = queue.popleft()
            if node_id in seen:
                continue
            seen.add(node_id)
            visited.append(node_id)
            for target in outgoing[node_id]:
                queue.append(target)

        if set(visited) != node_ids:
            unreachable = sorted(node_ids - set(visited))
            raise ValueError(f"Workflow graph must be reachable from entrypoint: {', '.join(unreachable)}")
        return visited

    def _disable_other_workflows(self, team_id: str, workflow_id: str) -> None:
        self.db.execute(
            "UPDATE team_workflows SET enabled = 0, updated_at = CURRENT_TIMESTAMP WHERE team_id = ? AND id != ?",
            (team_id, workflow_id),
        )

    @staticmethod
    def _to_workflow(row) -> TeamWorkflow:
        return TeamWorkflow(
            id=row["id"],
            team_id=row["team_id"],
            name=row["name"],
            description=row["description"],
            definition=WorkflowDefinition(**json.loads(row["definition"])),
            enabled=bool(row["enabled"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
