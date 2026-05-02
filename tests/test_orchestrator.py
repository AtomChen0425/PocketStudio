import asyncio
import shutil
import uuid
from pathlib import Path

from pocketStudio.core.config import Settings
from pocketStudio.core.database import Database
from pocketStudio.models import AgentCreate, AgentRun, MessageCreate, MessageStatus, TeamCreate, TeamMode
from pocketStudio.providers.registry import ProviderRegistry
from pocketStudio.services.agent_service import AgentService
from pocketStudio.services.chat_service import ChatService
from pocketStudio.services.event_service import EventService
from pocketStudio.services.orchestrator import Orchestrator
from pocketStudio.services.queue_service import QueueService
from pocketStudio.services.team_service import TeamService


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
        assert [run.agent_id for run in result.runs] == ["planner", "coder"]
        assert result.output == result.runs[-1].output
        assert chat[0].message == result.output
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

        assert [run.agent_id for run in result.runs] == ["reviewer", "planner", "coder"]
        assert any(item.target == "@agent:coder" and "Directed to you:" in item.content for item in queued)
        assert any(item.sender == "reviewer" and "kickoff" in item.message for item in chat)
    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_team_bracket_parser_handles_nested_brackets_and_strips_tags() -> None:
    text = "Plan first [@coder,reviewer: fix arr[0] and map[key]] then [#dev: update [phase-1] board]"

    mentions = Orchestrator._extract_tags(text, "@")
    broadcasts = Orchestrator._extract_tags(text, "#")
    stripped = Orchestrator._strip_tags(text, "@")

    assert mentions == [("coder,reviewer", "fix arr[0] and map[key]")]
    assert broadcasts == [("dev", "update [phase-1] board")]
    assert "Plan first" in stripped
    assert "then [#dev: update [phase-1] board]" in stripped
    assert "fix arr" not in stripped


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

        assert [run.agent_id for run in result.runs] == ["lead", "coder", "coder"]
        assert any(run.agent_id == "coder" and "implement the API" in run.input for run in result.runs)
        assert queued_mentions == []
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
