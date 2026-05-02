from __future__ import annotations

import asyncio
import os
import subprocess
import time
import shutil
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SubprocessResult:
    stdout: str
    stderr: str
    return_code: int
    process: dict


@dataclass
class ProcessRegistry:
    _processes: dict[str, asyncio.subprocess.Process] = field(default_factory=dict)
    _metadata: dict[str, dict] = field(default_factory=dict)

    def register(self, key: str, process: asyncio.subprocess.Process, metadata: dict | None = None) -> None:
        self._processes[key] = process
        self._metadata[key] = {"startedAt": int(time.time() * 1000), **(metadata or {})}

    def unregister(self, key: str, process: asyncio.subprocess.Process) -> None:
        if self._processes.get(key) is process:
            del self._processes[key]
            self._metadata.pop(key, None)

    def is_alive(self, key: str) -> bool:
        process = self._processes.get(key)
        return bool(process and process.returncode is None)

    def snapshot(self) -> list[dict]:
        now_ms = int(time.time() * 1000)
        items: list[dict] = []
        for key, process in sorted(self._processes.items()):
            metadata = self._metadata.get(key, {})
            started_at = metadata.get("startedAt")
            items.append(
                {
                    "agent": key,
                    "pid": getattr(process, "pid", None),
                    "alive": getattr(process, "returncode", None) is None,
                    "returnCode": getattr(process, "returncode", None),
                    "startedAt": started_at,
                    "duration": max(0, now_ms - started_at) if isinstance(started_at, int) else None,
                    "command": metadata.get("command"),
                    "args": metadata.get("args", []),
                    "cwd": metadata.get("cwd"),
                }
            )
        return items

    async def kill(self, key: str) -> bool:
        process = self._processes.get(key)
        if process is None or process.returncode is not None:
            return False
        process.kill()
        await process.wait()
        self._processes.pop(key, None)
        self._metadata.pop(key, None)
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
        stdin_text: str | None = None,
    ) -> SubprocessResult:
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        try:
            process = await asyncio.create_subprocess_exec(
                self.command,
                *args,
                cwd=str(cwd) if cwd else None,
                env=merged_env,
                stdin=asyncio.subprocess.PIPE if stdin_text is not None else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            if os.name != "nt" or not _should_fallback_to_windows_powershell(exc):
                raise
            process = await self._run_windows_powershell(args, cwd, merged_env, stdin_text)
        self.registry.register(
            process_key,
            process,
            {"command": self.command, "args": list(args), "cwd": str(cwd) if cwd else None},
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                self._communicate(process, on_stdout_line, stdin_text),
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
            process={
                "pid": process.pid,
                "command": self.command,
                "args": list(args),
                "cwd": str(cwd) if cwd else None,
                "timedOut": False,
            },
        )

    async def _run_windows_powershell(
        self,
        args: Sequence[str],
        cwd: Path | str | None,
        env: dict[str, str],
        stdin_text: str | None,
    ) -> asyncio.subprocess.Process:
        return await asyncio.create_subprocess_exec(
            _windows_powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            subprocess.list2cmdline([self.command, *args]),
            cwd=str(cwd) if cwd else None,
            env=env,
            stdin=asyncio.subprocess.PIPE if stdin_text is not None else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    @staticmethod
    async def _communicate(
        process: asyncio.subprocess.Process,
        on_stdout_line: Callable[[str], None] | None,
        stdin_text: str | None = None,
    ) -> tuple[bytes, bytes]:
        if on_stdout_line is None or process.stdout is None:
            return await process.communicate(input=stdin_text.encode() if stdin_text is not None else None)

        if stdin_text is not None and process.stdin is not None:
            process.stdin.write(stdin_text.encode())
            await process.stdin.drain()
            process.stdin.close()

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


def _should_fallback_to_windows_powershell(exc: OSError) -> bool:
    return isinstance(exc, (FileNotFoundError, PermissionError)) or getattr(exc, "winerror", None) in {2, 5}


def _windows_powershell() -> str:
    return shutil.which("powershell.exe") or shutil.which("powershell") or "powershell.exe"
