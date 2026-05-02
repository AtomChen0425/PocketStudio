from __future__ import annotations

import importlib.util
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

from pocketStudio.core.config import Settings
from pocketStudio.models import Event
from pocketStudio.services.event_service import EventService


@dataclass
class HookResult:
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LoadedPlugin:
    name: str
    path: Path
    config: dict[str, Any]
    module: ModuleType | None = None


class PluginContext:
    def __init__(self, name: str, home: Path, events: EventService) -> None:
        self.name = name
        self.home = home
        self.events = events
        self.handlers: dict[str, list[Callable[[dict[str, Any]], None]]] = {}

    def on(self, event_type: str, handler: Callable[[dict[str, Any]], None]) -> None:
        self.handlers.setdefault(event_type, []).append(handler)

    def log(self, level: str, message: str) -> None:
        self.events.emit("plugin.log", {"plugin": self.name, "level": level, "message": message})

    def get_pocketstudio_home(self) -> str:
        return str(self.home)


class PluginService:
    def __init__(self, settings: Settings, events: EventService) -> None:
        self.settings = settings
        self.events = events
        self._loaded: list[LoadedPlugin] | None = None
        self._last_loaded_at = 0
        self._contexts: dict[str, PluginContext] = {}

    @property
    def plugins_path(self) -> Path:
        return self.settings.pocketStudio_home / "plugins"

    def list_plugins(self, reload: bool = False) -> list[dict[str, Any]]:
        plugins = self.load_plugins(reload=reload)
        return [
            {
                "name": plugin.name,
                "path": str(plugin.path),
                "enabled": plugin.config.get("enabled", True),
                "hooks": sorted(set((plugin.config.get("hooks") or {}).keys()) | set(self._module_hooks(plugin.module).keys())),
                "runtime": "python" if plugin.module else "json",
            }
            for plugin in plugins
        ]

    def load_plugins(self, reload: bool = False) -> list[LoadedPlugin]:
        if self._loaded is not None and not reload:
            return self._loaded
        self.plugins_path.mkdir(parents=True, exist_ok=True)
        loaded: list[LoadedPlugin] = []
        self._contexts = {}
        for plugin_dir in sorted(path for path in self.plugins_path.iterdir() if path.is_dir()):
            config_path = plugin_dir / "plugin.json"
            module_path = plugin_dir / "plugin.py"
            if not config_path.exists() and not module_path.exists():
                continue
            config: dict[str, Any] = {}
            try:
                if config_path.exists():
                    config = json.loads(config_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                self.events.emit("plugin.error", {"plugin": plugin_dir.name, "error": str(exc)})
                continue
            if config.get("enabled", True) is False:
                continue
            module = self._load_module(plugin_dir, module_path) if module_path.exists() else None
            plugin = LoadedPlugin(name=config.get("name") or plugin_dir.name, path=plugin_dir, config=config, module=module)
            if module:
                self._activate(plugin)
            loaded.append(plugin)
        self._loaded = loaded
        self._last_loaded_at = int(time.time() * 1000)
        self.events.emit("plugins.loaded", {"count": len(loaded)})
        return loaded

    def run_incoming_hooks(self, message: str, context: dict[str, Any]) -> HookResult:
        return self._run_hook("transformIncoming", message, context)

    def run_outgoing_hooks(self, message: str, context: dict[str, Any]) -> HookResult:
        return self._run_hook("transformOutgoing", message, context)

    def broadcast_event(self, event_type: str, payload: dict[str, Any]) -> None:
        if event_type.startswith("plugin."):
            return
        event = {"type": event_type, "timestamp": int(time.time() * 1000), **payload}
        for plugin in self.load_plugins():
            events = plugin.config.get("events") or []
            if "*" in events or event_type in events:
                self.events.emit("plugin.event", {"plugin": plugin.name, "type": event_type, "payload": payload})
            context = self._contexts.get(plugin.name)
            if not context:
                continue
            for handler in context.handlers.get(event_type, []) + context.handlers.get("*", []):
                try:
                    handler(event)
                except Exception as exc:
                    self.events.emit("plugin.error", {"plugin": plugin.name, "event": event_type, "error": str(exc)})

    def handle_event(self, event: Event) -> None:
        self.broadcast_event(event.type, event.payload)

    def _run_hook(self, hook_name: str, message: str, context: dict[str, Any]) -> HookResult:
        text = message
        metadata: dict[str, Any] = {}
        for plugin in self.load_plugins():
            hooks = plugin.config.get("hooks") or {}
            hook = hooks.get(hook_name)
            if isinstance(hook, dict):
                try:
                    text, hook_metadata = self._apply_hook(text, hook, context)
                except Exception as exc:
                    self.events.emit("plugin.error", {"plugin": plugin.name, "hook": hook_name, "error": str(exc)})
                else:
                    metadata.update(hook_metadata)
                    self._mark_plugin(metadata, plugin.name)
            module_hook = self._module_hooks(plugin.module).get(hook_name)
            if not callable(module_hook):
                continue
            try:
                text, hook_metadata = self._apply_callable_hook(text, module_hook, context)
            except Exception as exc:
                self.events.emit("plugin.error", {"plugin": plugin.name, "hook": hook_name, "error": str(exc)})
                continue
            metadata.update(hook_metadata)
            self._mark_plugin(metadata, plugin.name)
        return HookResult(text=text, metadata=metadata)

    @staticmethod
    def _apply_hook(message: str, hook: dict[str, Any], context: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        when_channel = hook.get("channel")
        if when_channel and when_channel != context.get("channel"):
            return message, {}
        text = str(hook.get("text") or "")
        action = hook.get("action") or "append"
        if action == "prepend":
            output = f"{text}{message}"
        elif action == "replace":
            output = text
        elif action == "append":
            output = f"{message}{text}"
        else:
            output = message
        return output, dict(hook.get("metadata") or {})

    def _load_module(self, plugin_dir: Path, module_path: Path) -> ModuleType | None:
        module_name = f"pocketstudio_plugin_{plugin_dir.name}_{abs(hash(module_path))}"
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            self.events.emit("plugin.error", {"plugin": plugin_dir.name, "error": "Could not load plugin.py"})
            return None
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            self.events.emit("plugin.error", {"plugin": plugin_dir.name, "error": str(exc)})
            return None
        return module

    def _activate(self, plugin: LoadedPlugin) -> None:
        if plugin.module is None:
            return
        activate = getattr(plugin.module, "activate", None)
        if not callable(activate):
            return
        context = PluginContext(plugin.name, self.settings.pocketStudio_home, self.events)
        self._contexts[plugin.name] = context
        try:
            activate(context)
        except Exception as exc:
            self.events.emit("plugin.error", {"plugin": plugin.name, "hook": "activate", "error": str(exc)})

    @staticmethod
    def _module_hooks(module: ModuleType | None) -> dict[str, Callable]:
        if module is None:
            return {}
        hooks = getattr(module, "hooks", {})
        return hooks if isinstance(hooks, dict) else {}

    @staticmethod
    def _apply_callable_hook(
        message: str,
        hook: Callable[[str, dict[str, Any]], Any],
        context: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        result = hook(message, context)
        if isinstance(result, str):
            return result, {}
        if isinstance(result, HookResult):
            return result.text, result.metadata
        if isinstance(result, dict):
            return str(result.get("text", message)), dict(result.get("metadata") or {})
        return message, {}

    @staticmethod
    def _mark_plugin(metadata: dict[str, Any], plugin_name: str) -> None:
        plugins = metadata.setdefault("plugins", [])
        if plugin_name not in plugins:
            plugins.append(plugin_name)
