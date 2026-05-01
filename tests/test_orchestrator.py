import asyncio
import shutil
import uuid
from pathlib import Path

from pocketStudio.core.config import Settings
from pocketStudio.core.database import Database
from pocketStudio.models import AgentCreate, MessageCreate, TeamCreate, TeamMode
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
