from __future__ import annotations

import json
import shlex

from pocketStudio.providers.base import AgentProvider, ProviderRequest, ProviderResponse
from pocketStudio.providers.subprocess import ProcessRegistry, SubprocessHarness


class CliAgentProvider(AgentProvider):
    name = "cli"

    def __init__(
        self,
        name: str,
        command: str,
        base_args: list[str] | None = None,
        prompt_arg: str | None = None,
        registry: ProcessRegistry | None = None,
        timeout_seconds: int = 600,
    ) -> None:
        self.name = name
        self.command = command
        self.base_args = base_args or []
        self.prompt_arg = prompt_arg
        self.harness = SubprocessHarness(command=command, registry=registry, timeout_seconds=timeout_seconds)

    async def run(self, request: ProviderRequest) -> ProviderResponse:
        output = ""

        def on_line(line: str) -> None:
            nonlocal output
            if request.progress is not None and line.strip():
                request.progress(
                    {
                        "providerEventType": "stdout",
                        "summary": line[:240],
                        "content": line,
                        "raw": {"line": line, "stream": "stdout"},
                    }
                )
            text = self._extract_event_text(line)
            if text:
                output = text

        def on_stderr_line(line: str) -> None:
            if request.progress is None or not line.strip():
                return
            request.progress(
                {
                    "providerEventType": "stderr",
                    "summary": line[:240],
                    "content": line,
                    "raw": {"line": line, "stream": "stderr"},
                }
            )

        result = await self.harness.run(
            self._args(request),
            process_key=request.agent.id,
            cwd=request.agent.workspace,
            on_stdout_line=on_line,
            on_stderr_line=on_stderr_line,
        )
        if result.return_code != 0:
            raise RuntimeError(f"{self.command} exited with {result.return_code}: {result.stderr.strip()}")
        output = output or self._extract_text(result.stdout) or result.stdout.strip()
        return ProviderResponse(
            text=output or f"Sorry, I could not generate a response from {self.name}.",
            raw={
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.return_code,
                "process": result.process,
            },
        )

    def _args(self, request: ProviderRequest) -> list[str]:
        args = list(self.base_args)
        prompt = self._prompt(request)
        if self.prompt_arg:
            args.extend([self.prompt_arg, prompt])
        else:
            args.append(prompt)
        return args

    @staticmethod
    def _prompt(request: ProviderRequest) -> str:
        chunks = []
        system_prompt = request.agent.system_prompt or request.agent.role
        if system_prompt:
            chunks.append(f"System instructions:\n{system_prompt}")
        if request.context:
            chunks.append("Context:\n" + "\n\n".join(request.context))
        chunks.append(request.input)
        return "\n\n".join(chunks)

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
        if isinstance(event.get("result"), str):
            return event["result"]
        if isinstance(event.get("message"), str):
            return event["message"]
        if isinstance(event.get("text"), str):
            return event["text"]
        content = event.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = [item.get("text") for item in content if isinstance(item, dict) and item.get("type") == "text"]
            return "\n".join(part for part in text_parts if part) or None
        return None

    def is_alive(self, agent_id: str) -> bool:
        return self.harness.registry.is_alive(agent_id)

    async def kill_agent(self, agent_id: str) -> bool:
        return await self.harness.registry.kill(agent_id)


class ClaudeProvider(CliAgentProvider):
    def __init__(self, registry: ProcessRegistry | None = None, timeout_seconds: int = 600) -> None:
        super().__init__(
            name="claude",
            command="claude",
            base_args=["--print", "--output-format", "stream-json", "--verbose"],
            registry=registry,
            timeout_seconds=timeout_seconds,
        )


class OpenCodeProvider(CliAgentProvider):
    def __init__(self, registry: ProcessRegistry | None = None, timeout_seconds: int = 600) -> None:
        super().__init__(
            name="opencode",
            command="opencode",
            base_args=["run", "--print"],
            registry=registry,
            timeout_seconds=timeout_seconds,
        )


def provider_from_command(
    name: str,
    command_line: str,
    registry: ProcessRegistry | None = None,
    timeout_seconds: int = 600,
) -> CliAgentProvider:
    parts = shlex.split(command_line, posix=False)
    if not parts:
        raise ValueError("command_line must include a command")
    return CliAgentProvider(
        name=name,
        command=parts[0],
        base_args=parts[1:],
        registry=registry,
        timeout_seconds=timeout_seconds,
    )
