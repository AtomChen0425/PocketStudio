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


def test_python_plugin_module_hooks_and_event_handlers() -> None:
    home = Path(".pytest-local") / f"plugin-home-{uuid4().hex[:8]}"
    plugin_dir = home / "plugins" / "python-demo"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.py").write_text(
        '''
def transform_incoming(message, ctx):
    return {"text": f"{message} [py-in]", "metadata": {"incoming": ctx["sender"]}}


def transform_outgoing(message, ctx):
    return f"[py-out] {message}"


def activate(ctx):
    ctx.log("INFO", f"home={ctx.get_pocketstudio_home()}")

    def on_custom(event):
        ctx.log("INFO", f"saw {event['type']}:{event['value']}")

    ctx.on("custom.event", on_custom)


hooks = {
    "transformIncoming": transform_incoming,
    "transformOutgoing": transform_outgoing,
}
        ''',
        encoding="utf-8",
    )
    settings = Settings(pocketStudio_home=home)
    db = Database(settings.database_path)
    db.initialize()
    events = EventService(db)
    plugins = PluginService(settings, events)
    events.add_listener(plugins.handle_event)

    listed = plugins.list_plugins()
    assert listed == [
        {
            "name": "python-demo",
            "path": str(plugin_dir),
            "enabled": True,
            "hooks": ["transformIncoming", "transformOutgoing"],
            "runtime": "python",
        }
    ]

    incoming = plugins.run_incoming_hooks("hello", {"channel": "web", "sender": "tester"})
    outgoing = plugins.run_outgoing_hooks("reply", {"channel": "web", "sender": "tester"})
    events.emit("custom.event", {"value": "42"})

    assert incoming.text == "hello [py-in]"
    assert incoming.metadata["incoming"] == "tester"
    assert incoming.metadata["plugins"] == ["python-demo"]
    assert outgoing.text == "[py-out] reply"
    assert outgoing.metadata["plugins"] == ["python-demo"]

    log_events = [event for event in events.list(limit=20) if event.type == "plugin.log"]
    messages = [event.payload["message"] for event in log_events]
    assert any(message.startswith("home=") for message in messages)
    assert "saw custom.event:42" in messages
