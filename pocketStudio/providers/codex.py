from __future__ import annotations

import json

from pocketStudio.providers.base import AgentProvider, ProviderRequest, ProviderResponse
from pocketStudio.providers.subprocess import ProcessRegistry, SubprocessHarness


class CodexProvider(AgentProvider):
    name = "codex"

    def __init__(
        self,
        command: str = "codex",
        registry: ProcessRegistry | None = None,
        timeout_seconds: int = 600,
    ) -> None:
        self.harness = SubprocessHarness(command=command, registry=registry, timeout_seconds=timeout_seconds)

    async def run(self, request: ProviderRequest) -> ProviderResponse:
        args = self._args(request)
        output = ""

        def on_line(line: str) -> None:
            nonlocal output
            text = self._extract_event_text(line)
            if text:
                output = text

        result = await self.harness.run(
            args,
            process_key=request.agent.id,
            cwd=request.agent.workspace,
            on_stdout_line=on_line,
        )
        if result.return_code != 0:
            raise RuntimeError(f"Codex exited with {result.return_code}: {result.stderr.strip()}")
        if not output:
            output = self._extract_text(result.stdout)
        return ProviderResponse(
            text=output or "Sorry, I could not generate a response from Codex.",
            raw={"stdout": result.stdout, "stderr": result.stderr, "return_code": result.return_code},
        )

    @staticmethod
    def _args(request: ProviderRequest) -> list[str]:
        args = ["exec", "resume", "--last"]
        if request.agent.model:
            args.extend(["--model", request.agent.model])
        system_prompt = request.agent.system_prompt or request.agent.role
        if system_prompt:
            args.extend(["-c", f"developer_instructions={system_prompt}"])
        args.extend(["--skip-git-repo-check", "--dangerously-bypass-approvals-and-sandbox", "--json", request.input])
        return args

    @classmethod
    def _extract_text(cls, stdout: str) -> str:
        response = ""
        for line in stdout.splitlines():
            text = cls._extract_event_text(line)
            if text:
                response = text
        return response

    @staticmethod
    def _extract_event_text(line: str) -> str | None:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            return None
        if event.get("type") == "item.completed" and event.get("item", {}).get("type") == "agent_message":
            return event.get("item", {}).get("text") or None
        return None

    def is_alive(self, agent_id: str) -> bool:
        return self.harness.registry.is_alive(agent_id)

    async def kill_agent(self, agent_id: str) -> bool:
        return await self.harness.registry.kill(agent_id)
