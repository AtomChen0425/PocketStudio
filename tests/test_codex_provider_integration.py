import os
import shutil
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_CODEX_INTEGRATION") != "1",
    reason="Set RUN_CODEX_INTEGRATION=1 to run the real Codex CLI integration test.",
)


def test_api_message_can_be_processed_by_real_codex_provider() -> None:
    if shutil.which("codex") is None:
        pytest.skip("codex CLI is not available on PATH")

    home = Path(".pytest-tmp") / f"codex-api-{uuid.uuid4().hex}"
    shutil.rmtree(home, ignore_errors=True)
    home.mkdir(parents=True, exist_ok=True)

    previous_home = os.environ.get("POCKETSTUDIO_HOME")
    previous_worker_enabled = os.environ.get("POCKETSTUDIO_WORKER_ENABLED")
    os.environ["POCKETSTUDIO_HOME"] = str(home)
    os.environ["POCKETSTUDIO_WORKER_ENABLED"] = "false"
    get_settings_cache = None

    try:
        from pocketStudio.core.config import get_settings
        from pocketStudio.core import dependencies

        get_settings_cache = get_settings
        get_settings.cache_clear()
        for cached in (
            dependencies.get_database,
            dependencies.get_event_service,
            dependencies.get_agent_service,
            dependencies.get_team_service,
            dependencies.get_queue_service,
            dependencies.get_response_service,
            dependencies.get_plugin_service,
            dependencies.get_chat_service,
            dependencies.get_channel_service,
            dependencies.get_task_service,
            dependencies.get_project_service,
            dependencies.get_schedule_service,
            dependencies.get_settings_service,
            dependencies.get_heartbeat_service,
            dependencies.get_provider_registry,
            dependencies.get_orchestrator,
            dependencies.get_worker_service,
        ):
            cached.cache_clear()

        from pocketStudio.main import create_app

        app = create_app()
        agent_id = f"codex-api-{uuid.uuid4().hex[:8]}"
        expected = "pocketStudio API codex ok"

        with TestClient(app) as client:
            agent_response = client.post(
                "/api/agents",
                json={
                    "id": agent_id,
                    "name": "Codex API Smoke",
                    "role": "Reply with exactly the requested text and no extra commentary.",
                    "provider": "codex",
                    "model": None,
                    "workspace": str(Path.cwd()),
                    "heartbeat_enabled": False,
                },
            )
            assert agent_response.status_code == 200, agent_response.text

            message_response = client.post(
                "/api/messages",
                json={
                    "target": f"@agent:{agent_id}",
                    "content": f"Reply exactly: {expected}",
                    "sender": "integration-test",
                },
            )
            assert message_response.status_code == 200, message_response.text

            message_id = message_response.json()["id"]
            process_response = client.post(f"/api/messages/{message_id}/process")

            if process_response.status_code == 422 and _is_codex_windows_permission_error(process_response.text):
                if os.getenv("RUN_CODEX_INTEGRATION_STRICT") == "1":
                    pytest.fail(process_response.text)
                pytest.skip(
                    "Codex CLI is installed but Windows denied launch/session access from this Python process. "
                    "Run from an unrestricted PowerShell session, or set RUN_CODEX_INTEGRATION_STRICT=1 to fail here."
                )

            assert process_response.status_code == 200, process_response.text
            output = process_response.json()["output"]
            assert expected in output

            queue_response = client.get(f"/api/queue/{message_id}")
            assert queue_response.status_code == 200, queue_response.text
            assert queue_response.json()["status"] == "done"

            responses = client.get("/api/responses?limit=5")
            assert responses.status_code == 200, responses.text
            assert any(expected in response["message"] for response in responses.json())
    finally:
        if get_settings_cache is not None:
            get_settings_cache.cache_clear()
        if previous_home is None:
            os.environ.pop("POCKETSTUDIO_HOME", None)
        else:
            os.environ["POCKETSTUDIO_HOME"] = previous_home
        if previous_worker_enabled is None:
            os.environ.pop("POCKETSTUDIO_WORKER_ENABLED", None)
        else:
            os.environ["POCKETSTUDIO_WORKER_ENABLED"] = previous_worker_enabled
        shutil.rmtree(home, ignore_errors=True)


def _is_codex_windows_permission_error(text: str) -> bool:
    return "WinError 5" in text or "拒绝访问" in text or "permission denied" in text.lower()
