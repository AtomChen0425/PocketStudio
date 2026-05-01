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
        memory_response = client.get(f"/api/agents/{agent_id}/memory")
        assert memory_response.status_code == 200
        assert "Design Context" in memory_response.json()["index"]
        assert any(item["name"] == "design.md" for item in memory_response.json()["files"])

        install_response = client.post(
            f"/api/agents/{agent_id}/skills/install",
            json={"ref": "memory"},
        )
        assert install_response.status_code == 200
        skills_response = client.get(f"/api/agents/{agent_id}/skills")
        assert skills_response.status_code == 200
        assert any(item["id"] == "memory" for item in skills_response.json())

