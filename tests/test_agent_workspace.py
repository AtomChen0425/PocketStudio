import uuid
import shutil
from pathlib import Path

from pocketStudio.core.dependencies import get_database
from fastapi.testclient import TestClient

from pocketStudio.main import app


def test_agent_workspace_prompt_memory_and_skills() -> None:
    agent_id = f"workspace-agent-{uuid.uuid4().hex[:8]}"

    with TestClient(app) as client:
        response = client.post(
            "/api/agents",
            json={"id": agent_id, "name": "Workspace Agent", "role": "Owns files", "provider": "local"},
        )
        assert response.status_code == 200
        workspace = Path(response.json()["workspace"])

        assert (workspace / "AGENTS.md").exists()
        assert (workspace / "heartbeat.md").exists()
        assert (workspace / "memory").is_dir()
        assert (workspace / ".agents" / "skills").is_dir()
        assert (workspace / ".agents" / "skills" / "tasks" / "SKILL.md").is_file()
        assert (workspace / ".agents" / "skills" / "pocketstudio-admin" / "SKILL.md").is_file()
        assert (workspace / ".pocketStudio" / "SOUL.md").exists()
        assert (workspace / ".claude" / "skills").exists()
        assert (workspace / ".codex" / "skills").exists()

        prompt_update = client.put(
            f"/api/agents/{agent_id}/system-prompt",
            json={"content": "Always write crisp implementation notes."},
        )
        assert prompt_update.status_code == 200

        prompt_response = client.get(f"/api/agents/{agent_id}/system-prompt")
        assert prompt_response.status_code == 200
        assert "crisp implementation notes" in prompt_response.json()["content"]

        memory_file = workspace / "memory" / "design.md"
        memory_file.write_text(
            "---\nname: Design Context\nsummary: Notes about architectural intent\n---\n\nBody.\n",
            encoding="utf-8",
        )
        nested_dir = workspace / "memory" / "projects"
        nested_dir.mkdir()
        (nested_dir / "roadmap.md").write_text(
            "---\nname: Roadmap\nsummary: Planned implementation sequence\n---\n\nBody.\n",
            encoding="utf-8",
        )
        (workspace / "memory" / ".hidden.md").write_text(
            "---\nname: Hidden\nsummary: Should not appear\n---\n\nBody.\n",
            encoding="utf-8",
        )
        memory_response = client.get(f"/api/agents/{agent_id}/memory")
        assert memory_response.status_code == 200
        memory = memory_response.json()
        assert "Design Context" in memory["index"]
        assert "Roadmap" in memory["index"]
        assert "Hidden" not in memory["index"]
        assert any(item["name"] == "design.md" for item in memory["files"])
        assert memory["tree"]["entries"][0]["filePath"] == "design.md"
        assert memory["tree"]["subfolders"][0]["name"] == "projects"
        assert memory["tree"]["subfolders"][0]["entries"][0]["filePath"] == "projects/roadmap.md"

        install_response = client.post(
            f"/api/agents/{agent_id}/skills/install",
            json={"ref": "memory"},
        )
        assert install_response.status_code == 200
        skills_response = client.get(f"/api/agents/{agent_id}/skills")
        assert skills_response.status_code == 200
        assert any(item["id"] == "memory" for item in skills_response.json())


def test_agent_workspace_status_and_repair() -> None:
    agent_id = f"repair-agent-{uuid.uuid4().hex[:8]}"

    with TestClient(app) as client:
        response = client.post(
            "/api/agents",
            json={"id": agent_id, "name": "Repair Agent", "role": "Repairs workspace", "provider": "local"},
        )
        assert response.status_code == 200
        workspace = Path(".pytest-local") / f"missing-workspace-{uuid.uuid4().hex[:8]}"
        shutil.rmtree(workspace, ignore_errors=True)
        get_database().execute("UPDATE agents SET workspace = ? WHERE id = ?", (str(workspace), agent_id))

        broken = client.get(f"/api/agents/{agent_id}/workspace")
        repaired = client.post(f"/api/agents/{agent_id}/workspace/repair")
        healthy = client.get(f"/api/agents/{agent_id}/workspace")

        assert broken.status_code == 200
        assert broken.json()["ok"] is False
        assert any(item["relativePath"] == "heartbeat.md" and item["ok"] is False for item in broken.json()["checks"])
        assert any(item["relativePath"] == "memory" and item["ok"] is False for item in broken.json()["checks"])

        assert repaired.status_code == 200
        assert repaired.json()["ok"] is True
        assert "heartbeat.md" in {Path(path).name for path in repaired.json()["repaired"]}
        assert (workspace / "heartbeat.md").exists()
        assert (workspace / "memory").is_dir()
        assert (workspace / ".agents" / "skills" / "tasks" / "SKILL.md").is_file()
        assert (workspace / ".codex" / "skills").exists()
        assert healthy.json()["ok"] is True


def test_agent_memory_file_api_manages_markdown_safely() -> None:
    agent_id = f"memory-api-agent-{uuid.uuid4().hex[:8]}"
    workspace = Path(".pytest-local") / f"memory-api-workspace-{uuid.uuid4().hex[:8]}"
    content = "---\nname: API Memory\nsummary: Created through the backend\n---\n\nBody."

    with TestClient(app) as client:
        created = client.post(
            "/api/agents",
            json={
                "id": agent_id,
                "name": "Memory API Agent",
                "role": "Writes memories",
                "provider": "local",
                "workspace": str(workspace),
            },
        )
        assert created.status_code == 200

        saved = client.put(
            f"/api/agents/{agent_id}/memory/file",
            json={"path": "projects/api-memory.md", "content": content},
        )
        read = client.get(f"/api/agents/{agent_id}/memory/file", params={"path": "projects/api-memory.md"})
        index = client.get(f"/api/agents/{agent_id}/memory")
        traversal = client.put(
            f"/api/agents/{agent_id}/memory/file",
            json={"path": "../escape.md", "content": content},
        )
        hidden = client.get(f"/api/agents/{agent_id}/memory/file", params={"path": ".hidden.md"})
        deleted = client.delete(f"/api/agents/{agent_id}/memory/file", params={"path": "projects/api-memory.md"})
        missing = client.get(f"/api/agents/{agent_id}/memory/file", params={"path": "projects/api-memory.md"}) if deleted.status_code == 200 else None

        assert saved.status_code == 200
        assert saved.json()["relativePath"] == "projects/api-memory.md"
        assert saved.json()["frontmatter"] == {"name": "API Memory", "summary": "Created through the backend"}
        assert read.status_code == 200
        assert read.json()["content"] == content
        assert "API Memory" in index.json()["index"]
        assert traversal.status_code == 422
        assert hidden.status_code == 422
        assert deleted.status_code in {200, 409}
        if deleted.status_code == 200:
            assert missing.status_code == 404
        else:
            assert "Permission" in deleted.json()["detail"] or "拒绝访问" in deleted.json()["detail"]
