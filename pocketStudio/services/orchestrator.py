from __future__ import annotations

import asyncio
import json
from typing import Any
from pathlib import Path

from pocketStudio.models import (
    Agent,
    AgentRun,
    ChatMessageCreate,
    MessageCreate,
    OrchestrationResult,
    QueueMessage,
    Team,
    TeamMode,
)
from pocketStudio.providers.registry import ProviderRegistry
from pocketStudio.services.agent_service import AgentService
from pocketStudio.services.chat_service import ChatService
from pocketStudio.services.event_service import EventService
from pocketStudio.services.project_service import ProjectService
from pocketStudio.services.queue_service import QueueService
from pocketStudio.services.team_service import TeamService
from pocketStudio.services.workflow_service import WorkflowService
from pocketStudio.utils.tag_parser import (
    extract_tags,
    strip_tags,
    split_candidate_ids,
)


class Orchestrator:
    def __init__(
        self,
        agents: AgentService,
        teams: TeamService,
        queue: QueueService,
        chat: ChatService,
        events: EventService,
        providers: ProviderRegistry,
        projects: ProjectService | None = None,
        workflows: WorkflowService | None = None,
    ) -> None:
        self.agents = agents
        self.teams = teams
        self.queue = queue
        self.chat = chat
        self.events = events
        self.providers = providers
        self.projects = projects
        self.workflows = workflows
    def enqueue(self, payload: MessageCreate) -> QueueMessage:
        return self.queue.enqueue(payload)

    def _project_workspace_for_message(self, message: QueueMessage) -> Path | None:
        project_id = message.metadata.get("projectId") or message.metadata.get("project_id")
        if not project_id or self.projects is None:
            return None
        return self.projects.project_agent_workspace(str(project_id), "")

    async def reset_agent_session(
        self,
        agent_id: str,
        *,
        cleared: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        return await self.agents.reset_runtime(
            agent_id,
            providers=self.providers,
            events=self.events,
            cleared=cleared,
        )

    async def process_one(self, newest: bool = False) -> OrchestrationResult | None:
        message = self.queue.next_queued(newest=newest)
        if message is None:
            return None
        return await self.process_message(message.id)

    async def process_message(self, message_id: int) -> OrchestrationResult:
        message = self.queue.mark_running(message_id)
        try:
            result = await self._dispatch(message)
        except Exception as exc:
            self.queue.mark_failed(message_id, str(exc))
            raise
        completed = self.queue.mark_done(message_id, result.model_dump_json())
        self.queue.enqueue_responses_from_message(completed)
        return result

    async def _dispatch(self, message: QueueMessage) -> OrchestrationResult:
        target_type, target_id = self._parse_target(message.target)
        if target_type == "agent":
            agent = self._agent_for_message(target_id, message)
            project_workspace = self._project_workspace_for_message(message)
            self.queue.insert_agent_message(
                agent.id,
                "user",
                message.content,
                str(message.id),
                sender=message.sender,
            )
            run = await self._run_agent(
                agent,
                message.content,
                [],
                message_id=message.id,
                teams=self.teams.for_agent(agent.id),
                project_workspace=project_workspace,
            )
            self.queue.insert_agent_message(agent.id, "assistant", run.output, str(message.id), sender=agent.id)
            await self._handle_direct_agent_team_tags(agent, run, message)
            return OrchestrationResult(
                message_id=message.id,
                target=message.target,
                runs=[run],
                output=run.output,
            )

        team = self.teams.get(target_id)
        return await self._run_team(message, team)

    async def _run_team(self, message: QueueMessage, team: Team) -> OrchestrationResult:
        agents = [self._agent_for_message(agent_id, message) for agent_id in team.agent_ids]
        if not agents:
            raise ValueError(f"Team '{team.id}' has no agents")

        if team.mode == TeamMode.workflow:
            if self.workflows is None:
                raise ValueError(f"Team '{team.id}' is in workflow mode but workflow service is unavailable")
            workflow = self.workflows.active_for_team(team.id)
            if workflow is None:
                raise ValueError(f"Team '{team.id}' is in workflow mode but has no active workflow")
            return await self._run_workflow(message, team, agents, workflow)

        leader_run_for_summary: AgentRun | None = None
        leader_agent_for_summary: Agent | None = None
        chat_sender = "TeamManager"
        if team.mode == TeamMode.chain:
            runs: list[AgentRun] = []
            ordered_agents = self.teams.order_agents_for_team(team, agents)
            context: list[str] = []
            chatroom_origin = self.chat.is_chatroom_origin(message)
            project_workspace = self._project_workspace_for_message(message)
            leader = ordered_agents[0]
            chat_sender = leader.name
            leader_agent_for_summary = leader
            member_agents = ordered_agents[1:]
            if not chatroom_origin:
                self.queue.insert_agent_message(
                    leader.id,
                    "user",
                    message.content,
                    str(message.id),
                    sender=message.sender,
                )
            leader_run = await self._run_agent(
                leader,
                message.content,
                context,
                message_id=message.id,
                teams=[team],
                project_workspace=project_workspace,
            )
            leader_run_for_summary = leader_run
            runs.append(leader_run)
            self.queue.insert_agent_message(leader.id, "assistant", leader_run.output, str(message.id), sender=leader.id)
            context.append(leader_run.output)
            await self._handle_team_tags(team, leader_run, message, agents, enqueue_mentions=team.max_rounds <= 1)

            for agent in member_agents:
                member_input = self.teams.member_chain_input(team, message.content, leader_run, runs[1:], agent.id)
                run = await self._run_agent(
                    agent,
                    member_input,
                    context,
                    message_id=message.id,
                    teams=[team],
                    project_workspace=project_workspace,
                )
                runs.append(run)
                self.queue.insert_agent_message(agent.id, "assistant", run.output, str(message.id), sender=agent.id)
                context.append(run.output)
                await self._handle_team_tags(team, run, message, agents, enqueue_mentions=team.max_rounds <= 1)

            output = runs[-1].output
        else:
            ordered_agents = self.teams.order_agents_for_team(team, agents)
            chat_sender = ordered_agents[0].name if ordered_agents else "TeamManager"
            project_workspace = self._project_workspace_for_message(message)
            runs = await asyncio.gather(
                *(
                    self._run_agent(
                        agent,
                        message.content,
                        [],
                        message_id=message.id,
                        teams=[team],
                        project_workspace=project_workspace,
                    )
                    for agent in ordered_agents
                )
            )
            for run in runs:
                self.queue.insert_agent_message(
                    run.agent_id,
                    "user",
                    message.content,
                    str(message.id),
                    sender=message.sender,
                )
                self.queue.insert_agent_message(run.agent_id, "assistant", run.output, str(message.id), sender=run.agent_id)
                await self._handle_team_tags(team, run, message, agents, enqueue_mentions=team.max_rounds <= 1)
            output = "\n\n".join(f"## {run.agent_id}\n{run.output}" for run in runs)

        if team.max_rounds > 1:
            iterative_runs = await self._run_iterative_rounds(team, message, agents, runs, max_rounds=team.max_rounds)
            runs.extend(iterative_runs)
            if iterative_runs:
                output = "\n\n".join(f"## {run.agent_id}\n{run.output}" for run in runs)

        if (
            team.mode == TeamMode.chain
            and leader_agent_for_summary is not None
            and leader_run_for_summary is not None
            and not self.chat.is_chatroom_origin(message)
            and any(run.agent_id != leader_agent_for_summary.id for run in runs)
        ):
            member_results = [run for run in runs if run is not leader_run_for_summary]
            summary_input = self.teams.leader_summary_input(team, message.content, leader_run_for_summary, member_results)
            self.queue.insert_agent_message(
                leader_agent_for_summary.id,
                "user",
                summary_input,
                str(message.id),
                sender=f"team:{team.id}",
            )
            final_run = await self._run_agent(
                leader_agent_for_summary,
                summary_input,
                [run.output for run in runs],
                message_id=message.id,
                teams=[team],
                project_workspace=self._project_workspace_for_message(message),
            )
            runs.append(final_run)
            self.queue.insert_agent_message(
                leader_agent_for_summary.id,
                "assistant",
                final_run.output,
                str(message.id),
                sender=leader_agent_for_summary.id,
            )
            output = final_run.output

        if self.chat.is_chatroom_origin(message):
            self.chat.post_chatroom_run_outputs(team, runs)
        else:
            self.chat.post(team.id, ChatMessageCreate(sender=chat_sender, message=output))
        return OrchestrationResult(message_id=message.id, target=message.target, runs=runs, output=output)

    async def _run_workflow(self, message: QueueMessage, team: Team, agents: list[Agent], workflow) -> OrchestrationResult:
        if self.workflows is None:
            raise ValueError(f"Team '{team.id}' is in workflow mode but workflow service is unavailable")
        return await self.workflows.run_workflow(
            message,
            team,
            agents,
            workflow,
            run_agent=self._run_agent,
            queue=self.queue,
            chat=self.chat,
            events=self.events,
            project_workspace_for_message=self._project_workspace_for_message,
        )

    @staticmethod
    def _summarize_workflow_output(text: str, max_length: int = 240) -> str:
        
        '''TODO: use LLM summarize'''
        cleaned = " ".join(line.strip() for line in text.splitlines() if line.strip())
        if not cleaned:
            return "(empty)"
        if len(cleaned) <= max_length:
            return cleaned
        return f"{cleaned[: max_length - 1].rstrip()}…"

    async def _run_iterative_rounds(
        self,
        team: Team,
        message: QueueMessage,
        agents: list[Agent],
        seed_runs: list[AgentRun],
        max_rounds: int,
    ) -> list[AgentRun]:
        agent_by_id = {agent.id: agent for agent in agents}
        produced: list[AgentRun] = []
        frontier = self.teams.mentions_from_runs(seed_runs, agents)
        seen_pairs: set[tuple[str, str]] = set()
        current_round = 1
        while frontier and current_round < max_rounds:
            next_frontier: list[tuple[str, str, str]] = []
            for from_agent, to_agent, content in frontier:
                if to_agent not in agent_by_id:
                    continue
                pair = (from_agent, to_agent)
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                agent = agent_by_id[to_agent]
                self.queue.insert_agent_message(agent.id, "user", content, str(message.id), sender=f"team:{team.id}:{from_agent}")
                run = await self._run_agent(
                    agent,
                    content,
                    [existing.output for existing in seed_runs + produced],
                    message_id=message.id,
                    teams=[team],
                    project_workspace=self._project_workspace_for_message(message),
                )
                produced.append(run)
                self.queue.insert_agent_message(agent.id, "assistant", run.output, str(message.id), sender=agent.id)
                await self._handle_team_tags(team, run, message, agents, enqueue_mentions=False)
                next_frontier.extend(self.teams.mentions_from_runs([run], agents))
            if not next_frontier and team.stop_when_idle:
                break
            frontier = next_frontier
            current_round += 1
        if produced:
            self.events.emit("team.iteration", {"team_id": team.id, "rounds": current_round, "runs": len(produced)})
        return produced
    async def _handle_team_tags(
        self,
        team: Team,
        run: AgentRun,
        message: QueueMessage,
        agents: list[Agent],
        enqueue_mentions: bool = True,
        process_chatrooms: bool = True,
    ) -> None:
        agent_by_lookup = self.teams.agent_lookup(agents)
        if process_chatrooms:
            for team_id, content in extract_tags(run.output, "#"):
                if team_id.lower() == team.id.lower():
                    self.chat.post(team.id, ChatMessageCreate(sender=run.agent_id, message=content))
                    delivered = self.chat.broadcast_chatroom(self.queue, team, run.agent_id, content, agents, message)
                    self.events.emit("team.chatroom", {"team_id": team.id, "from_agent": run.agent_id, "delivered": delivered})

        shared_context = strip_tags(run.output, "@")
        seen_mentions: set[str] = set()
        for raw_ids, content in extract_tags(run.output, "@"):
            for candidate_id in split_candidate_ids(raw_ids):
                teammate_id = agent_by_lookup.get(candidate_id)
                if teammate_id is None or teammate_id in seen_mentions or teammate_id == run.agent_id:
                    continue
                seen_mentions.add(teammate_id)
                if not enqueue_mentions:
                    continue
                routed_content = f"{shared_context}\n\n------\n\nDirected to you:\n{content}" if shared_context else content
                self.queue.enqueue(
                    MessageCreate(
                        target=f"@agent:{teammate_id}",
                        content=routed_content,
                        sender=f"team:{team.id}:{run.agent_id}",
                        metadata=self.chat.team_child_metadata(
                            message,
                            team=team,
                            from_agent=run.agent_id,
                            kind="mention",
                            to_agent=teammate_id,
                        ),
                    )
                )
                self.events.emit(
                    "agent.mention",
                    {"team_id": team.id, "from_agent": run.agent_id, "to_agent": teammate_id},
                )

    async def _handle_direct_agent_team_tags(self, agent: Agent, run: AgentRun, message: QueueMessage) -> None:
        agent_teams = self.teams.for_agent(agent.id)
        if not agent_teams:
            return

        agents_by_team: dict[str, list[Agent]] = {}
        for team in agent_teams:
            members = [self.agents.get(agent_id) for agent_id in team.agent_ids]
            members = [self._agent_for_message(member.id, message) for member in members]
            agents_by_team[team.id] = members

        for team_id, content in extract_tags(run.output, "#"):
            team = self.teams.resolve_team_for_tag(team_id, agent_teams, agent.id)
            if team is None:
                continue
            self.chat.post(team.id, ChatMessageCreate(sender=agent.id, message=content))
            delivered = self.chat.broadcast_chatroom(self.queue, team, agent.id, content, agents_by_team[team.id], message)
            self.events.emit("team.chatroom", {"team_id": team.id, "from_agent": agent.id, "delivered": delivered})

        mention_team = self.teams.resolve_team_context_for_agent(agent.id, agent_teams)
        if mention_team is not None:
            await self._handle_team_tags(mention_team, run, message, agents_by_team[mention_team.id], process_chatrooms=False)

    def dispatch_team_message(
        self,
        team_id: str,
        message: str,
        *,
        sender: str = "user",
        chat_message_id: int | None = None,
        conn: Any | None = None,
        emit_event: bool = True,
    ) -> dict[str, Any]:
        team = self.teams.get(team_id)
        return self.chat.dispatch_team_message(
            self.queue,
            team,
            message,
            sender=sender,
            chat_message_id=chat_message_id,
            conn=conn,
            emit_event=emit_event,
        )

    async def _run_agent(
        self,
        agent: Agent,
        input_text: str,
        context: list[str],
        *,
        message_id: int | str | None = None,
        session_id: str | None = None,
        run_id: str | None = None,
        teams: list[Team] | None = None,
        project_workspace: Path | None = None,
    ) -> AgentRun:
        return await self.agents.run_agent(
            agent,
            input_text,
            context,
            providers=self.providers,
            events=self.events,
            message_id=message_id,
            session_id=session_id,
            run_id=run_id,
            teams=teams if teams is not None else self.teams.for_agent(agent.id),
            project_workspace=project_workspace,
        )

    def _agent_for_message(self, agent_id: str, message: QueueMessage) -> Agent:
        return self.agents.get(agent_id)

    @staticmethod
    def _parse_target(target: str) -> tuple[str, str]:
        if target.startswith("@agent:"):
            return "agent", target.split(":", 1)[1]
        if target.startswith("@team:"):
            return "team", target.split(":", 1)[1]
        if target.startswith("@"):
            return "agent", target[1:]
        return "team", target

    @staticmethod
    def decode_result(message: QueueMessage) -> OrchestrationResult | None:
        if not message.result:
            return None
        return OrchestrationResult(**json.loads(message.result))
