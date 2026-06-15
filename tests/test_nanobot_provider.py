import json
import asyncio
import shutil
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import uuid

from pocketStudio.core.config import Settings
from pocketStudio.core.database import Database
from pocketStudio.models import Agent, AgentCreate
from pocketStudio.providers.base import ProviderRequest
from pocketStudio.providers.nanobot import NanobotProvider
from pocketStudio.services.agent_service import AgentService


class FakeNanobot:
    instances: list["FakeNanobot"] = []

    def __init__(self, config_path=None, workspace=None) -> None:
        self.config_path = config_path
        self.workspace = Path(workspace) if workspace is not None else None
        self.runs: list[dict] = []

    @classmethod
    def from_config(cls, config_path=None, workspace=None):
        instance = cls(config_path=config_path, workspace=workspace)
        cls.instances.append(instance)
        return instance

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def run(self, message, *, session_key="sdk:default", hooks=None):
        self.runs.append({"message": message, "session_key": session_key, "hooks": list(hooks or [])})
        context = SimpleNamespace(
            iteration=1,
            tool_calls=[SimpleNamespace(name="read_file", arguments={"path": "README.md"})],
            tool_results=[SimpleNamespace(name="read_file", content="file contents")],
        )
        for hook in hooks or []:
            if hasattr(hook, "before_iteration"):
                await hook.before_iteration(context)
            if hasattr(hook, "before_execute_tools"):
                await hook.before_execute_tools(context)
            if hasattr(hook, "after_iteration"):
                await hook.after_iteration(context)
        return SimpleNamespace(
            content=f"reply:{message}",
            tools_used=["read_file"],
            messages=[{"role": "assistant", "content": f"reply:{message}"}],
            model_dump=lambda: {"content": f"reply:{message}", "session_key": session_key},
        )


class FakeAgentHook:
    async def before_iteration(self, context) -> None:
        return None

    async def before_execute_tools(self, context) -> None:
        return None

    async def after_iteration(self, context) -> None:
        return None


