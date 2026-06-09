# pocketStudio Project Structure and Function Usage

This document is generated from the Python backend source by `tools/generate_project_docs.py` so maintainers can quickly locate module responsibilities and function entry points.

## Project Structure

- `pocketStudio/api/`: FastAPI routes and TinyAGI/TinyOffice compatibility responses.
- `pocketStudio/channels/`: External channel bridges; currently includes Telegram.
- `pocketStudio/core/`: Configuration, database, dependency injection, IDs, runtime, and JSON file helpers.
- `pocketStudio/providers/`: Local, OpenAI-compatible, Codex, Claude/OpenCode CLI, and other provider adapters.
- `pocketStudio/services/`: Business service layer that owns the main domain logic.
- `pocketStudio/static/`: Bundled fallback UI.
- `tests/`: pytest behavior tests and compatibility contract tests.
- `docs/`: Architecture, mapping, and maintenance documentation.

## Maintenance Rules

- Keep route modules thin: put complex business logic in `services/`.
- Put external model or command execution in `providers/`; put external message channels in `channels/`.
- Reuse `pocketStudio/api/payloads.py` for API response shaping.
- Reuse `pocketStudio/core/json_store.py` for settings JSON file reads and writes.
- After adding or moving functions, run `python tools/generate_project_docs.py` to update both language versions.

## Function Index

### `pocketStudio/__init__.py`

Package entry point or application entry point.

### `pocketStudio/api/__init__.py`

FastAPI route layer. Keep HTTP validation, response shaping, and exception mapping here.

### `pocketStudio/api/agents.py`

FastAPI route layer. Keep HTTP validation, response shaping, and exception mapping here.

| Function | Usage |
|---|---|
| `list_agents(service: AgentService=Depends(get_agent_service))` | Lists resources or query results. |
| `upsert_agent(payload: AgentCreate, service: AgentService=Depends(get_agent_service))` | Module-level helper. Review callers and tests before changing behavior. |
| `update_agent(agent_id: str, payload: dict, service: AgentService=Depends(get_agent_service))` | Updates or persists an existing resource. |
| `get_agent(agent_id: str, service: AgentService=Depends(get_agent_service))` | Reads one resource, status object, or derived view. |
| `delete_agent(agent_id: str, service: AgentService=Depends(get_agent_service))` | Deletes a resource or clears state. |

### `pocketStudio/api/chat.py`

FastAPI route layer. Keep HTTP validation, response shaping, and exception mapping here.

| Function | Usage |
|---|---|
| `_chatroom_payload(message: ChatMessage)` | Builds API or compatibility-layer response/request payloads. |
| `list_chat(team_id: str, limit: int=Query(default=100, ge=1, le=500), since: int=Query(default=0, ge=0), sender: str \| None=None, q: str \| None=None, service: ChatService=Depends(get_chat_service))` | Lists resources or query results. |
| `post_chat(team_id: str, payload: ChatMessageCreate, service: ChatService=Depends(get_chat_service), queue: QueueService=Depends(get_queue_service), teams: TeamService=Depends(get_team_service))` | Module-level helper. Review callers and tests before changing behavior. |

### `pocketStudio/api/compat.py`

FastAPI route layer. Keep HTTP validation, response shaping, and exception mapping here.

