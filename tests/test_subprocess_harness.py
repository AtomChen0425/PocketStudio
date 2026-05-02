import asyncio
import shutil
import uuid
from pathlib import Path

from pocketStudio.models import Agent
from pocketStudio.providers.base import ProviderRequest
from pocketStudio.providers.cli_agent import ClaudeProvider, OpenCodeProvider
from pocketStudio.providers.codex import CodexProvider
from pocketStudio.providers.registry import ProviderRegistry
from pocketStudio.providers.subprocess import ProcessRegistry, SubprocessHarness


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

    registry.register("agent", process, {"command": "codex", "args": ["exec"], "cwd": str(Path.cwd())})

    assert registry.is_alive("agent") is True
    snapshot = registry.snapshot()
    assert snapshot[0]["agent"] == "agent"
    assert snapshot[0]["command"] == "codex"
    assert snapshot[0]["args"] == ["exec"]
    assert snapshot[0]["cwd"] == str(Path.cwd())
    assert snapshot[0]["alive"] is True
    assert snapshot[0]["duration"] >= 0
    assert asyncio.run(registry.kill("agent")) is True
    assert process.killed is True
    assert registry.is_alive("agent") is False
    assert registry.snapshot() == []


def test_subprocess_harness_falls_back_to_shell_on_windows_permission_error(monkeypatch) -> None:
    class CommunicatingProcess:
        pid = 456
        returncode = 0

        async def communicate(self, input=None):
            return b"shell output", b""

    calls = {}

    async def fake_exec(*args, **kwargs):
        raise PermissionError("denied")

    async def fake_powershell(*args, **kwargs):
        calls["args"] = args
        return CommunicatingProcess()

    monkeypatch.setattr("pocketStudio.providers.subprocess.os.name", "nt")
    monkeypatch.setattr("pocketStudio.providers.subprocess.asyncio.create_subprocess_exec", fake_exec)
    monkeypatch.setattr("pocketStudio.providers.subprocess.shutil.which", lambda name: "powershell.exe" if name == "powershell.exe" else None)

    async def fake_exec_with_fallback(*args, **kwargs):
        if args and args[0] == "codex":
            raise PermissionError("denied")
        return await fake_powershell(*args, **kwargs)

    monkeypatch.setattr("pocketStudio.providers.subprocess.asyncio.create_subprocess_exec", fake_exec_with_fallback)

    result = asyncio.run(SubprocessHarness("codex").run(["exec", "--json", "hello"], process_key="agent"))

    assert result.stdout == "shell output"
    assert calls["args"][:5] == ("powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command")
    assert calls["args"][5] == "codex exec --json hello"


def test_subprocess_harness_falls_back_to_powershell_when_command_is_missing_on_windows(monkeypatch) -> None:
    class CommunicatingProcess:
        pid = 789
        returncode = 0

        async def communicate(self, input=None):
            return b"shell output", b""

    calls = {}

    async def fake_exec(*args, **kwargs):
        if args and args[0] == "codex":
            raise FileNotFoundError("missing")
        calls["args"] = args
        return CommunicatingProcess()

    monkeypatch.setattr("pocketStudio.providers.subprocess.os.name", "nt")
    monkeypatch.setattr("pocketStudio.providers.subprocess.shutil.which", lambda name: "powershell.exe" if name == "powershell.exe" else None)
    monkeypatch.setattr("pocketStudio.providers.subprocess.asyncio.create_subprocess_exec", fake_exec)

    result = asyncio.run(SubprocessHarness("codex").run(["exec", "--json", "-"], process_key="agent", stdin_text="hello"))

    assert result.stdout == "shell output"
    assert calls["args"][:5] == ("powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command")
    assert calls["args"][5] == "codex exec --json -"


def test_codex_provider_builds_args_and_parses_jsonl() -> None:
    class FakeHarness:
        def __init__(self) -> None:
            self.args = None
            self.cwd = None
            self.process_key = None

        async def run(self, args, process_key, cwd=None, env=None, on_stdout_line=None, stdin_text=None):
            self.args = args
            self.cwd = cwd
            self.process_key = process_key
            self.stdin_text = stdin_text
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
    assert ["--model", "gpt-5.4"] == fake.args[3:5]
    assert "--json" in fake.args
    assert "--skip-git-repo-check" in fake.args
    assert "-c" in fake.args
    assert "developer_instructions=Writes code" in fake.args
    assert fake.args[-1] == "-"
    assert "System instructions:\nWrites code" in fake.stdin_text
    assert "Do work" in fake.stdin_text


