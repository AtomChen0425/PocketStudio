from pathlib import Path
from uuid import uuid4

from pocketStudio.core.config import Settings
from pocketStudio.core.database import Database
from pocketStudio.models import MessageCreate
from pocketStudio.services.event_service import EventService
from pocketStudio.services.plugin_service import PluginService
from pocketStudio.services.queue_service import QueueService
from pocketStudio.services.response_service import ResponseService


def test_plugin_hooks_transform_incoming_and_outgoing() -> None:
    home = Path(".pytest-local") / f"plugin-home-{uuid4().hex[:8]}"
    plugin_dir = home / "plugins" / "demo"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.json").write_text(
        """
        {
          "name": "demo",
          "hooks": {
            "transformIncoming": {"action": "prepend", "text": "[in] "},
            "transformOutgoing": {"action": "append", "text": " [out]", "metadata": {"parseMode": "markdown"}}
          }
        }
        """,
        encoding="utf-8",
    )
    settings = Settings(pocketStudio_home=home)
    db = Database(settings.database_path)
    db.initialize()
    events = EventService(db)
    plugins = PluginService(settings, events)
    responses = ResponseService(settings, plugins)
    queue = QueueService(db, events, settings, responses, plugins)

    message = queue.enqueue(MessageCreate(target="@agent:test", content="hello", sender="tester"))
    queue.mark_done(
        message.id,
        '{"runs":[{"agent_id":"test","input":"hello","output":"reply"}],"output":"reply","message_id":1,"target":"@agent:test"}',
    )
    jobs = queue.enqueue_responses_from_message(queue.get(message.id))

    assert queue.get(message.id).content == "[in] hello"
    assert jobs[0].message == "reply [out]"
    assert jobs[0].metadata["parseMode"] == "markdown"
    assert jobs[0].metadata["plugins"] == ["demo"]