| Function | Usage |
|---|---|
| `_schedule_create_payload(payload: dict[str, Any])` | Builds API or compatibility-layer response/request payloads. |
| `_custom_providers(db: Database)` | Module-level helper. Review callers and tests before changing behavior. |
| `_save_custom_provider_row(provider_id: str, payload: dict[str, Any], db: Database)` | Updates or persists an existing resource. |
| `_settings_apply_plan(payload: dict[str, Any])` | Updates or persists an existing resource. |
| `_settings_path_value(value: Any)` | Updates or persists an existing resource. |
| `_validate_settings_apply_plan(payload: dict[str, Any])` | Validates input or repairs required runtime state. |
| `_target_agent_id(target: str)` | Module-level helper. Review callers and tests before changing behavior. |
| `get_settings_snapshot(agents: AgentService=Depends(get_agent_service), teams: TeamService=Depends(get_team_service), db: Database=Depends(get_database), settings_service: SettingsService=Depends(get_settings_service))` | Reads one resource, status object, or derived view. |
| `export_settings_snapshot(agents: AgentService=Depends(get_agent_service), teams: TeamService=Depends(get_team_service), db: Database=Depends(get_database), settings_service: SettingsService=Depends(get_settings_service))` | Module-level helper. Review callers and tests before changing behavior. |
| `validate_settings_snapshot(payload: dict[str, Any], settings_service: SettingsService=Depends(get_settings_service))` | Validates input or repairs required runtime state. |
| `preview_settings_snapshot(payload: dict[str, Any], settings_service: SettingsService=Depends(get_settings_service))` | Module-level helper. Review callers and tests before changing behavior. |
| `settings_backup_info(settings_service: SettingsService=Depends(get_settings_service))` | Updates or persists an existing resource. |
| `restore_settings_backup(agents: AgentService=Depends(get_agent_service), teams: TeamService=Depends(get_team_service), db: Database=Depends(get_database), settings_service: SettingsService=Depends(get_settings_service))` | Module-level helper. Review callers and tests before changing behavior. |
| `update_settings_snapshot(payload: dict[str, Any], agents: AgentService=Depends(get_agent_service), teams: TeamService=Depends(get_team_service), db: Database=Depends(get_database), registry: ProviderRegistry=Depends(get_provider_registry), settings_service: SettingsService=Depends(get_settings_service))` | Updates or persists an existing resource. |
| `import_settings_snapshot(payload: dict[str, Any], agents: AgentService=Depends(get_agent_service), teams: TeamService=Depends(get_team_service), db: Database=Depends(get_database), registry: ProviderRegistry=Depends(get_provider_registry), settings_service: SettingsService=Depends(get_settings_service))` | Module-level helper. Review callers and tests before changing behavior. |
| `run_setup(payload: dict[str, Any], agents: AgentService=Depends(get_agent_service), teams: TeamService=Depends(get_team_service), db: Database=Depends(get_database), registry: ProviderRegistry=Depends(get_provider_registry), settings_service: SettingsService=Depends(get_settings_service))` | Runs a provider, orchestration flow, event handler, or external message handler. |
| `enqueue_legacy_message(payload: dict[str, Any], orchestrator: Orchestrator=Depends(get_orchestrator), channels: ChannelService=Depends(get_channel_service), queue: QueueService=Depends(get_queue_service))` | Queue, response, or message flow operation. |
| `queue_status(queue: QueueService=Depends(get_queue_service))` | Queue, response, or message flow operation. |
| `queue_diagnostics(stale_threshold_seconds: int \| None=None, queue: QueueService=Depends(get_queue_service))` | Queue, response, or message flow operation. |
| `queue_agent_status(queue: QueueService=Depends(get_queue_service))` | Queue, response, or message flow operation. |
| `queue_dead(limit: int=Query(default=100, ge=1, le=500), queue: QueueService=Depends(get_queue_service))` | Queue, response, or message flow operation. |
| `queue_dead_retry(message_id: int, queue: QueueService=Depends(get_queue_service))` | Queue, response, or message flow operation. |
| `queue_dead_delete(message_id: int, queue: QueueService=Depends(get_queue_service))` | Queue, response, or message flow operation. |
| `queue_recover_stale(threshold_seconds: int \| None=None, queue: QueueService=Depends(get_queue_service))` | Queue, response, or message flow operation. |
| `queue_processing(queue: QueueService=Depends(get_queue_service), registry: ProviderRegistry=Depends(get_provider_registry))` | Queue, response, or message flow operation. |
| `active_processes(registry: ProviderRegistry=Depends(get_provider_registry))` | Module-level helper. Review callers and tests before changing behavior. |
| `provider_diagnostics(registry: ProviderRegistry=Depends(get_provider_registry))` | Module-level helper. Review callers and tests before changing behavior. |
| `async kill_agent_process(agent_id: str, registry: ProviderRegistry=Depends(get_provider_registry))` | Module-level helper. Review callers and tests before changing behavior. |
| `async kill_processing(message_id: int, queue: QueueService=Depends(get_queue_service), registry: ProviderRegistry=Depends(get_provider_registry))` | Module-level helper. Review callers and tests before changing behavior. |
| `responses(limit: int=Query(default=20, ge=1, le=200), queue: QueueService=Depends(get_queue_service))` | Module-level helper. Review callers and tests before changing behavior. |
| `enqueue_response(payload: dict[str, Any], queue: QueueService=Depends(get_queue_service))` | Queue, response, or message flow operation. |
| `pending_responses(channel: str=Query(...), queue: QueueService=Depends(get_queue_service))` | Module-level helper. Review callers and tests before changing behavior. |
| `responses_for_channel(channel: str, queue: QueueService=Depends(get_queue_service))` | Module-level helper. Review callers and tests before changing behavior. |
| `ack_response(response_id: int, queue: QueueService=Depends(get_queue_service))` | Queue, response, or message flow operation. |
| `prune_responses(older_than_ms: int=86400000, queue: QueueService=Depends(get_queue_service))` | Queue, response, or message flow operation. |
| `prune_completed_messages(older_than_ms: int=86400000, queue: QueueService=Depends(get_queue_service))` | Queue, response, or message flow operation. |
| `logs(limit: int=Query(default=100, ge=1, le=500), event_type: str \| None=None, contains: str \| None=None, events: EventService=Depends(get_event_service))` | Module-level helper. Review callers and tests before changing behavior. |
| `list_chats(chat: ChatService=Depends(get_chat_service))` | Lists resources or query results. |
| `read_chat_archive(team_id: str, limit: int=Query(default=500, ge=1, le=2000), sender: str \| None=None, q: str \| None=None, chat: ChatService=Depends(get_chat_service))` | Module-level helper. Review callers and tests before changing behavior. |
| `agent_messages(agent_id: str, limit: int=Query(default=100, ge=1, le=500), since_id: int=Query(default=0, ge=0), queue: QueueService=Depends(get_queue_service))` | Module-level helper. Review callers and tests before changing behavior. |
| `all_agent_messages(limit: int=Query(default=100, ge=1, le=500), since_id: int=Query(default=0, ge=0), queue: QueueService=Depends(get_queue_service))` | Module-level helper. Review callers and tests before changing behavior. |
| `reset_agent_runtime(agent_id: str, agents: AgentService=Depends(get_agent_service), queue: QueueService=Depends(get_queue_service))` | Module-level helper. Review callers and tests before changing behavior. |
| `list_plugins(plugins: PluginService=Depends(get_plugin_service))` | Lists resources or query results. |
| `reload_plugins(plugins: PluginService=Depends(get_plugin_service))` | Module-level helper. Review callers and tests before changing behavior. |
| `get_agent_system_prompt(agent_id: str, agents: AgentService=Depends(get_agent_service))` | Reads one resource, status object, or derived view. |
| `save_agent_system_prompt(agent_id: str, payload: dict[str, str], agents: AgentService=Depends(get_agent_service))` | Updates or persists an existing resource. |
| `get_agent_workspace_status(agent_id: str, agents: AgentService=Depends(get_agent_service))` | Reads one resource, status object, or derived view. |
| `repair_agent_workspace(agent_id: str, agents: AgentService=Depends(get_agent_service))` | Validates input or repairs required runtime state. |
| `get_agent_memory(agent_id: str, agents: AgentService=Depends(get_agent_service))` | Reads one resource, status object, or derived view. |
| `get_agent_memory_file(agent_id: str, path: str=Query(...), agents: AgentService=Depends(get_agent_service))` | Reads one resource, status object, or derived view. |
| `save_agent_memory_file(agent_id: str, payload: dict[str, Any], agents: AgentService=Depends(get_agent_service))` | Updates or persists an existing resource. |
| `delete_agent_memory_file(agent_id: str, path: str=Query(...), agents: AgentService=Depends(get_agent_service))` | Deletes a resource or clears state. |
| `get_agent_heartbeat(agent_id: str, agents: AgentService=Depends(get_agent_service))` | Reads one resource, status object, or derived view. |
| `save_agent_heartbeat(agent_id: str, payload: dict[str, Any], agents: AgentService=Depends(get_agent_service))` | Updates or persists an existing resource. |
| `list_agent_skills(agent_id: str, agents: AgentService=Depends(get_agent_service))` | Lists resources or query results. |
| `search_agent_skills(agent_id: str, query: str='', agents: AgentService=Depends(get_agent_service))` | Module-level helper. Review callers and tests before changing behavior. |
| `install_agent_skill(agent_id: str, payload: dict[str, str], agents: AgentService=Depends(get_agent_service))` | Creates a resource, installs content, or adds a relationship. |
| `list_projects(status: str \| None=None, projects: ProjectService=Depends(get_project_service))` | Lists resources or query results. |
| `create_project(payload: ProjectCreate, projects: ProjectService=Depends(get_project_service))` | Creates a resource, installs content, or adds a relationship. |
| `get_project(project_id: str, projects: ProjectService=Depends(get_project_service))` | Reads one resource, status object, or derived view. |
| `update_project(project_id: str, payload: dict[str, Any], projects: ProjectService=Depends(get_project_service))` | Updates or persists an existing resource. |
| `get_project_workspace_status(project_id: str, projects: ProjectService=Depends(get_project_service))` | Reads one resource, status object, or derived view. |
| `repair_project_workspace(project_id: str, projects: ProjectService=Depends(get_project_service))` | Validates input or repairs required runtime state. |
| `delete_project(project_id: str, projects: ProjectService=Depends(get_project_service))` | Deletes a resource or clears state. |
| `reorder_tasks(payload: dict[str, Any], tasks: TaskService=Depends(get_task_service))` | Module-level helper. Review callers and tests before changing behavior. |
| `list_task_comments(task_id: int, projects: ProjectService=Depends(get_project_service))` | Lists resources or query results. |
| `create_task_comment(task_id: int, payload: TaskCommentCreate, projects: ProjectService=Depends(get_project_service))` | Creates a resource, installs content, or adds a relationship. |
| `delete_comment(comment_id: str, projects: ProjectService=Depends(get_project_service))` | Deletes a resource or clears state. |
| `list_schedules(agent: str \| None=None, schedules: ScheduleService=Depends(get_schedule_service))` | Lists resources or query results. |
| `create_schedule(payload: dict[str, Any], schedules: ScheduleService=Depends(get_schedule_service))` | Creates a resource, installs content, or adds a relationship. |
| `validate_schedule(payload: dict[str, Any], schedules: ScheduleService=Depends(get_schedule_service))` | Validates input or repairs required runtime state. |
| `update_schedule(schedule_id: str, payload: dict[str, Any], schedules: ScheduleService=Depends(get_schedule_service))` | Updates or persists an existing resource. |
| `fire_schedule(schedule_id: str, payload: dict[str, Any] \| None=None, schedules: ScheduleService=Depends(get_schedule_service), queue: QueueService=Depends(get_queue_service))` | Controls a background worker, scheduler, or processing flow. |
| `delete_schedule(schedule_id: str, schedules: ScheduleService=Depends(get_schedule_service))` | Deletes a resource or clears state. |
| `system_status(worker: WorkerService=Depends(get_worker_service), heartbeat: HeartbeatService=Depends(get_heartbeat_service), settings_service: SettingsService=Depends(get_settings_service), telegram: TelegramChannelService=Depends(get_telegram_channel_service))` | Module-level helper. Review callers and tests before changing behavior. |
| `_service_status_payload(worker: WorkerService, heartbeat: HeartbeatService, settings_service: SettingsService, telegram: TelegramChannelService \| None=None)` | Builds API or compatibility-layer response/request payloads. |
| `heartbeat_status(heartbeat: HeartbeatService=Depends(get_heartbeat_service))` | Module-level helper. Review callers and tests before changing behavior. |
| `heartbeat_tick(payload: dict[str, Any] \| None=None, heartbeat: HeartbeatService=Depends(get_heartbeat_service), queue: QueueService=Depends(get_queue_service))` | Module-level helper. Review callers and tests before changing behavior. |
| `clear_heartbeat_state(agent: str \| None=Query(default=None), heartbeat: HeartbeatService=Depends(get_heartbeat_service))` | Deletes a resource or clears state. |
| `worker_status(worker: WorkerService=Depends(get_worker_service))` | Module-level helper. Review callers and tests before changing behavior. |
| `async worker_start(worker: WorkerService=Depends(get_worker_service))` | Module-level helper. Review callers and tests before changing behavior. |
| `async worker_stop(worker: WorkerService=Depends(get_worker_service))` | Module-level helper. Review callers and tests before changing behavior. |
| `async worker_pause(worker: WorkerService=Depends(get_worker_service))` | Module-level helper. Review callers and tests before changing behavior. |
| `async worker_resume(worker: WorkerService=Depends(get_worker_service))` | Module-level helper. Review callers and tests before changing behavior. |
| `async worker_restart(worker: WorkerService=Depends(get_worker_service))` | Module-level helper. Review callers and tests before changing behavior. |
| `async worker_tick(force: bool=False, worker: WorkerService=Depends(get_worker_service))` | Module-level helper. Review callers and tests before changing behavior. |
| `worker_maintenance(older_than_ms: int=86400000, stale_threshold_seconds: int \| None=None, prune_chats: bool=False, worker: WorkerService=Depends(get_worker_service))` | Module-level helper. Review callers and tests before changing behavior. |
| `async apply_services(worker: WorkerService=Depends(get_worker_service), settings_service: SettingsService=Depends(get_settings_service), telegram: TelegramChannelService=Depends(get_telegram_channel_service))` | Module-level helper. Review callers and tests before changing behavior. |
| `services_status(worker: WorkerService=Depends(get_worker_service), heartbeat: HeartbeatService=Depends(get_heartbeat_service), settings_service: SettingsService=Depends(get_settings_service), telegram: TelegramChannelService=Depends(get_telegram_channel_service))` | Module-level helper. Review callers and tests before changing behavior. |
| `async start_services(worker: WorkerService=Depends(get_worker_service), heartbeat: HeartbeatService=Depends(get_heartbeat_service), settings_service: SettingsService=Depends(get_settings_service), telegram: TelegramChannelService=Depends(get_telegram_channel_service))` | Controls a background worker, scheduler, or processing flow. |
| `async stop_services(worker: WorkerService=Depends(get_worker_service), heartbeat: HeartbeatService=Depends(get_heartbeat_service), settings_service: SettingsService=Depends(get_settings_service), telegram: TelegramChannelService=Depends(get_telegram_channel_service))` | Controls a background worker, scheduler, or processing flow. |
| `async restart_service(worker: WorkerService=Depends(get_worker_service))` | Controls a background worker, scheduler, or processing flow. |
| `async channel_action(channel_id: str, action: str, telegram: TelegramChannelService=Depends(get_telegram_channel_service))` | Module-level helper. Review callers and tests before changing behavior. |
| `get_pairings(channels: ChannelService=Depends(get_channel_service))` | Reads one resource, status object, or derived view. |
| `approve_pairing(payload: dict[str, str], channels: ChannelService=Depends(get_channel_service))` | Module-level helper. Review callers and tests before changing behavior. |
| `revoke_pairing(channel: str, sender_id: str, channels: ChannelService=Depends(get_channel_service))` | Deletes a resource or clears state. |
| `dismiss_pairing(code: str, channels: ChannelService=Depends(get_channel_service))` | Module-level helper. Review callers and tests before changing behavior. |
| `list_custom_providers(db: Database=Depends(get_database))` | Lists resources or query results. |
| `save_custom_provider(provider_id: str, payload: dict[str, Any], db: Database=Depends(get_database), registry: ProviderRegistry=Depends(get_provider_registry))` | Updates or persists an existing resource. |
| `delete_custom_provider(provider_id: str, db: Database=Depends(get_database), registry: ProviderRegistry=Depends(get_provider_registry))` | Deletes a resource or clears state. |

### `pocketStudio/api/errors.py`

FastAPI route layer. Keep HTTP validation, response shaping, and exception mapping here.

| Function | Usage |
|---|---|
| `not_found(exc: KeyError)` | Module-level helper. Review callers and tests before changing behavior. |

### `pocketStudio/api/messages.py`

FastAPI route layer. Keep HTTP validation, response shaping, and exception mapping here.

| Function | Usage |
|---|---|
| `enqueue_message(payload: MessageCreate, orchestrator: Orchestrator=Depends(get_orchestrator))` | Queue, response, or message flow operation. |
| `async process_message(message_id: int, orchestrator: Orchestrator=Depends(get_orchestrator))` | Controls a background worker, scheduler, or processing flow. |
| `async process_next(orchestrator: Orchestrator=Depends(get_orchestrator))` | Controls a background worker, scheduler, or processing flow. |
| `list_queue(limit: int=Query(default=100, ge=1, le=500), status: MessageStatus \| None=None, service: QueueService=Depends(get_queue_service))` | Lists resources or query results. |
| `list_grouped_queue(limit: int=Query(default=100, ge=1, le=500), status: MessageStatus \| None=None, service: QueueService=Depends(get_queue_service))` | Lists resources or query results. |
| `get_message(message_id: int, service: QueueService=Depends(get_queue_service))` | Reads one resource, status object, or derived view. |
| `retry_message(message_id: int, service: QueueService=Depends(get_queue_service))` | Queue, response, or message flow operation. |

### `pocketStudio/api/payloads.py`

FastAPI route layer. Keep HTTP validation, response shaping, and exception mapping here.

| Function | Usage |
|---|---|
| `timestamp_millis(value: str \| int \| float \| None)` | Module-level helper. Review callers and tests before changing behavior. |
| `agent_config(agent: Agent)` | Builds API or compatibility-layer response/request payloads. |
| `team_config(team: Team)` | Builds API or compatibility-layer response/request payloads. |
| `task_payload(task: Task, comment_count: int=0)` | Builds API or compatibility-layer response/request payloads. |
| `task_response(task: Task, comment_count: int=0)` | Module-level helper. Review callers and tests before changing behavior. |
| `project_payload(project: Project, task_count: int \| None=None)` | Builds API or compatibility-layer response/request payloads. |
| `schedule_payload(schedule: Schedule)` | Builds API or compatibility-layer response/request payloads. |
| `schedule_payload_with_status(schedule: Schedule, schedules: ScheduleService)` | Builds API or compatibility-layer response/request payloads. |

