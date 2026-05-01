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
        self.queue.mark_done(message_id, result.model_dump_json())
        return result

    async def _dispatch(self, message: QueueMessage) -> OrchestrationResult:
        target_type, target_id = self._parse_target(message.target)
        if target_type == "agent":
            agent = self.agents.get(target_id)
            run = await self._run_agent(agent, message.content, [])
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
            current_input = message.content
            context: list[str] = []
            for agent in agents:
                run = await self._run_agent(agent, current_input, context)
                runs.append(run)
                context.append(run.output)
                current_input = run.output
            output = runs[-1].output
        else:
            runs = await asyncio.gather(*(self._run_agent(agent, message.content, []) for agent in agents))
            output = "\n\n".join(f"## {run.agent_id}\n{run.output}" for run in runs)

        self.chat.post(team.id, ChatMessageCreate(sender="orchestrator", message=output))
        return OrchestrationResult(message_id=message.id, target=message.target, runs=runs, output=output)

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
