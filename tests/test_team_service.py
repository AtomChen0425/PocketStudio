import shutil
import uuid
from pathlib import Path

from pocketStudio.core.config import Settings
from pocketStudio.core.database import Database
from pocketStudio.models import TeamCreate, TeamMode
from pocketStudio.services.team_service import TeamService


def temp_home() -> Path:
    root = Path(".pytest-tmp")
    root.mkdir(exist_ok=True)
    home = root / uuid.uuid4().hex
    home.mkdir()
    return home


def test_team_member_mutations_update_members_and_leader() -> None:
    home = temp_home()
    try:
        settings = Settings(pocketStudio_home=home)
        db = Database(settings.database_path, journal_mode=settings.sqlite_journal_mode)
        db.initialize()
        teams = TeamService(db, settings)
        teams.create(TeamCreate(id="dev", name="Dev", mode=TeamMode.chain, agent_ids=["planner"], leader_agent="planner"))

        added = teams.add_member("dev", "coder")
        promoted = teams.set_leader("dev", "coder")
        removed = teams.remove_member("dev", "coder")

        assert added.agent_ids == ["planner", "coder"]
        assert promoted.leader_agent == "coder"
        assert removed.agent_ids == ["planner"]
        assert removed.leader_agent == "planner"
    finally:
        shutil.rmtree(home, ignore_errors=True)
