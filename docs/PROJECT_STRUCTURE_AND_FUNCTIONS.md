# pocketStudio Project Structure and Function Index

This document is generated from the Python backend source so maintainers can see module ownership and function entry points in one place. It intentionally excludes `tinyoffice/`, static build artifacts, and `__pycache__` files.

## Project Structure

- `pocketStudio/api/`: FastAPI route modules. Keep request/response shaping here and delegate business logic to services.
- `pocketStudio/channels/`: External channel bridges. Each channel should own its transport API and call core queue/pairing services.
- `pocketStudio/core/`: Configuration, database, dependency construction, runtime helpers, and shared IDs.
- `pocketStudio/providers/`: Agent harness/provider adapters. Keep subprocess and provider-specific parsing here.
- `pocketStudio/services/`: Domain services for agents, queues, teams, projects, schedules, settings, events, and orchestration.
- `pocketStudio/static/`: Small bundled fallback UI served by FastAPI. The primary frontend is tinyoffice.
- `docs/`: architecture notes, TinyAGI mapping, and maintenance documentation.
- `tests/`: pytest coverage for backend behavior and compatibility contracts.
- `tinyoffice/`: adapted frontend. Keep backend refactors from forcing broad frontend rewrites unless an API contract changes intentionally.

## Maintenance Rules

- Keep route modules thin: validate HTTP input, shape responses, and call services.
- Put external transports under `pocketStudio/channels/`; do not mix transport loops into generic services.
- Keep provider/harness logic under `pocketStudio/providers/`; channel bridges should only enqueue messages and deliver responses.
- Store runtime state outside user settings unless it is true configuration. For example, Telegram offset state lives under `.pocketStudio/channels/`.
- Prefer adding focused service methods over expanding `api/compat.py` with business logic.
- Update this document and `docs/TINYAGI_PACKAGE_MAPPING.md` when moving modules or adding public behavior.

## Extension Points

- New channel: add `pocketStudio/channels/<name>.py`, wire it in `core/dependencies.py`, expose service actions in `api/compat.py`, and add tests for pairing, inbound queueing, outbound response acking, and error handling.
- New provider: add a provider class in `pocketStudio/providers/`, register it in `ProviderRegistry`, and cover command resolution plus response extraction.
- New control-plane endpoint: keep data changes in a service, expose a small API wrapper, and add TinyOffice/API compatibility tests.
- New persisted field: update `core/database.py` schema and migration, the Pydantic model in `models.py`, the service conversion helper, and at least one compatibility test.

## Module and Function Index

### `pocketStudio/__init__.py`

pocketStudio backend package.

### `pocketStudio/api/__init__.py`

API routers.

### `pocketStudio/api/agents.py`

HTTP route handlers and compatibility payload shaping.

