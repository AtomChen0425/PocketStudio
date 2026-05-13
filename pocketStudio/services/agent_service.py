from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from pocketStudio.core.config import Settings
from pocketStudio.core.database import Database
from pocketStudio.core.json_store import read_json_object, write_json_object
from pocketStudio.models import Agent, AgentCreate


BUILTIN_AGENT_INSTRUCTIONS = """# pocketStudio Agent

You are an autonomous teammate inside pocketStudio.

<!-- TEAMMATES_START -->
<!-- TEAMMATES_END -->

## Memory

<!-- MEMORY_START -->
<!-- MEMORY_END -->

Use your workspace files carefully. Keep useful long-term notes in `memory/`.
"""


class AgentService:
    def __init__(self, db: Database, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    def create(self, payload: AgentCreate) -> Agent:
        workspace = payload.workspace or self.settings.workspace_path / payload.id
        heartbeat_interval = payload.heartbeat_interval
        if heartbeat_interval is None:
            heartbeat_interval = self._default_heartbeat_interval()
        self.ensure_workspace(workspace, payload)
        self.db.execute(
            """
            INSERT INTO agents (id, name, role, system_prompt, provider, model, workspace, enabled, heartbeat_enabled, heartbeat_interval)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              name = excluded.name,
              role = excluded.role,
              system_prompt = excluded.system_prompt,
              provider = excluded.provider,
              model = excluded.model,
              workspace = excluded.workspace,
              enabled = excluded.enabled,
              heartbeat_enabled = excluded.heartbeat_enabled,
              heartbeat_interval = excluded.heartbeat_interval,
              updated_at = CURRENT_TIMESTAMP
            """,
            (
                payload.id,
                payload.name,
                payload.role,
                payload.system_prompt,
                payload.provider,
                payload.model,
                str(workspace),
                int(payload.enabled),
                int(payload.heartbeat_enabled),
                heartbeat_interval,
            ),
        )
        agent = self.get(payload.id)
        self._sync_agent_settings(agent)
        return agent

    def get(self, agent_id: str) -> Agent:
        row = self.db.fetch_one("SELECT * FROM agents WHERE id = ?", (agent_id,))
        if row is None:
            raise KeyError(f"Agent '{agent_id}' not found")
        return self._to_agent(row)

    def list(self) -> list[Agent]:
        rows = self.db.fetch_all("SELECT * FROM agents ORDER BY id")
        return [self._to_agent(row) for row in rows]

    def delete(self, agent_id: str) -> None:
        self.db.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
        self._remove_agent_settings(agent_id)

    def ensure_workspace(self, workspace: Path, payload: AgentCreate | None = None) -> None:
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / ".pocketStudio").mkdir(exist_ok=True)
        (workspace / ".agents" / "skills").mkdir(parents=True, exist_ok=True)
        (workspace / ".claude").mkdir(exist_ok=True)
        (workspace / ".codex").mkdir(exist_ok=True)
        (workspace / "memory").mkdir(exist_ok=True)
        self.ensure_tool_skills_link(workspace / ".agents" / "skills", workspace / ".claude" / "skills")
        self.ensure_tool_skills_link(workspace / ".agents" / "skills", workspace / ".codex" / "skills")
        agents_md = workspace / "AGENTS.md"
        if not agents_md.exists():
            agents_md.write_text("", encoding="utf-8")
        heartbeat = workspace / "heartbeat.md"
        if not heartbeat.exists():
            heartbeat.write_text("# Heartbeat\n\nNo heartbeat configured yet.\n", encoding="utf-8")
        soul = workspace / ".pocketStudio" / "SOUL.md"
        if not soul.exists():
            soul.write_text(f"# {payload.name if payload else 'Agent'}\n\nDefine this agent's operating principles here.\n", encoding="utf-8")

    def workspace_status(self, agent_id: str, repair: bool = False) -> dict:
        agent = self.get(agent_id)
        before = self._workspace_checks(agent.workspace)
        repaired = [item["path"] for item in before if not item["ok"]]
        if repair and repaired:
            self.ensure_workspace(agent.workspace, agent)
        after = self._workspace_checks(agent.workspace)
        return {
            "ok": all(item["ok"] for item in after),
            "agentId": agent.id,
            "workspace": str(agent.workspace),
            "repaired": repaired if repair else [],
            "checks": after,
            "before": before if repair else None,
        }

    def get_system_prompt_file(self, agent_id: str) -> dict:
        agent = self.get(agent_id)
        path = agent.workspace / "AGENTS.md"
        self.ensure_workspace(agent.workspace)
        return {"content": path.read_text(encoding="utf-8"), "path": str(path)}

    def save_system_prompt_file(self, agent_id: str, content: str) -> None:
        agent = self.get(agent_id)
        self.ensure_workspace(agent.workspace)
        path = agent.workspace / "AGENTS.md"
        path.write_text(content, encoding="utf-8")

    def get_heartbeat_file(self, agent_id: str) -> dict:
        agent = self.get(agent_id)
        self.ensure_workspace(agent.workspace)
        path = agent.workspace / "heartbeat.md"
        return {
            "content": path.read_text(encoding="utf-8") if path.exists() else "",
            "path": str(path),
            "enabled": agent.heartbeat_enabled,
            "interval": agent.heartbeat_interval,
        }

    def save_heartbeat_file(
        self,
        agent_id: str,
        content: str | None = None,
        enabled: bool | None = None,
        interval: int | None = None,
    ) -> dict:
        agent = self.get(agent_id)
        self.ensure_workspace(agent.workspace)
        path = agent.workspace / "heartbeat.md"
        if content is not None:
            path.write_text(content, encoding="utf-8")
        if enabled is not None or interval is not None:
            interval_value = interval if interval is not None else agent.heartbeat_interval
            self.db.execute(
                """
                UPDATE agents
                SET heartbeat_enabled = COALESCE(?, heartbeat_enabled),
                    heartbeat_interval = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (int(enabled) if enabled is not None else None, interval_value, agent_id),
            )
        return self.get_heartbeat_file(agent_id)

    def build_system_prompt(self, agent_id: str, teammates: str = "") -> str:
        agent = self.get(agent_id)
        self.ensure_workspace(agent.workspace)
        prompt = BUILTIN_AGENT_INSTRUCTIONS
        prompt = prompt.replace("<!-- TEAMMATES_START -->\n<!-- TEAMMATES_END -->", teammates.strip())
        memory_index = self.load_memory_index(agent_id)
        memory_block = (
            f"\n{memory_index}\n\nTo read a memory in detail, open the file under `memory/`."
            if memory_index
            else "\nNo memories yet. Use memory files to build long-term context.\n"
        )
        prompt = prompt.replace("<!-- MEMORY_START -->\n<!-- MEMORY_END -->", memory_block)
        file_prompt = self.get_system_prompt_file(agent_id)["content"].strip()
        if file_prompt:
            prompt += f"\n\n{file_prompt}"
        if agent.system_prompt:
            prompt += f"\n\n{agent.system_prompt}"
        return prompt

    def load_memory_index(self, agent_id: str) -> str:
        agent = self.get(agent_id)
        memory_dir = agent.workspace / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        tree = self.scan_memory_tree(memory_dir, "")
        return self._format_memory_tree(tree)

    def list_memory_files(self, agent_id: str) -> dict:
        agent = self.get(agent_id)
        memory_dir = agent.workspace / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        files = [
            {"name": path.name, "path": str(path), "relativePath": path.relative_to(memory_dir).as_posix()}
            for path in sorted(memory_dir.rglob("*.md"))
            if path.is_file() and not any(part.startswith(".") for part in path.relative_to(memory_dir).parts)
        ]
        tree = self.scan_memory_tree(memory_dir, "")
        return {
            "index": self._format_memory_tree(tree),
            "tree": tree,
            "files": files,
            "memoryDir": str(memory_dir),
        }

    def get_memory_file(self, agent_id: str, relative_path: str) -> dict:
        agent = self.get(agent_id)
        memory_dir = agent.workspace / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        path = self._resolve_memory_path(memory_dir, relative_path)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Memory file '{relative_path}' not found")
        content = path.read_text(encoding="utf-8")
        return {
            "path": str(path),
            "relativePath": path.relative_to(memory_dir.resolve()).as_posix(),
            "content": content,
            "frontmatter": self._parse_frontmatter(content),
        }

    def save_memory_file(self, agent_id: str, relative_path: str, content: str, create_dirs: bool = True) -> dict:
        agent = self.get(agent_id)
        memory_dir = agent.workspace / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        path = self._resolve_memory_path(memory_dir, relative_path)
        if create_dirs:
            path.parent.mkdir(parents=True, exist_ok=True)
        elif not path.parent.exists():
            raise FileNotFoundError(f"Memory folder '{path.parent.relative_to(memory_dir.resolve()).as_posix()}' not found")
        path.write_text(content, encoding="utf-8")
        return self.get_memory_file(agent_id, path.relative_to(memory_dir.resolve()).as_posix())

    def delete_memory_file(self, agent_id: str, relative_path: str) -> dict:
        agent = self.get(agent_id)
        memory_dir = agent.workspace / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        path = self._resolve_memory_path(memory_dir, relative_path)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Memory file '{relative_path}' not found")
        path.unlink()
        return {"ok": True, "relativePath": path.relative_to(memory_dir.resolve()).as_posix()}

    def list_skills(self, agent_id: str) -> list[dict]:
        agent = self.get(agent_id)
        skills_dir = agent.workspace / ".agents" / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        skills = []
        for path in sorted(skills_dir.rglob("SKILL.md")):
            skill_id = path.parent.name
            content = path.read_text(encoding="utf-8", errors="ignore")
            first_heading = next((line[2:].strip() for line in content.splitlines() if line.startswith("# ")), skill_id)
            skills.append({"id": skill_id, "name": first_heading, "description": str(path)})
        return skills

    def install_skill_placeholder(self, agent_id: str, ref: str) -> Path:
        agent = self.get(agent_id)
        skills_dir = agent.workspace / ".agents" / "skills"
        safe_name = self._safe_name(ref)
        target = skills_dir / safe_name
        target.mkdir(parents=True, exist_ok=True)
        skill_path = target / "SKILL.md"
        if not skill_path.exists():
            skill_path.write_text(f"# {ref}\n\nInstalled placeholder for pocketStudio.\n", encoding="utf-8")
        self.ensure_tool_skills_link(agent.workspace / ".agents" / "skills", agent.workspace / ".claude" / "skills")
        self.ensure_tool_skills_link(agent.workspace / ".agents" / "skills", agent.workspace / ".codex" / "skills")
        return skill_path

    @classmethod
    def scan_memory_tree(cls, dir_path: Path, relative_path: str) -> dict:
        folder = {
            "name": dir_path.name,
            "path": relative_path,
            "entries": [],
            "subfolders": [],
        }
        if not dir_path.exists():
            return folder
        for item in sorted(dir_path.iterdir(), key=lambda path: path.name):
            if item.name.startswith("."):
                continue
            item_relative = f"{relative_path}/{item.name}" if relative_path else item.name
            if item.is_dir():
                subfolder = cls.scan_memory_tree(item, item_relative)
                if subfolder["entries"] or subfolder["subfolders"]:
                    folder["subfolders"].append(subfolder)
            elif item.is_file() and item.suffix == ".md":
                frontmatter = cls._parse_frontmatter(item.read_text(encoding="utf-8", errors="ignore"))
                if frontmatter:
                    folder["entries"].append(
                        {
                            "name": frontmatter["name"],
                            "summary": frontmatter["summary"],
                            "filePath": item_relative,
                        }
                    )
        return folder

    @classmethod
    def _format_memory_tree(cls, folder: dict, indent: int = 0) -> str:
        prefix = "  " * indent
        lines: list[str] = []
        for entry in folder.get("entries", []):
            lines.append(f"{prefix}- **{entry['name']}** - {entry['summary']}  `{entry['filePath']}`")
        for subfolder in folder.get("subfolders", []):
            lines.append(f"{prefix}- **[{subfolder['name']}/]**")
            subtree = cls._format_memory_tree(subfolder, indent + 1)
            if subtree:
                lines.append(subtree)
        return "\n".join(lines)

    @staticmethod
    def ensure_tool_skills_link(source: Path, target: Path) -> None:
        source.mkdir(parents=True, exist_ok=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() or target.is_symlink():
            if target.is_dir() and not target.is_symlink():
                AgentService._sync_skill_tree(source, target)
            return
        try:
            target.symlink_to(source.resolve(), target_is_directory=True)
        except OSError:
            target.mkdir(parents=True, exist_ok=True)
            AgentService._sync_skill_tree(source, target)

    @staticmethod
    def _ensure_claude_skills_link(workspace: Path) -> None:
        AgentService.ensure_tool_skills_link(workspace / ".agents" / "skills", workspace / ".claude" / "skills")

    @staticmethod
    def _sync_skill_tree(source: Path, target: Path) -> None:
        if source.resolve() == target.resolve():
            return
        for path in source.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(source)
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)

    @staticmethod
    def _workspace_checks(workspace: Path) -> list[dict]:
        checks = [
            ("directory", workspace),
            ("directory", workspace / ".pocketStudio"),
            ("directory", workspace / ".agents" / "skills"),
            ("directory", workspace / ".claude"),
            ("directory", workspace / ".codex"),
            ("directory", workspace / "memory"),
            ("file", workspace / "AGENTS.md"),
            ("file", workspace / "heartbeat.md"),
            ("file", workspace / ".pocketStudio" / "SOUL.md"),
            ("skillsLink", workspace / ".claude" / "skills"),
            ("skillsLink", workspace / ".codex" / "skills"),
        ]
        result = []
        for kind, path in checks:
            if kind == "directory":
                ok = path.is_dir()
            elif kind == "file":
                ok = path.is_file()
            else:
                ok = path.is_symlink() or path.is_dir()
            result.append({"path": str(path), "relativePath": path.relative_to(workspace).as_posix() if path != workspace else ".", "kind": kind, "ok": ok})
        return result

    @staticmethod
    def _safe_name(value: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-").lower() or "skill"

    @staticmethod
    def _resolve_memory_path(memory_dir: Path, relative_path: str) -> Path:
        if not relative_path or not isinstance(relative_path, str):
            raise ValueError("memory path is required")
        normalized = relative_path.replace("\\", "/").strip("/")
        parts = Path(normalized).parts
        if not normalized.endswith(".md"):
            raise ValueError("memory path must end with .md")
        if any(part in {"", ".", ".."} or part.startswith(".") for part in parts):
            raise ValueError("memory path must stay inside memory/ and cannot include hidden path segments")
        root = memory_dir.resolve()
        path = (memory_dir / normalized).resolve()
        if root != path and root not in path.parents:
            raise ValueError("memory path must stay inside memory/")
        return path

    @staticmethod
    def _parse_frontmatter(content: str) -> dict | None:
        match = re.match(r"^---\s*\n(.*?)\n---", content, flags=re.DOTALL)
        if not match:
            return None
        values: dict[str, str] = {}
        for line in match.group(1).splitlines():
            key, sep, value = line.partition(":")
            if sep:
                values[key.strip()] = value.strip().strip("\"'")
        if not values.get("name") or not values.get("summary"):
            return None
        return {"name": values["name"], "summary": values["summary"]}

    def _default_heartbeat_interval(self) -> int:
        file_settings = read_json_object(self.settings.settings_path)
        try:
            value = (file_settings.get("monitoring") or {}).get("heartbeat_interval")
            if value is not None:
                return int(value)
        except (TypeError, ValueError):
            pass
        row = self.db.fetch_one("SELECT value FROM app_settings WHERE key = ?", ("monitoring",))
        if row is not None:
            try:
                value = json.loads(row["value"]).get("heartbeat_interval")
                if value is not None:
                    return int(value)
            except (TypeError, ValueError, json.JSONDecodeError):
                pass
        return self.settings.heartbeat_interval_seconds

    def _sync_agent_settings(self, agent: Agent) -> None:
        data = read_json_object(self.settings.settings_path)
        agents = data.setdefault("agents", {})
        agents[agent.id] = {
            "name": agent.name,
            "provider": agent.provider,
            "model": agent.model or "",
            "working_directory": str(agent.workspace),
            "system_prompt": agent.system_prompt or agent.role,
            "heartbeat": {"enabled": agent.heartbeat_enabled, "interval": agent.heartbeat_interval},
        }
        write_json_object(self.settings.settings_path, data)

    def _remove_agent_settings(self, agent_id: str) -> None:
        data = read_json_object(self.settings.settings_path)
        agents = data.get("agents")
        if isinstance(agents, dict) and agent_id in agents:
            agents.pop(agent_id, None)
            write_json_object(self.settings.settings_path, data)

    @staticmethod
    def _to_agent(row) -> Agent:
        return Agent(
            id=row["id"],
            name=row["name"],
            role=row["role"],
            system_prompt=row["system_prompt"],
            provider=row["provider"],
            model=row["model"],
            workspace=row["workspace"],
            enabled=bool(row["enabled"]),
            heartbeat_enabled=bool(row["heartbeat_enabled"]),
            heartbeat_interval=row["heartbeat_interval"],
        )
