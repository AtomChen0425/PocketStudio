from functools import lru_cache

from pocketStudio.core.config import get_settings
from pocketStudio.core.database import Database
from pocketStudio.providers.registry import ProviderRegistry
from pocketStudio.services.agent_service import AgentService
from pocketStudio.services.channel_service import ChannelService
from pocketStudio.services.chat_service import ChatService
from pocketStudio.services.event_service import EventService
from pocketStudio.services.heartbeat_service import HeartbeatService
from pocketStudio.services.orchestrator import Orchestrator
from pocketStudio.services.plugin_service import PluginService
from pocketStudio.services.project_service import ProjectService
from pocketStudio.services.queue_service import QueueService
from pocketStudio.services.response_service import ResponseService
from pocketStudio.services.schedule_service import ScheduleService
from pocketStudio.services.settings_service import SettingsService
from pocketStudio.services.task_service import TaskService
from pocketStudio.services.team_service import TeamService
from pocketStudio.services.worker_service import WorkerService


@lru_cache
def get_database() -> Database:
    settings = get_settings()
    db = Database(settings.database_path, journal_mode=settings.sqlite_journal_mode)
    db.initialize()
    return db


@lru_cache
def get_event_service() -> EventService:
    return EventService(get_database(), get_settings())


@lru_cache
def get_agent_service() -> AgentService:
    return AgentService(get_database(), get_settings())


@lru_cache
def get_team_service() -> TeamService:
    return TeamService(get_database(), get_settings())


@lru_cache
def get_queue_service() -> QueueService:
    return QueueService(get_database(), get_event_service(), get_settings(), get_response_service(), get_plugin_service())


@lru_cache
def get_response_service() -> ResponseService:
    return ResponseService(get_settings(), get_plugin_service())


@lru_cache
def get_plugin_service() -> PluginService:
    plugins = PluginService(get_settings(), get_event_service())
    get_event_service().add_listener(plugins.handle_event)
    return plugins


@lru_cache
def get_chat_service() -> ChatService:
    return ChatService(get_database(), get_event_service())


@lru_cache
def get_channel_service() -> ChannelService:
    return ChannelService(get_database(), get_agent_service(), get_team_service())


@lru_cache
def get_task_service() -> TaskService:
    return TaskService(get_database(), get_event_service())


@lru_cache
def get_project_service() -> ProjectService:
    return ProjectService(get_database(), get_event_service())


@lru_cache
def get_schedule_service() -> ScheduleService:
    return ScheduleService(get_database(), get_event_service())


@lru_cache
def get_settings_service() -> SettingsService:
    return SettingsService(get_database(), get_settings())


@lru_cache
def get_heartbeat_service() -> HeartbeatService:
    return HeartbeatService(get_database(), get_agent_service(), get_event_service(), get_settings())


@lru_cache
def get_provider_registry() -> ProviderRegistry:
    return ProviderRegistry(get_database())


@lru_cache
def get_orchestrator() -> Orchestrator:
    return Orchestrator(
        agents=get_agent_service(),
        teams=get_team_service(),
        queue=get_queue_service(),
        chat=get_chat_service(),
        events=get_event_service(),
        providers=get_provider_registry(),
    )


@lru_cache
def get_worker_service() -> WorkerService:
    return WorkerService(
        get_orchestrator(),
        get_schedule_service(),
        get_heartbeat_service(),
        get_event_service(),
        get_settings(),
    )
