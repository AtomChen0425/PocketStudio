from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from pocketStudio.core.config import Settings
from pocketStudio.services.plugin_service import PluginService


LONG_RESPONSE_THRESHOLD = 4000
SEND_FILE_RE = re.compile(r"\[send_file:\s*([^\]]+)\]")


@dataclass
class PreparedResponse:
    message: str
    files: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class ResponseService:
    def __init__(self, settings: Settings, plugins: PluginService | None = None) -> None:
        self.settings = settings
        self.plugins = plugins

    def prepare(
        self,
        response: str,
        existing_files: list[str] | None = None,
        context: dict | None = None,
    ) -> PreparedResponse:
        files = list(existing_files or [])
        cleaned = (response or "").strip()
        plugin_metadata: dict = {}
        if self.plugins:
            hooked = self.plugins.run_outgoing_hooks(cleaned, context or {})
            cleaned = hooked.text.strip()
            plugin_metadata = hooked.metadata
        tagged_files = self.collect_files(cleaned)
        for file_path in tagged_files:
            if file_path not in files:
                files.append(file_path)
        if tagged_files:
            cleaned = SEND_FILE_RE.sub("", cleaned).strip()

        metadata = {"responseLength": len(cleaned), **plugin_metadata}
        if len(cleaned) > LONG_RESPONSE_THRESHOLD:
            saved_file = self._save_long_response(cleaned)
            files.append(str(saved_file))
            preview = cleaned[:LONG_RESPONSE_THRESHOLD] + "\n\n_(Full response attached as file)_"
            metadata["truncated"] = True
            metadata["fullResponseFile"] = str(saved_file)
            return PreparedResponse(message=preview, files=files, metadata=metadata)
        metadata["truncated"] = False
        return PreparedResponse(message=cleaned, files=files, metadata=metadata)

    @staticmethod
    def collect_files(response: str) -> list[str]:
        files: list[str] = []
        for match in SEND_FILE_RE.finditer(response or ""):
            raw_path = match.group(1).strip()
            if raw_path and Path(raw_path).exists() and raw_path not in files:
                files.append(raw_path)
        return files

    def _save_long_response(self, response: str) -> Path:
        self.settings.files_path.mkdir(parents=True, exist_ok=True)
        path = self.settings.files_path / f"response_{int(time.time() * 1000)}.md"
        path.write_text(response, encoding="utf-8")
        return path