### `pocketStudio/api/system.py`

FastAPI route layer. Keep HTTP validation, response shaping, and exception mapping here.

| Function | Usage |
|---|---|
| `health(settings: Settings=Depends(get_settings))` | Module-level helper. Review callers and tests before changing behavior. |
| `providers(registry: ProviderRegistry=Depends(get_provider_registry))` | Module-level helper. Review callers and tests before changing behavior. |
| `events(limit: int=Query(default=100, ge=1, le=500), since: int=Query(default=0, ge=0), service: EventService=Depends(get_event_service))` | Module-level helper. Review callers and tests before changing behavior. |
| `office_events(limit: int=Query(default=100, ge=1, le=500), since: int=Query(default=0, ge=0), service: EventService=Depends(get_event_service))` | Module-level helper. Review callers and tests before changing behavior. |
| `_sse_message(event_name: str, data: dict)` | Module-level helper. Review callers and tests before changing behavior. |
| `async event_stream(since: int=Query(default=0, ge=0), replay: bool=Query(default=True), service: EventService=Depends(get_event_service))` | Module-level helper. Review callers and tests before changing behavior. |

### `pocketStudio/api/tasks.py`

FastAPI route layer. Keep HTTP validation, response shaping, and exception mapping here.

| Function | Usage |
|---|---|
| `list_tasks(projectId: str \| None=None, status: str \| None=None, assignee: str \| None=None, q: str \| None=None, service: TaskService=Depends(get_task_service))` | Lists resources or query results. |
| `create_task(payload: TaskCreate, service: TaskService=Depends(get_task_service), projects: ProjectService=Depends(get_project_service))` | Creates a resource, installs content, or adds a relationship. |
| `get_task(task_id: int, service: TaskService=Depends(get_task_service), projects: ProjectService=Depends(get_project_service))` | Reads one resource, status object, or derived view. |
| `update_task(task_id: int, payload: dict[str, Any], service: TaskService=Depends(get_task_service), projects: ProjectService=Depends(get_project_service))` | Updates or persists an existing resource. |
| `update_task_status(task_id: int, status: str, service: TaskService=Depends(get_task_service))` | Updates or persists an existing resource. |
| `delete_task(task_id: int, service: TaskService=Depends(get_task_service))` | Deletes a resource or clears state. |

### `pocketStudio/api/teams.py`

FastAPI route layer. Keep HTTP validation, response shaping, and exception mapping here.

| Function | Usage |
|---|---|
| `list_teams(service: TeamService=Depends(get_team_service))` | Lists resources or query results. |
| `upsert_team(payload: TeamCreate, service: TeamService=Depends(get_team_service))` | Module-level helper. Review callers and tests before changing behavior. |
| `update_team(team_id: str, payload: dict, service: TeamService=Depends(get_team_service))` | Updates or persists an existing resource. |
| `get_team(team_id: str, service: TeamService=Depends(get_team_service))` | Reads one resource, status object, or derived view. |
| `add_team_member(team_id: str, agent_id: str, service: TeamService=Depends(get_team_service))` | Creates a resource, installs content, or adds a relationship. |
| `remove_team_member(team_id: str, agent_id: str, service: TeamService=Depends(get_team_service))` | Deletes a resource or clears state. |
| `set_team_leader(team_id: str, agent_id: str, service: TeamService=Depends(get_team_service))` | Updates or persists an existing resource. |
| `delete_team(team_id: str, service: TeamService=Depends(get_team_service))` | Deletes a resource or clears state. |

### `pocketStudio/api/workflows.py`

FastAPI route layer. Keep HTTP validation, response shaping, and exception mapping here.

| Function | Usage |
|---|---|
| `list_workflows(team_id: str, service: WorkflowService=Depends(get_workflow_service))` | Lists resources or query results. |
| `upsert_workflow(team_id: str, payload: TeamWorkflowCreate, service: WorkflowService=Depends(get_workflow_service))` | Module-level helper. Review callers and tests before changing behavior. |
| `validate_workflow(team_id: str, definition: WorkflowDefinition, service: WorkflowService=Depends(get_workflow_service))` | Validates input or repairs required runtime state. |
| `import_workflow(team_id: str, payload: dict[str, Any], service: WorkflowService=Depends(get_workflow_service))` | Module-level helper. Review callers and tests before changing behavior. |
| `get_workflow(team_id: str, workflow_id: str, service: WorkflowService=Depends(get_workflow_service))` | Reads one resource, status object, or derived view. |
| `export_workflow(team_id: str, workflow_id: str, service: WorkflowService=Depends(get_workflow_service))` | Module-level helper. Review callers and tests before changing behavior. |
| `update_workflow(team_id: str, workflow_id: str, payload: TeamWorkflowUpdate, service: WorkflowService=Depends(get_workflow_service))` | Updates or persists an existing resource. |
| `delete_workflow(team_id: str, workflow_id: str, service: WorkflowService=Depends(get_workflow_service))` | Deletes a resource or clears state. |

### `pocketStudio/channels/__init__.py`

External channel adapters, such as Telegram receive, pairing, and delivery logic.

### `pocketStudio/channels/telegram.py`

External channel adapters, such as Telegram receive, pairing, and delivery logic.

#### `TelegramApiError(RuntimeError)`

Class, data model, service object, or exception type.

#### `TelegramChannelService`

Class, data model, service object, or exception type.

| Method | Usage |
|---|---|
| `__init__(self, db: Database, settings: Settings, settings_service: SettingsService, channels: ChannelService, queue: QueueService, events: EventService)` | Python object lifecycle or protocol method. |
| `configured_token(self)` | Helper method for its service or type. |
| `status(self)` | Helper method for its service or type. |
| `start(self)` | Controls a background worker, scheduler, or processing flow. |
| `async stop(self)` | Controls a background worker, scheduler, or processing flow. |
| `async restart(self)` | Controls a background worker, scheduler, or processing flow. |
| `async tick(self)` | Controls a background worker, scheduler, or processing flow. |
| `poll_once(self, limit: int=20, timeout: int=0)` | Helper method for its service or type. |
| `deliver_pending(self)` | Helper method for its service or type. |
| `async _run(self)` | Runs a provider, orchestration flow, event handler, or external message handler. |
| `_handle_update(self, update: dict, token: str)` | Runs a provider, orchestration flow, event handler, or external message handler. |
| `_handle_command(self, text: str, token: str, chat_id: str, reply_to: int \| None)` | Runs a provider, orchestration flow, event handler, or external message handler. |
| `_send_response(self, token: str, response: ResponseJob)` | Helper method for its service or type. |
| `_api_call(self, token: str, method: str, payload: dict[str, Any])` | Helper method for its service or type. |
| `_send_message(self, token: str, chat_id: str, text: str, reply_to: int \| None=None)` | Helper method for its service or type. |
| `_send_chat_action(self, token: str, chat_id: str)` | Helper method for its service or type. |
| `_require_token(self)` | Helper method for its service or type. |
| `_load_offset(self)` | Helper method for its service or type. |
| `_save_offset(self, offset: int)` | Updates or persists an existing resource. |
| `_offset_path(self)` | Helper method for its service or type. |
| `_status_label(self, configured: bool)` | Helper method for its service or type. |
| `_sender_name(message: dict)` | Helper method for its service or type. |
| `_pairing_message(code: str)` | Helper method for its service or type. |
| `_split_message(text: str)` | Helper method for its service or type. |

### `pocketStudio/cli.py`

Package entry point or application entry point.

| Function | Usage |
|---|---|
| `print_json(value: Any)` | Module-level helper. Review callers and tests before changing behavior. |
| `package_version()` | Module-level helper. Review callers and tests before changing behavior. |
| `build_parser()` | Module-level helper. Review callers and tests before changing behavior. |
| `run(args: argparse.Namespace, client: ApiClient)` | Runs a provider, orchestration flow, event handler, or external message handler. |
| `run_agent(args: argparse.Namespace, client: ApiClient)` | Runs a provider, orchestration flow, event handler, or external message handler. |
| `run_settings(args: argparse.Namespace, client: ApiClient)` | Runs a provider, orchestration flow, event handler, or external message handler. |
| `run_daemon(args: argparse.Namespace, manager: DaemonManager \| None=None)` | Runs a provider, orchestration flow, event handler, or external message handler. |
| `run_team(args: argparse.Namespace, client: ApiClient)` | Runs a provider, orchestration flow, event handler, or external message handler. |
| `run_provider(args: argparse.Namespace, client: ApiClient)` | Runs a provider, orchestration flow, event handler, or external message handler. |
| `run_schedule(args: argparse.Namespace, client: ApiClient)` | Runs a provider, orchestration flow, event handler, or external message handler. |
| `run_pairing(args: argparse.Namespace, client: ApiClient)` | Runs a provider, orchestration flow, event handler, or external message handler. |
| `run_project(args: argparse.Namespace, client: ApiClient)` | Runs a provider, orchestration flow, event handler, or external message handler. |
| `run_task(args: argparse.Namespace, client: ApiClient)` | Runs a provider, orchestration flow, event handler, or external message handler. |
| `main(argv: list[str] \| None=None, client: ApiClient \| None=None)` | Module-level helper. Review callers and tests before changing behavior. |

#### `ApiClient`

Class, data model, service object, or exception type.

| Method | Usage |
|---|---|
| `__init__(self, base_url: str \| None=None)` | Python object lifecycle or protocol method. |
| `request(self, method: str, path: str, payload: dict[str, Any] \| None=None)` | Helper method for its service or type. |
| `get(self, path: str)` | Reads one resource, status object, or derived view. |
| `post(self, path: str, payload: dict[str, Any] \| None=None)` | Helper method for its service or type. |
| `put(self, path: str, payload: dict[str, Any])` | Helper method for its service or type. |
| `delete(self, path: str)` | Deletes a resource or clears state. |

#### `DaemonManager`

Class, data model, service object, or exception type.

| Method | Usage |
|---|---|
| `__init__(self, host: str=DEFAULT_HOST, port: int=DEFAULT_PORT, home: Path \| None=None)` | Python object lifecycle or protocol method. |
| `api_url(self)` | Helper method for its service or type. |
| `status(self)` | Helper method for its service or type. |
| `start(self)` | Controls a background worker, scheduler, or processing flow. |
| `stop(self)` | Controls a background worker, scheduler, or processing flow. |
| `restart(self)` | Controls a background worker, scheduler, or processing flow. |
| `open(self)` | Helper method for its service or type. |
| `_read_pid(self)` | Helper method for its service or type. |
| `_pid_alive(self, pid: int)` | Helper method for its service or type. |
| `_unlink_pid(self)` | Helper method for its service or type. |
| `_fetch_status(self)` | Helper method for its service or type. |
| `_wait_for_status(self, timeout_seconds: float=8.0)` | Helper method for its service or type. |

### `pocketStudio/core/config.py`

