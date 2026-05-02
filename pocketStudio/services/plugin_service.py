from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pocketStudio.core.config import Settings
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


class PluginService:
    def __init__(self, settings: Settings, events: EventService) -> None:
        self.settings = settings
        self.events = events
        self._loaded: list[LoadedPlugin] | None = None
        self._last_loaded_at = 0

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
                "hooks": sorted((plugin.config.get("hooks") or {}).keys()),
            }
            for plugin in plugins
        ]

    def load_plugins(self, reload: bool = False) -> list[LoadedPlugin]:
        if self._loaded is not None and not reload:
            return self._loaded
        self.plugins_path.mkdir(parents=True, exist_ok=True)
        loaded: list[LoadedPlugin] = []
        for plugin_dir in sorted(path for path in self.plugins_path.iterdir() if path.is_dir()):
            config_path = plugin_dir / "plugin.json"
            if not config_path.exists():
                continue
            try:
                config = json.loads(config_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                self.events.emit("plugin.error", {"plugin": plugin_dir.name, "error": str(exc)})
                continue
            if config.get("enabled", True) is False:
                continue
            loaded.append(LoadedPlugin(name=config.get("name") or plugin_dir.name, path=plugin_dir, config=config))
        self._loaded = loaded
        self._last_loaded_at = int(time.time() * 1000)
        self.events.emit("plugins.loaded", {"count": len(loaded)})
        return loaded

    def run_incoming_hooks(self, message: str, context: dict[str, Any]) -> HookResult:
        return self._run_hook("transformIncoming", message, context)

    def run_outgoing_hooks(self, message: str, context: dict[str, Any]) -> HookResult:
        return self._run_hook("transformOutgoing", message, context)

    def broadcast_event(self, event_type: str, payload: dict[str, Any]) -> None:
        for plugin in self.load_plugins():
            events = plugin.config.get("events") or []
            if "*" in events or event_type in events:
                self.events.emit("plugin.event", {"plugin": plugin.name, "type": event_type, "payload": payload})

    def _run_hook(self, hook_name: str, message: str, context: dict[str, Any]) -> HookResult:
        text = message
        metadata: dict[str, Any] = {}
        for plugin in self.load_plugins():
            hooks = plugin.config.get("hooks") or {}
            hook = hooks.get(hook_name)
            if not isinstance(hook, dict):
                continue
            try:
                text, hook_metadata = self._apply_hook(text, hook, context)
            except Exception as exc:
                self.events.emit("plugin.error", {"plugin": plugin.name, "hook": hook_name, "error": str(exc)})
                continue
            metadata.update(hook_metadata)
            metadata.setdefault("plugins", []).append(plugin.name)
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
