from functools import lru_cache

from pocketStudio.core.config import get_settings
from pocketStudio.core.database import Database
from pocketStudio.providers.registry import ProviderRegistry
from pocketStudio.services.agent_service import AgentService
from pocketStudio.services.chat_service import ChatService
from pocketStudio.services.event_service import EventService
from pocketStudio.services.orchestrator import Orchestrator
from pocketStudio.services.queue_service import QueueService
from pocketStudio.services.task_service import TaskService
from pocketStudio.services.team_service import TeamService


@lru_cache
def get_database() -> Database:
    settings = get_settings()
    db = Database(settings.database_path, journal_mode=settings.sqlite_journal_mode)
    db.initialize()
    return db


@lru_cache
def get_event_service() -> EventService:
    return EventService(get_database())


@lru_cache
def get_agent_service() -> AgentService:
    return AgentService(get_database(), get_settings())


@lru_cache
def get_team_service() -> TeamService:
    return TeamService(get_database())


@lru_cache
def get_queue_service() -> QueueService:
    return QueueService(get_database(), get_event_service(), get_settings())


@lru_cache
def get_chat_service() -> ChatService:
    return ChatService(get_database(), get_event_service())


@lru_cache
def get_task_service() -> TaskService:
    return TaskService(get_database(), get_event_service())


@lru_cache
def get_provider_registry() -> ProviderRegistry:
    return ProviderRegistry()


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