Core infrastructure for configuration, database access, dependency assembly, JSON file storage, and runtime helpers.

| Function | Usage |
|---|---|
| `get_settings()` | Reads one resource, status object, or derived view. |

#### `Settings(BaseSettings)`

Class, data model, service object, or exception type.

| Method | Usage |
|---|---|
| `database_path(self)` | Helper method for its service or type. |
| `settings_path(self)` | Updates or persists an existing resource. |
| `workspace_path(self)` | Helper method for its service or type. |
| `files_path(self)` | Helper method for its service or type. |
| `logs_path(self)` | Helper method for its service or type. |
| `log_file_path(self)` | Helper method for its service or type. |

### `pocketStudio/core/database.py`

Core infrastructure for configuration, database access, dependency assembly, JSON file storage, and runtime helpers.

#### `Database`

Class, data model, service object, or exception type.

| Method | Usage |
|---|---|
| `__init__(self, path: Path, journal_mode: str='MEMORY')` | Python object lifecycle or protocol method. |
| `connect(self)` | Helper method for its service or type. |
| `initialize(self)` | Helper method for its service or type. |
| `_migrate(self, conn: sqlite3.Connection)` | Helper method for its service or type. |
| `_add_column(conn: sqlite3.Connection, table: str, column: str, definition: str)` | Creates a resource, installs content, or adds a relationship. |
| `_migrate_team_mode_check(conn: sqlite3.Connection)` | Helper method for its service or type. |
| `_backfill_task_numbers(conn: sqlite3.Connection)` | Helper method for its service or type. |
| `execute(self, query: str, params: Iterable[Any]=())` | Helper method for its service or type. |
| `fetch_one(self, query: str, params: Iterable[Any]=())` | Helper method for its service or type. |
| `fetch_all(self, query: str, params: Iterable[Any]=())` | Helper method for its service or type. |

### `pocketStudio/core/dependencies.py`

Core infrastructure for configuration, database access, dependency assembly, JSON file storage, and runtime helpers.

| Function | Usage |
|---|---|
| `get_database()` | Reads one resource, status object, or derived view. |
| `get_event_service()` | Reads one resource, status object, or derived view. |
| `get_agent_service()` | Reads one resource, status object, or derived view. |
| `get_team_service()` | Reads one resource, status object, or derived view. |
| `get_workflow_service()` | Reads one resource, status object, or derived view. |
| `get_queue_service()` | Reads one resource, status object, or derived view. |
| `get_response_service()` | Reads one resource, status object, or derived view. |
| `get_plugin_service()` | Reads one resource, status object, or derived view. |
| `get_chat_service()` | Reads one resource, status object, or derived view. |
| `get_channel_service()` | Reads one resource, status object, or derived view. |
| `get_telegram_channel_service()` | Reads one resource, status object, or derived view. |
| `get_task_service()` | Reads one resource, status object, or derived view. |
| `get_project_service()` | Reads one resource, status object, or derived view. |
| `get_schedule_service()` | Reads one resource, status object, or derived view. |
| `get_settings_service()` | Reads one resource, status object, or derived view. |
| `get_heartbeat_service()` | Reads one resource, status object, or derived view. |
| `get_provider_registry()` | Reads one resource, status object, or derived view. |
| `get_orchestrator()` | Reads one resource, status object, or derived view. |
| `get_worker_service()` | Reads one resource, status object, or derived view. |

### `pocketStudio/core/ids.py`

Core infrastructure for configuration, database access, dependency assembly, JSON file storage, and runtime helpers.

| Function | Usage |
|---|---|
| `nanoid(size: int=21, alphabet: str=DEFAULT_ALPHABET)` | Module-level helper. Review callers and tests before changing behavior. |
| `prefixed_id(prefix: str, size: int=12)` | Module-level helper. Review callers and tests before changing behavior. |

### `pocketStudio/core/json_store.py`

Core infrastructure for configuration, database access, dependency assembly, JSON file storage, and runtime helpers.

| Function | Usage |
|---|---|
| `read_json_object(path: Path)` | Module-level helper. Review callers and tests before changing behavior. |
| `write_json_object(path: Path, data: dict[str, Any])` | Updates or persists an existing resource. |

### `pocketStudio/core/runtime.py`

Core infrastructure for configuration, database access, dependency assembly, JSON file storage, and runtime helpers.

| Function | Usage |
|---|---|
| `uptime_seconds()` | Module-level helper. Review callers and tests before changing behavior. |

### `pocketStudio/main.py`

Package entry point or application entry point.

| Function | Usage |
|---|---|
| `async lifespan(app: FastAPI)` | Module-level helper. Review callers and tests before changing behavior. |
| `create_app()` | Creates a resource, installs content, or adds a relationship. |

### `pocketStudio/models/__init__.py`

Project module.

### `pocketStudio/models/agent.py`

Project module.

#### `AgentCreate(BaseModel)`

Class, data model, service object, or exception type.

#### `Agent(AgentCreate)`

Class, data model, service object, or exception type.

#### `AgentMessage(BaseModel)`

Class, data model, service object, or exception type.

### `pocketStudio/models/chat.py`

Project module.

#### `ChatMessageCreate(BaseModel)`

Class, data model, service object, or exception type.

#### `ChatMessage(BaseModel)`

Class, data model, service object, or exception type.

### `pocketStudio/models/enums.py`

Project module.

#### `TeamMode(StrEnum)`

Class, data model, service object, or exception type.

#### `MessageStatus(StrEnum)`

Class, data model, service object, or exception type.

### `pocketStudio/models/event.py`

Project module.

#### `Event(BaseModel)`

Class, data model, service object, or exception type.

### `pocketStudio/models/orchestration.py`

Project module.

#### `AgentRun(BaseModel)`

Class, data model, service object, or exception type.

#### `OrchestrationResult(BaseModel)`

Class, data model, service object, or exception type.

### `pocketStudio/models/project.py`

Project module.

#### `ProjectCreate(BaseModel)`

Class, data model, service object, or exception type.

#### `Project(ProjectCreate)`

Class, data model, service object, or exception type.

### `pocketStudio/models/queue.py`

Project module.

#### `MessageCreate(BaseModel)`

Class, data model, service object, or exception type.

#### `QueueMessage(BaseModel)`

Class, data model, service object, or exception type.

#### `QueueStatus(BaseModel)`

Class, data model, service object, or exception type.

#### `ResponseJob(BaseModel)`

Class, data model, service object, or exception type.

### `pocketStudio/models/schedule.py`

Project module.

#### `ScheduleCreate(BaseModel)`

Class, data model, service object, or exception type.

#### `Schedule(BaseModel)`

Class, data model, service object, or exception type.

### `pocketStudio/models/task.py`

Project module.

#### `TaskCreate(BaseModel)`

Class, data model, service object, or exception type.

#### `Task(TaskCreate)`

Class, data model, service object, or exception type.

#### `TaskCommentCreate(BaseModel)`

Class, data model, service object, or exception type.

#### `TaskComment(TaskCommentCreate)`

Class, data model, service object, or exception type.

### `pocketStudio/models/team.py`

Project module.

#### `TeamCreate(BaseModel)`

Class, data model, service object, or exception type.

#### `Team(TeamCreate)`

Class, data model, service object, or exception type.

### `pocketStudio/models/workflow.py`

Project module.

#### `WorkflowRoutingFunction(BaseModel)`

Class, data model, service object, or exception type.

| Method | Usage |
|---|---|
| `code_must_not_be_empty(cls, value: str)` | Helper method for its service or type. |
| `entrypoint_must_not_be_empty(cls, value: str)` | Helper method for its service or type. |

#### `WorkflowNode(BaseModel)`

Class, data model, service object, or exception type.

#### `WorkflowEdge(BaseModel)`

Class, data model, service object, or exception type.

#### `WorkflowRoute(BaseModel)`

Class, data model, service object, or exception type.

#### `WorkflowConditionalEdge(BaseModel)`

Class, data model, service object, or exception type.

#### `WorkflowDefinition(BaseModel)`

Class, data model, service object, or exception type.

| Method | Usage |
|---|---|
| `supported_version(cls, value: int)` | Helper method for its service or type. |
| `validate_graph_shape(self)` | Validates input or repairs required runtime state. |

#### `TeamWorkflowCreate(BaseModel)`

Class, data model, service object, or exception type.

#### `TeamWorkflowUpdate(BaseModel)`

Class, data model, service object, or exception type.

#### `TeamWorkflow(BaseModel)`

Class, data model, service object, or exception type.

### `pocketStudio/providers/base.py`

Agent provider and CLI/Subprocess adapters that isolate external model or command execution details.

#### `ProviderRequest(BaseModel)`

Class, data model, service object, or exception type.

#### `ProviderResponse(BaseModel)`

Class, data model, service object, or exception type.

#### `AgentProvider(ABC)`

Class, data model, service object, or exception type.

| Method | Usage |
|---|---|
| `setup_workspace(self, workspace: Path)` | Updates or persists an existing resource. |
| `async run(self, request: ProviderRequest)` | Runs a provider, orchestration flow, event handler, or external message handler. |

### `pocketStudio/providers/cli_agent.py`

Agent provider and CLI/Subprocess adapters that isolate external model or command execution details.

| Function | Usage |
|---|---|
| `provider_from_command(name: str, command_line: str, registry: ProcessRegistry \| None=None, timeout_seconds: int=600)` | Module-level helper. Review callers and tests before changing behavior. |

#### `CliAgentProvider(AgentProvider)`

Class, data model, service object, or exception type.

| Method | Usage |
|---|---|
| `__init__(self, name: str, command: str, base_args: list[str] \| None=None, prompt_arg: str \| None=None, registry: ProcessRegistry \| None=None, timeout_seconds: int=600)` | Python object lifecycle or protocol method. |
| `async run(self, request: ProviderRequest)` | Runs a provider, orchestration flow, event handler, or external message handler. |
| `_args(self, request: ProviderRequest)` | Helper method for its service or type. |
| `_prompt(request: ProviderRequest)` | Helper method for its service or type. |
| `_extract_text(cls, stdout: str)` | Converts, parses, or formats internal data. |
| `_extract_event_text(line: str)` | Converts, parses, or formats internal data. |
| `is_alive(self, agent_id: str)` | Helper method for its service or type. |
| `async kill_agent(self, agent_id: str)` | Helper method for its service or type. |

#### `ClaudeProvider(CliAgentProvider)`

Class, data model, service object, or exception type.

| Method | Usage |
|---|---|
| `__init__(self, registry: ProcessRegistry \| None=None, timeout_seconds: int=600)` | Python object lifecycle or protocol method. |

#### `OpenCodeProvider(CliAgentProvider)`

Class, data model, service object, or exception type.

| Method | Usage |
|---|---|
| `__init__(self, registry: ProcessRegistry \| None=None, timeout_seconds: int=600)` | Python object lifecycle or protocol method. |

### `pocketStudio/providers/codex.py`

Agent provider and CLI/Subprocess adapters that isolate external model or command execution details.