def test_nanobot_provider_uses_workspace_session_and_hooks(monkeypatch) -> None:
    home = Path(".pytest-tmp") / f"nanobot-{uuid.uuid4().hex}"
    home.mkdir(parents=True)
    nanobot_module = ModuleType("nanobot")
    nanobot_module.Nanobot = FakeNanobot
    agent_module = ModuleType("nanobot.agent")
    agent_module.AgentHook = FakeAgentHook
    monkeypatch.setitem(sys.modules, "nanobot", nanobot_module)
    monkeypatch.setitem(sys.modules, "nanobot.agent", agent_module)
    FakeNanobot.instances.clear()

    try:
        provider = NanobotProvider()
        agent_workspace = home / "agent-workspace"
        agent = Agent(
            id="nanobot-agent",
            name="Nanobot Agent",
            role="Uses nanobot",
            provider="nanobot",
            workspace=agent_workspace,
        )

        progress: list[dict] = []
        response = asyncio.run(provider.run(ProviderRequest(agent=agent, input="Hello", progress=progress.append)))

        assert response.text == "reply:Hello"
        assert FakeNanobot.instances[0].workspace == agent_workspace.resolve()
        assert FakeNanobot.instances[0].runs[0]["session_key"] == "nanobot-agent"
        assert any(item["providerEventType"] == "progress" for item in progress)
        assert any(item["providerEventType"] == "tool_call" for item in progress)
        assert any(item["providerEventType"] == "tool_result" for item in progress)
        assert (agent_workspace / ".pocketStudio" / "nanobot" / "session_key").read_text(encoding="utf-8") == "nanobot-agent"
    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_nanobot_provider_reset_rotates_session_key(monkeypatch) -> None:
    home = Path(".pytest-tmp") / f"nanobot-{uuid.uuid4().hex}"
    home.mkdir(parents=True)
    nanobot_module = ModuleType("nanobot")
    nanobot_module.Nanobot = FakeNanobot
    agent_module = ModuleType("nanobot.agent")
    agent_module.AgentHook = FakeAgentHook
    monkeypatch.setitem(sys.modules, "nanobot", nanobot_module)
    monkeypatch.setitem(sys.modules, "nanobot.agent", agent_module)
    FakeNanobot.instances.clear()

    try:
        provider = NanobotProvider()
        agent_workspace = home / "agent-workspace"
        agent = Agent(
            id="nanobot-agent",
            name="Nanobot Agent",
            role="Uses nanobot",
            provider="nanobot",
            workspace=agent_workspace,
        )

        asyncio.run(provider.run(ProviderRequest(agent=agent, input="Hello")))
        first_key = (agent_workspace / ".pocketStudio" / "nanobot" / "session_key").read_text(encoding="utf-8")

        assert asyncio.run(provider.reset_agent(agent.id)) is True
        second_key = (agent_workspace / ".pocketStudio" / "nanobot" / "session_key").read_text(encoding="utf-8")
        assert second_key != first_key
        assert second_key.startswith("nanobot-agent:")
    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_nanobot_provider_setup_workspace_creates_state_dir() -> None:
    home = Path(".pytest-tmp") / f"nanobot-{uuid.uuid4().hex}"
    home.mkdir(parents=True)
    provider = NanobotProvider()
    workspace = home / "workspace"
    template = Path("nanobot.config.template.json")

    try:
        provider.setup_workspace(workspace)
        assert (workspace / ".pocketStudio" / "nanobot").is_dir()
        assert (workspace / ".pocketStudio" / "nanobot" / "config.json").is_file()
        if template.exists():
            assert (workspace / ".pocketStudio" / "nanobot" / "config.json").read_text(encoding="utf-8") == template.read_text(encoding="utf-8")
    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_nanobot_provider_setup_workspace_writes_agents_md() -> None:
    home = Path(".pytest-tmp") / f"nanobot-{uuid.uuid4().hex}"
    home.mkdir(parents=True)
    provider = NanobotProvider()
    workspace = home / "workspace"

    try:
        provider.setup_workspace(workspace, system_prompt="SYSTEM PROMPT")
        assert (workspace / "AGENTS.md").read_text(encoding="utf-8") == "SYSTEM PROMPT"
    finally:
        shutil.rmtree(home, ignore_errors=True)


def test_nanobot_provider_syncs_agent_config_fields(monkeypatch) -> None:
    home = Path(".pytest-tmp") / f"nanobot-{uuid.uuid4().hex}"
    home.mkdir(parents=True)
    nanobot_module = ModuleType("nanobot")
    nanobot_module.Nanobot = FakeNanobot
    agent_module = ModuleType("nanobot.agent")
    agent_module.AgentHook = FakeAgentHook
    monkeypatch.setitem(sys.modules, "nanobot", nanobot_module)
    monkeypatch.setitem(sys.modules, "nanobot.agent", agent_module)
    FakeNanobot.instances.clear()

    try:
        settings = Settings(pocketStudio_home=home)
        db = Database(settings.database_path)
        db.initialize()
        service = AgentService(db, settings)
        agent = service.create(
            AgentCreate(
                id="nanobot-agent",
                name="Nanobot Agent",
                role="Uses nanobot",
                provider="nanobot",
                model="gpt-5.5",
                model_provider="openai",
                api_key="sk-test",
                workspace=home / "agent-workspace",
            )
        )

        provider = NanobotProvider(db=db)
        asyncio.run(provider.run(ProviderRequest(agent=agent, input="Hello")))

        config_path = agent.workspace / ".pocketStudio" / "nanobot" / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        assert config["agents"]["defaults"]["provider"] == "openai"
        assert config["agents"]["defaults"]["model"] == "gpt-5.5"
        assert config["providers"]["openai"]["apiKey"] == "sk-test"
        assert config["channels"]["sendProgress"] is True
    finally:
        shutil.rmtree(home, ignore_errors=True)
