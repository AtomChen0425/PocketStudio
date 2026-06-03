import shutil
import uuid
from pathlib import Path

import pytest

from pocketStudio.core.config import Settings
from pocketStudio.core.database import Database
from pocketStudio.models import AgentCreate, TeamCreate, TeamWorkflowCreate, TeamWorkflowUpdate, WorkflowDefinition
from pocketStudio.services.agent_service import AgentService
from pocketStudio.services.team_service import TeamService
from pocketStudio.services.workflow_service import WorkflowService


def temp_home() -> Path:
    root = Path(".pytest-tmp")
    root.mkdir(exist_ok=True)
    home = root / uuid.uuid4().hex
    home.mkdir()
    return home


def build_services(home: Path) -> tuple[AgentService, TeamService, WorkflowService]:
    settings = Settings(pocketStudio_home=home)
    db = Database(settings.database_path, journal_mode=settings.sqlite_journal_mode)
    db.initialize()
    teams = TeamService(db, settings)
    return AgentService(db, settings), teams, WorkflowService(db, teams)


def workflow_definition() -> WorkflowDefinition:
    return WorkflowDefinition(
        entrypoint="plan",
        outputNode="build",
        nodes=[
            {"id": "plan", "agentId": "planner", "prompt": "Plan the work"},
            {"id": "build", "agentId": "coder", "inputTemplate": "{message}\n\n{predecessor_outputs}"},
        ],
        edges=[{"source": "plan", "target": "build"}],
    )


def test_workflow_service_stores_updates_and_lists_team_workflows() -> None:
    home = temp_home()
    try:
        agents, teams, workflows = build_services(home)
        agents.create(AgentCreate(id="planner", name="Planner", role="Plans"))
        agents.create(AgentCreate(id="coder", name="Coder", role="Codes"))
        teams.create(TeamCreate(id="dev", name="Dev", agent_ids=["planner", "coder"]))

        created = workflows.create(
            "dev",
            TeamWorkflowCreate(id="delivery", name="Delivery", definition=workflow_definition()),
        )
        updated = workflows.update("dev", "delivery", TeamWorkflowUpdate(description="Release flow", enabled=False))

        assert created.enabled is True
        assert updated.description == "Release flow"
        assert updated.enabled is False
        assert workflows.list("dev")[0].id == "delivery"

    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_workflow_service_rejects_agents_outside_team() -> None:
    home = temp_home()
    try:
        agents, teams, workflows = build_services(home)
        agents.create(AgentCreate(id="planner", name="Planner", role="Plans"))
        agents.create(AgentCreate(id="coder", name="Coder", role="Codes"))
        teams.create(TeamCreate(id="dev", name="Dev", agent_ids=["planner"]))

        with pytest.raises(ValueError, match="outside team"):
            workflows.create("dev", TeamWorkflowCreate(id="bad", name="Bad", definition=workflow_definition()))
    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_workflow_service_exports_and_imports_portable_json() -> None:
    home = temp_home()
    try:
        agents, teams, workflows = build_services(home)
        agents.create(AgentCreate(id="planner", name="Planner", role="Plans"))
        agents.create(AgentCreate(id="coder", name="Coder", role="Codes"))
        teams.create(TeamCreate(id="dev", name="Dev", agent_ids=["planner", "coder"]))
        workflows.create("dev", TeamWorkflowCreate(id="delivery", name="Delivery", definition=workflow_definition()))

        exported = workflows.export_json("dev", "delivery")
        exported["workflow"]["id"] = "delivery-copy"
        imported = workflows.import_json("dev", exported)

        assert exported["format"] == "pocketstudio.team.workflow"
        assert exported["workflow"]["definition"]["outputNode"] == "build"
        assert imported.id == "delivery-copy"
        assert imported.definition.entrypoint == "plan"
    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_workflow_service_imports_bare_definition_json() -> None:
    home = temp_home()
    try:
        agents, teams, workflows = build_services(home)
        agents.create(AgentCreate(id="planner", name="Planner", role="Plans"))
        agents.create(AgentCreate(id="coder", name="Coder", role="Codes"))
        teams.create(TeamCreate(id="dev", name="Dev", agent_ids=["planner", "coder"]))
        payload = workflow_definition().model_dump(by_alias=True, mode="json")
        payload["metadata"] = {"id": "bare-flow", "name": "Bare Flow", "enabled": False}

        imported = workflows.import_json("dev", payload)

        assert imported.id == "bare-flow"
        assert imported.name == "Bare Flow"
        assert imported.enabled is False
    finally:
        shutil.rmtree(home, ignore_errors=True)