| Function | Usage |
|---|---|
| `list_agents(service: AgentService=Depends(get_agent_service)) -> list[Agent]` | Lists records or projections from storage/API. |
| `upsert_agent(payload: AgentCreate, service: AgentService=Depends(get_agent_service)) -> Agent` | Helper used by this module/class. Inspect callers before changing behavior. |
| `update_agent(agent_id: str, payload: dict, service: AgentService=Depends(get_agent_service)) -> dict` | Updates an existing record or resource. |
| `get_agent(agent_id: str, service: AgentService=Depends(get_agent_service)) -> Agent` | Fetches one record, status object, or derived view. |
| `delete_agent(agent_id: str, service: AgentService=Depends(get_agent_service)) -> dict` | Deletes or removes a record/resource. |
| `_agent_config_payload(agent: Agent) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |

### `pocketStudio/api/chat.py`

HTTP route handlers and compatibility payload shaping.

| Function | Usage |
|---|---|
| `_chatroom_payload(message: ChatMessage) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `list_chat(team_id: str, limit: int=Query(default=100, ge=1, le=500), since: int=Query(default=0, ge=0), sender: str | None=None, q: str | None=None, service: ChatService=Depends(get_chat_service)) -> list[dict]` | Lists records or projections from storage/API. |
| `post_chat(team_id: str, payload: ChatMessageCreate, service: ChatService=Depends(get_chat_service), queue: QueueService=Depends(get_queue_service), teams: TeamService=Depends(get_team_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |

### `pocketStudio/api/compat.py`

HTTP route handlers and compatibility payload shaping.

| Function | Usage |
|---|---|
| `_millis(value: str | int | float | None) -> int` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_agent_config(agent) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_team_config(team) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_task_payload(task, comment_count: int=0) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_project_payload(project, task_count: int | None=None) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_schedule_payload(schedule) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_schedule_payload_with_status(schedule, schedules: ScheduleService) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_schedule_create_payload(payload: dict[str, Any]) -> ScheduleCreate` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_custom_providers(db: Database) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_save_custom_provider_row(provider_id: str, payload: dict[str, Any], db: Database) -> None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_settings_apply_plan(payload: dict[str, Any]) -> dict[str, Any]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_settings_path_value(value: Any) -> str | None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_validate_settings_apply_plan(payload: dict[str, Any]) -> dict[str, Any]` | Validates user/config payloads. |
| `_target_agent_id(target: str) -> str` | Helper used by this module/class. Inspect callers before changing behavior. |
| `get_settings_snapshot(agents: AgentService=Depends(get_agent_service), teams: TeamService=Depends(get_team_service), db: Database=Depends(get_database), settings_service: SettingsService=Depends(get_settings_service)) -> dict` | Fetches one record, status object, or derived view. |
| `export_settings_snapshot(agents: AgentService=Depends(get_agent_service), teams: TeamService=Depends(get_team_service), db: Database=Depends(get_database), settings_service: SettingsService=Depends(get_settings_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `validate_settings_snapshot(payload: dict[str, Any], settings_service: SettingsService=Depends(get_settings_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `preview_settings_snapshot(payload: dict[str, Any], settings_service: SettingsService=Depends(get_settings_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `settings_backup_info(settings_service: SettingsService=Depends(get_settings_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `restore_settings_backup(agents: AgentService=Depends(get_agent_service), teams: TeamService=Depends(get_team_service), db: Database=Depends(get_database), settings_service: SettingsService=Depends(get_settings_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `update_settings_snapshot(payload: dict[str, Any], agents: AgentService=Depends(get_agent_service), teams: TeamService=Depends(get_team_service), db: Database=Depends(get_database), registry: ProviderRegistry=Depends(get_provider_registry), settings_service: SettingsService=Depends(get_settings_service)) -> dict` | Updates an existing record or resource. |
| `import_settings_snapshot(payload: dict[str, Any], agents: AgentService=Depends(get_agent_service), teams: TeamService=Depends(get_team_service), db: Database=Depends(get_database), registry: ProviderRegistry=Depends(get_provider_registry), settings_service: SettingsService=Depends(get_settings_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `run_setup(payload: dict[str, Any], agents: AgentService=Depends(get_agent_service), teams: TeamService=Depends(get_team_service), db: Database=Depends(get_database), registry: ProviderRegistry=Depends(get_provider_registry), settings_service: SettingsService=Depends(get_settings_service)) -> dict` | Runs a command, provider, setup, or workflow. |
| `enqueue_legacy_message(payload: dict[str, Any], orchestrator: Orchestrator=Depends(get_orchestrator), channels: ChannelService=Depends(get_channel_service), queue: QueueService=Depends(get_queue_service)) -> dict` | Adds a message or response to a queue. |
| `queue_status(queue: QueueService=Depends(get_queue_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `queue_diagnostics(stale_threshold_seconds: int | None=None, queue: QueueService=Depends(get_queue_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `queue_agent_status(queue: QueueService=Depends(get_queue_service)) -> list[dict]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `queue_dead(limit: int=Query(default=100, ge=1, le=500), queue: QueueService=Depends(get_queue_service)) -> list[dict]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `queue_dead_retry(message_id: int, queue: QueueService=Depends(get_queue_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `queue_dead_delete(message_id: int, queue: QueueService=Depends(get_queue_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `queue_recover_stale(threshold_seconds: int | None=None, queue: QueueService=Depends(get_queue_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `queue_processing(queue: QueueService=Depends(get_queue_service), registry: ProviderRegistry=Depends(get_provider_registry)) -> list[dict]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `active_processes(registry: ProviderRegistry=Depends(get_provider_registry)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `provider_diagnostics(registry: ProviderRegistry=Depends(get_provider_registry)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `kill_agent_process(agent_id: str, registry: ProviderRegistry=Depends(get_provider_registry)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `kill_processing(message_id: int, queue: QueueService=Depends(get_queue_service), registry: ProviderRegistry=Depends(get_provider_registry)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `responses(limit: int=Query(default=20, ge=1, le=200), queue: QueueService=Depends(get_queue_service)) -> list[dict]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `enqueue_response(payload: dict[str, Any], queue: QueueService=Depends(get_queue_service)) -> dict` | Adds a message or response to a queue. |
| `pending_responses(channel: str=Query(...), queue: QueueService=Depends(get_queue_service)) -> list[dict]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `responses_for_channel(channel: str, queue: QueueService=Depends(get_queue_service)) -> list[dict]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `ack_response(response_id: int, queue: QueueService=Depends(get_queue_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `prune_responses(older_than_ms: int=86400000, queue: QueueService=Depends(get_queue_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `prune_completed_messages(older_than_ms: int=86400000, queue: QueueService=Depends(get_queue_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `logs(limit: int=Query(default=100, ge=1, le=500), event_type: str | None=None, contains: str | None=None, events: EventService=Depends(get_event_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `list_chats(chat: ChatService=Depends(get_chat_service)) -> list[dict]` | Lists records or projections from storage/API. |
| `read_chat_archive(team_id: str, limit: int=Query(default=500, ge=1, le=2000), sender: str | None=None, q: str | None=None, chat: ChatService=Depends(get_chat_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `agent_messages(agent_id: str, limit: int=Query(default=100, ge=1, le=500), since_id: int=Query(default=0, ge=0), queue: QueueService=Depends(get_queue_service)) -> list[dict]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `all_agent_messages(limit: int=Query(default=100, ge=1, le=500), since_id: int=Query(default=0, ge=0), queue: QueueService=Depends(get_queue_service)) -> list[dict]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `reset_agent_runtime(agent_id: str, agents: AgentService=Depends(get_agent_service), queue: QueueService=Depends(get_queue_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `list_plugins(plugins: PluginService=Depends(get_plugin_service)) -> dict` | Lists records or projections from storage/API. |
| `reload_plugins(plugins: PluginService=Depends(get_plugin_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `get_agent_system_prompt(agent_id: str, agents: AgentService=Depends(get_agent_service)) -> dict` | Fetches one record, status object, or derived view. |
| `save_agent_system_prompt(agent_id: str, payload: dict[str, str], agents: AgentService=Depends(get_agent_service)) -> dict` | Persists content or configuration. |
| `get_agent_workspace_status(agent_id: str, agents: AgentService=Depends(get_agent_service)) -> dict` | Fetches one record, status object, or derived view. |
| `repair_agent_workspace(agent_id: str, agents: AgentService=Depends(get_agent_service)) -> dict` | Repairs or recreates expected runtime state. |
| `get_agent_memory(agent_id: str, agents: AgentService=Depends(get_agent_service)) -> dict` | Fetches one record, status object, or derived view. |
| `get_agent_memory_file(agent_id: str, path: str=Query(...), agents: AgentService=Depends(get_agent_service)) -> dict` | Fetches one record, status object, or derived view. |
| `save_agent_memory_file(agent_id: str, payload: dict[str, Any], agents: AgentService=Depends(get_agent_service)) -> dict` | Persists content or configuration. |
| `delete_agent_memory_file(agent_id: str, path: str=Query(...), agents: AgentService=Depends(get_agent_service)) -> dict` | Deletes or removes a record/resource. |
| `get_agent_heartbeat(agent_id: str, agents: AgentService=Depends(get_agent_service)) -> dict` | Fetches one record, status object, or derived view. |
| `save_agent_heartbeat(agent_id: str, payload: dict[str, Any], agents: AgentService=Depends(get_agent_service)) -> dict` | Persists content or configuration. |
| `list_agent_skills(agent_id: str, agents: AgentService=Depends(get_agent_service)) -> list[dict]` | Lists records or projections from storage/API. |
| `search_agent_skills(agent_id: str, query: str='', agents: AgentService=Depends(get_agent_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `install_agent_skill(agent_id: str, payload: dict[str, str], agents: AgentService=Depends(get_agent_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `list_projects(status: str | None=None, projects: ProjectService=Depends(get_project_service)) -> list[dict]` | Lists records or projections from storage/API. |
| `create_project(payload: ProjectCreate, projects: ProjectService=Depends(get_project_service)) -> dict` | Creates a new record or resource. |
| `get_project(project_id: str, projects: ProjectService=Depends(get_project_service)) -> dict` | Fetches one record, status object, or derived view. |
| `update_project(project_id: str, payload: dict[str, Any], projects: ProjectService=Depends(get_project_service)) -> dict` | Updates an existing record or resource. |
| `get_project_workspace_status(project_id: str, projects: ProjectService=Depends(get_project_service)) -> dict` | Fetches one record, status object, or derived view. |
| `repair_project_workspace(project_id: str, projects: ProjectService=Depends(get_project_service)) -> dict` | Repairs or recreates expected runtime state. |
| `delete_project(project_id: str, projects: ProjectService=Depends(get_project_service)) -> dict` | Deletes or removes a record/resource. |
| `reorder_tasks(payload: dict[str, Any], tasks: TaskService=Depends(get_task_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `list_task_comments(task_id: int, projects: ProjectService=Depends(get_project_service)) -> list[dict]` | Lists records or projections from storage/API. |
| `create_task_comment(task_id: int, payload: TaskCommentCreate, projects: ProjectService=Depends(get_project_service)) -> dict` | Creates a new record or resource. |
| `delete_comment(comment_id: str, projects: ProjectService=Depends(get_project_service)) -> dict` | Deletes or removes a record/resource. |
| `list_schedules(agent: str | None=None, schedules: ScheduleService=Depends(get_schedule_service)) -> list[dict]` | Lists records or projections from storage/API. |
| `create_schedule(payload: dict[str, Any], schedules: ScheduleService=Depends(get_schedule_service)) -> dict` | Creates a new record or resource. |
| `validate_schedule(payload: dict[str, Any], schedules: ScheduleService=Depends(get_schedule_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `update_schedule(schedule_id: str, payload: dict[str, Any], schedules: ScheduleService=Depends(get_schedule_service)) -> dict` | Updates an existing record or resource. |
| `fire_schedule(schedule_id: str, payload: dict[str, Any] | None=None, schedules: ScheduleService=Depends(get_schedule_service), queue: QueueService=Depends(get_queue_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `delete_schedule(schedule_id: str, schedules: ScheduleService=Depends(get_schedule_service)) -> dict` | Deletes or removes a record/resource. |
| `system_status(worker: WorkerService=Depends(get_worker_service), heartbeat: HeartbeatService=Depends(get_heartbeat_service), settings_service: SettingsService=Depends(get_settings_service), telegram: TelegramChannelService=Depends(get_telegram_channel_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_service_status_payload(worker: WorkerService, heartbeat: HeartbeatService, settings_service: SettingsService, telegram: TelegramChannelService | None=None) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `heartbeat_status(heartbeat: HeartbeatService=Depends(get_heartbeat_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `heartbeat_tick(payload: dict[str, Any] | None=None, heartbeat: HeartbeatService=Depends(get_heartbeat_service), queue: QueueService=Depends(get_queue_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `clear_heartbeat_state(agent: str | None=Query(default=None), heartbeat: HeartbeatService=Depends(get_heartbeat_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `worker_status(worker: WorkerService=Depends(get_worker_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `worker_start(worker: WorkerService=Depends(get_worker_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `worker_stop(worker: WorkerService=Depends(get_worker_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `worker_pause(worker: WorkerService=Depends(get_worker_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `worker_resume(worker: WorkerService=Depends(get_worker_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `worker_restart(worker: WorkerService=Depends(get_worker_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `worker_tick(force: bool=False, worker: WorkerService=Depends(get_worker_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `worker_maintenance(older_than_ms: int=86400000, stale_threshold_seconds: int | None=None, prune_chats: bool=False, worker: WorkerService=Depends(get_worker_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `apply_services(worker: WorkerService=Depends(get_worker_service), settings_service: SettingsService=Depends(get_settings_service), telegram: TelegramChannelService=Depends(get_telegram_channel_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `services_status(worker: WorkerService=Depends(get_worker_service), heartbeat: HeartbeatService=Depends(get_heartbeat_service), settings_service: SettingsService=Depends(get_settings_service), telegram: TelegramChannelService=Depends(get_telegram_channel_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `start_services(worker: WorkerService=Depends(get_worker_service), heartbeat: HeartbeatService=Depends(get_heartbeat_service), settings_service: SettingsService=Depends(get_settings_service), telegram: TelegramChannelService=Depends(get_telegram_channel_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `stop_services(worker: WorkerService=Depends(get_worker_service), heartbeat: HeartbeatService=Depends(get_heartbeat_service), settings_service: SettingsService=Depends(get_settings_service), telegram: TelegramChannelService=Depends(get_telegram_channel_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `restart_service(worker: WorkerService=Depends(get_worker_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `channel_action(channel_id: str, action: str, telegram: TelegramChannelService=Depends(get_telegram_channel_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `get_pairings(channels: ChannelService=Depends(get_channel_service)) -> dict` | Fetches one record, status object, or derived view. |
| `approve_pairing(payload: dict[str, str], channels: ChannelService=Depends(get_channel_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `revoke_pairing(channel: str, sender_id: str, channels: ChannelService=Depends(get_channel_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `dismiss_pairing(code: str, channels: ChannelService=Depends(get_channel_service)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `list_custom_providers(db: Database=Depends(get_database)) -> dict` | Lists records or projections from storage/API. |
| `save_custom_provider(provider_id: str, payload: dict[str, Any], db: Database=Depends(get_database), registry: ProviderRegistry=Depends(get_provider_registry)) -> dict` | Persists content or configuration. |
| `delete_custom_provider(provider_id: str, db: Database=Depends(get_database), registry: ProviderRegistry=Depends(get_provider_registry)) -> dict` | Deletes or removes a record/resource. |

### `pocketStudio/api/errors.py`

HTTP route handlers and compatibility payload shaping.

| Function | Usage |
|---|---|
| `not_found(exc: KeyError) -> HTTPException` | Helper used by this module/class. Inspect callers before changing behavior. |

### `pocketStudio/api/messages.py`

HTTP route handlers and compatibility payload shaping.

| Function | Usage |
|---|---|
| `enqueue_message(payload: MessageCreate, orchestrator: Orchestrator=Depends(get_orchestrator)) -> QueueMessage` | Adds a message or response to a queue. |
| `process_message(message_id: int, orchestrator: Orchestrator=Depends(get_orchestrator)) -> OrchestrationResult` | Processes a queue item or worker step. |
| `process_next(orchestrator: Orchestrator=Depends(get_orchestrator)) -> OrchestrationResult | None` | Processes a queue item or worker step. |
| `list_queue(limit: int=Query(default=100, ge=1, le=500), status: MessageStatus | None=None, service: QueueService=Depends(get_queue_service)) -> list[QueueMessage]` | Lists records or projections from storage/API. |
| `list_grouped_queue(limit: int=Query(default=100, ge=1, le=500), status: MessageStatus | None=None, service: QueueService=Depends(get_queue_service)) -> dict` | Lists records or projections from storage/API. |
| `get_message(message_id: int, service: QueueService=Depends(get_queue_service)) -> QueueMessage` | Fetches one record, status object, or derived view. |
| `retry_message(message_id: int, service: QueueService=Depends(get_queue_service)) -> QueueMessage` | Helper used by this module/class. Inspect callers before changing behavior. |

### `pocketStudio/api/system.py`

HTTP route handlers and compatibility payload shaping.

| Function | Usage |
|---|---|
| `health(settings: Settings=Depends(get_settings)) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `providers(registry: ProviderRegistry=Depends(get_provider_registry)) -> list[str]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `events(limit: int=Query(default=100, ge=1, le=500), since: int=Query(default=0, ge=0), service: EventService=Depends(get_event_service)) -> list[Event]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `office_events(limit: int=Query(default=100, ge=1, le=500), since: int=Query(default=0, ge=0), service: EventService=Depends(get_event_service)) -> list[dict]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_sse_message(event_name: str, data: dict) -> str` | Helper used by this module/class. Inspect callers before changing behavior. |
| `event_stream(since: int=Query(default=0, ge=0), replay: bool=Query(default=True), service: EventService=Depends(get_event_service)) -> StreamingResponse` | Helper used by this module/class. Inspect callers before changing behavior. |

### `pocketStudio/api/tasks.py`

HTTP route handlers and compatibility payload shaping.

| Function | Usage |
|---|---|
| `list_tasks(projectId: str | None=None, status: str | None=None, assignee: str | None=None, q: str | None=None, service: TaskService=Depends(get_task_service)) -> list[Task]` | Lists records or projections from storage/API. |
| `create_task(payload: TaskCreate, service: TaskService=Depends(get_task_service), projects: ProjectService=Depends(get_project_service)) -> dict` | Creates a new record or resource. |
| `get_task(task_id: int, service: TaskService=Depends(get_task_service), projects: ProjectService=Depends(get_project_service)) -> dict` | Fetches one record, status object, or derived view. |
| `update_task(task_id: int, payload: dict[str, Any], service: TaskService=Depends(get_task_service), projects: ProjectService=Depends(get_project_service)) -> dict` | Updates an existing record or resource. |
| `update_task_status(task_id: int, status: str, service: TaskService=Depends(get_task_service)) -> Task` | Updates an existing record or resource. |
| `delete_task(task_id: int, service: TaskService=Depends(get_task_service)) -> dict` | Deletes or removes a record/resource. |
| `_task_response(task: Task, projects: ProjectService) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_task_payload(task: Task, projects: ProjectService) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |

### `pocketStudio/api/teams.py`

HTTP route handlers and compatibility payload shaping.

| Function | Usage |
|---|---|
| `list_teams(service: TeamService=Depends(get_team_service)) -> list[Team]` | Lists records or projections from storage/API. |
| `upsert_team(payload: TeamCreate, service: TeamService=Depends(get_team_service)) -> Team` | Helper used by this module/class. Inspect callers before changing behavior. |
| `update_team(team_id: str, payload: dict, service: TeamService=Depends(get_team_service)) -> dict` | Updates an existing record or resource. |
| `get_team(team_id: str, service: TeamService=Depends(get_team_service)) -> Team` | Fetches one record, status object, or derived view. |
| `add_team_member(team_id: str, agent_id: str, service: TeamService=Depends(get_team_service)) -> Team` | Helper used by this module/class. Inspect callers before changing behavior. |
| `remove_team_member(team_id: str, agent_id: str, service: TeamService=Depends(get_team_service)) -> Team` | Helper used by this module/class. Inspect callers before changing behavior. |
| `set_team_leader(team_id: str, agent_id: str, service: TeamService=Depends(get_team_service)) -> Team` | Helper used by this module/class. Inspect callers before changing behavior. |
| `delete_team(team_id: str, service: TeamService=Depends(get_team_service)) -> dict` | Deletes or removes a record/resource. |

### `pocketStudio/channels/__init__.py`

Channel bridge implementations for pocketStudio.

### `pocketStudio/channels/telegram.py`

External channel transport bridge.

#### `TelegramApiError`

TelegramApiError data type or service class.

#### `TelegramChannelService`

TelegramChannelService data type or service class.

| Method | Usage |
|---|---|
| `__init__(self, db: Database, settings: Settings, settings_service: SettingsService, channels: ChannelService, queue: QueueService, events: EventService) -> None` | Python protocol or object lifecycle method. |
| `configured_token(self) -> str | None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `status(self) -> dict` | Controls or reports runtime service state. |
| `start(self) -> bool` | Controls or reports runtime service state. |
| `stop(self) -> bool` | Controls or reports runtime service state. |
| `restart(self) -> bool` | Controls or reports runtime service state. |
| `tick(self) -> dict` | Controls or reports runtime service state. |
| `poll_once(self, limit: int=20, timeout: int=0) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `deliver_pending(self) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_run(self) -> None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_handle_update(self, update: dict, token: str) -> dict` | Handles a route/event/sub-step inside a larger workflow. |
| `_handle_command(self, text: str, token: str, chat_id: str, reply_to: int | None) -> bool` | Handles a route/event/sub-step inside a larger workflow. |
| `_send_response(self, token: str, response: ResponseJob) -> None` | Sends data to an external transport or subprocess. |
| `_api_call(self, token: str, method: str, payload: dict[str, Any]) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_send_message(self, token: str, chat_id: str, text: str, reply_to: int | None=None) -> None` | Sends data to an external transport or subprocess. |
| `_send_chat_action(self, token: str, chat_id: str) -> None` | Sends data to an external transport or subprocess. |
| `_require_token(self) -> str` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_load_offset(self) -> int | None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_save_offset(self, offset: int) -> None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_offset_path(self)` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_status_label(self, configured: bool) -> str` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_sender_name(message: dict) -> str` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_pairing_message(code: str) -> str` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_split_message(text: str) -> list[str]` | Helper used by this module/class. Inspect callers before changing behavior. |

### `pocketStudio/cli.py`

Command-line control plane.

| Function | Usage |
|---|---|
| `print_json(value: Any) -> int` | Helper used by this module/class. Inspect callers before changing behavior. |
| `package_version() -> str` | Helper used by this module/class. Inspect callers before changing behavior. |
| `build_parser() -> argparse.ArgumentParser` | Helper used by this module/class. Inspect callers before changing behavior. |
| `run(args: argparse.Namespace, client: ApiClient) -> int` | Runs this provider, command, or workflow and returns its result. |
| `run_agent(args: argparse.Namespace, client: ApiClient) -> int` | Runs a command, provider, setup, or workflow. |
| `run_settings(args: argparse.Namespace, client: ApiClient) -> int` | Runs a command, provider, setup, or workflow. |
| `run_daemon(args: argparse.Namespace, manager: DaemonManager | None=None) -> int` | Runs a command, provider, setup, or workflow. |
| `run_team(args: argparse.Namespace, client: ApiClient) -> int` | Runs a command, provider, setup, or workflow. |
| `run_provider(args: argparse.Namespace, client: ApiClient) -> int` | Runs a command, provider, setup, or workflow. |
| `run_schedule(args: argparse.Namespace, client: ApiClient) -> int` | Runs a command, provider, setup, or workflow. |
| `run_pairing(args: argparse.Namespace, client: ApiClient) -> int` | Runs a command, provider, setup, or workflow. |
| `run_project(args: argparse.Namespace, client: ApiClient) -> int` | Runs a command, provider, setup, or workflow. |
| `run_task(args: argparse.Namespace, client: ApiClient) -> int` | Runs a command, provider, setup, or workflow. |
| `main(argv: list[str] | None=None, client: ApiClient | None=None) -> int` | Helper used by this module/class. Inspect callers before changing behavior. |

#### `ApiClient`

ApiClient data type or service class.

| Method | Usage |
|---|---|
| `__init__(self, base_url: str | None=None) -> None` | Python protocol or object lifecycle method. |
| `request(self, method: str, path: str, payload: dict[str, Any] | None=None) -> Any` | Helper used by this module/class. Inspect callers before changing behavior. |
| `get(self, path: str) -> Any` | Get operation for ApiClient. |
| `post(self, path: str, payload: dict[str, Any] | None=None) -> Any` | Helper used by this module/class. Inspect callers before changing behavior. |
| `put(self, path: str, payload: dict[str, Any]) -> Any` | Helper used by this module/class. Inspect callers before changing behavior. |
| `delete(self, path: str) -> Any` | Delete operation for ApiClient. |

#### `DaemonManager`

DaemonManager data type or service class.

| Method | Usage |
|---|---|
| `__init__(self, host: str=DEFAULT_HOST, port: int=DEFAULT_PORT, home: Path | None=None) -> None` | Python protocol or object lifecycle method. |
| `api_url(self) -> str` | Helper used by this module/class. Inspect callers before changing behavior. |
| `status(self) -> dict[str, Any]` | Controls or reports runtime service state. |
| `start(self) -> dict[str, Any]` | Controls or reports runtime service state. |
| `stop(self) -> dict[str, Any]` | Controls or reports runtime service state. |
| `restart(self) -> dict[str, Any]` | Controls or reports runtime service state. |
| `open(self) -> dict[str, Any]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_read_pid(self) -> int | None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_pid_alive(self, pid: int) -> bool` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_unlink_pid(self) -> None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_fetch_status(self) -> dict[str, Any] | None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_wait_for_status(self, timeout_seconds: float=8.0) -> dict[str, Any] | None` | Helper used by this module/class. Inspect callers before changing behavior. |

### `pocketStudio/core/config.py`

Core runtime/configuration helper.

| Function | Usage |
|---|---|
| `get_settings() -> Settings` | Fetches one record, status object, or derived view. |

#### `Settings`

Settings data type or service class.

| Method | Usage |
|---|---|
| `database_path(self) -> Path` | Helper used by this module/class. Inspect callers before changing behavior. |
| `settings_path(self) -> Path` | Helper used by this module/class. Inspect callers before changing behavior. |
| `workspace_path(self) -> Path` | Helper used by this module/class. Inspect callers before changing behavior. |
| `files_path(self) -> Path` | Helper used by this module/class. Inspect callers before changing behavior. |
| `logs_path(self) -> Path` | Helper used by this module/class. Inspect callers before changing behavior. |
| `log_file_path(self) -> Path` | Helper used by this module/class. Inspect callers before changing behavior. |

### `pocketStudio/core/database.py`

Core runtime/configuration helper.

#### `Database`

Database data type or service class.

| Method | Usage |
|---|---|
| `__init__(self, path: Path, journal_mode: str='MEMORY') -> None` | Python protocol or object lifecycle method. |
| `connect(self) -> sqlite3.Connection` | Creates a connection to the configured backend resource. |
| `initialize(self) -> None` | Initializes required runtime schema/state. |
| `_migrate(self, conn: sqlite3.Connection) -> None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_add_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_backfill_task_numbers(conn: sqlite3.Connection) -> None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `execute(self, query: str, params: Iterable[Any]=()) -> sqlite3.Cursor` | Helper used by this module/class. Inspect callers before changing behavior. |
| `fetch_one(self, query: str, params: Iterable[Any]=()) -> sqlite3.Row | None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `fetch_all(self, query: str, params: Iterable[Any]=()) -> list[sqlite3.Row]` | Helper used by this module/class. Inspect callers before changing behavior. |

### `pocketStudio/core/dependencies.py`

Core runtime/configuration helper.

| Function | Usage |
|---|---|
| `get_database() -> Database` | Fetches one record, status object, or derived view. |
| `get_event_service() -> EventService` | Fetches one record, status object, or derived view. |
| `get_agent_service() -> AgentService` | Fetches one record, status object, or derived view. |
| `get_team_service() -> TeamService` | Fetches one record, status object, or derived view. |
| `get_queue_service() -> QueueService` | Fetches one record, status object, or derived view. |
| `get_response_service() -> ResponseService` | Fetches one record, status object, or derived view. |
| `get_plugin_service() -> PluginService` | Fetches one record, status object, or derived view. |
| `get_chat_service() -> ChatService` | Fetches one record, status object, or derived view. |
| `get_channel_service() -> ChannelService` | Fetches one record, status object, or derived view. |
| `get_telegram_channel_service() -> TelegramChannelService` | Fetches one record, status object, or derived view. |
| `get_task_service() -> TaskService` | Fetches one record, status object, or derived view. |
| `get_project_service() -> ProjectService` | Fetches one record, status object, or derived view. |
| `get_schedule_service() -> ScheduleService` | Fetches one record, status object, or derived view. |
| `get_settings_service() -> SettingsService` | Fetches one record, status object, or derived view. |
| `get_heartbeat_service() -> HeartbeatService` | Fetches one record, status object, or derived view. |
| `get_provider_registry() -> ProviderRegistry` | Fetches one record, status object, or derived view. |
| `get_orchestrator() -> Orchestrator` | Fetches one record, status object, or derived view. |
| `get_worker_service() -> WorkerService` | Fetches one record, status object, or derived view. |

### `pocketStudio/core/ids.py`

Core runtime/configuration helper.

| Function | Usage |
|---|---|
| `nanoid(size: int=21, alphabet: str=DEFAULT_ALPHABET) -> str` | Helper used by this module/class. Inspect callers before changing behavior. |
| `prefixed_id(prefix: str, size: int=12) -> str` | Helper used by this module/class. Inspect callers before changing behavior. |

### `pocketStudio/core/runtime.py`

Core runtime/configuration helper.

| Function | Usage |
|---|---|
| `uptime_seconds() -> int` | Helper used by this module/class. Inspect callers before changing behavior. |

### `pocketStudio/main.py`

FastAPI application factory and lifespan.

| Function | Usage |
|---|---|
| `lifespan(app: FastAPI)` | Helper used by this module/class. Inspect callers before changing behavior. |
| `create_app() -> FastAPI` | Creates a new record or resource. |

### `pocketStudio/models.py`

Pydantic and enum data contracts.

#### `TeamMode`

TeamMode data type or service class.

#### `MessageStatus`

MessageStatus data type or service class.

#### `AgentCreate`

AgentCreate data type or service class.

#### `Agent`

Agent data type or service class.

#### `TeamCreate`

TeamCreate data type or service class.

#### `Team`

Team data type or service class.

#### `MessageCreate`

MessageCreate data type or service class.

#### `QueueMessage`

QueueMessage data type or service class.

#### `AgentRun`

AgentRun data type or service class.

#### `OrchestrationResult`

OrchestrationResult data type or service class.

#### `ChatMessageCreate`

ChatMessageCreate data type or service class.

#### `ChatMessage`

ChatMessage data type or service class.

#### `TaskCreate`

TaskCreate data type or service class.

#### `Task`

Task data type or service class.

#### `ProjectCreate`

ProjectCreate data type or service class.

#### `Project`

Project data type or service class.

#### `TaskCommentCreate`

TaskCommentCreate data type or service class.

#### `TaskComment`

TaskComment data type or service class.

#### `ScheduleCreate`

ScheduleCreate data type or service class.

#### `Schedule`

Schedule data type or service class.

#### `AgentMessage`

AgentMessage data type or service class.

#### `QueueStatus`

QueueStatus data type or service class.

#### `ResponseJob`

ResponseJob data type or service class.

#### `Event`

Event data type or service class.

### `pocketStudio/providers/base.py`

Agent provider or subprocess harness integration.

#### `ProviderRequest`

ProviderRequest data type or service class.

#### `ProviderResponse`

ProviderResponse data type or service class.

#### `AgentProvider`

AgentProvider data type or service class.

| Method | Usage |
|---|---|
| `run(self, request: ProviderRequest) -> ProviderResponse` | Execute an agent turn. |

### `pocketStudio/providers/cli_agent.py`

Agent provider or subprocess harness integration.

| Function | Usage |
|---|---|
| `provider_from_command(name: str, command_line: str, registry: ProcessRegistry | None=None, timeout_seconds: int=600) -> CliAgentProvider` | Helper used by this module/class. Inspect callers before changing behavior. |

#### `CliAgentProvider`

CliAgentProvider data type or service class.

| Method | Usage |
|---|---|
| `__init__(self, name: str, command: str, base_args: list[str] | None=None, prompt_arg: str | None=None, registry: ProcessRegistry | None=None, timeout_seconds: int=600) -> None` | Python protocol or object lifecycle method. |
| `run(self, request: ProviderRequest) -> ProviderResponse` | Runs this provider, command, or workflow and returns its result. |
| `_args(self, request: ProviderRequest) -> list[str]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_prompt(request: ProviderRequest) -> str` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_extract_text(cls, stdout: str) -> str` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_extract_event_text(line: str) -> str | None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `is_alive(self, agent_id: str) -> bool` | Helper used by this module/class. Inspect callers before changing behavior. |
| `kill_agent(self, agent_id: str) -> bool` | Helper used by this module/class. Inspect callers before changing behavior. |

#### `ClaudeProvider`

ClaudeProvider data type or service class.

| Method | Usage |
|---|---|
| `__init__(self, registry: ProcessRegistry | None=None, timeout_seconds: int=600) -> None` | Python protocol or object lifecycle method. |

#### `OpenCodeProvider`

OpenCodeProvider data type or service class.

| Method | Usage |
|---|---|
| `__init__(self, registry: ProcessRegistry | None=None, timeout_seconds: int=600) -> None` | Python protocol or object lifecycle method. |

### `pocketStudio/providers/codex.py`

Agent provider or subprocess harness integration.

| Function | Usage |
|---|---|
| `codex_provider_from_command(command_line: str, registry: ProcessRegistry | None=None, timeout_seconds: int=600) -> CodexProvider` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_split_command_line(command_line: str) -> list[str]` | Helper used by this module/class. Inspect callers before changing behavior. |

#### `CodexProvider`

CodexProvider data type or service class.

| Method | Usage |
|---|---|
| `__init__(self, command: str | None=None, base_args: list[str] | None=None, registry: ProcessRegistry | None=None, timeout_seconds: int=600) -> None` | Python protocol or object lifecycle method. |
| `run(self, request: ProviderRequest) -> ProviderResponse` | Runs this provider, command, or workflow and returns its result. |
| `_args(self, request: ProviderRequest) -> tuple[list[str], str | None]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_custom_args(self, request: ProviderRequest) -> tuple[list[str], str | None]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_prompt(request: ProviderRequest) -> str` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_extract_text(cls, stdout: str) -> str` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_extract_event_text(line: str) -> str | None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `is_alive(self, agent_id: str) -> bool` | Helper used by this module/class. Inspect callers before changing behavior. |
| `kill_agent(self, agent_id: str) -> bool` | Helper used by this module/class. Inspect callers before changing behavior. |

### `pocketStudio/providers/local.py`

Agent provider or subprocess harness integration.

#### `LocalEchoProvider`

LocalEchoProvider data type or service class.

| Method | Usage |
|---|---|
| `run(self, request: ProviderRequest) -> ProviderResponse` | Runs this provider, command, or workflow and returns its result. |

### `pocketStudio/providers/openai_compatible.py`

Agent provider or subprocess harness integration.

#### `OpenAICompatibleProvider`

OpenAICompatibleProvider data type or service class.

| Method | Usage |
|---|---|
| `__init__(self, name: str='openai', base_url: str | None=None, api_key: str | None=None, default_model: str | None=None) -> None` | Python protocol or object lifecycle method. |
| `run(self, request: ProviderRequest) -> ProviderResponse` | Runs this provider, command, or workflow and returns its result. |

### `pocketStudio/providers/registry.py`

Agent provider or subprocess harness integration.

| Function | Usage |
|---|---|
| `_codex_home_diagnostics(codex_home: Path) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_can_write(path: Path) -> bool` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_resolved_command_path(command: str | None) -> str | None` | Helper used by this module/class. Inspect callers before changing behavior. |

#### `ProviderRegistry`

ProviderRegistry data type or service class.

| Method | Usage |
|---|---|
| `__init__(self, db: Database | None=None) -> None` | Python protocol or object lifecycle method. |
| `register(self, provider: AgentProvider) -> None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `reload_custom(self) -> None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `get(self, name: str) -> AgentProvider` | Get operation for ProviderRegistry. |
| `list_names(self) -> list[str]` | Lists records or projections from storage/API. |
| `kill_agent(self, agent_id: str) -> bool` | Helper used by this module/class. Inspect callers before changing behavior. |
| `agent_process_alive(self, agent_id: str) -> bool` | Helper used by this module/class. Inspect callers before changing behavior. |
| `active_processes(self) -> list[dict]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `diagnostics(self) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |

### `pocketStudio/providers/subprocess.py`

Agent provider or subprocess harness integration.

| Function | Usage |
|---|---|
| `_empty_bytes() -> bytes` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_should_fallback_to_windows_powershell(exc: OSError) -> bool` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_should_fallback_to_windows_sync_subprocess(exc: OSError) -> bool` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_windows_powershell() -> str` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_resolved_command(command: str) -> str` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_powershell_command(command: Sequence[str], pipe_stdin: bool=False) -> str` | Helper used by this module/class. Inspect callers before changing behavior. |

#### `SubprocessResult`

SubprocessResult data type or service class.

#### `ProcessRegistry`

ProcessRegistry data type or service class.

| Method | Usage |
|---|---|
| `register(self, key: str, process: asyncio.subprocess.Process, metadata: dict | None=None) -> None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `unregister(self, key: str, process: asyncio.subprocess.Process) -> None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `is_alive(self, key: str) -> bool` | Helper used by this module/class. Inspect callers before changing behavior. |
| `snapshot(self) -> list[dict]` | Controls or reports runtime service state. |
| `kill(self, key: str) -> bool` | Helper used by this module/class. Inspect callers before changing behavior. |

#### `SubprocessHarness`

SubprocessHarness data type or service class.

| Method | Usage |
|---|---|
| `__init__(self, command: str, registry: ProcessRegistry | None=None, timeout_seconds: int=600) -> None` | Python protocol or object lifecycle method. |
| `run(self, args: Sequence[str], process_key: str, cwd: Path | str | None=None, env: dict[str, str] | None=None, on_stdout_line: Callable[[str], None] | None=None, stdin_text: str | None=None) -> SubprocessResult` | Runs this provider, command, or workflow and returns its result. |
| `_run_windows_powershell(self, command: str, args: Sequence[str], cwd: Path | str | None, env: dict[str, str], stdin_text: str | None) -> asyncio.subprocess.Process` | Private implementation for a longer running process. |
| `_run_windows_powershell_sync(self, command: str, args: Sequence[str], cwd: Path | str | None, env: dict[str, str], on_stdout_line: Callable[[str], None] | None, stdin_text: str | None) -> SubprocessResult` | Private implementation for a longer running process. |
| `_communicate(process: asyncio.subprocess.Process, on_stdout_line: Callable[[str], None] | None, stdin_text: str | None=None) -> tuple[bytes, bytes]` | Helper used by this module/class. Inspect callers before changing behavior. |

### `pocketStudio/services/agent_service.py`

Domain service used by routes, workers, or orchestrator.

#### `AgentService`

AgentService data type or service class.

| Method | Usage |
|---|---|
| `__init__(self, db: Database, settings: Settings) -> None` | Python protocol or object lifecycle method. |
| `create(self, payload: AgentCreate) -> Agent` | Create operation for AgentService. |
| `get(self, agent_id: str) -> Agent` | Get operation for AgentService. |
| `list(self) -> list[Agent]` | List operation for AgentService. |
| `delete(self, agent_id: str) -> None` | Delete operation for AgentService. |
| `ensure_workspace(self, workspace: Path, payload: AgentCreate | None=None) -> None` | Checks and creates required state when missing. |
| `workspace_status(self, agent_id: str, repair: bool=False) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `get_system_prompt_file(self, agent_id: str) -> dict` | Fetches one record, status object, or derived view. |
| `save_system_prompt_file(self, agent_id: str, content: str) -> None` | Persists content or configuration. |
| `get_heartbeat_file(self, agent_id: str) -> dict` | Fetches one record, status object, or derived view. |
| `save_heartbeat_file(self, agent_id: str, content: str | None=None, enabled: bool | None=None, interval: int | None=None) -> dict` | Persists content or configuration. |
| `build_system_prompt(self, agent_id: str, teammates: str='') -> str` | Helper used by this module/class. Inspect callers before changing behavior. |
| `load_memory_index(self, agent_id: str) -> str` | Loads content/configuration from storage. |
| `list_memory_files(self, agent_id: str) -> dict` | Lists records or projections from storage/API. |
| `get_memory_file(self, agent_id: str, relative_path: str) -> dict` | Fetches one record, status object, or derived view. |
| `save_memory_file(self, agent_id: str, relative_path: str, content: str, create_dirs: bool=True) -> dict` | Persists content or configuration. |
| `delete_memory_file(self, agent_id: str, relative_path: str) -> dict` | Deletes or removes a record/resource. |
| `list_skills(self, agent_id: str) -> list[dict]` | Lists records or projections from storage/API. |
| `install_skill_placeholder(self, agent_id: str, ref: str) -> Path` | Helper used by this module/class. Inspect callers before changing behavior. |
| `scan_memory_tree(cls, dir_path: Path, relative_path: str) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_format_memory_tree(cls, folder: dict, indent: int=0) -> str` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_ensure_claude_skills_link(workspace: Path) -> None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_workspace_checks(workspace: Path) -> list[dict]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_safe_name(value: str) -> str` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_resolve_memory_path(memory_dir: Path, relative_path: str) -> Path` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_parse_frontmatter(content: str) -> dict | None` | Parses text, configuration, or persisted values. |
| `_default_heartbeat_interval(self) -> int` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_read_settings_file(self) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_write_settings_file(self, data: dict) -> None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_sync_agent_settings(self, agent: Agent) -> None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_remove_agent_settings(self, agent_id: str) -> None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_to_agent(row) -> Agent` | Converts database rows or internal objects into models/payloads. |

### `pocketStudio/services/channel_service.py`

Domain service used by routes, workers, or orchestrator.

#### `PairingResult`

PairingResult data type or service class.

#### `RoutedChannelMessage`

RoutedChannelMessage data type or service class.

#### `ChannelService`

ChannelService data type or service class.

| Method | Usage |
|---|---|
| `__init__(self, db: Database, agents: AgentService, teams: TeamService) -> None` | Python protocol or object lifecycle method. |
| `pairing_state(self) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `ensure_sender_paired(self, channel: str, sender_id: str, sender: str) -> PairingResult` | Checks and creates required state when missing. |
| `approve(self, code: str | None) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `revoke(self, channel: str, sender_id: str) -> bool` | Helper used by this module/class. Inspect callers before changing behavior. |
| `dismiss_pending(self, code: str) -> bool` | Helper used by this module/class. Inspect callers before changing behavior. |
| `route_message(self, channel: str, sender_id: str, text: str, explicit_agent: str | None=None) -> RoutedChannelMessage` | Helper used by this module/class. Inspect callers before changing behavior. |
| `resolve_target(self, tag: str) -> str | None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `get_default(self, channel: str, sender_id: str) -> str | None` | Fetches one record, status object, or derived view. |
| `save_default(self, channel: str, sender_id: str, target: str) -> None` | Persists content or configuration. |
| `clear_default(self, channel: str, sender_id: str) -> bool` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_unique_pairing_code(self) -> str` | Helper used by this module/class. Inspect callers before changing behavior. |

### `pocketStudio/services/chat_service.py`

Domain service used by routes, workers, or orchestrator.

#### `ChatService`

ChatService data type or service class.

| Method | Usage |
|---|---|
| `__init__(self, db: Database, events: EventService) -> None` | Python protocol or object lifecycle method. |
| `post(self, team_id: str, payload: ChatMessageCreate) -> ChatMessage` | Helper used by this module/class. Inspect callers before changing behavior. |
| `get(self, message_id: int) -> ChatMessage` | Get operation for ChatService. |
| `list(self, team_id: str, limit: int=100, since: int=0, sender: str | None=None, query: str | None=None) -> list[ChatMessage]` | List operation for ChatService. |
| `archives(self) -> list[dict]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `prune(self, older_than_ms: int) -> int` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_to_message(row) -> ChatMessage` | Converts database rows or internal objects into models/payloads. |

### `pocketStudio/services/event_service.py`

Domain service used by routes, workers, or orchestrator.

#### `EventService`

EventService data type or service class.

| Method | Usage |
|---|---|
| `__init__(self, db: Database, settings: Settings | None=None) -> None` | Python protocol or object lifecycle method. |
| `emit(self, event_type: str, payload: dict) -> Event` | Helper used by this module/class. Inspect callers before changing behavior. |
| `add_listener(self, listener: Callable[[Event], None]) -> None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `remove_listener(self, listener: Callable[[Event], None]) -> None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `list(self, limit: int=100, since: int=0) -> list[Event]` | List operation for EventService. |
| `log_lines(self, limit: int=100) -> list[str]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `log_records(self, limit: int=100, event_type: str | None=None, contains: str | None=None) -> list[dict]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `office_event(self, event: Event) -> tuple[str, dict]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_append_log(self, event_type: str, payload_json: str, created_at: str | None=None) -> None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_notify(self, event: Event) -> None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_parse_log_line(line: str) -> dict` | Parses text, configuration, or persisted values. |
| `_event_timestamp_ms(value: str) -> int` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_to_event(row) -> Event` | Converts database rows or internal objects into models/payloads. |

### `pocketStudio/services/heartbeat_service.py`

Domain service used by routes, workers, or orchestrator.

#### `HeartbeatService`

HeartbeatService data type or service class.

| Method | Usage |
|---|---|
| `__init__(self, db: Database, agents: AgentService, events: EventService, settings: Settings) -> None` | Python protocol or object lifecycle method. |
| `fire_due(self, queue: QueueService, now_ms: int | None=None) -> list[QueueMessage]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `tick(self, queue: QueueService, now_ms: int | None=None, agent_id: str | None=None, force: bool=False) -> dict` | Controls or reports runtime service state. |
| `clear_state(self, agent_id: str | None=None) -> int` | Helper used by this module/class. Inspect callers before changing behavior. |
| `snapshot(self, now_ms: int | None=None) -> dict` | Controls or reports runtime service state. |
| `base_interval_seconds(self) -> int` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_is_due(self, agent, now_ms: int) -> bool` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_fire_agent(self, queue: QueueService, agent, now_ms: int) -> QueueMessage` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_read_prompt(workspace: Path) -> str` | Helper used by this module/class. Inspect callers before changing behavior. |

### `pocketStudio/services/orchestrator.py`

Domain service used by routes, workers, or orchestrator.

#### `TeamActions`

TeamActions data type or service class.

| Method | Usage |
|---|---|
| `__init__(self, mentions: list[tuple[str, str]], chatrooms: list[tuple[str, str]]) -> None` | Python protocol or object lifecycle method. |

#### `Orchestrator`

Orchestrator data type or service class.

| Method | Usage |
|---|---|
| `__init__(self, agents: AgentService, teams: TeamService, queue: QueueService, chat: ChatService, events: EventService, providers: ProviderRegistry, projects: ProjectService | None=None) -> None` | Python protocol or object lifecycle method. |
| `enqueue(self, payload: MessageCreate) -> QueueMessage` | Helper used by this module/class. Inspect callers before changing behavior. |
| `process_one(self, newest: bool=False) -> OrchestrationResult | None` | Processes a queue item or worker step. |
| `process_message(self, message_id: int) -> OrchestrationResult` | Processes a queue item or worker step. |
| `_dispatch(self, message: QueueMessage) -> OrchestrationResult` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_run_team(self, message: QueueMessage, team: Team) -> OrchestrationResult` | Private implementation for a longer running process. |
| `_run_iterative_rounds(self, team: Team, message: QueueMessage, agents: list[Agent], seed_runs: list[AgentRun], max_rounds: int) -> list[AgentRun]` | Private implementation for a longer running process. |
| `_mentions_from_runs(self, team: Team, runs: list[AgentRun], agents: list[Agent]) -> list[tuple[str, str, str]]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_handle_team_tags(self, team: Team, run: AgentRun, message: QueueMessage, agents: list[Agent], enqueue_mentions: bool=True, process_chatrooms: bool=True) -> None` | Handles a route/event/sub-step inside a larger workflow. |
| `_handle_direct_agent_team_tags(self, agent: Agent, run: AgentRun, message: QueueMessage) -> None` | Handles a route/event/sub-step inside a larger workflow. |
| `_broadcast_chatroom(self, team: Team, from_agent: str, content: str, agents: list[Agent], parent: QueueMessage) -> int` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_post_chatroom_run_outputs(self, team: Team, runs: list[AgentRun]) -> None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_is_chatroom_origin(message: QueueMessage) -> bool` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_team_child_metadata(parent: QueueMessage | None, *, team: Team, from_agent: str, kind: str, to_agent: str) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_order_agents_for_team(team: Team, agents: list[Agent]) -> list[Agent]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_teams_for_agent(self, agent_id: str) -> list[Team]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_resolve_team_context_for_agent(agent_id: str, teams: list[Team]) -> Team | None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_resolve_team_for_tag(team_id: str, teams: list[Team], agent_id: str) -> Team | None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_agent_lookup(agents: list[Agent]) -> dict[str, str]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_split_candidate_ids(raw_ids: str) -> list[str]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_extract_tags(text: str, prefix: str) -> list[tuple[str, str]]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_strip_tags(text: str, prefix: str) -> str` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_extract_bracket_tags(text: str, prefix: str) -> list[tuple[str, str, int, int]]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_run_agent(self, agent: Agent, input_text: str, context: list[str]) -> AgentRun` | Private implementation for a longer running process. |
| `_agent_for_message(self, agent_id: str, message: QueueMessage) -> Agent` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_parse_target(target: str) -> tuple[str, str]` | Parses text, configuration, or persisted values. |
| `decode_result(message: QueueMessage) -> OrchestrationResult | None` | Helper used by this module/class. Inspect callers before changing behavior. |

### `pocketStudio/services/plugin_service.py`

Domain service used by routes, workers, or orchestrator.

#### `HookResult`

HookResult data type or service class.

#### `LoadedPlugin`

LoadedPlugin data type or service class.

#### `PluginContext`

PluginContext data type or service class.

| Method | Usage |
|---|---|
| `__init__(self, name: str, home: Path, events: EventService) -> None` | Python protocol or object lifecycle method. |
| `on(self, event_type: str, handler: Callable[[dict[str, Any]], None]) -> None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `log(self, level: str, message: str) -> None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `get_pocketstudio_home(self) -> str` | Fetches one record, status object, or derived view. |

#### `PluginService`

PluginService data type or service class.

| Method | Usage |
|---|---|
| `__init__(self, settings: Settings, events: EventService) -> None` | Python protocol or object lifecycle method. |
| `plugins_path(self) -> Path` | Helper used by this module/class. Inspect callers before changing behavior. |
| `list_plugins(self, reload: bool=False) -> list[dict[str, Any]]` | Lists records or projections from storage/API. |
| `load_plugins(self, reload: bool=False) -> list[LoadedPlugin]` | Loads content/configuration from storage. |
| `run_incoming_hooks(self, message: str, context: dict[str, Any]) -> HookResult` | Runs a command, provider, setup, or workflow. |
| `run_outgoing_hooks(self, message: str, context: dict[str, Any]) -> HookResult` | Runs a command, provider, setup, or workflow. |
| `broadcast_event(self, event_type: str, payload: dict[str, Any]) -> None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `handle_event(self, event: Event) -> None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_run_hook(self, hook_name: str, message: str, context: dict[str, Any]) -> HookResult` | Private implementation for a longer running process. |
| `_apply_hook(message: str, hook: dict[str, Any], context: dict[str, Any]) -> tuple[str, dict[str, Any]]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_load_module(self, plugin_dir: Path, module_path: Path) -> ModuleType | None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_activate(self, plugin: LoadedPlugin) -> None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_module_hooks(module: ModuleType | None) -> dict[str, Callable]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_apply_callable_hook(message: str, hook: Callable[[str, dict[str, Any]], Any], context: dict[str, Any]) -> tuple[str, dict[str, Any]]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_mark_plugin(metadata: dict[str, Any], plugin_name: str) -> None` | Helper used by this module/class. Inspect callers before changing behavior. |

### `pocketStudio/services/project_service.py`

Domain service used by routes, workers, or orchestrator.

#### `ProjectService`

ProjectService data type or service class.

| Method | Usage |
|---|---|
| `__init__(self, db: Database, events: EventService) -> None` | Python protocol or object lifecycle method. |
| `list_projects(self) -> list[Project]` | Lists records or projections from storage/API. |
| `create_project(self, payload: ProjectCreate) -> Project` | Creates a new record or resource. |
| `get_project(self, project_id: str) -> Project` | Fetches one record, status object, or derived view. |
| `update_project(self, project_id: str, payload: ProjectCreate) -> Project` | Updates an existing record or resource. |
| `project_agent_workspace(self, project_id: str, agent_id: str) -> Path | None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `workspace_status(self, project_id: str, repair: bool=False) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `ensure_working_directory(path: Path) -> None` | Checks and creates required state when missing. |
| `_workspace_checks(workspace: Path) -> list[dict]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `delete_project(self, project_id: str) -> None` | Deletes or removes a record/resource. |
| `task_count(self, project_id: str) -> int` | Helper used by this module/class. Inspect callers before changing behavior. |
| `comment_count(self, task_id: int) -> int` | Helper used by this module/class. Inspect callers before changing behavior. |
| `list_comments(self, task_id: int) -> list[TaskComment]` | Lists records or projections from storage/API. |
| `create_comment(self, task_id: int, payload: TaskCommentCreate) -> TaskComment` | Creates a new record or resource. |
| `delete_comment(self, comment_id: str) -> None` | Deletes or removes a record/resource. |
| `_project_id(name: str) -> str` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_workspace_path(workspace: str | None) -> Path | None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `generate_prefix(name: str) -> str` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_next_global_task_number(self) -> int` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_to_project(row) -> Project` | Converts database rows or internal objects into models/payloads. |
| `_legacy_default_workspace(project_id: str) -> Path` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_to_comment(row) -> TaskComment` | Converts database rows or internal objects into models/payloads. |

### `pocketStudio/services/queue_service.py`

Domain service used by routes, workers, or orchestrator.

#### `QueueService`

QueueService data type or service class.

| Method | Usage |
|---|---|
| `__init__(self, db: Database, events: EventService, settings: Settings, responses: ResponseService | None=None, plugins: PluginService | None=None) -> None` | Python protocol or object lifecycle method. |
| `enqueue(self, payload: MessageCreate) -> QueueMessage` | Helper used by this module/class. Inspect callers before changing behavior. |
| `get(self, message_id: int) -> QueueMessage` | Get operation for QueueService. |
| `list(self, limit: int=100, status: MessageStatus | None=None) -> list[QueueMessage]` | List operation for QueueService. |
| `find_by_client_message_id(self, client_message_id: str, limit: int=1000) -> QueueMessage | None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `grouped_chatroom_messages(self, limit: int=100, status: MessageStatus | None=None) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `status(self) -> QueueStatus` | Controls or reports runtime service state. |
| `diagnostics(self, stale_threshold_seconds: int | None=None) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `agent_status(self) -> list[dict]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `next_queued(self, newest: bool=False) -> QueueMessage | None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `recover_stale_messages(self, threshold_seconds: int | None=None) -> int` | Helper used by this module/class. Inspect callers before changing behavior. |
| `mark_running(self, message_id: int) -> QueueMessage` | Transitions persisted state. |
| `mark_done(self, message_id: int, result: str) -> QueueMessage` | Transitions persisted state. |
| `mark_failed(self, message_id: int, error: str) -> QueueMessage` | Transitions persisted state. |
| `list_dead(self, limit: int=100) -> list[QueueMessage]` | Lists records or projections from storage/API. |
| `dead_payloads(self, limit: int=100) -> list[dict]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `retry_dead(self, message_id: int) -> bool` | Helper used by this module/class. Inspect callers before changing behavior. |
| `retry_message(self, message_id: int) -> QueueMessage` | Helper used by this module/class. Inspect callers before changing behavior. |
| `delete_dead(self, message_id: int) -> bool` | Deletes or removes a record/resource. |
| `insert_agent_message(self, agent_id: str, role: str, content: str, message_id: str, sender: str='', channel: str='web', created_at: int | None=None) -> AgentMessage` | Helper used by this module/class. Inspect callers before changing behavior. |
| `get_agent_messages(self, agent_id: str, limit: int=100, since_id: int=0) -> list[AgentMessage]` | Fetches one record, status object, or derived view. |
| `get_all_agent_messages(self, limit: int=100, since_id: int=0) -> list[AgentMessage]` | Fetches one record, status object, or derived view. |
| `reset_agent(self, agent_id: str) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `recent_responses(self, limit: int=20) -> list[dict]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `enqueue_response(self, message_id: str, channel: str, sender: str, message: str, original_message: str, agent: str | None=None, sender_id: str | None=None, files: list[str] | None=None, metadata: dict | None=None) -> ResponseJob` | Adds a message or response to a queue. |
| `get_responses_for_channel(self, channel: str) -> list[ResponseJob]` | Fetches one record, status object, or derived view. |
| `ack_response(self, response_id: int) -> bool` | Helper used by this module/class. Inspect callers before changing behavior. |
| `prune_acked_responses(self, older_than_ms: int=86400000) -> int` | Helper used by this module/class. Inspect callers before changing behavior. |
| `prune_completed_messages(self, older_than_ms: int=86400000) -> int` | Helper used by this module/class. Inspect callers before changing behavior. |
| `enqueue_responses_from_message(self, message: QueueMessage) -> list[ResponseJob]` | Adds a message or response to a queue. |
| `processing_payloads(self) -> list[dict]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_dead_payload(message: QueueMessage) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_target_label(target: str) -> str` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_is_chatroom_message(message: QueueMessage) -> bool` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_combined_chatroom_payload(messages: list[QueueMessage]) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_pending_response_count(self) -> int` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_message_summary(row) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_timestamp_ms(value: str) -> int` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_to_message(row) -> QueueMessage` | Converts database rows or internal objects into models/payloads. |
| `_to_agent_message(row) -> AgentMessage` | Converts database rows or internal objects into models/payloads. |
| `_to_response(row) -> ResponseJob` | Converts database rows or internal objects into models/payloads. |
| `_response_api_payload(response: ResponseJob) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_prepare_team_response_text(run: dict) -> tuple[str, dict]` | Helper used by this module/class. Inspect callers before changing behavior. |

### `pocketStudio/services/response_service.py`

Domain service used by routes, workers, or orchestrator.

#### `PreparedResponse`

PreparedResponse data type or service class.

#### `ResponseService`

ResponseService data type or service class.

| Method | Usage |
|---|---|
| `__init__(self, settings: Settings, plugins: PluginService | None=None) -> None` | Python protocol or object lifecycle method. |
| `prepare(self, response: str, existing_files: list[str] | None=None, context: dict | None=None) -> PreparedResponse` | Helper used by this module/class. Inspect callers before changing behavior. |
| `collect_files(response: str) -> list[str]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_save_long_response(self, response: str) -> Path` | Helper used by this module/class. Inspect callers before changing behavior. |

### `pocketStudio/services/schedule_service.py`

Domain service used by routes, workers, or orchestrator.

#### `ScheduleService`

ScheduleService data type or service class.

| Method | Usage |
|---|---|
| `__init__(self, db: Database, events: EventService) -> None` | Python protocol or object lifecycle method. |
| `list(self, agent_id: str | None=None) -> list[Schedule]` | List operation for ScheduleService. |
| `schedule_status(self, schedule: Schedule, now: datetime | None=None) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `next_fire_at(self, schedule: Schedule, now: datetime | None=None) -> datetime | None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `create(self, payload: ScheduleCreate) -> Schedule` | Create operation for ScheduleService. |
| `get(self, schedule_id: str) -> Schedule` | Get operation for ScheduleService. |
| `update(self, schedule_id: str, payload: ScheduleCreate) -> Schedule` | Update operation for ScheduleService. |
| `delete(self, schedule_id: str) -> None` | Delete operation for ScheduleService. |
| `validate(self, payload: ScheduleCreate, now: datetime | None=None) -> dict` | Validate operation for ScheduleService. |
| `fire(self, schedule_id: str, queue: QueueService, now: datetime | None=None, force: bool=False) -> QueueMessage` | Fire operation for ScheduleService. |
| `fire_due(self, queue: QueueService, now: datetime | None=None) -> list[QueueMessage]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_fire(self, queue: QueueService, schedule: Schedule, now: datetime) -> QueueMessage` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_validate_payload(self, payload: ScheduleCreate) -> None` | Validates user/config payloads. |
| `_ensure_label_available(self, label: str, exclude_id: str | None=None) -> None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_find_row(self, identifier: str)` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_parse_datetime(value: str) -> datetime | None` | Parses text, configuration, or persisted values. |
| `_cron_matches(expression: str, now: datetime) -> bool` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_field_matches(field: str, value: int, minimum: int, maximum: int) -> bool` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_field_is_valid(field: str, minimum: int, maximum: int) -> bool` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_range(value: str) -> tuple[int | None, int | None]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_epoch_ms(value: datetime) -> int` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_to_schedule(row) -> Schedule` | Converts database rows or internal objects into models/payloads. |

### `pocketStudio/services/settings_service.py`

Domain service used by routes, workers, or orchestrator.

#### `SettingsValidationError`

SettingsValidationError data type or service class.

#### `SettingsService`

SettingsService data type or service class.

| Method | Usage |
|---|---|
| `__init__(self, db: Database, settings: Settings) -> None` | Python protocol or object lifecycle method. |
| `snapshot(self) -> dict[str, Any]` | Controls or reports runtime service state. |
| `update(self, payload: dict[str, Any]) -> dict[str, Any]` | Update operation for SettingsService. |
| `preview_update(self, payload: dict[str, Any]) -> dict[str, Any]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `validate(self, payload: dict[str, Any]) -> None` | Validate operation for SettingsService. |
| `_validate_object(payload: dict[str, Any], key: str) -> None` | Validates user/config payloads. |
| `_validate_mapping(payload: dict[str, Any], key: str) -> None` | Validates user/config payloads. |
| `write(self, settings: dict[str, Any]) -> None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_file_settings(self) -> dict[str, Any]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_legacy_db_settings(self) -> dict[str, Any]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `ensure_setup_dirs(self, settings: dict[str, Any]) -> None` | Checks and creates required state when missing. |
| `backup_info(self) -> dict[str, Any]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `restore_backup(self) -> dict[str, Any]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `backup_path(self) -> Path` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_backup_current_settings(self) -> None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_merge(cls, current: Any, update: Any) -> Any` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_normalize_paths(cls, payload: dict[str, Any]) -> dict[str, Any]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_expand_home_path(value: str) -> str` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_known_sections(settings: dict[str, Any]) -> dict[str, Any]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_diff(cls, current: Any, next_value: Any, prefix: str='') -> list[dict[str, Any]]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_repair_json(raw: str) -> dict[str, Any] | None` | Helper used by this module/class. Inspect callers before changing behavior. |

### `pocketStudio/services/task_service.py`

Domain service used by routes, workers, or orchestrator.

#### `TaskService`

TaskService data type or service class.

| Method | Usage |
|---|---|
| `__init__(self, db: Database, events: EventService) -> None` | Python protocol or object lifecycle method. |
| `create(self, payload: TaskCreate) -> Task` | Create operation for TaskService. |
| `get(self, task_id: int) -> Task` | Get operation for TaskService. |
| `list(self, project_id: str | None=None, status: str | None=None, assignee: str | None=None, query: str | None=None) -> list[Task]` | List operation for TaskService. |
| `update(self, task_id: int, payload: TaskCreate) -> Task` | Update operation for TaskService. |
| `update_status(self, task_id: int, status: str) -> Task` | Updates an existing record or resource. |
| `reorder(self, columns: dict[str, list[str]]) -> int` | Helper used by this module/class. Inspect callers before changing behavior. |
| `delete(self, task_id: int) -> None` | Delete operation for TaskService. |
| `_to_task(row) -> Task` | Converts database rows or internal objects into models/payloads. |
| `_next_number(self, project_id: str | None) -> int` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_next_position(self, status: str) -> int` | Helper used by this module/class. Inspect callers before changing behavior. |

### `pocketStudio/services/team_routing.py`

Domain service used by routes, workers, or orchestrator.

| Function | Usage |
|---|---|
| `extract_bracket_tags(text: str, prefix: str) -> list[BracketTag]` | Helper used by this module/class. Inspect callers before changing behavior. |
| `strip_bracket_tags(text: str, prefix: str) -> str` | Helper used by this module/class. Inspect callers before changing behavior. |
| `convert_tags_to_readable(text: str, from_agent: str | None=None) -> str` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_convert_prefix_tags(text: str, prefix: str, readable_prefix: str) -> str` | Helper used by this module/class. Inspect callers before changing behavior. |

#### `BracketTag`

BracketTag data type or service class.

### `pocketStudio/services/team_service.py`

Domain service used by routes, workers, or orchestrator.

#### `TeamService`

TeamService data type or service class.

| Method | Usage |
|---|---|
| `__init__(self, db: Database, settings: Settings | None=None) -> None` | Python protocol or object lifecycle method. |
| `create(self, payload: TeamCreate) -> Team` | Create operation for TeamService. |
| `get(self, team_id: str) -> Team` | Get operation for TeamService. |
| `list(self) -> list[Team]` | List operation for TeamService. |
| `delete(self, team_id: str) -> None` | Delete operation for TeamService. |
| `add_member(self, team_id: str, agent_id: str) -> Team` | Helper used by this module/class. Inspect callers before changing behavior. |
| `remove_member(self, team_id: str, agent_id: str) -> Team` | Helper used by this module/class. Inspect callers before changing behavior. |
| `set_leader(self, team_id: str, agent_id: str) -> Team` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_read_settings_file(self) -> dict` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_write_settings_file(self, data: dict) -> None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_sync_team_settings(self, team: Team) -> None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_remove_team_settings(self, team_id: str) -> None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_to_team(row) -> Team` | Converts database rows or internal objects into models/payloads. |

### `pocketStudio/services/worker_service.py`

Domain service used by routes, workers, or orchestrator.

#### `WorkerState`

WorkerState data type or service class.

#### `WorkerService`

WorkerService data type or service class.

| Method | Usage |
|---|---|
| `__init__(self, orchestrator: Orchestrator, schedules: ScheduleService, heartbeat: HeartbeatService, events: EventService, settings: Settings) -> None` | Python protocol or object lifecycle method. |
| `start(self) -> bool` | Controls or reports runtime service state. |
| `stop(self) -> bool` | Controls or reports runtime service state. |
| `pause(self) -> bool` | Controls or reports runtime service state. |
| `resume(self) -> bool` | Controls or reports runtime service state. |
| `restart(self) -> None` | Controls or reports runtime service state. |
| `process_once(self, force: bool=False) -> bool` | Processes a queue item or worker step. |
| `snapshot(self) -> dict` | Controls or reports runtime service state. |
| `maintenance(self, older_than_ms: int=86400000, stale_threshold_seconds: int | None=None, prune_chats: bool=False) -> dict` | Controls or reports runtime service state. |
| `_health(self, queue_status: dict) -> str` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_process_fired_messages(self, messages: list[QueueMessage]) -> int` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_process_next_available(self, newest: bool=False) -> int` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_record_failure(self, exc: Exception) -> None` | Helper used by this module/class. Inspect callers before changing behavior. |
| `_run(self) -> None` | Helper used by this module/class. Inspect callers before changing behavior. |