| Function | Usage |
|---|---|
| `codex_provider_from_command(command_line: str, registry: ProcessRegistry \| None=None, timeout_seconds: int=600)` | Module-level helper. Review callers and tests before changing behavior. |
| `_split_command_line(command_line: str)` | Module-level helper. Review callers and tests before changing behavior. |

#### `CodexProvider(AgentProvider)`

Class, data model, service object, or exception type.

| Method | Usage |
|---|---|
| `__init__(self, command: str \| None=None, base_args: list[str] \| None=None, registry: ProcessRegistry \| None=None, timeout_seconds: int=600)` | Python object lifecycle or protocol method. |
| `setup_workspace(self, workspace: Path)` | Updates or persists an existing resource. |
| `async run(self, request: ProviderRequest)` | Runs a provider, orchestration flow, event handler, or external message handler. |
| `_args(self, request: ProviderRequest)` | Helper method for its service or type. |
| `_custom_args(self, request: ProviderRequest)` | Helper method for its service or type. |
| `_prompt(self, request: ProviderRequest)` | Helper method for its service or type. |
| `_extract_text(cls, stdout: str)` | Converts, parses, or formats internal data. |
| `_extract_event_text(line: str)` | Converts, parses, or formats internal data. |
| `_parse_event(line: str)` | Converts, parses, or formats internal data. |
| `_extract_event_text_from_event(event: dict \| None)` | Converts, parses, or formats internal data. |
| `_progress_payload(cls, event: dict)` | Builds API or compatibility-layer response/request payloads. |
| `_tool_name(event: dict, item: dict)` | Helper method for its service or type. |
| `_event_summary(event_type: str, item: dict, content: str, tool: str \| None)` | Helper method for its service or type. |
| `_compact_event(event: dict)` | Helper method for its service or type. |
| `is_alive(self, agent_id: str)` | Helper method for its service or type. |
| `async kill_agent(self, agent_id: str)` | Helper method for its service or type. |

### `pocketStudio/providers/local.py`

Agent provider and CLI/Subprocess adapters that isolate external model or command execution details.

#### `LocalEchoProvider(AgentProvider)`

Class, data model, service object, or exception type.

| Method | Usage |
|---|---|
| `async run(self, request: ProviderRequest)` | Runs a provider, orchestration flow, event handler, or external message handler. |

### `pocketStudio/providers/openai_compatible.py`

Agent provider and CLI/Subprocess adapters that isolate external model or command execution details.

#### `OpenAICompatibleProvider(AgentProvider)`

Class, data model, service object, or exception type.

| Method | Usage |
|---|---|
| `__init__(self, name: str='openai', base_url: str \| None=None, api_key: str \| None=None, default_model: str \| None=None)` | Python object lifecycle or protocol method. |
| `async run(self, request: ProviderRequest)` | Runs a provider, orchestration flow, event handler, or external message handler. |

### `pocketStudio/providers/registry.py`

Agent provider and CLI/Subprocess adapters that isolate external model or command execution details.

| Function | Usage |
|---|---|
| `_codex_home_diagnostics(codex_home: Path)` | Module-level helper. Review callers and tests before changing behavior. |
| `_can_write(path: Path)` | Module-level helper. Review callers and tests before changing behavior. |
| `_resolved_command_path(command: str \| None)` | Module-level helper. Review callers and tests before changing behavior. |

#### `ProviderRegistry`

Class, data model, service object, or exception type.

| Method | Usage |
|---|---|
| `__init__(self, db: Database \| None=None)` | Python object lifecycle or protocol method. |
| `register(self, provider: AgentProvider)` | Helper method for its service or type. |
| `reload_custom(self)` | Helper method for its service or type. |
| `get(self, name: str)` | Reads one resource, status object, or derived view. |
| `list_names(self)` | Lists resources or query results. |
| `async kill_agent(self, agent_id: str)` | Helper method for its service or type. |
| `agent_process_alive(self, agent_id: str)` | Helper method for its service or type. |
| `active_processes(self)` | Helper method for its service or type. |
| `diagnostics(self)` | Helper method for its service or type. |

### `pocketStudio/providers/subprocess.py`

Agent provider and CLI/Subprocess adapters that isolate external model or command execution details.

| Function | Usage |
|---|---|
| `async _empty_bytes()` | Module-level helper. Review callers and tests before changing behavior. |
| `_should_fallback_to_windows_powershell(exc: OSError)` | Module-level helper. Review callers and tests before changing behavior. |
| `_should_fallback_to_windows_sync_subprocess(exc: OSError)` | Module-level helper. Review callers and tests before changing behavior. |
| `_windows_powershell()` | Module-level helper. Review callers and tests before changing behavior. |
| `_resolved_command(command: str)` | Module-level helper. Review callers and tests before changing behavior. |
| `_powershell_command(command: Sequence[str], pipe_stdin: bool=False)` | Module-level helper. Review callers and tests before changing behavior. |

#### `SubprocessResult`

Class, data model, service object, or exception type.

#### `ProcessRegistry`

Class, data model, service object, or exception type.

| Method | Usage |
|---|---|
| `register(self, key: str, process: asyncio.subprocess.Process, metadata: dict \| None=None)` | Helper method for its service or type. |
| `unregister(self, key: str, process: asyncio.subprocess.Process)` | Helper method for its service or type. |
| `is_alive(self, key: str)` | Helper method for its service or type. |
| `snapshot(self)` | Helper method for its service or type. |
| `async kill(self, key: str)` | Helper method for its service or type. |

#### `SubprocessHarness`

Class, data model, service object, or exception type.

| Method | Usage |
|---|---|
| `__init__(self, command: str, registry: ProcessRegistry \| None=None, timeout_seconds: int=600)` | Python object lifecycle or protocol method. |
| `async run(self, args: Sequence[str], process_key: str, cwd: Path \| str \| None=None, env: dict[str, str] \| None=None, on_stdout_line: Callable[[str], None] \| None=None, on_stderr_line: Callable[[str], None] \| None=None, stdin_text: str \| None=None)` | Runs a provider, orchestration flow, event handler, or external message handler. |
| `async _run_windows_powershell(self, command: str, args: Sequence[str], cwd: Path \| str \| None, env: dict[str, str], stdin_text: str \| None)` | Runs a provider, orchestration flow, event handler, or external message handler. |
| `async _run_windows_powershell_sync(self, command: str, args: Sequence[str], cwd: Path \| str \| None, env: dict[str, str], on_stdout_line: Callable[[str], None] \| None, on_stderr_line: Callable[[str], None] \| None, stdin_text: str \| None)` | Runs a provider, orchestration flow, event handler, or external message handler. |
| `async _communicate(process: asyncio.subprocess.Process, on_stdout_line: Callable[[str], None] \| None, on_stderr_line: Callable[[str], None] \| None, stdin_text: str \| None=None)` | Helper method for its service or type. |

### `pocketStudio/services/agent_service.py`

Domain service layer for agents, teams, queues, projects, tasks, schedules, and related logic.

#### `AgentService`

Class, data model, service object, or exception type.

| Method | Usage |
|---|---|
| `__init__(self, db: Database, settings: Settings)` | Python object lifecycle or protocol method. |
| `create(self, payload: AgentCreate)` | Creates a resource, installs content, or adds a relationship. |
| `get(self, agent_id: str)` | Reads one resource, status object, or derived view. |
| `list(self)` | Lists resources or query results. |
| `delete(self, agent_id: str)` | Deletes a resource or clears state. |
| `ensure_workspace(self, workspace: Path, payload: AgentCreate \| None=None)` | Validates input or repairs required runtime state. |
| `workspace_status(self, agent_id: str, repair: bool=False)` | Helper method for its service or type. |
| `get_system_prompt_file(self, agent_id: str)` | Reads one resource, status object, or derived view. |
| `save_system_prompt_file(self, agent_id: str, content: str)` | Updates or persists an existing resource. |
| `get_heartbeat_file(self, agent_id: str)` | Reads one resource, status object, or derived view. |
| `save_heartbeat_file(self, agent_id: str, content: str \| None=None, enabled: bool \| None=None, interval: int \| None=None)` | Updates or persists an existing resource. |
| `build_system_prompt(self, agent_id: str, teammates: str='')` | Helper method for its service or type. |
| `load_memory_index(self, agent_id: str)` | Helper method for its service or type. |
| `list_memory_files(self, agent_id: str)` | Lists resources or query results. |
| `get_memory_file(self, agent_id: str, relative_path: str)` | Reads one resource, status object, or derived view. |
| `save_memory_file(self, agent_id: str, relative_path: str, content: str, create_dirs: bool=True)` | Updates or persists an existing resource. |
| `delete_memory_file(self, agent_id: str, relative_path: str)` | Deletes a resource or clears state. |
| `list_skills(self, agent_id: str)` | Lists resources or query results. |
| `install_skill_placeholder(self, agent_id: str, ref: str)` | Creates a resource, installs content, or adds a relationship. |
| `scan_memory_tree(cls, dir_path: Path, relative_path: str)` | Helper method for its service or type. |
| `_format_memory_tree(cls, folder: dict, indent: int=0)` | Converts, parses, or formats internal data. |
| `ensure_tool_skills_link(source: Path, target: Path)` | Validates input or repairs required runtime state. |
| `_sync_skill_tree(source: Path, target: Path)` | Helper method for its service or type. |
| `_sync_root_skills(self, target: Path)` | Helper method for its service or type. |
| `_root_skills_dir()` | Helper method for its service or type. |
| `_workspace_checks(workspace: Path)` | Helper method for its service or type. |
| `_safe_name(value: str)` | Helper method for its service or type. |
| `_resolve_memory_path(memory_dir: Path, relative_path: str)` | Helper method for its service or type. |
| `_parse_frontmatter(content: str)` | Converts, parses, or formats internal data. |
| `_default_heartbeat_interval(self)` | Helper method for its service or type. |
| `_sync_agent_settings(self, agent: Agent)` | Helper method for its service or type. |
| `_remove_agent_settings(self, agent_id: str)` | Deletes a resource or clears state. |
| `_to_agent(row)` | Converts, parses, or formats internal data. |

### `pocketStudio/services/channel_service.py`

Domain service layer for agents, teams, queues, projects, tasks, schedules, and related logic.

#### `PairingResult`

Class, data model, service object, or exception type.

#### `RoutedChannelMessage`

Class, data model, service object, or exception type.

#### `ChannelService`

Class, data model, service object, or exception type.

| Method | Usage |
|---|---|
| `__init__(self, db: Database, agents: AgentService, teams: TeamService)` | Python object lifecycle or protocol method. |
| `pairing_state(self)` | Helper method for its service or type. |
| `ensure_sender_paired(self, channel: str, sender_id: str, sender: str)` | Validates input or repairs required runtime state. |
| `approve(self, code: str \| None)` | Helper method for its service or type. |
| `revoke(self, channel: str, sender_id: str)` | Deletes a resource or clears state. |
| `dismiss_pending(self, code: str)` | Helper method for its service or type. |
| `route_message(self, channel: str, sender_id: str, text: str, explicit_agent: str \| None=None)` | Helper method for its service or type. |
| `resolve_target(self, tag: str)` | Helper method for its service or type. |
| `get_default(self, channel: str, sender_id: str)` | Reads one resource, status object, or derived view. |
| `save_default(self, channel: str, sender_id: str, target: str)` | Updates or persists an existing resource. |
| `clear_default(self, channel: str, sender_id: str)` | Deletes a resource or clears state. |
| `_unique_pairing_code(self)` | Helper method for its service or type. |

