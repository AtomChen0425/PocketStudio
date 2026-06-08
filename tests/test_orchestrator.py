import asyncio
import json
import shutil
import uuid
from pathlib import Path

from pocketStudio.core.config import Settings
from pocketStudio.core.database import Database
from pocketStudio.models import ChatMessageCreate, AgentCreate, AgentRun, MessageCreate, MessageStatus, ProjectCreate, TeamCreate, TeamMode, TeamWorkflowCreate
from pocketStudio.providers.base import AgentProvider, ProviderRequest, ProviderResponse
from pocketStudio.providers.registry import ProviderRegistry
from pocketStudio.services.agent_service import AgentService
from pocketStudio.services.chat_service import ChatService
from pocketStudio.services.event_service import EventService
from pocketStudio.services.orchestrator import Orchestrator
from pocketStudio.services.project_service import ProjectService
from pocketStudio.services.queue_service import QueueService
from pocketStudio.services.team_service import TeamService
from pocketStudio.services.team_routing import convert_tags_to_readable, extract_bracket_tags, strip_bracket_tags
from pocketStudio.services.workflow_service import WorkflowService


def temp_home() -> Path:
    root = Path(".pytest-tmp")
    root.mkdir(exist_ok=True)
    home = root / uuid.uuid4().hex
    home.mkdir()
    return home


def build_orchestrator(home: Path) -> Orchestrator:
    settings = Settings(pocketStudio_home=home)
    db = Database(settings.database_path, journal_mode=settings.sqlite_journal_mode)
    db.initialize()
    events = EventService(db)
    return Orchestrator(
        agents=AgentService(db, settings),
        teams=TeamService(db),
        queue=QueueService(db, events, settings),
        chat=ChatService(db, events),
        events=events,
        providers=ProviderRegistry(),
    )


class WorkspaceRecordingProvider(AgentProvider):
    name = "recording"

    def __init__(self) -> None:
        self.workspaces: list[Path] = []

    async def run(self, request: ProviderRequest) -> ProviderResponse:
        self.workspaces.append(request.agent.workspace)
        return ProviderResponse(text=f"workspace={request.agent.workspace}")


class AgentIdEchoProvider(AgentProvider):
    name = "agent-id-echo"

    async def run(self, request: ProviderRequest) -> ProviderResponse:
        return ProviderResponse(text=f"{request.agent.id} says hello")


class TeamRelayProvider(AgentProvider):
    name = "team-relay"

    def __init__(self) -> None:
        self.inputs: list[tuple[str, str]] = []

    async def run(self, request: ProviderRequest) -> ProviderResponse:
        self.inputs.append((request.agent.id, request.input))
        if request.agent.id == "lead" and "Teammate results:" in request.input:
            return ProviderResponse(text=f"final summary includes teammates:\n{request.input}")
        if request.agent.id == "lead":
            return ProviderResponse(text="Leader plan [@coder: implement API] [@reviewer: review design]")
        return ProviderResponse(text=f"{request.agent.id} result from:\n{request.input}")


class SystemPromptRecordingProvider(AgentProvider):
    name = "system-prompt-recording"

    def __init__(self) -> None:
        self.system_prompts: list[str | None] = []

    async def run(self, request: ProviderRequest) -> ProviderResponse:
        self.system_prompts.append(request.agent.system_prompt)
        return ProviderResponse(text=request.agent.system_prompt or "missing system prompt")


class WorkflowRecordingProvider(AgentProvider):
    name = "workflow-recording"

    def __init__(self) -> None:
        self.inputs: list[tuple[str, str]] = []

    async def run(self, request: ProviderRequest) -> ProviderResponse:
        self.inputs.append((request.agent.id, request.input))
        return ProviderResponse(text=f"{request.agent.id} handled:\n{request.input}")


class ConditionalWorkflowProvider(AgentProvider):
    name = "conditional-workflow"

    def __init__(self, review_output: str) -> None:
        self.review_output = review_output
        self.agent_ids: list[str] = []

    async def run(self, request: ProviderRequest) -> ProviderResponse:
        self.agent_ids.append(request.agent.id)
        if request.agent.id == "reviewer":
            return ProviderResponse(text=self.review_output)
        return ProviderResponse(text=f"{request.agent.id} done")