def test_codex_provider_can_reset_without_resume() -> None:
    class FakeHarness:
        async def run(self, args, process_key, cwd=None, env=None, on_stdout_line=None, stdin_text=None):
            self.args = args
            return type("Result", (), {"stdout": '{"result":"reset output"}', "stderr": "", "return_code": 0, "process": {"pid": 123}})()

    provider = CodexProvider()
    fake = FakeHarness()
    provider.harness = fake
    agent = Agent(id="codex-agent", name="Codex Agent", role="Writes code", provider="codex", workspace=Path.cwd())

    response = asyncio.run(provider.run(ProviderRequest(agent=agent, input="Do work", reset=True)))

    assert response.text == "reset output"
    assert fake.args[0] == "exec"
    assert "resume" not in fake.args
    assert "--last" not in fake.args


def test_codex_provider_includes_context_and_supports_custom_command_line() -> None:
    class FakeHarness:
        def __init__(self) -> None:
            self.args = None
            self.process_key = None

        async def run(self, args, process_key, cwd=None, env=None, on_stdout_line=None, stdin_text=None):
            self.args = args
            self.process_key = process_key
            self.stdin_text = stdin_text
            return type("Result", (), {"stdout": '{"result":"custom output"}', "stderr": "", "return_code": 0, "process": {"pid": 123}})()

    provider = CodexProvider(command="codex-test", base_args=["exec", "--json", "{prompt}"])
    fake = FakeHarness()
    provider.harness = fake
    agent = Agent(
        id="codex-agent",
        name="Codex Agent",
        role="Writes code",
        provider="codex",
        workspace=Path.cwd(),
    )

    response = asyncio.run(provider.run(ProviderRequest(agent=agent, input="Do work", context=["previous output"])))

    assert response.text == "custom output"
    assert fake.args[:2] == ["exec", "--json"]
    assert "Context:\nprevious output" in fake.args[-1]
    assert "Do work" in fake.args[-1]
    assert fake.stdin_text is None


def test_codex_provider_reads_env_command_args(monkeypatch) -> None:
    monkeypatch.setenv("POCKETSTUDIO_CODEX_COMMAND", "codex-env")
    monkeypatch.setenv("POCKETSTUDIO_CODEX_ARGS", "exec --json {prompt}")

    provider = CodexProvider()

    assert provider.command == "codex-env"
    assert provider.base_args == ["exec", "--json", "{prompt}"]


def test_cli_agent_providers_build_args_and_parse_output() -> None:
    class FakeHarness:
        def __init__(self) -> None:
            self.args = None
            self.process_key = None

        async def run(self, args, process_key, cwd=None, env=None, on_stdout_line=None, stdin_text=None):
            self.args = args
            self.process_key = process_key
            line = '{"type":"message","content":[{"type":"text","text":"cli output"}]}'
            if on_stdout_line:
                on_stdout_line(line)
            return type("Result", (), {"stdout": line, "stderr": "", "return_code": 0, "process": {"pid": 123}})()

    agent = Agent(
        id="agent",
        name="Agent",
        role="Follows instructions",
        provider="claude",
        workspace=Path.cwd(),
    )
    provider = ClaudeProvider()
    fake = FakeHarness()
    provider.harness = fake

    response = asyncio.run(provider.run(ProviderRequest(agent=agent, input="Do work", context=["prior context"])))

    assert response.text == "cli output"
    assert fake.process_key == "agent"
    assert fake.args[:4] == ["--print", "--output-format", "stream-json", "--verbose"]
    assert "prior context" in fake.args[-1]
    assert "Do work" in fake.args[-1]
    assert response.raw["process"]["pid"] == 123


def test_provider_registry_exposes_core_harnesses() -> None:
    registry = ProviderRegistry()

    assert {"local", "openai", "codex", "claude", "opencode"} <= set(registry.list_names())
    assert isinstance(registry.get("opencode"), OpenCodeProvider)


def test_provider_registry_builds_custom_codex_command_from_provider_config() -> None:
    from pocketStudio.core.database import Database

    temp_dir = Path(".pytest-tmp") / f"providers-{uuid.uuid4().hex}"
    temp_dir.mkdir(parents=True)
    try:
        db = Database(temp_dir / "providers.db")
        db.initialize()
        db.execute(
            """
            INSERT INTO custom_providers (id, name, harness, base_url, api_key, model)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
        ("codex-custom", "Custom Codex", "codex", '"codex-test" exec --json', "", ""),
        )

        registry = ProviderRegistry(db)
        provider = registry.get("codex-custom")

        assert isinstance(provider, CodexProvider)
        assert provider.command == "codex-test"
        assert provider.base_args == ["exec", "--json"]
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
