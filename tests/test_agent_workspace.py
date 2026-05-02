import uuid
from pathlib import Path

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
        assert (workspace / ".pocketStudio" / "SOUL.md").exists()
        assert (workspace / ".claude" / "skills").exists()

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
