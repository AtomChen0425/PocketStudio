from __future__ import annotations

import json
import shlex
from pathlib import Path

from pocketStudio.providers.base import AgentProvider, ProviderRequest, ProviderResponse
from pocketStudio.providers.subprocess import ProcessRegistry, SubprocessHarness


class CodexProvider(AgentProvider):
    name = "codex"
    harness_name = "codex"

    def __init__(
        self,
        command: str | None = None,
        base_args: list[str] | None = None,
        registry: ProcessRegistry | None = None,
        timeout_seconds: int = 600,
    ) -> None:
        self.command = command or "codex"
        self.base_args = base_args
        self.harness = SubprocessHarness(command=self.command, registry=registry, timeout_seconds=timeout_seconds)

    async def run(self, request: ProviderRequest) -> ProviderResponse:
        args, stdin_text = self._args(request)
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
            stdin_text=stdin_text,
        )
        if result.return_code != 0:
            raise RuntimeError(f"Codex exited with {result.return_code}: {result.stderr.strip()}")
        if not output:
            output = self._extract_text(result.stdout)
        return ProviderResponse(
            text=output or result.stdout.strip() or "Sorry, I could not generate a response from Codex.",
            raw={
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.return_code,
                "process": getattr(result, "process", None),
            },
        )

    def _args(self, request: ProviderRequest) -> tuple[list[str], str | None]:
        if self.base_args is not None:
            return self._custom_args(request)

        args = ["exec"]
        if not request.reset:
            args.extend(["resume", "--last"])
        if request.agent.model:
            args.extend(["--model", request.agent.model])
        system_prompt = request.agent.system_prompt or request.agent.role
        if system_prompt:
            args.extend(["-c", f"developer_instructions={system_prompt}"])
        args.extend(["--skip-git-repo-check"])
        args.append("--dangerously-bypass-approvals-and-sandbox")
        args.extend(["--json", "-"])
        return args, self._prompt(request)

    def _custom_args(self, request: ProviderRequest) -> tuple[list[str], str | None]:
        prompt = self._prompt(request)
        args = [arg.replace("{prompt}", prompt) for arg in self.base_args or []]
        if not any("{prompt}" in arg for arg in self.base_args or []):
            args.append("-")
            return args, prompt
        return args, None

    def _prompt(self, request: ProviderRequest) -> str:
        chunks: list[str] = []
        system_prompt = request.agent.system_prompt or request.agent.role
        if system_prompt:
            chunks.append(f"System instructions:\n{system_prompt}")
        skill_context = self._skill_context(request.agent.workspace)
        if skill_context:
            chunks.append(skill_context)
        if request.context:
            chunks.append("Context:\n" + "\n\n".join(request.context))
        chunks.append(request.input)
        return "\n\n".join(chunks)

    @staticmethod
    def _skill_context(workspace: Path) -> str:
        skills_dir = workspace / ".codex" / "skills"
        if not skills_dir.exists():
            skills_dir = workspace / ".agents" / "skills"
        if not skills_dir.exists():
            return ""
        skills = []
        for skill_path in sorted(skills_dir.rglob("SKILL.md")):
            skill_id = skill_path.parent.name
            skills.append(f"- {skill_id}: {skill_path}")
        if not skills:
            return ""
        return (
            "Available pocketStudio skills:\n"
            + "\n".join(skills)
            + "\nUse a listed skill when it is relevant, and read its SKILL.md before applying it."
        )

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
            text_parts = [item.get("text") for item in content if isinstance(item, dict) and item.get("text")]
            return "\n".join(part for part in text_parts if part) or None
        if event.get("type") == "item.completed" and event.get("item", {}).get("type") == "agent_message":
            return event.get("item", {}).get("text") or None
        if isinstance(event.get("item"), dict):
            item = event["item"]
            if isinstance(item.get("text"), str):
                return item["text"]
            if isinstance(item.get("content"), str):
                return item["content"]
        return None

    def is_alive(self, agent_id: str) -> bool:
        return self.harness.registry.is_alive(agent_id)

    async def kill_agent(self, agent_id: str) -> bool:
        return await self.harness.registry.kill(agent_id)


def codex_provider_from_command(
    command_line: str,
    registry: ProcessRegistry | None = None,
    timeout_seconds: int = 600,
) -> CodexProvider:
    parts = _split_command_line(command_line)
    if not parts:
        raise ValueError("command_line must include a command")
    return CodexProvider(
        command=parts[0],
        base_args=parts[1:] or None,
        registry=registry,
        timeout_seconds=timeout_seconds,
    )


def _split_command_line(command_line: str) -> list[str]:
    return [part.strip("\"'") for part in shlex.split(command_line, posix=False)]
