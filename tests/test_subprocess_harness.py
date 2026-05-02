import asyncio
from pathlib import Path

from pocketStudio.models import Agent
from pocketStudio.providers.base import ProviderRequest
from pocketStudio.providers.codex import CodexProvider
from pocketStudio.providers.subprocess import ProcessRegistry


class FakeProcess:
    returncode = None

    def __init__(self) -> None:
        self.killed = False

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9

    async def wait(self) -> int:
        return self.returncode or 0


def test_process_registry_tracks_and_kills_processes() -> None:
    registry = ProcessRegistry()
    process = FakeProcess()

    registry.register("agent", process)

    assert registry.is_alive("agent") is True
    assert asyncio.run(registry.kill("agent")) is True
    assert process.killed is True
    assert registry.is_alive("agent") is False


def test_codex_provider_builds_args_and_parses_jsonl() -> None:
    class FakeHarness:
        def __init__(self) -> None:
            self.args = None
            self.cwd = None
            self.process_key = None

        async def run(self, args, process_key, cwd=None, env=None, on_stdout_line=None):
            self.args = args
            self.cwd = cwd
            self.process_key = process_key
            line = '{"type":"item.completed","item":{"type":"agent_message","text":"codex output"}}'
            if on_stdout_line:
                on_stdout_line(line)
            return type("Result", (), {"stdout": line, "stderr": "", "return_code": 0})()

    provider = CodexProvider()
    fake = FakeHarness()
    provider.harness = fake
    agent = Agent(
        id="codex-agent",
        name="Codex Agent",
        role="Writes code",
        provider="codex",
        model="gpt-5.4",
        workspace=Path.cwd(),
    )

    response = asyncio.run(provider.run(ProviderRequest(agent=agent, input="Do work")))

    assert response.text == "codex output"
    assert fake.process_key == "codex-agent"
    assert fake.cwd == Path.cwd()
    assert fake.args[:3] == ["exec", "resume", "--last"]
    assert "--json" in fake.args
    assert "Do work" == fake.args[-1]