### `pocketStudio/services/chat_service.py`

Domain service layer for agents, teams, queues, projects, tasks, schedules, and related logic.

#### `ChatService`

Class, data model, service object, or exception type.

| Method | Usage |
|---|---|
| `__init__(self, db: Database, events: EventService)` | Python object lifecycle or protocol method. |
| `post(self, team_id: str, payload: ChatMessageCreate)` | Helper method for its service or type. |
| `get(self, message_id: int)` | Reads one resource, status object, or derived view. |
| `list(self, team_id: str, limit: int=100, since: int=0, sender: str \| None=None, query: str \| None=None)` | Lists resources or query results. |
| `archives(self)` | Helper method for its service or type. |
| `prune(self, older_than_ms: int)` | Queue, response, or message flow operation. |
| `_to_message(row)` | Converts, parses, or formats internal data. |

### `pocketStudio/services/event_service.py`

Domain service layer for agents, teams, queues, projects, tasks, schedules, and related logic.

#### `EventService`

Class, data model, service object, or exception type.

| Method | Usage |
|---|---|
| `__init__(self, db: Database, settings: Settings \| None=None)` | Python object lifecycle or protocol method. |
| `emit(self, event_type: str, payload: dict)` | Runs a provider, orchestration flow, event handler, or external message handler. |
| `add_listener(self, listener: Callable[[Event], None])` | Creates a resource, installs content, or adds a relationship. |
| `remove_listener(self, listener: Callable[[Event], None])` | Deletes a resource or clears state. |
| `list(self, limit: int=100, since: int=0)` | Lists resources or query results. |
| `log_lines(self, limit: int=100)` | Helper method for its service or type. |
| `log_records(self, limit: int=100, event_type: str \| None=None, contains: str \| None=None)` | Helper method for its service or type. |
| `office_event(self, event: Event)` | Helper method for its service or type. |
| `_office_base(event: Event, payload: dict, timestamp: int)` | Helper method for its service or type. |
| `_str_payload(payload: dict, *keys: str)` | Builds API or compatibility-layer response/request payloads. |
| `_agent_progress_type(payload: dict)` | Helper method for its service or type. |
| `_append_log(self, event_type: str, payload_json: str, created_at: str \| None=None)` | Helper method for its service or type. |
| `_notify(self, event: Event)` | Helper method for its service or type. |
| `_parse_log_line(line: str)` | Converts, parses, or formats internal data. |
| `_event_timestamp_ms(value: str)` | Helper method for its service or type. |
| `_to_event(row)` | Converts, parses, or formats internal data. |

### `pocketStudio/services/heartbeat_service.py`

Domain service layer for agents, teams, queues, projects, tasks, schedules, and related logic.

#### `HeartbeatService`

Class, data model, service object, or exception type.

| Method | Usage |
|---|---|
| `__init__(self, db: Database, agents: AgentService, events: EventService, settings: Settings)` | Python object lifecycle or protocol method. |
| `fire_due(self, queue: QueueService, now_ms: int \| None=None)` | Controls a background worker, scheduler, or processing flow. |
| `tick(self, queue: QueueService, now_ms: int \| None=None, agent_id: str \| None=None, force: bool=False)` | Controls a background worker, scheduler, or processing flow. |
| `clear_state(self, agent_id: str \| None=None)` | Deletes a resource or clears state. |
| `snapshot(self, now_ms: int \| None=None)` | Helper method for its service or type. |
| `base_interval_seconds(self)` | Helper method for its service or type. |
| `_is_due(self, agent, now_ms: int)` | Helper method for its service or type. |
| `_fire_agent(self, queue: QueueService, agent, now_ms: int)` | Controls a background worker, scheduler, or processing flow. |
| `_read_prompt(workspace: Path)` | Helper method for its service or type. |

### `pocketStudio/services/orchestrator.py`

Domain service layer for agents, teams, queues, projects, tasks, schedules, and related logic.

| Function | Usage |
|---|---|
| `merge_dicts(left: dict[str, Any], right: dict[str, Any])` | Module-level helper. Review callers and tests before changing behavior. |

#### `TeamActions`

Class, data model, service object, or exception type.

| Method | Usage |
|---|---|
| `__init__(self, mentions: list[tuple[str, str]], chatrooms: list[tuple[str, str]])` | Python object lifecycle or protocol method. |

#### `WorkflowState(TypedDict)`

Class, data model, service object, or exception type.

#### `Orchestrator`

Class, data model, service object, or exception type.

| Method | Usage |
|---|---|
| `__init__(self, agents: AgentService, teams: TeamService, queue: QueueService, chat: ChatService, events: EventService, providers: ProviderRegistry, projects: ProjectService \| None=None, workflows: WorkflowService \| None=None)` | Python object lifecycle or protocol method. |
| `enqueue(self, payload: MessageCreate)` | Queue, response, or message flow operation. |
| `async process_one(self, newest: bool=False)` | Controls a background worker, scheduler, or processing flow. |
| `async process_message(self, message_id: int)` | Controls a background worker, scheduler, or processing flow. |
| `async _dispatch(self, message: QueueMessage)` | Runs a provider, orchestration flow, event handler, or external message handler. |
| `async _run_team(self, message: QueueMessage, team: Team)` | Runs a provider, orchestration flow, event handler, or external message handler. |
| `async _run_workflow(self, message: QueueMessage, team: Team, agents: list[Agent], workflow)` | Runs a provider, orchestration flow, event handler, or external message handler. |
| `_workflow_node_input(team: Team, workflow_id: str, original_request: str, node, predecessor_ids: list[str], outputs: dict[str, str])` | Helper method for its service or type. |
| `_langchain_runnable_for_agent(self, agent: Agent)` | Helper method for its service or type. |
| `_build_langgraph_workflow(self, *, team: Team, workflow_id: str, message: QueueMessage, agents: list[Agent], node_by_id: dict[str, Any], agent_by_id: dict[str, Agent], predecessors: dict[str, list[str]], outgoing: dict[str, list[str]], edge_pairs: list[tuple[str, str]], conditional_edges: list[Any], entrypoint: str)` | Helper method for its service or type. |
| `_compile_workflow_routing_function(node)` | Helper method for its service or type. |
| `_route_from_output(output: str, conditions: list[str])` | Helper method for its service or type. |
| `async _run_iterative_rounds(self, team: Team, message: QueueMessage, agents: list[Agent], seed_runs: list[AgentRun], max_rounds: int)` | Runs a provider, orchestration flow, event handler, or external message handler. |
| `_agent_lookup(agents: list[Agent])` | Helper method for its service or type. |
| `_mentions_from_runs(self, team: Team, runs: list[AgentRun], agents: list[Agent])` | Helper method for its service or type. |
| `_member_chain_input(self, team: Team, original_request: str, leader_run: AgentRun, previous_member_runs: list[AgentRun], member_id: str)` | Helper method for its service or type. |
| `_leader_summary_input(self, team: Team, original_request: str, leader_run: AgentRun, member_runs: list[AgentRun])` | Helper method for its service or type. |
| `_format_runs(runs: list[AgentRun])` | Converts, parses, or formats internal data. |
| `async _handle_team_tags(self, team: Team, run: AgentRun, message: QueueMessage, agents: list[Agent], enqueue_mentions: bool=True, process_chatrooms: bool=True)` | Runs a provider, orchestration flow, event handler, or external message handler. |
| `async _handle_direct_agent_team_tags(self, agent: Agent, run: AgentRun, message: QueueMessage)` | Runs a provider, orchestration flow, event handler, or external message handler. |
| `_broadcast_chatroom(self, team: Team, from_agent: str, content: str, agents: list[Agent], parent: QueueMessage)` | Runs a provider, orchestration flow, event handler, or external message handler. |
| `_post_chatroom_run_outputs(self, team: Team, runs: list[AgentRun])` | Helper method for its service or type. |
| `_is_chatroom_origin(message: QueueMessage)` | Helper method for its service or type. |
| `_team_child_metadata(parent: QueueMessage \| None, *, team: Team, from_agent: str, kind: str, to_agent: str)` | Helper method for its service or type. |
| `_order_agents_for_team(team: Team, agents: list[Agent])` | Helper method for its service or type. |
| `_teams_for_agent(self, agent_id: str)` | Helper method for its service or type. |
| `_resolve_team_context_for_agent(agent_id: str, teams: list[Team])` | Helper method for its service or type. |
| `_resolve_team_for_tag(team_id: str, teams: list[Team], agent_id: str)` | Helper method for its service or type. |
| `async _run_agent(self, agent: Agent, input_text: str, context: list[str], *, message_id: int \| str \| None=None, session_id: str \| None=None, run_id: str \| None=None)` | Runs a provider, orchestration flow, event handler, or external message handler. |
| `_agent_for_message(self, agent_id: str, message: QueueMessage)` | Helper method for its service or type. |
| `_parse_target(target: str)` | Converts, parses, or formats internal data. |
| `decode_result(message: QueueMessage)` | Converts, parses, or formats internal data. |

### `pocketStudio/services/plugin_service.py`

Domain service layer for agents, teams, queues, projects, tasks, schedules, and related logic.

#### `HookResult`

Class, data model, service object, or exception type.

#### `LoadedPlugin`

Class, data model, service object, or exception type.

#### `PluginContext`

Class, data model, service object, or exception type.

| Method | Usage |
|---|---|
| `__init__(self, name: str, home: Path, events: EventService)` | Python object lifecycle or protocol method. |
| `on(self, event_type: str, handler: Callable[[dict[str, Any]], None])` | Helper method for its service or type. |
| `log(self, level: str, message: str)` | Helper method for its service or type. |
| `get_pocketstudio_home(self)` | Reads one resource, status object, or derived view. |

#### `PluginService`

Class, data model, service object, or exception type.

| Method | Usage |
|---|---|
| `__init__(self, settings: Settings, events: EventService)` | Python object lifecycle or protocol method. |
| `plugins_path(self)` | Helper method for its service or type. |
| `list_plugins(self, reload: bool=False)` | Lists resources or query results. |
| `load_plugins(self, reload: bool=False)` | Helper method for its service or type. |
| `run_incoming_hooks(self, message: str, context: dict[str, Any])` | Runs a provider, orchestration flow, event handler, or external message handler. |
| `run_outgoing_hooks(self, message: str, context: dict[str, Any])` | Runs a provider, orchestration flow, event handler, or external message handler. |
| `broadcast_event(self, event_type: str, payload: dict[str, Any])` | Runs a provider, orchestration flow, event handler, or external message handler. |
| `handle_event(self, event: Event)` | Runs a provider, orchestration flow, event handler, or external message handler. |
| `_run_hook(self, hook_name: str, message: str, context: dict[str, Any])` | Runs a provider, orchestration flow, event handler, or external message handler. |
| `_apply_hook(message: str, hook: dict[str, Any], context: dict[str, Any])` | Helper method for its service or type. |
| `_load_module(self, plugin_dir: Path, module_path: Path)` | Helper method for its service or type. |
| `_activate(self, plugin: LoadedPlugin)` | Helper method for its service or type. |
| `_module_hooks(module: ModuleType \| None)` | Helper method for its service or type. |
| `_apply_callable_hook(message: str, hook: Callable[[str, dict[str, Any]], Any], context: dict[str, Any])` | Helper method for its service or type. |
| `_mark_plugin(metadata: dict[str, Any], plugin_name: str)` | Helper method for its service or type. |

