from __future__ import annotations

import json
import re
from pathlib import Path

from pocketStudio.core.config import Settings
from pocketStudio.core.database import Database
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
        (workspace / "memory").mkdir(exist_ok=True)
        agents_md = workspace / "AGENTS.md"
        if not agents_md.exists():
            agents_md.write_text("", encoding="utf-8")
        heartbeat = workspace / "heartbeat.md"
        if not heartbeat.exists():
            heartbeat.write_text("# Heartbeat\n\nNo heartbeat configured yet.\n", encoding="utf-8")
        soul = workspace / ".pocketStudio" / "SOUL.md"
        if not soul.exists():
            soul.write_text(f"# {payload.name if payload else 'Agent'}\n\nDefine this agent's operating principles here.\n", encoding="utf-8")

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
        entries: list[str] = []
        for path in sorted(memory_dir.rglob("*.md")):
            if any(part.startswith(".") for part in path.relative_to(memory_dir).parts):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            frontmatter = self._parse_frontmatter(text)
            if not frontmatter:
                continue
            relative = path.relative_to(memory_dir).as_posix()
            entries.append(f"- **{frontmatter['name']}** - {frontmatter['summary']}  `{relative}`")
        return "\n".join(entries)

    def list_memory_files(self, agent_id: str) -> dict:
        agent = self.get(agent_id)
        memory_dir = agent.workspace / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        files = [
            {"name": path.name, "path": str(path), "relativePath": path.relative_to(memory_dir).as_posix()}
            for path in sorted(memory_dir.rglob("*.md"))
            if path.is_file()
        ]
        return {"index": self.load_memory_index(agent_id), "files": files, "memoryDir": str(memory_dir)}

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
        return skill_path

    @staticmethod
    def _safe_name(value: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-").lower() or "skill"

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
        file_settings = self._read_settings_file()
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

    def _read_settings_file(self) -> dict:
        path = self.settings.settings_path
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _write_settings_file(self, data: dict) -> None:
        self.settings.pocketStudio_home.mkdir(parents=True, exist_ok=True)
        self.settings.settings_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _sync_agent_settings(self, agent: Agent) -> None:
        data = self._read_settings_file()
        agents = data.setdefault("agents", {})
        agents[agent.id] = {
            "name": agent.name,
            "provider": agent.provider,
            "model": agent.model or "",
            "working_directory": str(agent.workspace),
            "system_prompt": agent.system_prompt or agent.role,
            "heartbeat": {"enabled": agent.heartbeat_enabled, "interval": agent.heartbeat_interval},
        }
        self._write_settings_file(data)

    def _remove_agent_settings(self, agent_id: str) -> None:
        data = self._read_settings_file()
        agents = data.get("agents")
        if isinstance(agents, dict) and agent_id in agents:
            agents.pop(agent_id, None)
            self._write_settings_file(data)

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
