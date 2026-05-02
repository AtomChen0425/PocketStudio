from __future__ import annotations

import asyncio
import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SubprocessResult:
    stdout: str
    stderr: str
    return_code: int


@dataclass
class ProcessRegistry:
    _processes: dict[str, asyncio.subprocess.Process] = field(default_factory=dict)

    def register(self, key: str, process: asyncio.subprocess.Process) -> None:
        self._processes[key] = process

    def unregister(self, key: str, process: asyncio.subprocess.Process) -> None:
        if self._processes.get(key) is process:
            del self._processes[key]

    def is_alive(self, key: str) -> bool:
        process = self._processes.get(key)
        return bool(process and process.returncode is None)

    async def kill(self, key: str) -> bool:
        process = self._processes.get(key)
        if process is None or process.returncode is not None:
            return False
        process.kill()
        await process.wait()
        self._processes.pop(key, None)
        return True


class SubprocessHarness:
    def __init__(
        self,
        command: str,
        registry: ProcessRegistry | None = None,
        timeout_seconds: int = 600,
    ) -> None:
        self.command = command
        self.registry = registry or ProcessRegistry()
        self.timeout_seconds = timeout_seconds

    async def run(
        self,
        args: Sequence[str],
        process_key: str,
        cwd: Path | str | None = None,
        env: dict[str, str] | None = None,
        on_stdout_line: Callable[[str], None] | None = None,
    ) -> SubprocessResult:
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        process = await asyncio.create_subprocess_exec(
            self.command,
            *args,
            cwd=str(cwd) if cwd else None,
            env=merged_env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self.registry.register(process_key, process)
        try:
            stdout, stderr = await asyncio.wait_for(
                self._communicate(process, on_stdout_line),
                timeout=self.timeout_seconds,
            )
        except TimeoutError:
            process.kill()
            stdout, stderr = await process.communicate()
            raise TimeoutError(f"Subprocess '{self.command}' timed out after {self.timeout_seconds}s")
        finally:
            self.registry.unregister(process_key, process)
        return SubprocessResult(
            stdout=stdout.decode(errors="replace"),
            stderr=stderr.decode(errors="replace"),
            return_code=process.returncode or 0,
        )

    @staticmethod
    async def _communicate(
        process: asyncio.subprocess.Process,
        on_stdout_line: Callable[[str], None] | None,
    ) -> tuple[bytes, bytes]:
        if on_stdout_line is None or process.stdout is None:
            return await process.communicate()

        stdout_parts: list[bytes] = []

        async def read_stdout() -> None:
            assert process.stdout is not None
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                stdout_parts.append(line)
                on_stdout_line(line.decode(errors="replace").rstrip("\r\n"))

        stderr_task = asyncio.create_task(process.stderr.read() if process.stderr else _empty_bytes())
        await read_stdout()
        await process.wait()
        stderr = await stderr_task
        return b"".join(stdout_parts), stderr


async def _empty_bytes() -> bytes:
    return b""