### `pocketStudio/services/project_service.py`

Domain service layer for agents, teams, queues, projects, tasks, schedules, and related logic.

#### `ProjectService`

Class, data model, service object, or exception type.

| Method | Usage |
|---|---|
| `__init__(self, db: Database, events: EventService)` | Python object lifecycle or protocol method. |
| `list_projects(self)` | Lists resources or query results. |
| `create_project(self, payload: ProjectCreate)` | Creates a resource, installs content, or adds a relationship. |
| `get_project(self, project_id: str)` | Reads one resource, status object, or derived view. |
| `update_project(self, project_id: str, payload: ProjectCreate)` | Updates or persists an existing resource. |
| `project_agent_workspace(self, project_id: str, agent_id: str)` | Helper method for its service or type. |
| `workspace_status(self, project_id: str, repair: bool=False)` | Helper method for its service or type. |
| `ensure_working_directory(path: Path)` | Validates input or repairs required runtime state. |
| `_workspace_checks(workspace: Path)` | Helper method for its service or type. |
| `delete_project(self, project_id: str)` | Deletes a resource or clears state. |
| `task_count(self, project_id: str)` | Helper method for its service or type. |
| `comment_count(self, task_id: int)` | Helper method for its service or type. |
| `list_comments(self, task_id: int)` | Lists resources or query results. |
| `create_comment(self, task_id: int, payload: TaskCommentCreate)` | Creates a resource, installs content, or adds a relationship. |
| `delete_comment(self, comment_id: str)` | Deletes a resource or clears state. |
| `_project_id(name: str)` | Helper method for its service or type. |
| `_workspace_path(workspace: str \| None)` | Helper method for its service or type. |
| `generate_prefix(name: str)` | Helper method for its service or type. |
| `_next_global_task_number(self)` | Helper method for its service or type. |
| `_to_project(row)` | Converts, parses, or formats internal data. |
| `_legacy_default_workspace(project_id: str)` | Helper method for its service or type. |
| `_to_comment(row)` | Converts, parses, or formats internal data. |

### `pocketStudio/services/queue_service.py`

Domain service layer for agents, teams, queues, projects, tasks, schedules, and related logic.

#### `QueueService`

Class, data model, service object, or exception type.

| Method | Usage |
|---|---|
| `__init__(self, db: Database, events: EventService, settings: Settings, responses: ResponseService \| None=None, plugins: PluginService \| None=None)` | Python object lifecycle or protocol method. |
| `enqueue(self, payload: MessageCreate)` | Queue, response, or message flow operation. |
| `get(self, message_id: int)` | Reads one resource, status object, or derived view. |
| `list(self, limit: int=100, status: MessageStatus \| None=None)` | Lists resources or query results. |
| `find_by_client_message_id(self, client_message_id: str, limit: int=1000)` | Helper method for its service or type. |
| `grouped_chatroom_messages(self, limit: int=100, status: MessageStatus \| None=None)` | Helper method for its service or type. |
| `status(self)` | Helper method for its service or type. |
| `diagnostics(self, stale_threshold_seconds: int \| None=None)` | Helper method for its service or type. |
| `agent_status(self)` | Helper method for its service or type. |
| `next_queued(self, newest: bool=False)` | Helper method for its service or type. |
| `recover_stale_messages(self, threshold_seconds: int \| None=None)` | Queue, response, or message flow operation. |
| `mark_running(self, message_id: int)` | Helper method for its service or type. |
| `mark_done(self, message_id: int, result: str)` | Helper method for its service or type. |
| `mark_failed(self, message_id: int, error: str)` | Helper method for its service or type. |
| `list_dead(self, limit: int=100)` | Lists resources or query results. |
| `dead_payloads(self, limit: int=100)` | Builds API or compatibility-layer response/request payloads. |
| `retry_dead(self, message_id: int)` | Queue, response, or message flow operation. |
| `retry_message(self, message_id: int)` | Queue, response, or message flow operation. |
| `delete_dead(self, message_id: int)` | Deletes a resource or clears state. |
| `insert_agent_message(self, agent_id: str, role: str, content: str, message_id: str, sender: str='', channel: str='web', created_at: int \| None=None)` | Helper method for its service or type. |
| `get_agent_messages(self, agent_id: str, limit: int=100, since_id: int=0)` | Reads one resource, status object, or derived view. |
| `get_all_agent_messages(self, limit: int=100, since_id: int=0)` | Reads one resource, status object, or derived view. |
| `reset_agent(self, agent_id: str)` | Helper method for its service or type. |
| `recent_responses(self, limit: int=20)` | Helper method for its service or type. |
| `enqueue_response(self, message_id: str, channel: str, sender: str, message: str, original_message: str, agent: str \| None=None, sender_id: str \| None=None, files: list[str] \| None=None, metadata: dict \| None=None)` | Queue, response, or message flow operation. |
| `get_responses_for_channel(self, channel: str)` | Reads one resource, status object, or derived view. |
| `ack_response(self, response_id: int)` | Queue, response, or message flow operation. |
| `prune_acked_responses(self, older_than_ms: int=86400000)` | Queue, response, or message flow operation. |
| `prune_completed_messages(self, older_than_ms: int=86400000)` | Queue, response, or message flow operation. |
| `enqueue_responses_from_message(self, message: QueueMessage)` | Queue, response, or message flow operation. |
| `processing_payloads(self)` | Controls a background worker, scheduler, or processing flow. |
| `_dead_payload(message: QueueMessage)` | Builds API or compatibility-layer response/request payloads. |
| `_target_label(target: str)` | Helper method for its service or type. |
| `_is_chatroom_message(message: QueueMessage)` | Helper method for its service or type. |
| `_combined_chatroom_payload(messages: list[QueueMessage])` | Builds API or compatibility-layer response/request payloads. |
| `_pending_response_count(self)` | Helper method for its service or type. |
| `_message_summary(row)` | Helper method for its service or type. |
| `_timestamp_ms(value: str)` | Helper method for its service or type. |
| `_to_message(row)` | Converts, parses, or formats internal data. |
| `_to_agent_message(row)` | Converts, parses, or formats internal data. |
| `_to_response(row)` | Converts, parses, or formats internal data. |
| `_response_api_payload(response: ResponseJob)` | Builds API or compatibility-layer response/request payloads. |
| `_prepare_team_response_text(run: dict)` | Helper method for its service or type. |

### `pocketStudio/services/response_service.py`

Domain service layer for agents, teams, queues, projects, tasks, schedules, and related logic.

#### `PreparedResponse`

Class, data model, service object, or exception type.

#### `ResponseService`

Class, data model, service object, or exception type.

| Method | Usage |
|---|---|
| `__init__(self, settings: Settings, plugins: PluginService \| None=None)` | Python object lifecycle or protocol method. |
| `prepare(self, response: str, existing_files: list[str] \| None=None, context: dict \| None=None)` | Helper method for its service or type. |
| `collect_files(response: str)` | Helper method for its service or type. |
| `_save_long_response(self, response: str)` | Updates or persists an existing resource. |

### `pocketStudio/services/schedule_service.py`

Domain service layer for agents, teams, queues, projects, tasks, schedules, and related logic.

#### `ScheduleService`

Class, data model, service object, or exception type.

| Method | Usage |
|---|---|
| `__init__(self, db: Database, events: EventService)` | Python object lifecycle or protocol method. |
| `list(self, agent_id: str \| None=None)` | Lists resources or query results. |
| `schedule_status(self, schedule: Schedule, now: datetime \| None=None)` | Helper method for its service or type. |
| `next_fire_at(self, schedule: Schedule, now: datetime \| None=None)` | Helper method for its service or type. |
| `create(self, payload: ScheduleCreate)` | Creates a resource, installs content, or adds a relationship. |
| `get(self, schedule_id: str)` | Reads one resource, status object, or derived view. |
| `update(self, schedule_id: str, payload: ScheduleCreate)` | Updates or persists an existing resource. |
| `delete(self, schedule_id: str)` | Deletes a resource or clears state. |
| `validate(self, payload: ScheduleCreate, now: datetime \| None=None)` | Validates input or repairs required runtime state. |
| `fire(self, schedule_id: str, queue: QueueService, now: datetime \| None=None, force: bool=False)` | Controls a background worker, scheduler, or processing flow. |
| `fire_due(self, queue: QueueService, now: datetime \| None=None)` | Controls a background worker, scheduler, or processing flow. |
| `_fire(self, queue: QueueService, schedule: Schedule, now: datetime)` | Controls a background worker, scheduler, or processing flow. |
| `_validate_payload(self, payload: ScheduleCreate)` | Validates input or repairs required runtime state. |
| `_ensure_label_available(self, label: str, exclude_id: str \| None=None)` | Validates input or repairs required runtime state. |
| `_find_row(self, identifier: str)` | Helper method for its service or type. |
| `_parse_datetime(value: str)` | Converts, parses, or formats internal data. |
| `_cron_matches(expression: str, now: datetime)` | Helper method for its service or type. |
| `_field_matches(field: str, value: int, minimum: int, maximum: int)` | Helper method for its service or type. |
| `_field_is_valid(field: str, minimum: int, maximum: int)` | Helper method for its service or type. |
| `_range(value: str)` | Helper method for its service or type. |
| `_epoch_ms(value: datetime)` | Helper method for its service or type. |
| `_to_schedule(row)` | Converts, parses, or formats internal data. |

### `pocketStudio/services/settings_service.py`

Domain service layer for agents, teams, queues, projects, tasks, schedules, and related logic.

#### `SettingsValidationError(ValueError)`

Class, data model, service object, or exception type.

#### `SettingsService`

Class, data model, service object, or exception type.

| Method | Usage |
|---|---|
| `__init__(self, db: Database, settings: Settings)` | Python object lifecycle or protocol method. |
| `snapshot(self)` | Helper method for its service or type. |
| `update(self, payload: dict[str, Any])` | Updates or persists an existing resource. |
| `preview_update(self, payload: dict[str, Any])` | Helper method for its service or type. |
| `validate(self, payload: dict[str, Any])` | Validates input or repairs required runtime state. |
| `_validate_object(payload: dict[str, Any], key: str)` | Validates input or repairs required runtime state. |
| `_validate_mapping(payload: dict[str, Any], key: str)` | Validates input or repairs required runtime state. |
| `write(self, settings: dict[str, Any])` | Updates or persists an existing resource. |
| `_file_settings(self)` | Helper method for its service or type. |
| `_legacy_db_settings(self)` | Helper method for its service or type. |
| `ensure_setup_dirs(self, settings: dict[str, Any])` | Validates input or repairs required runtime state. |
| `backup_info(self)` | Helper method for its service or type. |
| `restore_backup(self)` | Helper method for its service or type. |
| `backup_path(self)` | Helper method for its service or type. |
| `_backup_current_settings(self)` | Helper method for its service or type. |
| `_merge(cls, current: Any, update: Any)` | Helper method for its service or type. |
| `_normalize_paths(cls, payload: dict[str, Any])` | Converts, parses, or formats internal data. |
| `_expand_home_path(value: str)` | Helper method for its service or type. |
| `_known_sections(settings: dict[str, Any])` | Helper method for its service or type. |
| `_diff(cls, current: Any, next_value: Any, prefix: str='')` | Helper method for its service or type. |
| `_repair_json(raw: str)` | Validates input or repairs required runtime state. |