def test_chain_team_processes_agents_in_order() -> None:
    home = temp_home()
    try:
        orchestrator = build_orchestrator(home)
        orchestrator.agents.create(AgentCreate(id="planner", name="Planner", role="Plans work"))
        orchestrator.agents.create(AgentCreate(id="coder", name="Coder", role="Writes code"))
        orchestrator.teams.create(
            TeamCreate(id="dev", name="Dev", mode=TeamMode.chain, agent_ids=["planner", "coder"])
        )

        message = orchestrator.enqueue(MessageCreate(target="@team:dev", content="Build an API"))
        result = asyncio.run(orchestrator.process_message(message.id))
        stored = orchestrator.queue.get(message.id)
        chat = orchestrator.chat.list("dev")

        assert stored.status == "done"
        assert [run.agent_id for run in result.runs] == ["planner", "coder", "planner"]
        assert result.output == result.runs[-1].output
        assert "Teammate results:" in result.output
        assert chat[0].message == result.output
    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_team_chain_does_not_store_teammate_output_as_user_input() -> None:
    home = temp_home()
    try:
        orchestrator = build_orchestrator(home)
        orchestrator.providers.register(AgentIdEchoProvider())
        orchestrator.agents.create(AgentCreate(id="planner", name="Planner", role="Plans", provider="agent-id-echo"))
        orchestrator.agents.create(AgentCreate(id="coder", name="Coder", role="Codes", provider="agent-id-echo"))
        orchestrator.teams.create(TeamCreate(id="dev", name="Dev", mode=TeamMode.chain, agent_ids=["planner", "coder"]))

        message = orchestrator.enqueue(MessageCreate(target="@team:dev", content="Build it", sender="Web"))
        asyncio.run(orchestrator.process_message(message.id))

        planner_messages = orchestrator.queue.get_agent_messages("planner")
        coder_messages = orchestrator.queue.get_agent_messages("coder")
        assert [item.role for item in planner_messages] == ["user", "assistant", "user", "assistant"]
        assert [item.role for item in coder_messages] == ["assistant"]
        assert all(not (item.role == "user" and "planner says hello" in item.content) for item in coder_messages)
        assert "coder says hello" in planner_messages[-2].content
    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_direct_agent_run_uses_full_system_prompt() -> None:
    home = temp_home()
    try:
        orchestrator = build_orchestrator(home)
        provider = SystemPromptRecordingProvider()
        orchestrator.providers.register(provider)
        orchestrator.agents.create(
            AgentCreate(id="planner", name="Planner", role="Plans", provider="system-prompt-recording")
        )
        orchestrator.agents.create(AgentCreate(id="coder", name="Coder", role="Codes", provider="system-prompt-recording"))
        orchestrator.teams.create(TeamCreate(id="dev", name="Dev", mode=TeamMode.chain, agent_ids=["planner", "coder"]))
        orchestrator.agents.save_system_prompt_file("planner", "Always answer in bullet points.")

        message = orchestrator.enqueue(MessageCreate(target="@agent:planner", content="Draft a plan"))
        asyncio.run(orchestrator.process_message(message.id))

        assert provider.system_prompts
        prompt = provider.system_prompts[0] or ""
        assert "Stay proactive and responsive to messages." in prompt
        assert "### You" in prompt
        assert "### Team `#dev`" in prompt
        assert "Always answer in bullet points." in prompt
        assert "coder" in prompt
    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_chain_team_leader_directs_members_and_summarizes_their_results() -> None:
    home = temp_home()
    try:
        orchestrator = build_orchestrator(home)
        provider = TeamRelayProvider()
        orchestrator.providers.register(provider)
        orchestrator.agents.create(AgentCreate(id="lead", name="Lead", role="Leads", provider="team-relay"))
        orchestrator.agents.create(AgentCreate(id="coder", name="Coder", role="Codes", provider="team-relay"))
        orchestrator.agents.create(AgentCreate(id="reviewer", name="Reviewer", role="Reviews", provider="team-relay"))
        orchestrator.teams.create(
            TeamCreate(
                id="dev",
                name="Dev",
                mode=TeamMode.chain,
                agent_ids=["lead", "coder", "reviewer"],
                leaderAgent="lead",
            )
        )

        message = orchestrator.enqueue(MessageCreate(target="@team:dev", content="Build the API"))
        result = asyncio.run(orchestrator.process_message(message.id))

        assert [run.agent_id for run in result.runs] == ["lead", "coder", "reviewer", "lead"]
        coder_input = next(input_text for agent_id, input_text in provider.inputs if agent_id == "coder")
        reviewer_input = next(input_text for agent_id, input_text in provider.inputs if agent_id == "reviewer")
        final_leader_input = provider.inputs[-1][1]
        assert "Team leader @lead context:" in coder_input
        assert "Directed to you:\nimplement API" in coder_input
        assert "Directed to you:\nreview design" in reviewer_input
        assert "## @coder" in final_leader_input
        assert "## @reviewer" in final_leader_input
        assert result.output.startswith("final summary includes teammates")
    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_chatroom_origin_records_agent_outputs_without_orchestrator_echo() -> None:
    home = temp_home()
    try:
        orchestrator = build_orchestrator(home)
        orchestrator.providers.register(AgentIdEchoProvider())
        orchestrator.agents.create(AgentCreate(id="planner", name="Planner", role="Plans", provider="agent-id-echo"))
        orchestrator.agents.create(AgentCreate(id="coder", name="Coder", role="Codes", provider="agent-id-echo"))
        orchestrator.teams.create(TeamCreate(id="dev", name="Dev", mode=TeamMode.chain, agent_ids=["planner", "coder"]))
        orchestrator.chat.post("dev", ChatMessageCreate(sender="user", message="Build it"))

        message = orchestrator.enqueue(
            MessageCreate(
                target="@team:dev",
                content="Build it",
                sender="Web",
                metadata={"channel": "chatroom", "teamId": "dev"},
            )
        )
        asyncio.run(orchestrator.process_message(message.id))

        chat = orchestrator.chat.list("dev")
        assert [item.sender for item in chat] == ["user", "planner", "coder"]
        assert "planner says hello" in chat[1].message
        assert "coder says hello" in chat[2].message
        assert all(item.sender != "orchestrator" for item in chat)
    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_project_context_runs_agent_inside_project_workspace() -> None:
    home = temp_home()
    try:
        settings = Settings(pocketStudio_home=home)
        db = Database(settings.database_path, journal_mode=settings.sqlite_journal_mode)
        db.initialize()
        events = EventService(db)
        registry = ProviderRegistry()
        provider = WorkspaceRecordingProvider()
        registry.register(provider)
        projects = ProjectService(db, events)
        project = projects.create_project(ProjectCreate(name="Scoped Project", workspace=str(home / "project-root")))
        orchestrator = Orchestrator(
            agents=AgentService(db, settings),
            teams=TeamService(db),
            queue=QueueService(db, events, settings),
            chat=ChatService(db, events),
            events=events,
            providers=registry,
            projects=projects,
        )
        agent = orchestrator.agents.create(AgentCreate(id="scoped", name="Scoped", role="Uses project", provider="recording"))
        skill = agent.workspace / ".agents" / "skills" / "project-helper" / "SKILL.md"
        skill.parent.mkdir(parents=True, exist_ok=True)
        skill.write_text("# Project Helper\n\nUse this inside project workspaces.\n", encoding="utf-8")

        message = orchestrator.enqueue(
            MessageCreate(
                target="@agent:scoped",
                content="work inside project",
                metadata={"projectId": project.id},
            )
        )
        result = asyncio.run(orchestrator.process_message(message.id))

        expected_workspace = home / "project-root"
        assert provider.workspaces == [expected_workspace]
        assert expected_workspace.is_dir()
        assert not (expected_workspace / ".pocketStudio").exists()
        assert not (expected_workspace / ".agents").exists()
        assert not (expected_workspace / "memory").exists()
        assert not (expected_workspace / "AGENTS.md").exists()
        assert "workspace=" in result.output
        assert orchestrator.agents.get("scoped").workspace != expected_workspace
    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_project_without_workspace_keeps_agent_workspace() -> None:
    home = temp_home()
    try:
        settings = Settings(pocketStudio_home=home)
        db = Database(settings.database_path, journal_mode=settings.sqlite_journal_mode)
        db.initialize()
        events = EventService(db)
        registry = ProviderRegistry()
        provider = WorkspaceRecordingProvider()
        registry.register(provider)
        projects = ProjectService(db, events)
        project = projects.create_project(ProjectCreate(name="Default Agent Workspace"))
        orchestrator = Orchestrator(
            agents=AgentService(db, settings),
            teams=TeamService(db),
            queue=QueueService(db, events, settings),
            chat=ChatService(db, events),
            events=events,
            providers=registry,
            projects=projects,
        )
        agent = orchestrator.agents.create(
            AgentCreate(id="defaulted", name="Defaulted", role="Uses agent workspace", provider="recording")
        )

        message = orchestrator.enqueue(
            MessageCreate(
                target="@agent:defaulted",
                content="work inside agent workspace",
                metadata={"projectId": project.id},
            )
        )
        asyncio.run(orchestrator.process_message(message.id))

        assert project.workspace is None
        assert provider.workspaces == [agent.workspace]
        assert not (home / ".pocketStudio" / "projects").exists()
    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_legacy_default_project_workspace_keeps_agent_workspace() -> None:
    home = temp_home()
    try:
        settings = Settings(pocketStudio_home=home)
        db = Database(settings.database_path, journal_mode=settings.sqlite_journal_mode)
        db.initialize()
        events = EventService(db)
        registry = ProviderRegistry()
        provider = WorkspaceRecordingProvider()
        registry.register(provider)
        projects = ProjectService(db, events)
        project = projects.create_project(ProjectCreate(name="Legacy Default"))
        db.execute(
            "UPDATE projects SET workspace = ? WHERE id = ?",
            (str(Path(".pocketStudio") / "projects" / project.id), project.id),
        )
        project = projects.get_project(project.id)
        orchestrator = Orchestrator(
            agents=AgentService(db, settings),
            teams=TeamService(db),
            queue=QueueService(db, events, settings),
            chat=ChatService(db, events),
            events=events,
            providers=registry,
            projects=projects,
        )
        agent = orchestrator.agents.create(
            AgentCreate(id="legacy", name="Legacy", role="Uses agent workspace", provider="recording")
        )

        message = orchestrator.enqueue(
            MessageCreate(
                target="@agent:legacy",
                content="work inside agent workspace",
                metadata={"projectId": project.id},
            )
        )
        asyncio.run(orchestrator.process_message(message.id))

        assert project.workspace is None
        assert provider.workspaces == [agent.workspace]
    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_team_leader_runs_first_and_mentions_enqueue_teammates() -> None:
    home = temp_home()
    try:
        orchestrator = build_orchestrator(home)
        orchestrator.agents.create(AgentCreate(id="planner", name="Planner", role="Plans"))
        orchestrator.agents.create(AgentCreate(id="coder", name="Coder", role="Codes"))
        orchestrator.agents.create(AgentCreate(id="reviewer", name="Reviewer", role="Reviews"))
        orchestrator.teams.create(
            TeamCreate(
                id="dev",
                name="Dev",
                mode=TeamMode.chain,
                agent_ids=["planner", "coder", "reviewer"],
                leaderAgent="reviewer",
            )
        )

        message = orchestrator.enqueue(
            MessageCreate(target="@team:dev", content="Coordinate work [@coder: implement API] [#dev: kickoff]")
        )
        result = asyncio.run(orchestrator.process_message(message.id))
        queued = orchestrator.queue.list(status=MessageStatus.queued)
        chat = orchestrator.chat.list("dev")

        assert [run.agent_id for run in result.runs] == ["reviewer", "planner", "coder", "reviewer"]
        assert any(item.target == "@agent:coder" and "Directed to you:" in item.content for item in queued)
        assert any(item.sender == "reviewer" and "kickoff" in item.message for item in chat)
    finally:
        shutil.rmtree(home, ignore_errors=True)



