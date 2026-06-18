from __future__ import annotations

import json
import operator
from collections import defaultdict, deque
from pathlib import Path
from typing import Annotated, Any, Awaitable, Callable, TypedDict

from pocketStudio.core.database import Database
from pocketStudio.core.ids import prefixed_id
from pocketStudio.models import Agent, AgentRun, ChatMessageCreate, OrchestrationResult, QueueMessage, Team, TeamWorkflow, TeamWorkflowCreate, TeamWorkflowUpdate, WorkflowDefinition
from pocketStudio.services.chat_service import ChatService
from pocketStudio.services.event_service import EventService
from pocketStudio.services.queue_service import QueueService
from pocketStudio.services.team_service import TeamService

_WORKFLOW_SUMMARY_COMPACT_EVERY = 5
_WORKFLOW_RUNNING_SUMMARY_LIMIT = 1000


def merge_dicts(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    return {**left, **right}


def merge_workflow_memory(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    return right


class WorkflowMemoryState(TypedDict):
    running_summary: str
    recent_outputs: list[dict[str, str]]
    nodes_since_compaction: int


class WorkflowState(TypedDict):
    original_request: str
    memory: Annotated[WorkflowMemoryState, merge_workflow_memory]
    outputs: Annotated[dict[str, str], merge_dicts]
    runs_by_node: Annotated[dict[str, AgentRun], merge_dicts]
    runs: Annotated[list[AgentRun], operator.add]
    run_order: Annotated[list[str], operator.add]


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

    async def run_workflow(
        self,
        message: QueueMessage,
        team: Team,
        agents: list[Agent],
        workflow: TeamWorkflow,
        *,
        run_agent: Callable[..., Awaitable[AgentRun]],
        queue: QueueService,
        chat: ChatService,
        events: EventService,
        project_workspace_for_message: Callable[[QueueMessage], Path | None],
    ) -> OrchestrationResult:
        definition = workflow.definition
        order = self._topological_order(definition)
        node_by_id = {node.id: node for node in definition.nodes}
        agent_by_id = {agent.id: agent for agent in agents}
        outgoing, predecessors = self.graph_io(definition)

        compiled_graph = self._build_langgraph_workflow(
            team=team,
            workflow_id=workflow.id,
            message=message,
            agents=agents,
            node_by_id=node_by_id,
            agent_by_id=agent_by_id,
            predecessors=predecessors,
            outgoing=outgoing,
            edge_pairs=[(edge.source, edge.target) for edge in definition.edges],
            conditional_edges=definition.conditional_edges,
            entrypoint=definition.entrypoint,
            run_agent=run_agent,
            queue=queue,
            events=events,
            project_workspace_for_message=project_workspace_for_message,
        )
        state = await compiled_graph.ainvoke(
            {
                "original_request": message.content,
                "memory": self._initial_workflow_memory(),
                "outputs": {},
                "runs_by_node": {},
                "runs": [],
                "run_order": [],
            },
            {"recursion_limit": 50},
        )
        runs = state.get("runs", [])
        outputs = state["outputs"]

        output_node = definition.output_node or order[-1]
        output = outputs.get(output_node) or (runs[-1].output if runs else "")
        if chat.is_chatroom_origin(message):
            chat.post_chatroom_run_outputs(team, runs)
        else:
            chat.post(team.id, ChatMessageCreate(sender="TeamManager", message=output))
        events.emit(
            "team.workflow.completed",
            {"team_id": team.id, "workflow_id": workflow.id, "nodes": len(runs), "output_node": output_node},
        )
        return OrchestrationResult(message_id=message.id, target=message.target, runs=runs, output=output)

    @staticmethod
    def workflow_node_input(
        team: Team,
        workflow_id: str,
        original_request: str,
        memory: WorkflowMemoryState,
        node,
        node_name: str,
        predecessor_ids: list[str],
        outputs: dict[str, str],
    ) -> str:
        lastNode_output = WorkflowService.format_workflow_predecessors(predecessor_ids, outputs)
        recent_text = WorkflowService.format_recent_workflow_outputs(memory["recent_outputs"])
        if node.input_template:
            try:
                return node.input_template.format(
                    team_id=team.id,
                    workflow_id=workflow_id,
                    node_name=node_name,
                    agent_id=node.agent_id,
                    message=original_request,
                    running_summary=memory["running_summary"],
                    recent_outputs=recent_text,
                    direct_predecessor_outputs=lastNode_output,
                    predecessor_outputs=lastNode_output,
                )
            except KeyError as exc:
                raise ValueError(f"Workflow node '{node.id}' inputTemplate references unknown field: {exc}") from exc
        chunks = [f"Team #{team.id} workflow '{workflow_id}' request:\n{original_request}"]
        if memory["running_summary"].strip():
            chunks.append(f"Running summary:\n{memory['running_summary'].strip()}")
        if recent_text:
            chunks.append(f"Last node outputs:\n{lastNode_output}")
        if node_name:
            chunks.append(f"Your are:\n{node_name}")
        if node.prompt:
            chunks.append(f"Your Need to:\n{node.prompt}")
        # if predecessor_text:
        #     chunks.append(f"Upstream results:\n{predecessor_text}")
        return "\n\n------\n\n".join(chunks)

    @classmethod
    def format_workflow_predecessors(cls, predecessor_ids: list[str], outputs: dict[str, str]) -> str:
        if not predecessor_ids:
            return ""

        chunks: list[str] = []
        for predecessor_id in predecessor_ids:
            if predecessor_id not in outputs:
                continue
            chunks.append(f"## {predecessor_id}\n{outputs[predecessor_id]}")

        return "\n\n".join(chunks)

    @staticmethod
    def summarize_workflow_output(text: str, max_length: int = 240) -> str:
        '''
        TODO: add LLM to handle summarize
        '''
        cleaned = " ".join(line.strip() for line in text.splitlines() if line.strip())
        if not cleaned:
            return "(empty)"
        if len(cleaned) <= max_length:
            return cleaned
        return f"{cleaned[: max_length - 1].rstrip()}..."

    @staticmethod
    def format_recent_workflow_outputs(recent_outputs: list[dict[str, str]]) -> str:
        if not recent_outputs:
            return ""
        return "\n\n".join(f"## node '{item['node_id']}' response: \n{item['output']}" for item in recent_outputs)

    @staticmethod
    def _initial_workflow_memory() -> WorkflowMemoryState:
        return {"running_summary": "", "recent_outputs": [], "nodes_since_compaction": 0}

    def _workflow_memory_after_run(self, memory: WorkflowMemoryState, node_id: str, output: str) -> WorkflowMemoryState:
        updated: WorkflowMemoryState = {
            "running_summary": memory["running_summary"],
            "recent_outputs": [*memory["recent_outputs"], {"node_id": node_id, "output": output}],
            "nodes_since_compaction": memory["nodes_since_compaction"] + 1,
        }
        if updated["nodes_since_compaction"] < _WORKFLOW_SUMMARY_COMPACT_EVERY:
            return updated
        return self._compact_workflow_memory(updated)

    def _compact_workflow_memory(self, memory: WorkflowMemoryState) -> WorkflowMemoryState:
        recent_text = self.format_recent_workflow_outputs(memory["recent_outputs"]).strip()
        if recent_text:
            chunk = self.summarize_workflow_output(recent_text, max_length=_WORKFLOW_RUNNING_SUMMARY_LIMIT)
            running_summary = memory["running_summary"].strip()
            merged = "\n\n".join(part for part in [running_summary, chunk] if part).strip()
            memory = {
                "running_summary": self.summarize_workflow_output(
                    merged,
                    max_length=_WORKFLOW_RUNNING_SUMMARY_LIMIT,
                ),
                "recent_outputs": [],
                "nodes_since_compaction": 0,
            }
        else:
            memory = {
                "running_summary": memory["running_summary"],
                "recent_outputs": [],
                "nodes_since_compaction": 0,
            }
        return memory

    @staticmethod
    def _langchain_runnable_for_agent(agent: Agent, run_agent: Callable[..., Awaitable[AgentRun]]):
        try:
            from langchain_core.runnables import RunnableLambda
        except ImportError as exc:
            raise RuntimeError("LangChain is required to execute team workflows") from exc

        async def run_agent_node(payload: dict) -> AgentRun:
            return await run_agent(
                agent,
                payload["input"],
                payload.get("context", []),
                message_id=payload.get("message_id"),
                session_id=payload.get("session_id"),
                run_id=payload.get("run_id"),
                teams=payload.get("teams"),
                project_workspace=payload.get("project_workspace"),
            )

        return RunnableLambda(run_agent_node)

    def _build_langgraph_workflow(
        self,
        *,
        team: Team,
        workflow_id: str,
        message: QueueMessage,
        agents: list[Agent],
        node_by_id: dict[str, Any],
        agent_by_id: dict[str, Agent],
        predecessors: dict[str, list[str]],
        outgoing: dict[str, list[str]],
        edge_pairs: list[tuple[str, str]],
        conditional_edges: list[Any],
        entrypoint: str,
        run_agent: Callable[..., Awaitable[AgentRun]],
        queue: QueueService,
        events: EventService,
        project_workspace_for_message: Callable[[QueueMessage], Path | None],
    ):
        try:
            from langgraph.graph import END, StateGraph
        except ImportError as exc:
            raise RuntimeError("LangGraph is required to execute team workflows") from exc

        graph = StateGraph(WorkflowState)
        for node_id, node in node_by_id.items():
            agent = agent_by_id.get(node.agent_id) if node.type == "agent" else None
            if node.type == "agent" and agent is None:
                raise ValueError(f"Workflow node '{node.id}' references unavailable agent '{node.agent_id}'")
            runnable = self._langchain_runnable_for_agent(agent, run_agent) if agent is not None else None

            async def run_node(state: WorkflowState, *, node=node, agent=agent, runnable=runnable) -> dict:
                memory = state["memory"]
                if agent is not None:
                    node_name = agent.name
                elif node.type == "start":
                    node_name = "Start"
                elif node.type == "end":
                    node_name = "End"
                elif node.type == "tool":
                    node_name = node.prompt or "Tool"
                else:
                    node_name = node.prompt or node.id
                input_text = self.workflow_node_input(
                    team,
                    workflow_id,
                    state["original_request"],
                    memory,
                    node,
                    node_name,
                    predecessors[node.id],
                    state["outputs"],
                )
                context = [state["outputs"][source] for source in predecessors[node.id] if source in state["outputs"]]
                if node.type == "agent" and agent is not None and runnable is not None:
                    queue.insert_agent_message(agent.id, "user", input_text, str(message.id), sender=f"workflow:{workflow_id}")
                    run = await runnable.ainvoke(
                        {
                            "input": input_text,
                            "context": context,
                            "teams": [team],
                            "project_workspace": project_workspace_for_message(message),
                        }
                    )
                    queue.insert_agent_message(agent.id, "assistant", run.output, str(message.id), sender=agent.id)
                elif node.type == "start":
                    run = AgentRun(agent_id=node.id, input=input_text, output=state["original_request"])
                elif node.type == "end":
                    output = context[-1] if context else state["original_request"]
                    run = AgentRun(agent_id=node.id, input=input_text, output=output)
                else:
                    output = node.prompt or (context[-1] if context else state["original_request"])
                    run = AgentRun(agent_id=node.id, input=input_text, output=output)
                next_memory = self._workflow_memory_after_run(memory, node.id, run.output)
                return {
                    "memory": next_memory,
                    "outputs": {node.id: run.output},
                    "runs_by_node": {node.id: run},
                    "runs": [run],
                    "run_order": [node.id],
                }

            graph.add_node(node_id, run_node)

        graph.set_entry_point(entrypoint)
        for source, target in edge_pairs:
            graph.add_edge(source, target)
        for conditional_edge in conditional_edges:
            route_map = {route.condition: route.target for route in conditional_edge.routes}
            default_route = "__default__"
            route_map[default_route] = conditional_edge.default_target or END
            source_node = node_by_id[conditional_edge.source]
            custom_route = self.compile_workflow_routing_function(source_node) if source_node.routing_function else None

            def route_from_output(
                state: WorkflowState,
                *,
                conditional_edge=conditional_edge,
                route_map=route_map,
                custom_route=custom_route,
            ) -> str:
                if custom_route is not None:
                    route = custom_route(state)
                else:
                    source_output = state["outputs"].get(conditional_edge.source, "")
                    route = self.route_from_output(source_output, [route.condition for route in conditional_edge.routes])
                selected_route = route if route in route_map else default_route
                target = route_map[selected_route]
                events.emit(
                    "team.workflow.route",
                    {
                        "team_id": team.id,
                        "workflow_id": workflow_id,
                        "source": conditional_edge.source,
                        "route": selected_route,
                        "target": target if target != END else "END",
                    },
                )
                return selected_route

            graph.add_conditional_edges(conditional_edge.source, route_from_output, route_map)

        terminal_nodes = [node_id for node_id in node_by_id if not outgoing.get(node_id)]
        for node_id in terminal_nodes:
            graph.add_edge(node_id, END)
        compiled = graph.compile()
        events.emit("team.workflow.runtime", {"runtime": "langgraph"})
        return compiled

    @staticmethod
    def compile_workflow_routing_function(node) -> Any:
        routing_function = node.routing_function
        if routing_function is None:
            raise ValueError(f"Workflow node '{node.id}' does not define routingFunction")
        if routing_function.language != "python":
            raise ValueError(
                f"Workflow node '{node.id}' routingFunction language '{routing_function.language}' is not supported"
            )
        namespace: dict[str, Any] = {}
        safe_builtins = {
            "all": all,
            "any": any,
            "bool": bool,
            "dict": dict,
            "float": float,
            "int": int,
            "len": len,
            "list": list,
            "max": max,
            "min": min,
            "set": set,
            "sorted": sorted,
            "str": str,
            "sum": sum,
            "tuple": tuple,
        }
        globals_dict = {"__builtins__": safe_builtins, "json": json}
        try:
            exec(routing_function.code, globals_dict, namespace)
        except Exception as exc:
            raise ValueError(f"Workflow node '{node.id}' routingFunction failed to compile: {exc}") from exc
        route_callable = namespace.get(routing_function.entrypoint) or globals_dict.get(routing_function.entrypoint)
        if not callable(route_callable):
            raise ValueError(
                f"Workflow node '{node.id}' routingFunction entrypoint '{routing_function.entrypoint}' is not callable"
            )

        def route(state: WorkflowState) -> str:
            try:
                selected_route = route_callable(state)
            except Exception as exc:
                raise ValueError(f"Workflow node '{node.id}' routingFunction failed: {exc}") from exc
            if not isinstance(selected_route, str):
                raise ValueError(f"Workflow node '{node.id}' routingFunction must return a string route")
            return selected_route

        return route

    @staticmethod
    def route_from_output(output: str, conditions: list[str]) -> str:
        try:
            parsed = json.loads(output)
            if isinstance(parsed, dict):
                route = parsed.get("route")
                if isinstance(route, str):
                    return route
        except json.JSONDecodeError:
            pass
        lowered_output = output.lower()
        for condition in conditions:
            if condition.lower() in lowered_output:
                return condition
        return "__default__"

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