### `pocketStudio/services/task_service.py`

Domain service layer for agents, teams, queues, projects, tasks, schedules, and related logic.

#### `TaskService`

Class, data model, service object, or exception type.

| Method | Usage |
|---|---|
| `__init__(self, db: Database, events: EventService)` | Python object lifecycle or protocol method. |
| `create(self, payload: TaskCreate)` | Creates a resource, installs content, or adds a relationship. |
| `get(self, task_id: int)` | Reads one resource, status object, or derived view. |
| `list(self, project_id: str \| None=None, status: str \| None=None, assignee: str \| None=None, query: str \| None=None)` | Lists resources or query results. |
| `update(self, task_id: int, payload: TaskCreate)` | Updates or persists an existing resource. |
| `update_status(self, task_id: int, status: str)` | Updates or persists an existing resource. |
| `reorder(self, columns: dict[str, list[str]])` | Helper method for its service or type. |
| `delete(self, task_id: int)` | Deletes a resource or clears state. |
| `_to_task(row)` | Converts, parses, or formats internal data. |
| `_next_number(self, project_id: str \| None)` | Helper method for its service or type. |
| `_next_position(self, status: str)` | Helper method for its service or type. |

### `pocketStudio/services/team_routing.py`

Domain service layer for agents, teams, queues, projects, tasks, schedules, and related logic.

| Function | Usage |
|---|---|
| `extract_bracket_tags(text: str, prefix: str)` | Converts, parses, or formats internal data. |
| `strip_bracket_tags(text: str, prefix: str)` | Converts, parses, or formats internal data. |
| `convert_tags_to_readable(text: str, from_agent: str \| None=None)` | Converts, parses, or formats internal data. |
| `_convert_prefix_tags(text: str, prefix: str, readable_prefix: str)` | Converts, parses, or formats internal data. |

#### `BracketTag`

Class, data model, service object, or exception type.

### `pocketStudio/services/team_service.py`

Domain service layer for agents, teams, queues, projects, tasks, schedules, and related logic.

#### `TeamService`

Class, data model, service object, or exception type.

| Method | Usage |
|---|---|
| `__init__(self, db: Database, settings: Settings \| None=None)` | Python object lifecycle or protocol method. |
| `create(self, payload: TeamCreate)` | Creates a resource, installs content, or adds a relationship. |
| `get(self, team_id: str)` | Reads one resource, status object, or derived view. |
| `list(self)` | Lists resources or query results. |
| `delete(self, team_id: str)` | Deletes a resource or clears state. |
| `add_member(self, team_id: str, agent_id: str)` | Creates a resource, installs content, or adds a relationship. |
| `remove_member(self, team_id: str, agent_id: str)` | Deletes a resource or clears state. |
| `set_leader(self, team_id: str, agent_id: str)` | Updates or persists an existing resource. |
| `_sync_team_settings(self, team: Team)` | Helper method for its service or type. |
| `_remove_team_settings(self, team_id: str)` | Deletes a resource or clears state. |
| `_to_team(row)` | Converts, parses, or formats internal data. |

### `pocketStudio/services/worker_service.py`

Domain service layer for agents, teams, queues, projects, tasks, schedules, and related logic.

#### `WorkerState`

Class, data model, service object, or exception type.

#### `WorkerService`

Class, data model, service object, or exception type.

| Method | Usage |
|---|---|
| `__init__(self, orchestrator: Orchestrator, schedules: ScheduleService, heartbeat: HeartbeatService, events: EventService, settings: Settings)` | Python object lifecycle or protocol method. |
| `start(self)` | Controls a background worker, scheduler, or processing flow. |
| `async stop(self)` | Controls a background worker, scheduler, or processing flow. |
| `pause(self)` | Controls a background worker, scheduler, or processing flow. |
| `resume(self)` | Controls a background worker, scheduler, or processing flow. |
| `async restart(self)` | Controls a background worker, scheduler, or processing flow. |
| `async process_once(self, force: bool=False)` | Controls a background worker, scheduler, or processing flow. |
| `snapshot(self)` | Helper method for its service or type. |
| `maintenance(self, older_than_ms: int=86400000, stale_threshold_seconds: int \| None=None, prune_chats: bool=False)` | Helper method for its service or type. |
| `_health(self, queue_status: dict)` | Helper method for its service or type. |
| `async _process_fired_messages(self, messages: list[QueueMessage])` | Controls a background worker, scheduler, or processing flow. |
| `async _process_next_available(self, newest: bool=False)` | Controls a background worker, scheduler, or processing flow. |
| `_record_failure(self, exc: Exception)` | Helper method for its service or type. |
| `async _run(self)` | Runs a provider, orchestration flow, event handler, or external message handler. |

### `pocketStudio/services/workflow_service.py`

Domain service layer for agents, teams, queues, projects, tasks, schedules, and related logic.

#### `WorkflowService`

Class, data model, service object, or exception type.

| Method | Usage |
|---|---|
| `__init__(self, db: Database, teams: TeamService)` | Python object lifecycle or protocol method. |
| `create(self, team_id: str, payload: TeamWorkflowCreate)` | Creates a resource, installs content, or adds a relationship. |
| `list(self, team_id: str)` | Lists resources or query results. |
| `get(self, team_id: str, workflow_id: str)` | Reads one resource, status object, or derived view. |
| `active_for_team(self, team_id: str)` | Helper method for its service or type. |
| `update(self, team_id: str, workflow_id: str, payload: TeamWorkflowUpdate)` | Updates or persists an existing resource. |
| `delete(self, team_id: str, workflow_id: str)` | Deletes a resource or clears state. |
| `export_json(self, team_id: str, workflow_id: str)` | Helper method for its service or type. |
| `import_json(self, team_id: str, payload: dict[str, Any])` | Helper method for its service or type. |
| `validate(self, team_id: str, definition: WorkflowDefinition)` | Validates input or repairs required runtime state. |
| `_payload_from_import_json(payload: dict[str, Any])` | Builds API or compatibility-layer response/request payloads. |
| `_validate_definition_for_team(self, team_id: str, definition: WorkflowDefinition)` | Validates input or repairs required runtime state. |
| `graph_io(definition: WorkflowDefinition)` | Helper method for its service or type. |
| `terminal_nodes(definition: WorkflowDefinition)` | Helper method for its service or type. |
| `_topological_order(definition: WorkflowDefinition)` | Helper method for its service or type. |
| `_disable_other_workflows(self, team_id: str, workflow_id: str)` | Helper method for its service or type. |
| `_to_workflow(row)` | Converts, parses, or formats internal data. |

### `pocketStudio/utils/tag_parser.py`

Project module.

| Function | Usage |
|---|---|
| `split_candidate_ids(raw_ids: str)` | Module-level helper. Review callers and tests before changing behavior. |
| `extract_tags(text: str, prefix: str)` | Converts, parses, or formats internal data. |
| `strip_tags(text: str, prefix: str)` | Converts, parses, or formats internal data. |
| `get_directed_messages(leader_output: str, member_id: str)` | Reads one resource, status object, or derived view. |

### `pocketStudio/visualizer.py`

Package entry point or application entry point.

| Function | Usage |
|---|---|
| `json_loads(body: str)` | Module-level helper. Review callers and tests before changing behavior. |
| `json_dumps(payload: dict[str, Any])` | Module-level helper. Review callers and tests before changing behavior. |
| `normalize_agents(raw: Any)` | Converts, parses, or formats internal data. |
| `normalize_teams(raw: Any)` | Converts, parses, or formats internal data. |
| `normalize_office_events(raw: Any)` | Converts, parses, or formats internal data. |
| `build_agent_states(agents: dict[str, dict[str, Any]], teams: dict[str, dict[str, Any]], events: list[dict[str, Any]], team_id: str \| None=None)` | Module-level helper. Review callers and tests before changing behavior. |
| `build_flows(events: list[dict[str, Any]], team_id: str \| None=None, limit: int=8)` | Module-level helper. Review callers and tests before changing behavior. |
| `visible_agent_ids(agents: dict[str, dict[str, Any]], teams: dict[str, dict[str, Any]], team_id: str \| None=None)` | Module-level helper. Review callers and tests before changing behavior. |
| `render_team_dashboard(snapshot: VisualizerSnapshot, team_id: str \| None=None)` | Module-level helper. Review callers and tests before changing behavior. |
| `render_team_lines(teams: dict[str, dict[str, Any]], team_id: str \| None=None)` | Module-level helper. Review callers and tests before changing behavior. |
| `render_chatroom(team_id: str, messages: list[dict[str, Any]], connected: bool=True, limit: int=50)` | Module-level helper. Review callers and tests before changing behavior. |
| `format_event(event: dict[str, Any])` | Converts, parses, or formats internal data. |
| `compact_text(text: str, max_length: int)` | Module-level helper. Review callers and tests before changing behavior. |
| `clear_terminal()` | Deletes a resource or clears state. |
| `_enable_windows_virtual_terminal()` | Module-level helper. Review callers and tests before changing behavior. |
| `_clear_windows_console()` | Deletes a resource or clears state. |
| `run_team_visualizer(client: VisualizerClient, team_id: str \| None=None, interval: float=1.0, once: bool=False, event_limit: int=80, clear_screen: bool=True)` | Runs a provider, orchestration flow, event handler, or external message handler. |
| `run_chatroom_viewer(client: VisualizerClient, team_id: str, interval: float=1.0, once: bool=False, send: str \| None=None, sender: str='user', limit: int=50, clear_screen: bool=True)` | Runs a provider, orchestration flow, event handler, or external message handler. |

#### `AgentVisualState`

Class, data model, service object, or exception type.

#### `VisualizerSnapshot`

Class, data model, service object, or exception type.

#### `VisualizerClient`

Class, data model, service object, or exception type.

| Method | Usage |
|---|---|
| `__init__(self, base_url: str \| None=None, timeout: float=5.0)` | Python object lifecycle or protocol method. |
| `get_json(self, path: str)` | Reads one resource, status object, or derived view. |
| `post_json(self, path: str, payload: dict[str, Any])` | Helper method for its service or type. |
| `snapshot(self, team_id: str \| None=None, event_limit: int=80)` | Helper method for its service or type. |
| `chat_messages(self, team_id: str, limit: int=50, since: int=0)` | Helper method for its service or type. |
| `post_chat(self, team_id: str, message: str, sender: str='user')` | Helper method for its service or type. |