def test_team_routing_converts_tags_to_readable_text() -> None:
    text = "Plan [@coder,reviewer: fix arr[0]] and [#dev: update [phase-1] board]"
    tags = extract_bracket_tags(text, "@")

    assert tags[0].id == "coder,reviewer"
    assert tags[0].message == "fix arr[0]"
    assert strip_bracket_tags(text, "@") == "Plan  and [#dev: update [phase-1] board]"
    assert convert_tags_to_readable(text, "lead") == "Plan @lead -> @coder,reviewer: fix arr[0] and #dev: update [phase-1] board"


def test_team_mentions_support_multiple_teammates_and_dedupe() -> None:
    home = temp_home()
    try:
        orchestrator = build_orchestrator(home)
        orchestrator.agents.create(AgentCreate(id="lead", name="Lead", role="Leads"))
        orchestrator.agents.create(AgentCreate(id="coder", name="Coder", role="Codes"))
        orchestrator.agents.create(AgentCreate(id="reviewer", name="Reviewer", role="Reviews"))
        team = orchestrator.teams.create(
            TeamCreate(id="dev", name="Dev", mode=TeamMode.chain, agent_ids=["lead", "coder", "reviewer"])
        )

        agent_run = AgentRun(
            agent_id="lead",
            input="Start",
            output="Shared context [@coder,reviewer: inspect list[0]] [@coder: duplicate]",
        )
        message = orchestrator.enqueue(
            MessageCreate(
                target="@team:dev",
                content="Start",
                sender="Tester",
                metadata={"channel": "cli", "senderId": "tester-1"},
            )
        )

        asyncio.run(orchestrator._handle_team_tags(team, agent_run, message, [orchestrator.agents.get("lead"), orchestrator.agents.get("coder"), orchestrator.agents.get("reviewer")]))
        queued = orchestrator.queue.list(status=MessageStatus.queued)

        targets = [item.target for item in queued if item.sender == "team:dev:lead"]
        assert targets.count("@agent:coder") == 1
        assert targets.count("@agent:reviewer") == 1
        assert any("inspect list[0]" in item.content for item in queued)
        mention = next(item for item in queued if item.target == "@agent:coder" and item.sender == "team:dev:lead")
        assert mention.metadata["kind"] == "mention"
        assert mention.metadata["teamId"] == "dev"
        assert mention.metadata["fromAgent"] == "lead"
        assert mention.metadata["parentMessageId"] == str(message.id)
        assert mention.metadata["channel"] == "cli"
        assert mention.metadata["senderId"] == "tester-1"
    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_chatroom_broadcast_enqueues_messages_for_teammates() -> None:
    home = temp_home()
    try:
        orchestrator = build_orchestrator(home)
        orchestrator.agents.create(AgentCreate(id="lead", name="Lead", role="Leads"))
        orchestrator.agents.create(AgentCreate(id="coder", name="Coder", role="Codes"))
        orchestrator.agents.create(AgentCreate(id="reviewer", name="Reviewer", role="Reviews"))
        team = orchestrator.teams.create(
            TeamCreate(id="dev", name="Dev", mode=TeamMode.chain, agent_ids=["lead", "coder", "reviewer"])
        )
        agent_run = AgentRun(agent_id="lead", input="Start", output="Status [#dev: update [phase-1] board]")
        message = orchestrator.enqueue(
            MessageCreate(
                target="@team:dev",
                content="Start",
                sender="Tester",
                metadata={"channel": "discord", "senderId": "user-123"},
            )
        )

        asyncio.run(
            orchestrator._handle_team_tags(
                team,
                agent_run,
                message,
                [
                    orchestrator.agents.get("lead"),
                    orchestrator.agents.get("coder"),
                    orchestrator.agents.get("reviewer"),
                ],
            )
        )

        queued = orchestrator.queue.list(status=MessageStatus.queued)
        chat = orchestrator.chat.list("dev")
        chatroom_messages = [item for item in queued if item.sender == "chatroom:dev:lead"]

        assert chat[0].message == "update [phase-1] board"
        assert {item.target for item in chatroom_messages} == {"@agent:coder", "@agent:reviewer"}
        assert all("[Chat room #dev - @lead]" in item.content for item in chatroom_messages)
        assert all(item.metadata["kind"] == "chatroom" for item in chatroom_messages)
        assert all(item.metadata["parentMessageId"] == str(message.id) for item in chatroom_messages)
        assert all(item.metadata["channel"] == "discord" for item in chatroom_messages)
        assert all(item.metadata["senderId"] == "user-123" for item in chatroom_messages)
    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_direct_agent_response_can_route_team_mentions_and_chatrooms() -> None:
    home = temp_home()
    try:
        orchestrator = build_orchestrator(home)
        orchestrator.agents.create(AgentCreate(id="lead", name="Lead", role="Leads"))
        orchestrator.agents.create(AgentCreate(id="coder", name="Coder", role="Codes"))
        orchestrator.agents.create(AgentCreate(id="reviewer", name="Reviewer", role="Reviews"))
        orchestrator.teams.create(
            TeamCreate(id="dev", name="Dev", mode=TeamMode.chain, agent_ids=["lead", "coder", "reviewer"])
        )

        message = orchestrator.enqueue(
            MessageCreate(
                target="@agent:lead",
                content="Status [@CODER,reviewer: inspect queue[0]] [#DEV: standup note]",
                sender="Tester",
                metadata={"channel": "web", "senderId": "tester-1"},
            )
        )
        result = asyncio.run(orchestrator.process_message(message.id))
        queued = orchestrator.queue.list(status=MessageStatus.queued)
        chat = orchestrator.chat.list("dev")

        mention_targets = {item.target for item in queued if item.sender == "team:dev:lead"}
        chatroom_targets = {item.target for item in queued if item.sender == "chatroom:dev:lead"}
        assert result.runs[0].agent_id == "lead"
        assert mention_targets == {"@agent:coder", "@agent:reviewer"}
        assert chatroom_targets == {"@agent:coder", "@agent:reviewer"}
        assert any(message.sender == "lead" and message.message == "standup note" for message in chat)
        assert all(item.metadata["parentMessageId"] == str(message.id) for item in queued)
    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_queue_can_group_consecutive_chatroom_messages() -> None:
    home = temp_home()
    try:
        orchestrator = build_orchestrator(home)
        first = orchestrator.queue.enqueue(
            MessageCreate(
                target="@agent:coder",
                content="[Chat room #dev - @lead]:\nfirst",
                sender="chatroom:dev:lead",
                metadata={"kind": "chatroom"},
            )
        )
        second = orchestrator.queue.enqueue(
            MessageCreate(
                target="@agent:reviewer",
                content="[Chat room #dev - @lead]:\nsecond",
                sender="chatroom:dev:lead",
                metadata={"kind": "chatroom"},
            )
        )
        third = orchestrator.queue.enqueue(MessageCreate(target="@agent:lead", content="regular", sender="api"))

        grouped = orchestrator.queue.grouped_chatroom_messages()

        assert grouped["messageIds"] == [[first.id, second.id], [third.id]]
        assert grouped["messages"][0]["content"] == f"{first.content}\n\n{second.content}"
        assert grouped["messages"][0]["metadata"]["groupedMessageIds"] == [first.id, second.id]
        assert grouped["messages"][0]["metadata"]["groupedCount"] == 2
    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_team_response_projection_converts_internal_tags_for_responses() -> None:
    home = temp_home()
    try:
        orchestrator = build_orchestrator(home)
        message = orchestrator.enqueue(MessageCreate(target="@agent:lead", content="hello", sender="Tester"))
        result = {
            "message_id": message.id,
            "target": message.target,
            "runs": [{"agent_id": "lead", "input": "hello", "output": "Plan [@coder: do work] [#dev: note]"}],
            "output": "Plan [@coder: do work] [#dev: note]",
        }
        completed = orchestrator.queue.mark_done(message.id, json.dumps(result))
        responses = orchestrator.queue.enqueue_responses_from_message(completed)

        assert responses[0].message == "Plan @lead -> @coder: do work #dev: note"
        assert responses[0].metadata["teamTagsConverted"] is True
    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_team_iterative_rounds_run_mentions_inline_until_idle() -> None:
    home = temp_home()
    try:
        orchestrator = build_orchestrator(home)
        orchestrator.agents.create(AgentCreate(id="lead", name="Lead", role="Leads", provider="local"))
        orchestrator.agents.create(AgentCreate(id="coder", name="Coder", role="Codes", provider="local"))
        orchestrator.teams.create(
            TeamCreate(id="dev", name="Dev", mode=TeamMode.chain, agent_ids=["lead"], maxRounds=3)
        )
        orchestrator.teams.add_member("dev", "coder")

        message = orchestrator.enqueue(MessageCreate(target="@team:dev", content="Start [@coder: implement the API]"))
        result = asyncio.run(orchestrator.process_message(message.id))
        queued_mentions = [
            item
            for item in orchestrator.queue.list(status=MessageStatus.queued)
            if item.sender.startswith("team:dev:")
        ]

        assert [run.agent_id for run in result.runs] == ["lead", "coder", "coder", "lead"]
        assert any(run.agent_id == "coder" and "implement the API" in run.input for run in result.runs)
        assert queued_mentions == []
        assert "Teammate results:" in result.output
        assert "Coder (Codes) received" in result.output
    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_fanout_team_runs_all_agents() -> None:
    home = temp_home()
    try:
        orchestrator = build_orchestrator(home)
        orchestrator.agents.create(AgentCreate(id="writer", name="Writer", role="Writes"))
        orchestrator.agents.create(AgentCreate(id="reviewer", name="Reviewer", role="Reviews"))
        orchestrator.teams.create(
            TeamCreate(id="content", name="Content", mode=TeamMode.fanout, agent_ids=["writer", "reviewer"])
        )

        message = orchestrator.enqueue(MessageCreate(target="content", content="Draft release notes"))
        result = asyncio.run(orchestrator.process_message(message.id))

        assert {run.agent_id for run in result.runs} == {"writer", "reviewer"}
        assert "## writer" in result.output
        assert "## reviewer" in result.output
    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_active_team_workflow_controls_agent_order_and_inputs() -> None:
    home = temp_home()
    try:
        settings = Settings(pocketStudio_home=home)
        db = Database(settings.database_path, journal_mode=settings.sqlite_journal_mode)
        db.initialize()
        events = EventService(db)
        teams = TeamService(db)
        workflows = WorkflowService(db, teams)
        registry = ProviderRegistry()
        provider = WorkflowRecordingProvider()
        registry.register(provider)
        orchestrator = Orchestrator(
            agents=AgentService(db, settings),
            teams=teams,
            queue=QueueService(db, events, settings),
            chat=ChatService(db, events),
            events=events,
            providers=registry,
            workflows=workflows,
        )
        orchestrator.agents.create(AgentCreate(id="planner", name="Planner", role="Plans", provider="workflow-recording"))
        orchestrator.agents.create(AgentCreate(id="coder", name="Coder", role="Codes", provider="workflow-recording"))
        orchestrator.teams.create(TeamCreate(id="dev", name="Dev", mode=TeamMode.workflow, agent_ids=["planner", "coder"]))
        workflows.create(
            "dev",
            TeamWorkflowCreate(
                id="delivery",
                name="Delivery",
                definition={
                    "entrypoint": "plan",
                    "outputNode": "build",
                    "nodes": [
                        {"id": "plan", "agentId": "planner", "prompt": "Create a short plan"},
                        {"id": "build", "agentId": "coder", "inputTemplate": "{message}\n\nUpstream:\n{predecessor_outputs}"},
                    ],
                    "edges": [{"source": "plan", "target": "build"}],
                },
            ),
        )

        message = orchestrator.enqueue(MessageCreate(target="@team:dev", content="Ship workflow API"))
        result = asyncio.run(orchestrator.process_message(message.id))

        assert [run.agent_id for run in result.runs] == ["planner", "coder"]
        assert result.output == result.runs[-1].output
        assert "Create a short plan" in provider.inputs[0][1]
        assert "planner handled" in provider.inputs[1][1]
        assert orchestrator.chat.list("dev")[0].message == result.output
        runtime_events = [event for event in orchestrator.events.list(limit=20) if event.type == "team.workflow.runtime"]
        assert runtime_events[-1].payload["runtime"] == "langgraph"
    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_active_team_workflow_is_ignored_unless_team_mode_is_workflow() -> None:
    home = temp_home()
    try:
        settings = Settings(pocketStudio_home=home)
        db = Database(settings.database_path, journal_mode=settings.sqlite_journal_mode)
        db.initialize()
        events = EventService(db)
        teams = TeamService(db)
        workflows = WorkflowService(db, teams)
        registry = ProviderRegistry()
        provider = WorkflowRecordingProvider()
        registry.register(provider)
        orchestrator = Orchestrator(
            agents=AgentService(db, settings),
            teams=teams,
            queue=QueueService(db, events, settings),
            chat=ChatService(db, events),
            events=events,
            providers=registry,
            workflows=workflows,
        )
        orchestrator.agents.create(AgentCreate(id="planner", name="Planner", role="Plans", provider="workflow-recording"))
        orchestrator.agents.create(AgentCreate(id="coder", name="Coder", role="Codes", provider="workflow-recording"))
        orchestrator.teams.create(TeamCreate(id="dev", name="Dev", mode=TeamMode.chain, agent_ids=["planner", "coder"]))
        workflows.create(
            "dev",
            TeamWorkflowCreate(
                id="delivery",
                name="Delivery",
                definition={
                    "entrypoint": "build",
                    "outputNode": "build",
                    "nodes": [{"id": "build", "agentId": "coder"}],
                },
            ),
        )

        message = orchestrator.enqueue(MessageCreate(target="@team:dev", content="Ship workflow API"))
        result = asyncio.run(orchestrator.process_message(message.id))
        runtime_events = [event for event in orchestrator.events.list(limit=20) if event.type == "team.workflow.runtime"]

        assert [run.agent_id for run in result.runs] == ["planner", "coder", "planner"]
        assert runtime_events == []
    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_team_workflow_conditional_edges_route_from_json_output() -> None:
    home = temp_home()
    try:
        settings = Settings(pocketStudio_home=home)
        db = Database(settings.database_path, journal_mode=settings.sqlite_journal_mode)
        db.initialize()
        events = EventService(db)
        teams = TeamService(db)
        workflows = WorkflowService(db, teams)
        registry = ProviderRegistry()
        provider = ConditionalWorkflowProvider('{"route":"approved"}')
        registry.register(provider)
        orchestrator = Orchestrator(
            agents=AgentService(db, settings),
            teams=teams,
            queue=QueueService(db, events, settings),
            chat=ChatService(db, events),
            events=events,
            providers=registry,
            workflows=workflows,
        )
        for agent_id in ["planner", "reviewer", "coder", "reviser"]:
            orchestrator.agents.create(
                AgentCreate(id=agent_id, name=agent_id.title(), role="Works", provider="conditional-workflow")
            )
        orchestrator.teams.create(
            TeamCreate(
                id="dev",
                name="Dev",
                mode=TeamMode.workflow,
                agent_ids=["planner", "reviewer", "coder", "reviser"],
            )
        )
        workflows.create(
            "dev",
            TeamWorkflowCreate(
                id="conditional",
                name="Conditional",
                definition={
                    "entrypoint": "plan",
                    "outputNode": "build",
                    "nodes": [
                        {"id": "plan", "agentId": "planner"},
                        {"id": "review", "agentId": "reviewer"},
                        {"id": "build", "agentId": "coder"},
                        {"id": "revise", "agentId": "reviser"},
                    ],
                    "edges": [{"source": "plan", "target": "review"}],
                    "conditionalEdges": [
                        {
                            "source": "review",
                            "routes": [
                                {"condition": "approved", "target": "build"},
                                {"condition": "needs_revision", "target": "revise"},
                            ],
                            "defaultTarget": "revise",
                        }
                    ],
                },
            ),
        )

        message = orchestrator.enqueue(MessageCreate(target="@team:dev", content="Ship it"))
        result = asyncio.run(orchestrator.process_message(message.id))
        route_events = [event for event in events.list(limit=20) if event.type == "team.workflow.route"]

        assert provider.agent_ids == ["planner", "reviewer", "coder"]
        assert [run.agent_id for run in result.runs] == ["planner", "reviewer", "coder"]
        assert result.output == "coder done"
        assert route_events[-1].payload["route"] == "approved"
        assert route_events[-1].payload["target"] == "build"
    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_team_workflow_conditional_edges_fall_back_to_default_target() -> None:
    home = temp_home()
    try:
        settings = Settings(pocketStudio_home=home)
        db = Database(settings.database_path, journal_mode=settings.sqlite_journal_mode)
        db.initialize()
        events = EventService(db)
        teams = TeamService(db)
        workflows = WorkflowService(db, teams)
        registry = ProviderRegistry()
        provider = ConditionalWorkflowProvider("unclear")
        registry.register(provider)
        orchestrator = Orchestrator(
            agents=AgentService(db, settings),
            teams=teams,
            queue=QueueService(db, events, settings),
            chat=ChatService(db, events),
            events=events,
            providers=registry,
            workflows=workflows,
        )
        for agent_id in ["reviewer", "coder", "reviser"]:
            orchestrator.agents.create(
                AgentCreate(id=agent_id, name=agent_id.title(), role="Works", provider="conditional-workflow")
            )
        orchestrator.teams.create(
            TeamCreate(id="dev", name="Dev", mode=TeamMode.workflow, agent_ids=["reviewer", "coder", "reviser"])
        )
        workflows.create(
            "dev",
            TeamWorkflowCreate(
                id="conditional",
                name="Conditional",
                definition={
                    "entrypoint": "review",
                    "nodes": [
                        {"id": "review", "agentId": "reviewer"},
                        {"id": "build", "agentId": "coder"},
                        {"id": "revise", "agentId": "reviser"},
                    ],
                    "conditionalEdges": [
                        {
                            "source": "review",
                            "routes": [{"condition": "approved", "target": "build"}],
                            "defaultTarget": "revise",
                        }
                    ],
                },
            ),
        )

        message = orchestrator.enqueue(MessageCreate(target="@team:dev", content="Ship it"))
        result = asyncio.run(orchestrator.process_message(message.id))
        route_events = [event for event in events.list(limit=20) if event.type == "team.workflow.route"]

        assert provider.agent_ids == ["reviewer", "reviser"]
        assert result.output == "reviser done"
        assert route_events[-1].payload["route"] == "__default__"
        assert route_events[-1].payload["target"] == "revise"
    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_team_workflow_uses_python_routing_function_for_conditional_edges() -> None:
    home = temp_home()
    try:
        settings = Settings(pocketStudio_home=home)
        db = Database(settings.database_path, journal_mode=settings.sqlite_journal_mode)
        db.initialize()
        events = EventService(db)
        teams = TeamService(db)
        workflows = WorkflowService(db, teams)
        registry = ProviderRegistry()
        provider = ConditionalWorkflowProvider("route should come from python")
        registry.register(provider)
        orchestrator = Orchestrator(
            agents=AgentService(db, settings),
            teams=teams,
            queue=QueueService(db, events, settings),
            chat=ChatService(db, events),
            events=events,
            providers=registry,
            workflows=workflows,
        )
        for agent_id in ["reviewer", "coder", "reviser"]:
            orchestrator.agents.create(
                AgentCreate(id=agent_id, name=agent_id.title(), role="Works", provider="conditional-workflow")
            )
        orchestrator.teams.create(
            TeamCreate(id="dev", name="Dev", mode=TeamMode.workflow, agent_ids=["reviewer", "coder", "reviser"])
        )
        workflows.create(
            "dev",
            TeamWorkflowCreate(
                id="python-routing",
                name="Python Routing",
                definition={
                    "entrypoint": "review",
                    "nodes": [
                        {
                            "id": "review",
                            "agentId": "reviewer",
                            "routingFunction": {
                                "language": "python",
                                "entrypoint": "route",
                                "code": (
                                    "def route(state):\n"
                                    "    output = state.get('outputs', {}).get('review', '')\n"
                                    "    if 'python' in output:\n"
                                    "        return 'needs_revision'\n"
                                    "    return 'approved'\n"
                                ),
                            },
                        },
                        {"id": "build", "agentId": "coder"},
                        {"id": "revise", "agentId": "reviser"},
                    ],
                    "conditionalEdges": [
                        {
                            "source": "review",
                            "routes": [
                                {"condition": "approved", "target": "build"},
                                {"condition": "needs_revision", "target": "revise"},
                            ],
                        }
                    ],
                },
            ),
        )

        message = orchestrator.enqueue(MessageCreate(target="@team:dev", content="Ship it"))
        result = asyncio.run(orchestrator.process_message(message.id))
        route_events = [event for event in events.list(limit=20) if event.type == "team.workflow.route"]

        assert provider.agent_ids == ["reviewer", "reviser"]
        assert result.output == "reviser done"
        assert route_events[-1].payload["route"] == "needs_revision"
        assert route_events[-1].payload["target"] == "revise"
    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_team_workflow_runs_start_tool_and_end_nodes() -> None:
    home = temp_home()
    try:
        settings = Settings(pocketStudio_home=home)
        db = Database(settings.database_path, journal_mode=settings.sqlite_journal_mode)
        db.initialize()
        events = EventService(db)
        teams = TeamService(db)
        workflows = WorkflowService(db, teams)
        orchestrator = Orchestrator(
            agents=AgentService(db, settings),
            teams=teams,
            queue=QueueService(db, events, settings),
            chat=ChatService(db, events),
            events=events,
            providers=ProviderRegistry(),
            workflows=workflows,
        )
        orchestrator.agents.create(AgentCreate(id="planner", name="Planner", role="Plans"))
        orchestrator.teams.create(TeamCreate(id="dev", name="Dev", mode=TeamMode.workflow, agent_ids=["planner"]))
        workflows.create(
            "dev",
            TeamWorkflowCreate(
                id="control-nodes",
                name="Control Nodes",
                definition={
                    "entrypoint": "start",
                    "outputNode": "end",
                    "nodes": [
                        {"id": "start", "type": "start"},
                        {"id": "tool", "type": "tool", "prompt": "tool result"},
                        {"id": "end", "type": "end"},
                    ],
                    "edges": [
                        {"source": "start", "target": "tool"},
                        {"source": "tool", "target": "end"},
                    ],
                },
            ),
        )

        message = orchestrator.enqueue(MessageCreate(target="@team:dev", content="Input"))
        result = asyncio.run(orchestrator.process_message(message.id))

        assert [run.agent_id for run in result.runs] == ["start", "tool", "end"]
        assert result.output == "tool result"
    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_agent_process_metadata_is_emitted_as_core_event() -> None:
    class ProcessProvider(AgentProvider):
        name = "process-provider"

        async def run(self, request: ProviderRequest) -> ProviderResponse:
            return ProviderResponse(text="done", raw={"process": {"pid": 123, "command": "tool"}})

    home = temp_home()
    try:
        orchestrator = build_orchestrator(home)
        orchestrator.providers.register(ProcessProvider())
        orchestrator.agents.create(AgentCreate(id="runner", name="Runner", role="Runs", provider="process-provider"))

        message = orchestrator.enqueue(MessageCreate(target="@agent:runner", content="Run it"))
        asyncio.run(orchestrator.process_message(message.id))
        events = orchestrator.events.list(limit=20)

        process_events = [event for event in events if event.type == "agent.process"]
        assert process_events
        assert process_events[0].payload["agent_id"] == "runner"
        assert process_events[0].payload["process"]["pid"] == 123
    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_agent_progress_callback_is_emitted_as_core_event() -> None:
    class ProgressProvider(AgentProvider):
        name = "progress-provider"

        async def run(self, request: ProviderRequest) -> ProviderResponse:
            if request.progress:
                request.progress({"providerEventType": "item.started", "summary": "working", "tool": "shell"})
            return ProviderResponse(text="done")

    home = temp_home()
    try:
        orchestrator = build_orchestrator(home)
        orchestrator.providers.register(ProgressProvider())
        orchestrator.agents.create(AgentCreate(id="runner", name="Runner", role="Runs", provider="progress-provider"))

        message = orchestrator.enqueue(MessageCreate(target="@agent:runner", content="Run it"))
        asyncio.run(orchestrator.process_message(message.id))
        events = orchestrator.events.list(limit=20)

        progress_events = [event for event in events if event.type == "agent.progress"]
        assert progress_events
        assert progress_events[0].payload["agent_id"] == "runner"
        assert progress_events[0].payload["provider"] == "progress-provider"
        assert progress_events[0].payload["providerEventType"] == "item.started"
        assert progress_events[0].payload["summary"] == "working"
        assert progress_events[0].payload["tool"] == "shell"
    finally:
        shutil.rmtree(home, ignore_errors=True)
