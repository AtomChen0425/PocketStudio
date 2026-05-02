from __future__ import annotations

import asyncio
import json

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
from pocketStudio.providers.base import ProviderRequest
from pocketStudio.providers.registry import ProviderRegistry
from pocketStudio.services.agent_service import AgentService
from pocketStudio.services.chat_service import ChatService
from pocketStudio.services.event_service import EventService
from pocketStudio.services.queue_service import QueueService
from pocketStudio.services.team_service import TeamService


class TeamActions:
    def __init__(self, mentions: list[tuple[str, str]], chatrooms: list[tuple[str, str]]) -> None:
        self.mentions = mentions
        self.chatrooms = chatrooms


class Orchestrator:
    def __init__(
        self,
        agents: AgentService,
        teams: TeamService,
        queue: QueueService,
        chat: ChatService,
        events: EventService,
        providers: ProviderRegistry,
    ) -> None:
        self.agents = agents
        self.teams = teams
        self.queue = queue
        self.chat = chat
        self.events = events
        self.providers = providers

    def enqueue(self, payload: MessageCreate) -> QueueMessage:
        return self.queue.enqueue(payload)

    async def process_one(self) -> OrchestrationResult | None:
        message = self.queue.next_queued()
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
            agent = self.agents.get(target_id)
            self.queue.insert_agent_message(
                agent.id,
                "user",
                message.content,
                str(message.id),
                sender=message.sender,
            )
            run = await self._run_agent(agent, message.content, [])
            self.queue.insert_agent_message(agent.id, "assistant", run.output, str(message.id), sender=agent.id)
            return OrchestrationResult(
                message_id=message.id,
                target=message.target,
                runs=[run],
                output=run.output,
            )

        team = self.teams.get(target_id)
        return await self._run_team(message, team)

    async def _run_team(self, message: QueueMessage, team: Team) -> OrchestrationResult:
        agents = [self.agents.get(agent_id) for agent_id in team.agent_ids]
        if not agents:
            raise ValueError(f"Team '{team.id}' has no agents")

        if team.mode == TeamMode.chain:
            runs: list[AgentRun] = []
            ordered_agents = self._order_agents_for_team(team, agents)
            current_input = message.content
            context: list[str] = []
            for agent in ordered_agents:
                self.queue.insert_agent_message(
                    agent.id,
                    "user",
                    current_input,
                    str(message.id),
                    sender=message.sender,
                )
                run = await self._run_agent(agent, current_input, context)
                runs.append(run)
                self.queue.insert_agent_message(agent.id, "assistant", run.output, str(message.id), sender=agent.id)
                context.append(run.output)
                await self._handle_team_tags(team, run, message, agents, enqueue_mentions=team.max_rounds <= 1)
                current_input = run.output
            output = runs[-1].output
        else:
            ordered_agents = self._order_agents_for_team(team, agents)
            runs = await asyncio.gather(*(self._run_agent(agent, message.content, []) for agent in ordered_agents))
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

        self.chat.post(team.id, ChatMessageCreate(sender="orchestrator", message=output))
        return OrchestrationResult(message_id=message.id, target=message.target, runs=runs, output=output)

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
        frontier = self._mentions_from_runs(team, seed_runs, agents)
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
                run = await self._run_agent(agent, content, [existing.output for existing in seed_runs + produced])
                produced.append(run)
                self.queue.insert_agent_message(agent.id, "assistant", run.output, str(message.id), sender=agent.id)
                await self._handle_team_tags(team, run, message, agents, enqueue_mentions=False)
                next_frontier.extend(self._mentions_from_runs(team, [run], agents))
            if not next_frontier and team.stop_when_idle:
                break
            frontier = next_frontier
            current_round += 1
        if produced:
            self.events.emit("team.iteration", {"team_id": team.id, "rounds": current_round, "runs": len(produced)})
        return produced

    def _mentions_from_runs(self, team: Team, runs: list[AgentRun], agents: list[Agent]) -> list[tuple[str, str, str]]:
        agent_ids = {agent.id for agent in agents}
        mentions: list[tuple[str, str, str]] = []
        for run in runs:
            shared_context = self._strip_tags(run.output, "@")
            seen: set[str] = set()
            for raw_ids, content in self._extract_tags(run.output, "@"):
                for teammate_id in [item.strip() for item in raw_ids.split(",") if item.strip()]:
                    if teammate_id in seen or teammate_id == run.agent_id or teammate_id not in agent_ids:
                        continue
                    seen.add(teammate_id)
                    routed_content = f"{shared_context}\n\n------\n\nDirected to you:\n{content}" if shared_context else content
                    mentions.append((run.agent_id, teammate_id, routed_content))
        return mentions

    async def _handle_team_tags(
        self,
        team: Team,
        run: AgentRun,
        message: QueueMessage,
        agents: list[Agent],
        enqueue_mentions: bool = True,
    ) -> None:
        agent_ids = {agent.id for agent in agents}
        for team_id, content in self._extract_tags(run.output, "#"):
            if team_id == team.id:
                self.chat.post(team.id, ChatMessageCreate(sender=run.agent_id, message=content))
                delivered = self._broadcast_chatroom(team, run.agent_id, content, agents, message)
                self.events.emit("team.chatroom", {"team_id": team.id, "from_agent": run.agent_id, "delivered": delivered})

        shared_context = self._strip_tags(run.output, "@")
        seen_mentions: set[str] = set()
        for raw_ids, content in self._extract_tags(run.output, "@"):
            for teammate_id in [item.strip() for item in raw_ids.split(",") if item.strip()]:
                if teammate_id in seen_mentions or teammate_id == run.agent_id or teammate_id not in agent_ids:
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
                        metadata=self._team_child_metadata(
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

    def _broadcast_chatroom(self, team: Team, from_agent: str, content: str, agents: list[Agent], parent: QueueMessage) -> int:
        delivered = 0
        agent_ids = {agent.id for agent in agents}
        chat_message = f"[Chat room #{team.id} - @{from_agent}]:\n{content}"
        for teammate_id in team.agent_ids:
            if teammate_id == from_agent or teammate_id not in agent_ids:
                continue
            self.queue.enqueue(
                MessageCreate(
                    target=f"@agent:{teammate_id}",
                    content=chat_message,
                    sender=f"chatroom:{team.id}:{from_agent}",
                    metadata=self._team_child_metadata(
                        parent,
                        team=team,
                        from_agent=from_agent,
                        kind="chatroom",
                        to_agent=teammate_id,
                    ),
                )
            )
            delivered += 1
        return delivered

    @staticmethod
    def _team_child_metadata(
        parent: QueueMessage | None,
        *,
        team: Team,
        from_agent: str,
        kind: str,
        to_agent: str,
    ) -> dict:
        parent_metadata = parent.metadata if parent else {}
        metadata = {
            "kind": kind,
            "teamId": team.id,
            "fromAgent": from_agent,
            "toAgent": to_agent,
            "parentMessageId": str(parent.id) if parent else None,
            "parentTarget": parent.target if parent else None,
            "channel": parent_metadata.get("channel", "team"),
            "sender": parent.sender if parent else "",
            "senderId": parent_metadata.get("senderId") or parent_metadata.get("sender_id"),
        }
        return {key: value for key, value in metadata.items() if value is not None}

    @staticmethod
    def _order_agents_for_team(team: Team, agents: list[Agent]) -> list[Agent]:
        if not team.leader_agent:
            return agents
        leaders = [agent for agent in agents if agent.id == team.leader_agent]
        others = [agent for agent in agents if agent.id != team.leader_agent]
        return leaders + others if leaders else agents

    @staticmethod
    def _extract_tags(text: str, prefix: str) -> list[tuple[str, str]]:
        return [(tag_id, message) for tag_id, message, _, _ in Orchestrator._extract_bracket_tags(text, prefix)]

    @staticmethod
    def _strip_tags(text: str, prefix: str) -> str:
        tags = Orchestrator._extract_bracket_tags(text, prefix)
        if not tags:
            return text
        result = ""
        last_end = 0
        for _, _, start, end in tags:
            result += text[last_end:start]
            last_end = end
        result += text[last_end:]
        return result.strip()

    @staticmethod
    def _extract_bracket_tags(text: str, prefix: str) -> list[tuple[str, str, int, int]]:
        tags: list[tuple[str, str, int, int]] = []
        i = 0
        while i < len(text):
            if text[i] != "[" or i + 1 >= len(text) or text[i + 1] != prefix:
                i += 1
                continue
            tag_start = i
            colon_index = text.find(":", i + 2)
            if colon_index == -1:
                i += 1
                continue
            tag_id = text[i + 2 : colon_index].strip()
            if not tag_id or "[" in tag_id or "]" in tag_id:
                i += 1
                continue
            depth = 1
            j = colon_index + 1
            while j < len(text) and depth > 0:
                if text[j] == "[":
                    depth += 1
                elif text[j] == "]":
                    depth -= 1
                j += 1
            if depth == 0:
                tags.append((tag_id, text[colon_index + 1 : j - 1].strip(), tag_start, j))
            i = j
        return tags

    async def _run_agent(self, agent: Agent, input_text: str, context: list[str]) -> AgentRun:
        if not agent.enabled:
            raise ValueError(f"Agent '{agent.id}' is disabled")
        provider = self.providers.get(agent.provider)
        self.events.emit("agent.started", {"agent_id": agent.id, "provider": agent.provider})
        response = await provider.run(ProviderRequest(agent=agent, input=input_text, context=context))
        self.events.emit("agent.completed", {"agent_id": agent.id, "content": response.text})
        return AgentRun(agent_id=agent.id, input=input_text, output=response.text)

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
