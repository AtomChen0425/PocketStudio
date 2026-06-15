from __future__ import annotations

import inspect
import importlib
import json
import shutil
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from pocketStudio.core.database import Database
from pocketStudio.providers.base import AgentProvider, ProviderRequest, ProviderResponse
from pocketStudio.services.agent_service import AgentService
_REPO_ROOT = Path(__file__).resolve().parents[2]
_BUILTIN_NANOBOT_CONFIG_TEMPLATE_PATH = _REPO_ROOT / "nanobot.config.template.json"


class NanobotProvider(AgentProvider):
    name = "nanobot"

    def __init__(
        self,
        *,
        db: Database | None = None,
        config_path: str | Path | None = None,
    ) -> None:
        self.db = db
        self.config_path = Path(config_path).expanduser() if config_path else None
        self._session_keys: dict[str, str] = {}
        self._agent_workspaces: dict[str, Path] = {}

    def setup_workspace(self, workspace: Path) -> None:
        workspace.mkdir(parents=True, exist_ok=True)
        root_skills_dir = workspace / ".agents" / "skills"
        AgentService.ensure_tool_skills_link(root_skills_dir, workspace / "skills")
        config_path = self._config_path_for_workspace(workspace)
        if self.config_path is None and not config_path.exists():
            if _BUILTIN_NANOBOT_CONFIG_TEMPLATE_PATH.exists():
                shutil.copy2(_BUILTIN_NANOBOT_CONFIG_TEMPLATE_PATH, config_path)
            else:
                config_path.write_text("{}", encoding="utf-8")

    async def run(self, request: ProviderRequest) -> ProviderResponse:
        Nanobot, AgentHook = self._load_sdk()
        workspace = request.agent.workspace.resolve()
        self.setup_workspace(workspace)
        self._agent_workspaces[request.agent.id] = workspace
        session_key = self._session_key_for(request.agent.id, workspace)
        config_path = self.config_path or self._config_path_for_workspace(workspace)

        provider = self

        class PocketStudioHook(AgentHook):
            async def before_iteration(self, context) -> None:  # type: ignore[override]
                if request.progress is None:
                    return
                iteration = getattr(context, "iteration", None)
                summary = f"nanobot iteration {iteration}" if iteration is not None else "nanobot iteration"
                request.progress(
                    {
                        "providerEventType": "progress",
                        "summary": summary,
                        "content": summary,
                        "raw": {"iteration": iteration, "stage": "before_iteration"},
                    }
                )

            async def before_execute_tools(self, context) -> None:  # type: ignore[override]
                if request.progress is None:
                    return
                for tool_call in getattr(context, "tool_calls", []) or []:
                    payload = provider._tool_call_payload(tool_call)
                    request.progress(payload)

            async def after_iteration(self, context) -> None:  # type: ignore[override]
                if request.progress is None:
                    return
                for tool_result in getattr(context, "tool_results", []) or []:
                    payload = provider._tool_result_payload(tool_result)
                    request.progress(payload)

        bot = Nanobot.from_config(config_path=config_path, workspace=workspace)
        try:
            result = await bot.run(
                request.input,
                session_key=session_key,
                hooks=[PocketStudioHook()],
            )
        finally:
            aclose = getattr(bot, "aclose", None)
            if callable(aclose):
                maybe_close = aclose()
                if inspect.isawaitable(maybe_close):
                    await maybe_close

        content = getattr(result, "content", "") or ""
        raw = {
            "content": content,
            "session_key": session_key,
            "tools_used": getattr(result, "tools_used", None),
            "messages": getattr(result, "messages", None),
            "result": self._safe_model_dump(result),
        }
        return ProviderResponse(
            text=content or "Sorry, I could not generate a response from nanobot.",
            raw=raw,
        )

    async def reset_agent(self, agent_id: str) -> bool:
        workspace = self._agent_workspaces.get(agent_id) or self._workspace_from_db(agent_id)
        session_key = f"{agent_id}:{uuid4().hex}"
        self._session_keys[agent_id] = session_key
        if workspace is None:
            return True
        path = self._session_key_path(workspace)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(session_key, encoding="utf-8")
        return True

    def _session_key_for(self, agent_id: str, workspace: Path) -> str:
        path = self._session_key_path(workspace)
        if agent_id in self._session_keys:
            session_key = self._session_keys[agent_id]
        elif path.exists():
            session_key = path.read_text(encoding="utf-8").strip() or agent_id
        else:
            session_key = agent_id
        self._session_keys[agent_id] = session_key
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(session_key, encoding="utf-8")
        return session_key

    def _workspace_from_db(self, agent_id: str) -> Path | None:
        if self.db is None:
            return None
        row = self.db.fetch_one("SELECT workspace FROM agents WHERE id = ?", (agent_id,))
        if row is None or not row["workspace"]:
            return None
        return Path(row["workspace"]).expanduser()

    @staticmethod
    def _session_key_path(workspace: Path) -> Path:
        return workspace / "sessions_key.txt"

    @staticmethod
    def _config_path_for_workspace(workspace: Path) -> Path:
        return workspace / "config.json"

    @staticmethod
    def _load_sdk():
        try:
            nanobot_module = importlib.import_module("nanobot")
            agent_module = importlib.import_module("nanobot.agent")
        except ImportError as exc:
            raise RuntimeError("The nanobot provider requires the `nanobot` Python package") from exc
        return nanobot_module.Nanobot, agent_module.AgentHook

    @staticmethod
    def _safe_model_dump(value) -> dict | list | str | None:
        if value is None:
            return None
        dump = getattr(value, "model_dump", None)
        if callable(dump):
            try:
                return dump()
            except Exception:
                pass
        if isinstance(value, (dict, list, str, int, float, bool)):
            return value
        return {"value": str(value)}

    @staticmethod
    def _tool_call_payload(tool_call) -> dict:
        name = getattr(tool_call, "name", None)
        arguments = getattr(tool_call, "arguments", None)
        if arguments is None:
            arguments = getattr(tool_call, "args", None)
        summary = name or "tool call"
        content = json.dumps({"name": name, "arguments": arguments}, ensure_ascii=False, default=str)
        return {
            "providerEventType": "tool_call",
            "summary": summary,
            "content": content,
            "tool": name,
            "raw": {
                "name": name,
                "arguments": arguments,
                "value": NanobotProvider._safe_model_dump(tool_call),
            },
        }

    @staticmethod
    def _tool_result_payload(tool_result) -> dict:
        name = getattr(tool_result, "name", None)
        content_value = getattr(tool_result, "content", None)
        if content_value is None:
            content_value = getattr(tool_result, "result", None)
        if content_value is None:
            content_value = getattr(tool_result, "text", None)
        if content_value is None:
            content_value = getattr(tool_result, "output", None)
        content = NanobotProvider._stringify(content_value)
        summary = f"{name}: {content[:120]}" if name and content else (name or "tool result")
        return {
            "providerEventType": "tool_result",
            "summary": summary,
            "content": content,
            "tool": name,
            "raw": {
                "name": name,
                "value": NanobotProvider._safe_model_dump(tool_result),
            },
        }

    @staticmethod
    def _stringify(value) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, default=str)
        return str(value)
