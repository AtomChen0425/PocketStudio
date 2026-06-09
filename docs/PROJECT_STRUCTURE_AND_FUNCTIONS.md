# pocketStudio 项目结构与函数用法

本文档由 `tools/generate_project_docs.py` 根据 Python 后端源码生成，用来帮助维护者快速定位模块职责和函数入口。

## 项目结构

- `pocketStudio/api/`: FastAPI 路由与 TinyAGI/TinyOffice 兼容响应。
- `pocketStudio/channels/`: 外部渠道桥接，当前包含 Telegram。
- `pocketStudio/core/`: 配置、数据库、依赖注入、ID、运行时和 JSON 文件工具。
- `pocketStudio/providers/`: 本地、OpenAI-compatible、Codex、Claude/OpenCode CLI 等 provider 适配。
- `pocketStudio/services/`: 业务服务层，承载主要领域逻辑。
- `pocketStudio/static/`: 内置备用 UI。
- `tests/`: pytest 行为测试与兼容契约测试。
- `docs/`: 架构、映射和维护文档。

## 维护约定

- 路由层保持轻薄：复杂业务逻辑放到 `services/`。
- 外部模型或命令执行放到 `providers/`，外部消息渠道放到 `channels/`。
- API 响应整形优先复用 `pocketStudio/api/payloads.py`。
- settings JSON 文件读写优先复用 `pocketStudio/core/json_store.py`。
- 新增或移动函数后运行 `python tools/generate_project_docs.py` 更新本文档和英文版文档。

## 函数索引

### `pocketStudio/__init__.py`

包入口或应用入口。

### `pocketStudio/api/__init__.py`

FastAPI 路由层，只负责 HTTP 入参、响应形状和异常映射。

### `pocketStudio/api/agents.py`

FastAPI 路由层，只负责 HTTP 入参、响应形状和异常映射。

| Function | 用法 |
|---|---|
| `list_agents(service: AgentService=Depends(get_agent_service))` | 列出资源集合或查询结果。 |
| `upsert_agent(payload: AgentCreate, service: AgentService=Depends(get_agent_service))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `update_agent(agent_id: str, payload: dict, service: AgentService=Depends(get_agent_service))` | 更新或持久化已有资源。 |
| `get_agent(agent_id: str, service: AgentService=Depends(get_agent_service))` | 读取单个资源、状态或派生视图。 |
| `delete_agent(agent_id: str, service: AgentService=Depends(get_agent_service))` | 删除资源或清理状态。 |

### `pocketStudio/api/chat.py`

FastAPI 路由层，只负责 HTTP 入参、响应形状和异常映射。

| Function | 用法 |
|---|---|
| `_chatroom_payload(message: ChatMessage)` | 构造 API/兼容层响应或请求载荷。 |
| `list_chat(team_id: str, limit: int=Query(default=100, ge=1, le=500), since: int=Query(default=0, ge=0), sender: str \| None=None, q: str \| None=None, service: ChatService=Depends(get_chat_service))` | 列出资源集合或查询结果。 |
| `post_chat(team_id: str, payload: ChatMessageCreate, service: ChatService=Depends(get_chat_service), queue: QueueService=Depends(get_queue_service), teams: TeamService=Depends(get_team_service))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |

### `pocketStudio/api/compat.py`

FastAPI 路由层，只负责 HTTP 入参、响应形状和异常映射。

| Function | 用法 |
|---|---|
| `_schedule_create_payload(payload: dict[str, Any])` | 构造 API/兼容层响应或请求载荷。 |
| `_custom_providers(db: Database)` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `_save_custom_provider_row(provider_id: str, payload: dict[str, Any], db: Database)` | 更新或持久化已有资源。 |
| `_settings_apply_plan(payload: dict[str, Any])` | 更新或持久化已有资源。 |
| `_settings_path_value(value: Any)` | 更新或持久化已有资源。 |
| `_validate_settings_apply_plan(payload: dict[str, Any])` | 校验输入或修复必需的运行状态。 |
| `_target_agent_id(target: str)` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `get_settings_snapshot(agents: AgentService=Depends(get_agent_service), teams: TeamService=Depends(get_team_service), db: Database=Depends(get_database), settings_service: SettingsService=Depends(get_settings_service))` | 读取单个资源、状态或派生视图。 |
| `export_settings_snapshot(agents: AgentService=Depends(get_agent_service), teams: TeamService=Depends(get_team_service), db: Database=Depends(get_database), settings_service: SettingsService=Depends(get_settings_service))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `validate_settings_snapshot(payload: dict[str, Any], settings_service: SettingsService=Depends(get_settings_service))` | 校验输入或修复必需的运行状态。 |
| `preview_settings_snapshot(payload: dict[str, Any], settings_service: SettingsService=Depends(get_settings_service))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `settings_backup_info(settings_service: SettingsService=Depends(get_settings_service))` | 更新或持久化已有资源。 |
| `restore_settings_backup(agents: AgentService=Depends(get_agent_service), teams: TeamService=Depends(get_team_service), db: Database=Depends(get_database), settings_service: SettingsService=Depends(get_settings_service))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `update_settings_snapshot(payload: dict[str, Any], agents: AgentService=Depends(get_agent_service), teams: TeamService=Depends(get_team_service), db: Database=Depends(get_database), registry: ProviderRegistry=Depends(get_provider_registry), settings_service: SettingsService=Depends(get_settings_service))` | 更新或持久化已有资源。 |
| `import_settings_snapshot(payload: dict[str, Any], agents: AgentService=Depends(get_agent_service), teams: TeamService=Depends(get_team_service), db: Database=Depends(get_database), registry: ProviderRegistry=Depends(get_provider_registry), settings_service: SettingsService=Depends(get_settings_service))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `run_setup(payload: dict[str, Any], agents: AgentService=Depends(get_agent_service), teams: TeamService=Depends(get_team_service), db: Database=Depends(get_database), registry: ProviderRegistry=Depends(get_provider_registry), settings_service: SettingsService=Depends(get_settings_service))` | 执行 provider、编排流程、事件或外部消息处理。 |
| `enqueue_legacy_message(payload: dict[str, Any], orchestrator: Orchestrator=Depends(get_orchestrator), channels: ChannelService=Depends(get_channel_service), queue: QueueService=Depends(get_queue_service))` | 队列、响应或消息流转操作。 |
| `queue_status(queue: QueueService=Depends(get_queue_service))` | 队列、响应或消息流转操作。 |
| `queue_diagnostics(stale_threshold_seconds: int \| None=None, queue: QueueService=Depends(get_queue_service))` | 队列、响应或消息流转操作。 |
| `queue_agent_status(queue: QueueService=Depends(get_queue_service))` | 队列、响应或消息流转操作。 |
| `queue_dead(limit: int=Query(default=100, ge=1, le=500), queue: QueueService=Depends(get_queue_service))` | 队列、响应或消息流转操作。 |
| `queue_dead_retry(message_id: int, queue: QueueService=Depends(get_queue_service))` | 队列、响应或消息流转操作。 |
| `queue_dead_delete(message_id: int, queue: QueueService=Depends(get_queue_service))` | 队列、响应或消息流转操作。 |
| `queue_recover_stale(threshold_seconds: int \| None=None, queue: QueueService=Depends(get_queue_service))` | 队列、响应或消息流转操作。 |
| `queue_processing(queue: QueueService=Depends(get_queue_service), registry: ProviderRegistry=Depends(get_provider_registry))` | 队列、响应或消息流转操作。 |
| `active_processes(registry: ProviderRegistry=Depends(get_provider_registry))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `provider_diagnostics(registry: ProviderRegistry=Depends(get_provider_registry))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `async kill_agent_process(agent_id: str, registry: ProviderRegistry=Depends(get_provider_registry))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `async kill_processing(message_id: int, queue: QueueService=Depends(get_queue_service), registry: ProviderRegistry=Depends(get_provider_registry))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `responses(limit: int=Query(default=20, ge=1, le=200), queue: QueueService=Depends(get_queue_service))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `enqueue_response(payload: dict[str, Any], queue: QueueService=Depends(get_queue_service))` | 队列、响应或消息流转操作。 |
| `pending_responses(channel: str=Query(...), queue: QueueService=Depends(get_queue_service))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `responses_for_channel(channel: str, queue: QueueService=Depends(get_queue_service))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `ack_response(response_id: int, queue: QueueService=Depends(get_queue_service))` | 队列、响应或消息流转操作。 |
| `prune_responses(older_than_ms: int=86400000, queue: QueueService=Depends(get_queue_service))` | 队列、响应或消息流转操作。 |
| `prune_completed_messages(older_than_ms: int=86400000, queue: QueueService=Depends(get_queue_service))` | 队列、响应或消息流转操作。 |
| `logs(limit: int=Query(default=100, ge=1, le=500), event_type: str \| None=None, contains: str \| None=None, events: EventService=Depends(get_event_service))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `list_chats(chat: ChatService=Depends(get_chat_service))` | 列出资源集合或查询结果。 |
| `read_chat_archive(team_id: str, limit: int=Query(default=500, ge=1, le=2000), sender: str \| None=None, q: str \| None=None, chat: ChatService=Depends(get_chat_service))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `agent_messages(agent_id: str, limit: int=Query(default=100, ge=1, le=500), since_id: int=Query(default=0, ge=0), queue: QueueService=Depends(get_queue_service))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `all_agent_messages(limit: int=Query(default=100, ge=1, le=500), since_id: int=Query(default=0, ge=0), queue: QueueService=Depends(get_queue_service))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `reset_agent_runtime(agent_id: str, agents: AgentService=Depends(get_agent_service), queue: QueueService=Depends(get_queue_service))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `list_plugins(plugins: PluginService=Depends(get_plugin_service))` | 列出资源集合或查询结果。 |
| `reload_plugins(plugins: PluginService=Depends(get_plugin_service))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `get_agent_system_prompt(agent_id: str, agents: AgentService=Depends(get_agent_service))` | 读取单个资源、状态或派生视图。 |
| `save_agent_system_prompt(agent_id: str, payload: dict[str, str], agents: AgentService=Depends(get_agent_service))` | 更新或持久化已有资源。 |
| `get_agent_workspace_status(agent_id: str, agents: AgentService=Depends(get_agent_service))` | 读取单个资源、状态或派生视图。 |
| `repair_agent_workspace(agent_id: str, agents: AgentService=Depends(get_agent_service))` | 校验输入或修复必需的运行状态。 |
| `get_agent_memory(agent_id: str, agents: AgentService=Depends(get_agent_service))` | 读取单个资源、状态或派生视图。 |
| `get_agent_memory_file(agent_id: str, path: str=Query(...), agents: AgentService=Depends(get_agent_service))` | 读取单个资源、状态或派生视图。 |
| `save_agent_memory_file(agent_id: str, payload: dict[str, Any], agents: AgentService=Depends(get_agent_service))` | 更新或持久化已有资源。 |
| `delete_agent_memory_file(agent_id: str, path: str=Query(...), agents: AgentService=Depends(get_agent_service))` | 删除资源或清理状态。 |
| `get_agent_heartbeat(agent_id: str, agents: AgentService=Depends(get_agent_service))` | 读取单个资源、状态或派生视图。 |
| `save_agent_heartbeat(agent_id: str, payload: dict[str, Any], agents: AgentService=Depends(get_agent_service))` | 更新或持久化已有资源。 |
| `list_agent_skills(agent_id: str, agents: AgentService=Depends(get_agent_service))` | 列出资源集合或查询结果。 |
| `search_agent_skills(agent_id: str, query: str='', agents: AgentService=Depends(get_agent_service))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `install_agent_skill(agent_id: str, payload: dict[str, str], agents: AgentService=Depends(get_agent_service))` | 创建资源、安装内容或追加关系。 |
| `list_projects(status: str \| None=None, projects: ProjectService=Depends(get_project_service))` | 列出资源集合或查询结果。 |
| `create_project(payload: ProjectCreate, projects: ProjectService=Depends(get_project_service))` | 创建资源、安装内容或追加关系。 |
| `get_project(project_id: str, projects: ProjectService=Depends(get_project_service))` | 读取单个资源、状态或派生视图。 |
| `update_project(project_id: str, payload: dict[str, Any], projects: ProjectService=Depends(get_project_service))` | 更新或持久化已有资源。 |
| `get_project_workspace_status(project_id: str, projects: ProjectService=Depends(get_project_service))` | 读取单个资源、状态或派生视图。 |
| `repair_project_workspace(project_id: str, projects: ProjectService=Depends(get_project_service))` | 校验输入或修复必需的运行状态。 |
| `delete_project(project_id: str, projects: ProjectService=Depends(get_project_service))` | 删除资源或清理状态。 |
| `reorder_tasks(payload: dict[str, Any], tasks: TaskService=Depends(get_task_service))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `list_task_comments(task_id: int, projects: ProjectService=Depends(get_project_service))` | 列出资源集合或查询结果。 |
| `create_task_comment(task_id: int, payload: TaskCommentCreate, projects: ProjectService=Depends(get_project_service))` | 创建资源、安装内容或追加关系。 |
| `delete_comment(comment_id: str, projects: ProjectService=Depends(get_project_service))` | 删除资源或清理状态。 |
| `list_schedules(agent: str \| None=None, schedules: ScheduleService=Depends(get_schedule_service))` | 列出资源集合或查询结果。 |
| `create_schedule(payload: dict[str, Any], schedules: ScheduleService=Depends(get_schedule_service))` | 创建资源、安装内容或追加关系。 |
| `validate_schedule(payload: dict[str, Any], schedules: ScheduleService=Depends(get_schedule_service))` | 校验输入或修复必需的运行状态。 |
| `update_schedule(schedule_id: str, payload: dict[str, Any], schedules: ScheduleService=Depends(get_schedule_service))` | 更新或持久化已有资源。 |
| `fire_schedule(schedule_id: str, payload: dict[str, Any] \| None=None, schedules: ScheduleService=Depends(get_schedule_service), queue: QueueService=Depends(get_queue_service))` | 控制后台 worker、调度器或处理流程。 |
| `delete_schedule(schedule_id: str, schedules: ScheduleService=Depends(get_schedule_service))` | 删除资源或清理状态。 |
| `system_status(worker: WorkerService=Depends(get_worker_service), heartbeat: HeartbeatService=Depends(get_heartbeat_service), settings_service: SettingsService=Depends(get_settings_service), telegram: TelegramChannelService=Depends(get_telegram_channel_service))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `_service_status_payload(worker: WorkerService, heartbeat: HeartbeatService, settings_service: SettingsService, telegram: TelegramChannelService \| None=None)` | 构造 API/兼容层响应或请求载荷。 |
| `heartbeat_status(heartbeat: HeartbeatService=Depends(get_heartbeat_service))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `heartbeat_tick(payload: dict[str, Any] \| None=None, heartbeat: HeartbeatService=Depends(get_heartbeat_service), queue: QueueService=Depends(get_queue_service))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `clear_heartbeat_state(agent: str \| None=Query(default=None), heartbeat: HeartbeatService=Depends(get_heartbeat_service))` | 删除资源或清理状态。 |
| `worker_status(worker: WorkerService=Depends(get_worker_service))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `async worker_start(worker: WorkerService=Depends(get_worker_service))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `async worker_stop(worker: WorkerService=Depends(get_worker_service))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `async worker_pause(worker: WorkerService=Depends(get_worker_service))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `async worker_resume(worker: WorkerService=Depends(get_worker_service))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `async worker_restart(worker: WorkerService=Depends(get_worker_service))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `async worker_tick(force: bool=False, worker: WorkerService=Depends(get_worker_service))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `worker_maintenance(older_than_ms: int=86400000, stale_threshold_seconds: int \| None=None, prune_chats: bool=False, worker: WorkerService=Depends(get_worker_service))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `async apply_services(worker: WorkerService=Depends(get_worker_service), settings_service: SettingsService=Depends(get_settings_service), telegram: TelegramChannelService=Depends(get_telegram_channel_service))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `services_status(worker: WorkerService=Depends(get_worker_service), heartbeat: HeartbeatService=Depends(get_heartbeat_service), settings_service: SettingsService=Depends(get_settings_service), telegram: TelegramChannelService=Depends(get_telegram_channel_service))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `async start_services(worker: WorkerService=Depends(get_worker_service), heartbeat: HeartbeatService=Depends(get_heartbeat_service), settings_service: SettingsService=Depends(get_settings_service), telegram: TelegramChannelService=Depends(get_telegram_channel_service))` | 控制后台 worker、调度器或处理流程。 |
| `async stop_services(worker: WorkerService=Depends(get_worker_service), heartbeat: HeartbeatService=Depends(get_heartbeat_service), settings_service: SettingsService=Depends(get_settings_service), telegram: TelegramChannelService=Depends(get_telegram_channel_service))` | 控制后台 worker、调度器或处理流程。 |
| `async restart_service(worker: WorkerService=Depends(get_worker_service))` | 控制后台 worker、调度器或处理流程。 |
| `async channel_action(channel_id: str, action: str, telegram: TelegramChannelService=Depends(get_telegram_channel_service))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `get_pairings(channels: ChannelService=Depends(get_channel_service))` | 读取单个资源、状态或派生视图。 |
| `approve_pairing(payload: dict[str, str], channels: ChannelService=Depends(get_channel_service))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `revoke_pairing(channel: str, sender_id: str, channels: ChannelService=Depends(get_channel_service))` | 删除资源或清理状态。 |
| `dismiss_pairing(code: str, channels: ChannelService=Depends(get_channel_service))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `list_custom_providers(db: Database=Depends(get_database))` | 列出资源集合或查询结果。 |
| `save_custom_provider(provider_id: str, payload: dict[str, Any], db: Database=Depends(get_database), registry: ProviderRegistry=Depends(get_provider_registry))` | 更新或持久化已有资源。 |
| `delete_custom_provider(provider_id: str, db: Database=Depends(get_database), registry: ProviderRegistry=Depends(get_provider_registry))` | 删除资源或清理状态。 |

### `pocketStudio/api/errors.py`

FastAPI 路由层，只负责 HTTP 入参、响应形状和异常映射。

| Function | 用法 |
|---|---|
| `not_found(exc: KeyError)` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |

### `pocketStudio/api/messages.py`

FastAPI 路由层，只负责 HTTP 入参、响应形状和异常映射。

| Function | 用法 |
|---|---|
| `enqueue_message(payload: MessageCreate, orchestrator: Orchestrator=Depends(get_orchestrator))` | 队列、响应或消息流转操作。 |
| `async process_message(message_id: int, orchestrator: Orchestrator=Depends(get_orchestrator))` | 控制后台 worker、调度器或处理流程。 |
| `async process_next(orchestrator: Orchestrator=Depends(get_orchestrator))` | 控制后台 worker、调度器或处理流程。 |
| `list_queue(limit: int=Query(default=100, ge=1, le=500), status: MessageStatus \| None=None, service: QueueService=Depends(get_queue_service))` | 列出资源集合或查询结果。 |
| `list_grouped_queue(limit: int=Query(default=100, ge=1, le=500), status: MessageStatus \| None=None, service: QueueService=Depends(get_queue_service))` | 列出资源集合或查询结果。 |
| `get_message(message_id: int, service: QueueService=Depends(get_queue_service))` | 读取单个资源、状态或派生视图。 |
| `retry_message(message_id: int, service: QueueService=Depends(get_queue_service))` | 队列、响应或消息流转操作。 |

### `pocketStudio/api/payloads.py`

FastAPI 路由层，只负责 HTTP 入参、响应形状和异常映射。

| Function | 用法 |
|---|---|
| `timestamp_millis(value: str \| int \| float \| None)` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `agent_config(agent: Agent)` | 构造 API/兼容层响应或请求载荷。 |
| `team_config(team: Team)` | 构造 API/兼容层响应或请求载荷。 |
| `task_payload(task: Task, comment_count: int=0)` | 构造 API/兼容层响应或请求载荷。 |
| `task_response(task: Task, comment_count: int=0)` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `project_payload(project: Project, task_count: int \| None=None)` | 构造 API/兼容层响应或请求载荷。 |
| `schedule_payload(schedule: Schedule)` | 构造 API/兼容层响应或请求载荷。 |
| `schedule_payload_with_status(schedule: Schedule, schedules: ScheduleService)` | 构造 API/兼容层响应或请求载荷。 |

### `pocketStudio/api/system.py`

FastAPI 路由层，只负责 HTTP 入参、响应形状和异常映射。

| Function | 用法 |
|---|---|
| `health(settings: Settings=Depends(get_settings))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `providers(registry: ProviderRegistry=Depends(get_provider_registry))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `events(limit: int=Query(default=100, ge=1, le=500), since: int=Query(default=0, ge=0), service: EventService=Depends(get_event_service))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `office_events(limit: int=Query(default=100, ge=1, le=500), since: int=Query(default=0, ge=0), service: EventService=Depends(get_event_service))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `_sse_message(event_name: str, data: dict)` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `async event_stream(since: int=Query(default=0, ge=0), replay: bool=Query(default=True), service: EventService=Depends(get_event_service))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |

### `pocketStudio/api/tasks.py`

FastAPI 路由层，只负责 HTTP 入参、响应形状和异常映射。

| Function | 用法 |
|---|---|
| `list_tasks(projectId: str \| None=None, status: str \| None=None, assignee: str \| None=None, q: str \| None=None, service: TaskService=Depends(get_task_service))` | 列出资源集合或查询结果。 |
| `create_task(payload: TaskCreate, service: TaskService=Depends(get_task_service), projects: ProjectService=Depends(get_project_service))` | 创建资源、安装内容或追加关系。 |
| `get_task(task_id: int, service: TaskService=Depends(get_task_service), projects: ProjectService=Depends(get_project_service))` | 读取单个资源、状态或派生视图。 |
| `update_task(task_id: int, payload: dict[str, Any], service: TaskService=Depends(get_task_service), projects: ProjectService=Depends(get_project_service))` | 更新或持久化已有资源。 |
| `update_task_status(task_id: int, status: str, service: TaskService=Depends(get_task_service))` | 更新或持久化已有资源。 |
| `delete_task(task_id: int, service: TaskService=Depends(get_task_service))` | 删除资源或清理状态。 |

### `pocketStudio/api/teams.py`

FastAPI 路由层，只负责 HTTP 入参、响应形状和异常映射。

| Function | 用法 |
|---|---|
| `list_teams(service: TeamService=Depends(get_team_service))` | 列出资源集合或查询结果。 |
| `upsert_team(payload: TeamCreate, service: TeamService=Depends(get_team_service))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `update_team(team_id: str, payload: dict, service: TeamService=Depends(get_team_service))` | 更新或持久化已有资源。 |
| `get_team(team_id: str, service: TeamService=Depends(get_team_service))` | 读取单个资源、状态或派生视图。 |
| `add_team_member(team_id: str, agent_id: str, service: TeamService=Depends(get_team_service))` | 创建资源、安装内容或追加关系。 |
| `remove_team_member(team_id: str, agent_id: str, service: TeamService=Depends(get_team_service))` | 删除资源或清理状态。 |
| `set_team_leader(team_id: str, agent_id: str, service: TeamService=Depends(get_team_service))` | 更新或持久化已有资源。 |
| `delete_team(team_id: str, service: TeamService=Depends(get_team_service))` | 删除资源或清理状态。 |

### `pocketStudio/api/workflows.py`

FastAPI 路由层，只负责 HTTP 入参、响应形状和异常映射。

| Function | 用法 |
|---|---|
| `list_workflows(team_id: str, service: WorkflowService=Depends(get_workflow_service))` | 列出资源集合或查询结果。 |
| `upsert_workflow(team_id: str, payload: TeamWorkflowCreate, service: WorkflowService=Depends(get_workflow_service))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `validate_workflow(team_id: str, definition: WorkflowDefinition, service: WorkflowService=Depends(get_workflow_service))` | 校验输入或修复必需的运行状态。 |
| `import_workflow(team_id: str, payload: dict[str, Any], service: WorkflowService=Depends(get_workflow_service))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `get_workflow(team_id: str, workflow_id: str, service: WorkflowService=Depends(get_workflow_service))` | 读取单个资源、状态或派生视图。 |
| `export_workflow(team_id: str, workflow_id: str, service: WorkflowService=Depends(get_workflow_service))` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `update_workflow(team_id: str, workflow_id: str, payload: TeamWorkflowUpdate, service: WorkflowService=Depends(get_workflow_service))` | 更新或持久化已有资源。 |
| `delete_workflow(team_id: str, workflow_id: str, service: WorkflowService=Depends(get_workflow_service))` | 删除资源或清理状态。 |

### `pocketStudio/channels/__init__.py`

外部消息渠道适配层，例如 Telegram 的收发、配对和投递。

### `pocketStudio/channels/telegram.py`

外部消息渠道适配层，例如 Telegram 的收发、配对和投递。

#### `TelegramApiError(RuntimeError)`

类、数据模型、服务对象或异常类型。

#### `TelegramChannelService`

类、数据模型、服务对象或异常类型。

| Method | 用法 |
|---|---|
| `__init__(self, db: Database, settings: Settings, settings_service: SettingsService, channels: ChannelService, queue: QueueService, events: EventService)` | Python 对象生命周期或协议方法。 |
| `configured_token(self)` | 所属服务/类型的辅助方法。 |
| `status(self)` | 所属服务/类型的辅助方法。 |
| `start(self)` | 控制后台 worker、调度器或处理流程。 |
| `async stop(self)` | 控制后台 worker、调度器或处理流程。 |
| `async restart(self)` | 控制后台 worker、调度器或处理流程。 |
| `async tick(self)` | 控制后台 worker、调度器或处理流程。 |
| `poll_once(self, limit: int=20, timeout: int=0)` | 所属服务/类型的辅助方法。 |
| `deliver_pending(self)` | 所属服务/类型的辅助方法。 |
| `async _run(self)` | 执行 provider、编排流程、事件或外部消息处理。 |
| `_handle_update(self, update: dict, token: str)` | 执行 provider、编排流程、事件或外部消息处理。 |
| `_handle_command(self, text: str, token: str, chat_id: str, reply_to: int \| None)` | 执行 provider、编排流程、事件或外部消息处理。 |
| `_send_response(self, token: str, response: ResponseJob)` | 所属服务/类型的辅助方法。 |
| `_api_call(self, token: str, method: str, payload: dict[str, Any])` | 所属服务/类型的辅助方法。 |
| `_send_message(self, token: str, chat_id: str, text: str, reply_to: int \| None=None)` | 所属服务/类型的辅助方法。 |
| `_send_chat_action(self, token: str, chat_id: str)` | 所属服务/类型的辅助方法。 |
| `_require_token(self)` | 所属服务/类型的辅助方法。 |
| `_load_offset(self)` | 所属服务/类型的辅助方法。 |
| `_save_offset(self, offset: int)` | 更新或持久化已有资源。 |
| `_offset_path(self)` | 所属服务/类型的辅助方法。 |
| `_status_label(self, configured: bool)` | 所属服务/类型的辅助方法。 |
| `_sender_name(message: dict)` | 所属服务/类型的辅助方法。 |
| `_pairing_message(code: str)` | 所属服务/类型的辅助方法。 |
| `_split_message(text: str)` | 所属服务/类型的辅助方法。 |

### `pocketStudio/cli.py`

包入口或应用入口。

| Function | 用法 |
|---|---|
| `print_json(value: Any)` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `package_version()` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `build_parser()` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `run(args: argparse.Namespace, client: ApiClient)` | 执行 provider、编排流程、事件或外部消息处理。 |
| `run_agent(args: argparse.Namespace, client: ApiClient)` | 执行 provider、编排流程、事件或外部消息处理。 |
| `run_settings(args: argparse.Namespace, client: ApiClient)` | 执行 provider、编排流程、事件或外部消息处理。 |
| `run_daemon(args: argparse.Namespace, manager: DaemonManager \| None=None)` | 执行 provider、编排流程、事件或外部消息处理。 |
| `run_team(args: argparse.Namespace, client: ApiClient)` | 执行 provider、编排流程、事件或外部消息处理。 |
| `run_provider(args: argparse.Namespace, client: ApiClient)` | 执行 provider、编排流程、事件或外部消息处理。 |
| `run_schedule(args: argparse.Namespace, client: ApiClient)` | 执行 provider、编排流程、事件或外部消息处理。 |
| `run_pairing(args: argparse.Namespace, client: ApiClient)` | 执行 provider、编排流程、事件或外部消息处理。 |
| `run_project(args: argparse.Namespace, client: ApiClient)` | 执行 provider、编排流程、事件或外部消息处理。 |
| `run_task(args: argparse.Namespace, client: ApiClient)` | 执行 provider、编排流程、事件或外部消息处理。 |
| `main(argv: list[str] \| None=None, client: ApiClient \| None=None)` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |

#### `ApiClient`

类、数据模型、服务对象或异常类型。

| Method | 用法 |
|---|---|
| `__init__(self, base_url: str \| None=None)` | Python 对象生命周期或协议方法。 |
| `request(self, method: str, path: str, payload: dict[str, Any] \| None=None)` | 所属服务/类型的辅助方法。 |
| `get(self, path: str)` | 读取单个资源、状态或派生视图。 |
| `post(self, path: str, payload: dict[str, Any] \| None=None)` | 所属服务/类型的辅助方法。 |
| `put(self, path: str, payload: dict[str, Any])` | 所属服务/类型的辅助方法。 |
| `delete(self, path: str)` | 删除资源或清理状态。 |

#### `DaemonManager`

类、数据模型、服务对象或异常类型。

| Method | 用法 |
|---|---|
| `__init__(self, host: str=DEFAULT_HOST, port: int=DEFAULT_PORT, home: Path \| None=None)` | Python 对象生命周期或协议方法。 |
| `api_url(self)` | 所属服务/类型的辅助方法。 |
| `status(self)` | 所属服务/类型的辅助方法。 |
| `start(self)` | 控制后台 worker、调度器或处理流程。 |
| `stop(self)` | 控制后台 worker、调度器或处理流程。 |
| `restart(self)` | 控制后台 worker、调度器或处理流程。 |
| `open(self)` | 所属服务/类型的辅助方法。 |
| `_read_pid(self)` | 所属服务/类型的辅助方法。 |
| `_pid_alive(self, pid: int)` | 所属服务/类型的辅助方法。 |
| `_unlink_pid(self)` | 所属服务/类型的辅助方法。 |
| `_fetch_status(self)` | 所属服务/类型的辅助方法。 |
| `_wait_for_status(self, timeout_seconds: float=8.0)` | 所属服务/类型的辅助方法。 |

### `pocketStudio/core/config.py`

核心基础设施，包括配置、数据库、依赖装配、JSON 文件存储和运行时工具。

| Function | 用法 |
|---|---|
| `get_settings()` | 读取单个资源、状态或派生视图。 |

#### `Settings(BaseSettings)`

类、数据模型、服务对象或异常类型。

| Method | 用法 |
|---|---|
| `database_path(self)` | 所属服务/类型的辅助方法。 |
| `settings_path(self)` | 更新或持久化已有资源。 |
| `workspace_path(self)` | 所属服务/类型的辅助方法。 |
| `files_path(self)` | 所属服务/类型的辅助方法。 |
| `logs_path(self)` | 所属服务/类型的辅助方法。 |
| `log_file_path(self)` | 所属服务/类型的辅助方法。 |

### `pocketStudio/core/database.py`

核心基础设施，包括配置、数据库、依赖装配、JSON 文件存储和运行时工具。

#### `Database`

类、数据模型、服务对象或异常类型。

| Method | 用法 |
|---|---|
| `__init__(self, path: Path, journal_mode: str='MEMORY')` | Python 对象生命周期或协议方法。 |
| `connect(self)` | 所属服务/类型的辅助方法。 |
| `initialize(self)` | 所属服务/类型的辅助方法。 |
| `_migrate(self, conn: sqlite3.Connection)` | 所属服务/类型的辅助方法。 |
| `_add_column(conn: sqlite3.Connection, table: str, column: str, definition: str)` | 创建资源、安装内容或追加关系。 |
| `_migrate_team_mode_check(conn: sqlite3.Connection)` | 所属服务/类型的辅助方法。 |
| `_backfill_task_numbers(conn: sqlite3.Connection)` | 所属服务/类型的辅助方法。 |
| `execute(self, query: str, params: Iterable[Any]=())` | 所属服务/类型的辅助方法。 |
| `fetch_one(self, query: str, params: Iterable[Any]=())` | 所属服务/类型的辅助方法。 |
| `fetch_all(self, query: str, params: Iterable[Any]=())` | 所属服务/类型的辅助方法。 |

### `pocketStudio/core/dependencies.py`

核心基础设施，包括配置、数据库、依赖装配、JSON 文件存储和运行时工具。

| Function | 用法 |
|---|---|
| `get_database()` | 读取单个资源、状态或派生视图。 |
| `get_event_service()` | 读取单个资源、状态或派生视图。 |
| `get_agent_service()` | 读取单个资源、状态或派生视图。 |
| `get_team_service()` | 读取单个资源、状态或派生视图。 |
| `get_workflow_service()` | 读取单个资源、状态或派生视图。 |
| `get_queue_service()` | 读取单个资源、状态或派生视图。 |
| `get_response_service()` | 读取单个资源、状态或派生视图。 |
| `get_plugin_service()` | 读取单个资源、状态或派生视图。 |
| `get_chat_service()` | 读取单个资源、状态或派生视图。 |
| `get_channel_service()` | 读取单个资源、状态或派生视图。 |
| `get_telegram_channel_service()` | 读取单个资源、状态或派生视图。 |
| `get_task_service()` | 读取单个资源、状态或派生视图。 |
| `get_project_service()` | 读取单个资源、状态或派生视图。 |
| `get_schedule_service()` | 读取单个资源、状态或派生视图。 |
| `get_settings_service()` | 读取单个资源、状态或派生视图。 |
| `get_heartbeat_service()` | 读取单个资源、状态或派生视图。 |
| `get_provider_registry()` | 读取单个资源、状态或派生视图。 |
| `get_orchestrator()` | 读取单个资源、状态或派生视图。 |
| `get_worker_service()` | 读取单个资源、状态或派生视图。 |

### `pocketStudio/core/ids.py`

核心基础设施，包括配置、数据库、依赖装配、JSON 文件存储和运行时工具。

| Function | 用法 |
|---|---|
| `nanoid(size: int=21, alphabet: str=DEFAULT_ALPHABET)` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `prefixed_id(prefix: str, size: int=12)` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |

### `pocketStudio/core/json_store.py`

核心基础设施，包括配置、数据库、依赖装配、JSON 文件存储和运行时工具。

| Function | 用法 |
|---|---|
| `read_json_object(path: Path)` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `write_json_object(path: Path, data: dict[str, Any])` | 更新或持久化已有资源。 |

### `pocketStudio/core/runtime.py`

核心基础设施，包括配置、数据库、依赖装配、JSON 文件存储和运行时工具。

| Function | 用法 |
|---|---|
| `uptime_seconds()` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |

### `pocketStudio/main.py`

包入口或应用入口。

| Function | 用法 |
|---|---|
| `async lifespan(app: FastAPI)` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `create_app()` | 创建资源、安装内容或追加关系。 |

### `pocketStudio/models/__init__.py`

项目模块。

### `pocketStudio/models/agent.py`

项目模块。

#### `AgentCreate(BaseModel)`

类、数据模型、服务对象或异常类型。

#### `Agent(AgentCreate)`

类、数据模型、服务对象或异常类型。

#### `AgentMessage(BaseModel)`

类、数据模型、服务对象或异常类型。

### `pocketStudio/models/chat.py`

项目模块。

#### `ChatMessageCreate(BaseModel)`

类、数据模型、服务对象或异常类型。

#### `ChatMessage(BaseModel)`

类、数据模型、服务对象或异常类型。

### `pocketStudio/models/enums.py`

项目模块。

#### `TeamMode(StrEnum)`

类、数据模型、服务对象或异常类型。

#### `MessageStatus(StrEnum)`

类、数据模型、服务对象或异常类型。

### `pocketStudio/models/event.py`

项目模块。

#### `Event(BaseModel)`

类、数据模型、服务对象或异常类型。

### `pocketStudio/models/orchestration.py`

项目模块。

#### `AgentRun(BaseModel)`

类、数据模型、服务对象或异常类型。

#### `OrchestrationResult(BaseModel)`

类、数据模型、服务对象或异常类型。

### `pocketStudio/models/project.py`

项目模块。

#### `ProjectCreate(BaseModel)`

类、数据模型、服务对象或异常类型。

#### `Project(ProjectCreate)`

类、数据模型、服务对象或异常类型。

### `pocketStudio/models/queue.py`

项目模块。

#### `MessageCreate(BaseModel)`

类、数据模型、服务对象或异常类型。

#### `QueueMessage(BaseModel)`

类、数据模型、服务对象或异常类型。

#### `QueueStatus(BaseModel)`

类、数据模型、服务对象或异常类型。

#### `ResponseJob(BaseModel)`

类、数据模型、服务对象或异常类型。

### `pocketStudio/models/schedule.py`

项目模块。

#### `ScheduleCreate(BaseModel)`

类、数据模型、服务对象或异常类型。

#### `Schedule(BaseModel)`

类、数据模型、服务对象或异常类型。

### `pocketStudio/models/task.py`

项目模块。

#### `TaskCreate(BaseModel)`

类、数据模型、服务对象或异常类型。

#### `Task(TaskCreate)`

类、数据模型、服务对象或异常类型。

#### `TaskCommentCreate(BaseModel)`

类、数据模型、服务对象或异常类型。

#### `TaskComment(TaskCommentCreate)`

类、数据模型、服务对象或异常类型。

### `pocketStudio/models/team.py`

项目模块。

#### `TeamCreate(BaseModel)`

类、数据模型、服务对象或异常类型。

#### `Team(TeamCreate)`

类、数据模型、服务对象或异常类型。

### `pocketStudio/models/workflow.py`

项目模块。

#### `WorkflowRoutingFunction(BaseModel)`

类、数据模型、服务对象或异常类型。

| Method | 用法 |
|---|---|
| `code_must_not_be_empty(cls, value: str)` | 所属服务/类型的辅助方法。 |
| `entrypoint_must_not_be_empty(cls, value: str)` | 所属服务/类型的辅助方法。 |

#### `WorkflowNode(BaseModel)`

类、数据模型、服务对象或异常类型。

#### `WorkflowEdge(BaseModel)`

类、数据模型、服务对象或异常类型。

#### `WorkflowRoute(BaseModel)`

类、数据模型、服务对象或异常类型。

#### `WorkflowConditionalEdge(BaseModel)`

类、数据模型、服务对象或异常类型。

#### `WorkflowDefinition(BaseModel)`

类、数据模型、服务对象或异常类型。

| Method | 用法 |
|---|---|
| `supported_version(cls, value: int)` | 所属服务/类型的辅助方法。 |
| `validate_graph_shape(self)` | 校验输入或修复必需的运行状态。 |

#### `TeamWorkflowCreate(BaseModel)`

类、数据模型、服务对象或异常类型。

#### `TeamWorkflowUpdate(BaseModel)`

类、数据模型、服务对象或异常类型。

#### `TeamWorkflow(BaseModel)`

类、数据模型、服务对象或异常类型。

### `pocketStudio/providers/base.py`

Agent Provider 和 CLI/Subprocess 适配层，隔离外部模型或命令执行细节。

#### `ProviderRequest(BaseModel)`

类、数据模型、服务对象或异常类型。

#### `ProviderResponse(BaseModel)`

类、数据模型、服务对象或异常类型。

#### `AgentProvider(ABC)`

类、数据模型、服务对象或异常类型。

| Method | 用法 |
|---|---|
| `setup_workspace(self, workspace: Path)` | 更新或持久化已有资源。 |
| `async run(self, request: ProviderRequest)` | 执行 provider、编排流程、事件或外部消息处理。 |

### `pocketStudio/providers/cli_agent.py`

Agent Provider 和 CLI/Subprocess 适配层，隔离外部模型或命令执行细节。

| Function | 用法 |
|---|---|
| `provider_from_command(name: str, command_line: str, registry: ProcessRegistry \| None=None, timeout_seconds: int=600)` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |

#### `CliAgentProvider(AgentProvider)`

类、数据模型、服务对象或异常类型。

| Method | 用法 |
|---|---|
| `__init__(self, name: str, command: str, base_args: list[str] \| None=None, prompt_arg: str \| None=None, registry: ProcessRegistry \| None=None, timeout_seconds: int=600)` | Python 对象生命周期或协议方法。 |
| `async run(self, request: ProviderRequest)` | 执行 provider、编排流程、事件或外部消息处理。 |
| `_args(self, request: ProviderRequest)` | 所属服务/类型的辅助方法。 |
| `_prompt(request: ProviderRequest)` | 所属服务/类型的辅助方法。 |
| `_extract_text(cls, stdout: str)` | 转换、解析或格式化内部数据。 |
| `_extract_event_text(line: str)` | 转换、解析或格式化内部数据。 |
| `is_alive(self, agent_id: str)` | 所属服务/类型的辅助方法。 |
| `async kill_agent(self, agent_id: str)` | 所属服务/类型的辅助方法。 |

#### `ClaudeProvider(CliAgentProvider)`

类、数据模型、服务对象或异常类型。

| Method | 用法 |
|---|---|
| `__init__(self, registry: ProcessRegistry \| None=None, timeout_seconds: int=600)` | Python 对象生命周期或协议方法。 |

#### `OpenCodeProvider(CliAgentProvider)`

类、数据模型、服务对象或异常类型。

| Method | 用法 |
|---|---|
| `__init__(self, registry: ProcessRegistry \| None=None, timeout_seconds: int=600)` | Python 对象生命周期或协议方法。 |

### `pocketStudio/providers/codex.py`

Agent Provider 和 CLI/Subprocess 适配层，隔离外部模型或命令执行细节。

| Function | 用法 |
|---|---|
| `codex_provider_from_command(command_line: str, registry: ProcessRegistry \| None=None, timeout_seconds: int=600)` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `_split_command_line(command_line: str)` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |

#### `CodexProvider(AgentProvider)`

类、数据模型、服务对象或异常类型。

| Method | 用法 |
|---|---|
| `__init__(self, command: str \| None=None, base_args: list[str] \| None=None, registry: ProcessRegistry \| None=None, timeout_seconds: int=600)` | Python 对象生命周期或协议方法。 |
| `setup_workspace(self, workspace: Path)` | 更新或持久化已有资源。 |
| `async run(self, request: ProviderRequest)` | 执行 provider、编排流程、事件或外部消息处理。 |
| `_args(self, request: ProviderRequest)` | 所属服务/类型的辅助方法。 |
| `_custom_args(self, request: ProviderRequest)` | 所属服务/类型的辅助方法。 |
| `_prompt(self, request: ProviderRequest)` | 所属服务/类型的辅助方法。 |
| `_extract_text(cls, stdout: str)` | 转换、解析或格式化内部数据。 |
| `_extract_event_text(line: str)` | 转换、解析或格式化内部数据。 |
| `_parse_event(line: str)` | 转换、解析或格式化内部数据。 |
| `_extract_event_text_from_event(event: dict \| None)` | 转换、解析或格式化内部数据。 |
| `_progress_payload(cls, event: dict)` | 构造 API/兼容层响应或请求载荷。 |
| `_tool_name(event: dict, item: dict)` | 所属服务/类型的辅助方法。 |
| `_event_summary(event_type: str, item: dict, content: str, tool: str \| None)` | 所属服务/类型的辅助方法。 |
| `_compact_event(event: dict)` | 所属服务/类型的辅助方法。 |
| `is_alive(self, agent_id: str)` | 所属服务/类型的辅助方法。 |
| `async kill_agent(self, agent_id: str)` | 所属服务/类型的辅助方法。 |

### `pocketStudio/providers/local.py`

Agent Provider 和 CLI/Subprocess 适配层，隔离外部模型或命令执行细节。

#### `LocalEchoProvider(AgentProvider)`

类、数据模型、服务对象或异常类型。

| Method | 用法 |
|---|---|
| `async run(self, request: ProviderRequest)` | 执行 provider、编排流程、事件或外部消息处理。 |

### `pocketStudio/providers/openai_compatible.py`

Agent Provider 和 CLI/Subprocess 适配层，隔离外部模型或命令执行细节。

#### `OpenAICompatibleProvider(AgentProvider)`

类、数据模型、服务对象或异常类型。

| Method | 用法 |
|---|---|
| `__init__(self, name: str='openai', base_url: str \| None=None, api_key: str \| None=None, default_model: str \| None=None)` | Python 对象生命周期或协议方法。 |
| `async run(self, request: ProviderRequest)` | 执行 provider、编排流程、事件或外部消息处理。 |

### `pocketStudio/providers/registry.py`

Agent Provider 和 CLI/Subprocess 适配层，隔离外部模型或命令执行细节。

| Function | 用法 |
|---|---|
| `_codex_home_diagnostics(codex_home: Path)` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `_can_write(path: Path)` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `_resolved_command_path(command: str \| None)` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |

#### `ProviderRegistry`

类、数据模型、服务对象或异常类型。

| Method | 用法 |
|---|---|
| `__init__(self, db: Database \| None=None)` | Python 对象生命周期或协议方法。 |
| `register(self, provider: AgentProvider)` | 所属服务/类型的辅助方法。 |
| `reload_custom(self)` | 所属服务/类型的辅助方法。 |
| `get(self, name: str)` | 读取单个资源、状态或派生视图。 |
| `list_names(self)` | 列出资源集合或查询结果。 |
| `async kill_agent(self, agent_id: str)` | 所属服务/类型的辅助方法。 |
| `agent_process_alive(self, agent_id: str)` | 所属服务/类型的辅助方法。 |
| `active_processes(self)` | 所属服务/类型的辅助方法。 |
| `diagnostics(self)` | 所属服务/类型的辅助方法。 |

### `pocketStudio/providers/subprocess.py`

Agent Provider 和 CLI/Subprocess 适配层，隔离外部模型或命令执行细节。

| Function | 用法 |
|---|---|
| `async _empty_bytes()` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `_should_fallback_to_windows_powershell(exc: OSError)` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `_should_fallback_to_windows_sync_subprocess(exc: OSError)` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `_windows_powershell()` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `_resolved_command(command: str)` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `_powershell_command(command: Sequence[str], pipe_stdin: bool=False)` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |

#### `SubprocessResult`

类、数据模型、服务对象或异常类型。

#### `ProcessRegistry`

类、数据模型、服务对象或异常类型。

| Method | 用法 |
|---|---|
| `register(self, key: str, process: asyncio.subprocess.Process, metadata: dict \| None=None)` | 所属服务/类型的辅助方法。 |
| `unregister(self, key: str, process: asyncio.subprocess.Process)` | 所属服务/类型的辅助方法。 |
| `is_alive(self, key: str)` | 所属服务/类型的辅助方法。 |
| `snapshot(self)` | 所属服务/类型的辅助方法。 |
| `async kill(self, key: str)` | 所属服务/类型的辅助方法。 |

#### `SubprocessHarness`

类、数据模型、服务对象或异常类型。

| Method | 用法 |
|---|---|
| `__init__(self, command: str, registry: ProcessRegistry \| None=None, timeout_seconds: int=600)` | Python 对象生命周期或协议方法。 |
| `async run(self, args: Sequence[str], process_key: str, cwd: Path \| str \| None=None, env: dict[str, str] \| None=None, on_stdout_line: Callable[[str], None] \| None=None, on_stderr_line: Callable[[str], None] \| None=None, stdin_text: str \| None=None)` | 执行 provider、编排流程、事件或外部消息处理。 |
| `async _run_windows_powershell(self, command: str, args: Sequence[str], cwd: Path \| str \| None, env: dict[str, str], stdin_text: str \| None)` | 执行 provider、编排流程、事件或外部消息处理。 |
| `async _run_windows_powershell_sync(self, command: str, args: Sequence[str], cwd: Path \| str \| None, env: dict[str, str], on_stdout_line: Callable[[str], None] \| None, on_stderr_line: Callable[[str], None] \| None, stdin_text: str \| None)` | 执行 provider、编排流程、事件或外部消息处理。 |
| `async _communicate(process: asyncio.subprocess.Process, on_stdout_line: Callable[[str], None] \| None, on_stderr_line: Callable[[str], None] \| None, stdin_text: str \| None=None)` | 所属服务/类型的辅助方法。 |

### `pocketStudio/services/agent_service.py`

业务领域服务层，封装 agent、team、queue、project、task、schedule 等核心逻辑。

#### `AgentService`

类、数据模型、服务对象或异常类型。

| Method | 用法 |
|---|---|
| `__init__(self, db: Database, settings: Settings)` | Python 对象生命周期或协议方法。 |
| `create(self, payload: AgentCreate)` | 创建资源、安装内容或追加关系。 |
| `get(self, agent_id: str)` | 读取单个资源、状态或派生视图。 |
| `list(self)` | 列出资源集合或查询结果。 |
| `delete(self, agent_id: str)` | 删除资源或清理状态。 |
| `ensure_workspace(self, workspace: Path, payload: AgentCreate \| None=None)` | 校验输入或修复必需的运行状态。 |
| `workspace_status(self, agent_id: str, repair: bool=False)` | 所属服务/类型的辅助方法。 |
| `get_system_prompt_file(self, agent_id: str)` | 读取单个资源、状态或派生视图。 |
| `save_system_prompt_file(self, agent_id: str, content: str)` | 更新或持久化已有资源。 |
| `get_heartbeat_file(self, agent_id: str)` | 读取单个资源、状态或派生视图。 |
| `save_heartbeat_file(self, agent_id: str, content: str \| None=None, enabled: bool \| None=None, interval: int \| None=None)` | 更新或持久化已有资源。 |
| `build_system_prompt(self, agent_id: str, teammates: str='')` | 所属服务/类型的辅助方法。 |
| `load_memory_index(self, agent_id: str)` | 所属服务/类型的辅助方法。 |
| `list_memory_files(self, agent_id: str)` | 列出资源集合或查询结果。 |
| `get_memory_file(self, agent_id: str, relative_path: str)` | 读取单个资源、状态或派生视图。 |
| `save_memory_file(self, agent_id: str, relative_path: str, content: str, create_dirs: bool=True)` | 更新或持久化已有资源。 |
| `delete_memory_file(self, agent_id: str, relative_path: str)` | 删除资源或清理状态。 |
| `list_skills(self, agent_id: str)` | 列出资源集合或查询结果。 |
| `install_skill_placeholder(self, agent_id: str, ref: str)` | 创建资源、安装内容或追加关系。 |
| `scan_memory_tree(cls, dir_path: Path, relative_path: str)` | 所属服务/类型的辅助方法。 |
| `_format_memory_tree(cls, folder: dict, indent: int=0)` | 转换、解析或格式化内部数据。 |
| `ensure_tool_skills_link(source: Path, target: Path)` | 校验输入或修复必需的运行状态。 |
| `_sync_skill_tree(source: Path, target: Path)` | 所属服务/类型的辅助方法。 |
| `_sync_root_skills(self, target: Path)` | 所属服务/类型的辅助方法。 |
| `_root_skills_dir()` | 所属服务/类型的辅助方法。 |
| `_workspace_checks(workspace: Path)` | 所属服务/类型的辅助方法。 |
| `_safe_name(value: str)` | 所属服务/类型的辅助方法。 |
| `_resolve_memory_path(memory_dir: Path, relative_path: str)` | 所属服务/类型的辅助方法。 |
| `_parse_frontmatter(content: str)` | 转换、解析或格式化内部数据。 |
| `_default_heartbeat_interval(self)` | 所属服务/类型的辅助方法。 |
| `_sync_agent_settings(self, agent: Agent)` | 所属服务/类型的辅助方法。 |
| `_remove_agent_settings(self, agent_id: str)` | 删除资源或清理状态。 |
| `_to_agent(row)` | 转换、解析或格式化内部数据。 |

### `pocketStudio/services/channel_service.py`

业务领域服务层，封装 agent、team、queue、project、task、schedule 等核心逻辑。

#### `PairingResult`

类、数据模型、服务对象或异常类型。

#### `RoutedChannelMessage`

类、数据模型、服务对象或异常类型。

#### `ChannelService`

类、数据模型、服务对象或异常类型。

| Method | 用法 |
|---|---|
| `__init__(self, db: Database, agents: AgentService, teams: TeamService)` | Python 对象生命周期或协议方法。 |
| `pairing_state(self)` | 所属服务/类型的辅助方法。 |
| `ensure_sender_paired(self, channel: str, sender_id: str, sender: str)` | 校验输入或修复必需的运行状态。 |
| `approve(self, code: str \| None)` | 所属服务/类型的辅助方法。 |
| `revoke(self, channel: str, sender_id: str)` | 删除资源或清理状态。 |
| `dismiss_pending(self, code: str)` | 所属服务/类型的辅助方法。 |
| `route_message(self, channel: str, sender_id: str, text: str, explicit_agent: str \| None=None)` | 所属服务/类型的辅助方法。 |
| `resolve_target(self, tag: str)` | 所属服务/类型的辅助方法。 |
| `get_default(self, channel: str, sender_id: str)` | 读取单个资源、状态或派生视图。 |
| `save_default(self, channel: str, sender_id: str, target: str)` | 更新或持久化已有资源。 |
| `clear_default(self, channel: str, sender_id: str)` | 删除资源或清理状态。 |
| `_unique_pairing_code(self)` | 所属服务/类型的辅助方法。 |

### `pocketStudio/services/chat_service.py`

业务领域服务层，封装 agent、team、queue、project、task、schedule 等核心逻辑。

#### `ChatService`

类、数据模型、服务对象或异常类型。

| Method | 用法 |
|---|---|
| `__init__(self, db: Database, events: EventService)` | Python 对象生命周期或协议方法。 |
| `post(self, team_id: str, payload: ChatMessageCreate)` | 所属服务/类型的辅助方法。 |
| `get(self, message_id: int)` | 读取单个资源、状态或派生视图。 |
| `list(self, team_id: str, limit: int=100, since: int=0, sender: str \| None=None, query: str \| None=None)` | 列出资源集合或查询结果。 |
| `archives(self)` | 所属服务/类型的辅助方法。 |
| `prune(self, older_than_ms: int)` | 队列、响应或消息流转操作。 |
| `_to_message(row)` | 转换、解析或格式化内部数据。 |

### `pocketStudio/services/event_service.py`

业务领域服务层，封装 agent、team、queue、project、task、schedule 等核心逻辑。

#### `EventService`

类、数据模型、服务对象或异常类型。

| Method | 用法 |
|---|---|
| `__init__(self, db: Database, settings: Settings \| None=None)` | Python 对象生命周期或协议方法。 |
| `emit(self, event_type: str, payload: dict)` | 执行 provider、编排流程、事件或外部消息处理。 |
| `add_listener(self, listener: Callable[[Event], None])` | 创建资源、安装内容或追加关系。 |
| `remove_listener(self, listener: Callable[[Event], None])` | 删除资源或清理状态。 |
| `list(self, limit: int=100, since: int=0)` | 列出资源集合或查询结果。 |
| `log_lines(self, limit: int=100)` | 所属服务/类型的辅助方法。 |
| `log_records(self, limit: int=100, event_type: str \| None=None, contains: str \| None=None)` | 所属服务/类型的辅助方法。 |
| `office_event(self, event: Event)` | 所属服务/类型的辅助方法。 |
| `_office_base(event: Event, payload: dict, timestamp: int)` | 所属服务/类型的辅助方法。 |
| `_str_payload(payload: dict, *keys: str)` | 构造 API/兼容层响应或请求载荷。 |
| `_agent_progress_type(payload: dict)` | 所属服务/类型的辅助方法。 |
| `_append_log(self, event_type: str, payload_json: str, created_at: str \| None=None)` | 所属服务/类型的辅助方法。 |
| `_notify(self, event: Event)` | 所属服务/类型的辅助方法。 |
| `_parse_log_line(line: str)` | 转换、解析或格式化内部数据。 |
| `_event_timestamp_ms(value: str)` | 所属服务/类型的辅助方法。 |
| `_to_event(row)` | 转换、解析或格式化内部数据。 |

### `pocketStudio/services/heartbeat_service.py`

业务领域服务层，封装 agent、team、queue、project、task、schedule 等核心逻辑。

#### `HeartbeatService`

类、数据模型、服务对象或异常类型。

| Method | 用法 |
|---|---|
| `__init__(self, db: Database, agents: AgentService, events: EventService, settings: Settings)` | Python 对象生命周期或协议方法。 |
| `fire_due(self, queue: QueueService, now_ms: int \| None=None)` | 控制后台 worker、调度器或处理流程。 |
| `tick(self, queue: QueueService, now_ms: int \| None=None, agent_id: str \| None=None, force: bool=False)` | 控制后台 worker、调度器或处理流程。 |
| `clear_state(self, agent_id: str \| None=None)` | 删除资源或清理状态。 |
| `snapshot(self, now_ms: int \| None=None)` | 所属服务/类型的辅助方法。 |
| `base_interval_seconds(self)` | 所属服务/类型的辅助方法。 |
| `_is_due(self, agent, now_ms: int)` | 所属服务/类型的辅助方法。 |
| `_fire_agent(self, queue: QueueService, agent, now_ms: int)` | 控制后台 worker、调度器或处理流程。 |
| `_read_prompt(workspace: Path)` | 所属服务/类型的辅助方法。 |

### `pocketStudio/services/orchestrator.py`

业务领域服务层，封装 agent、team、queue、project、task、schedule 等核心逻辑。

| Function | 用法 |
|---|---|
| `merge_dicts(left: dict[str, Any], right: dict[str, Any])` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |

#### `TeamActions`

类、数据模型、服务对象或异常类型。

| Method | 用法 |
|---|---|
| `__init__(self, mentions: list[tuple[str, str]], chatrooms: list[tuple[str, str]])` | Python 对象生命周期或协议方法。 |

#### `WorkflowState(TypedDict)`

类、数据模型、服务对象或异常类型。

#### `Orchestrator`

类、数据模型、服务对象或异常类型。

| Method | 用法 |
|---|---|
| `__init__(self, agents: AgentService, teams: TeamService, queue: QueueService, chat: ChatService, events: EventService, providers: ProviderRegistry, projects: ProjectService \| None=None, workflows: WorkflowService \| None=None)` | Python 对象生命周期或协议方法。 |
| `enqueue(self, payload: MessageCreate)` | 队列、响应或消息流转操作。 |
| `async process_one(self, newest: bool=False)` | 控制后台 worker、调度器或处理流程。 |
| `async process_message(self, message_id: int)` | 控制后台 worker、调度器或处理流程。 |
| `async _dispatch(self, message: QueueMessage)` | 执行 provider、编排流程、事件或外部消息处理。 |
| `async _run_team(self, message: QueueMessage, team: Team)` | 执行 provider、编排流程、事件或外部消息处理。 |
| `async _run_workflow(self, message: QueueMessage, team: Team, agents: list[Agent], workflow)` | 执行 provider、编排流程、事件或外部消息处理。 |
| `_workflow_node_input(team: Team, workflow_id: str, original_request: str, node, predecessor_ids: list[str], outputs: dict[str, str])` | 所属服务/类型的辅助方法。 |
| `_langchain_runnable_for_agent(self, agent: Agent)` | 所属服务/类型的辅助方法。 |
| `_build_langgraph_workflow(self, *, team: Team, workflow_id: str, message: QueueMessage, agents: list[Agent], node_by_id: dict[str, Any], agent_by_id: dict[str, Agent], predecessors: dict[str, list[str]], outgoing: dict[str, list[str]], edge_pairs: list[tuple[str, str]], conditional_edges: list[Any], entrypoint: str)` | 所属服务/类型的辅助方法。 |
| `_compile_workflow_routing_function(node)` | 所属服务/类型的辅助方法。 |
| `_route_from_output(output: str, conditions: list[str])` | 所属服务/类型的辅助方法。 |
| `async _run_iterative_rounds(self, team: Team, message: QueueMessage, agents: list[Agent], seed_runs: list[AgentRun], max_rounds: int)` | 执行 provider、编排流程、事件或外部消息处理。 |
| `_agent_lookup(agents: list[Agent])` | 所属服务/类型的辅助方法。 |
| `_mentions_from_runs(self, team: Team, runs: list[AgentRun], agents: list[Agent])` | 所属服务/类型的辅助方法。 |
| `_member_chain_input(self, team: Team, original_request: str, leader_run: AgentRun, previous_member_runs: list[AgentRun], member_id: str)` | 所属服务/类型的辅助方法。 |
| `_leader_summary_input(self, team: Team, original_request: str, leader_run: AgentRun, member_runs: list[AgentRun])` | 所属服务/类型的辅助方法。 |
| `_format_runs(runs: list[AgentRun])` | 转换、解析或格式化内部数据。 |
| `async _handle_team_tags(self, team: Team, run: AgentRun, message: QueueMessage, agents: list[Agent], enqueue_mentions: bool=True, process_chatrooms: bool=True)` | 执行 provider、编排流程、事件或外部消息处理。 |
| `async _handle_direct_agent_team_tags(self, agent: Agent, run: AgentRun, message: QueueMessage)` | 执行 provider、编排流程、事件或外部消息处理。 |
| `_broadcast_chatroom(self, team: Team, from_agent: str, content: str, agents: list[Agent], parent: QueueMessage)` | 执行 provider、编排流程、事件或外部消息处理。 |
| `_post_chatroom_run_outputs(self, team: Team, runs: list[AgentRun])` | 所属服务/类型的辅助方法。 |
| `_is_chatroom_origin(message: QueueMessage)` | 所属服务/类型的辅助方法。 |
| `_team_child_metadata(parent: QueueMessage \| None, *, team: Team, from_agent: str, kind: str, to_agent: str)` | 所属服务/类型的辅助方法。 |
| `_order_agents_for_team(team: Team, agents: list[Agent])` | 所属服务/类型的辅助方法。 |
| `_teams_for_agent(self, agent_id: str)` | 所属服务/类型的辅助方法。 |
| `_resolve_team_context_for_agent(agent_id: str, teams: list[Team])` | 所属服务/类型的辅助方法。 |
| `_resolve_team_for_tag(team_id: str, teams: list[Team], agent_id: str)` | 所属服务/类型的辅助方法。 |
| `async _run_agent(self, agent: Agent, input_text: str, context: list[str], *, message_id: int \| str \| None=None, session_id: str \| None=None, run_id: str \| None=None)` | 执行 provider、编排流程、事件或外部消息处理。 |
| `_agent_for_message(self, agent_id: str, message: QueueMessage)` | 所属服务/类型的辅助方法。 |
| `_parse_target(target: str)` | 转换、解析或格式化内部数据。 |
| `decode_result(message: QueueMessage)` | 转换、解析或格式化内部数据。 |

### `pocketStudio/services/plugin_service.py`

业务领域服务层，封装 agent、team、queue、project、task、schedule 等核心逻辑。

#### `HookResult`

类、数据模型、服务对象或异常类型。

#### `LoadedPlugin`

类、数据模型、服务对象或异常类型。

#### `PluginContext`

类、数据模型、服务对象或异常类型。

| Method | 用法 |
|---|---|
| `__init__(self, name: str, home: Path, events: EventService)` | Python 对象生命周期或协议方法。 |
| `on(self, event_type: str, handler: Callable[[dict[str, Any]], None])` | 所属服务/类型的辅助方法。 |
| `log(self, level: str, message: str)` | 所属服务/类型的辅助方法。 |
| `get_pocketstudio_home(self)` | 读取单个资源、状态或派生视图。 |

#### `PluginService`

类、数据模型、服务对象或异常类型。

| Method | 用法 |
|---|---|
| `__init__(self, settings: Settings, events: EventService)` | Python 对象生命周期或协议方法。 |
| `plugins_path(self)` | 所属服务/类型的辅助方法。 |
| `list_plugins(self, reload: bool=False)` | 列出资源集合或查询结果。 |
| `load_plugins(self, reload: bool=False)` | 所属服务/类型的辅助方法。 |
| `run_incoming_hooks(self, message: str, context: dict[str, Any])` | 执行 provider、编排流程、事件或外部消息处理。 |
| `run_outgoing_hooks(self, message: str, context: dict[str, Any])` | 执行 provider、编排流程、事件或外部消息处理。 |
| `broadcast_event(self, event_type: str, payload: dict[str, Any])` | 执行 provider、编排流程、事件或外部消息处理。 |
| `handle_event(self, event: Event)` | 执行 provider、编排流程、事件或外部消息处理。 |
| `_run_hook(self, hook_name: str, message: str, context: dict[str, Any])` | 执行 provider、编排流程、事件或外部消息处理。 |
| `_apply_hook(message: str, hook: dict[str, Any], context: dict[str, Any])` | 所属服务/类型的辅助方法。 |
| `_load_module(self, plugin_dir: Path, module_path: Path)` | 所属服务/类型的辅助方法。 |
| `_activate(self, plugin: LoadedPlugin)` | 所属服务/类型的辅助方法。 |
| `_module_hooks(module: ModuleType \| None)` | 所属服务/类型的辅助方法。 |
| `_apply_callable_hook(message: str, hook: Callable[[str, dict[str, Any]], Any], context: dict[str, Any])` | 所属服务/类型的辅助方法。 |
| `_mark_plugin(metadata: dict[str, Any], plugin_name: str)` | 所属服务/类型的辅助方法。 |

### `pocketStudio/services/project_service.py`

业务领域服务层，封装 agent、team、queue、project、task、schedule 等核心逻辑。

#### `ProjectService`

类、数据模型、服务对象或异常类型。

| Method | 用法 |
|---|---|
| `__init__(self, db: Database, events: EventService)` | Python 对象生命周期或协议方法。 |
| `list_projects(self)` | 列出资源集合或查询结果。 |
| `create_project(self, payload: ProjectCreate)` | 创建资源、安装内容或追加关系。 |
| `get_project(self, project_id: str)` | 读取单个资源、状态或派生视图。 |
| `update_project(self, project_id: str, payload: ProjectCreate)` | 更新或持久化已有资源。 |
| `project_agent_workspace(self, project_id: str, agent_id: str)` | 所属服务/类型的辅助方法。 |
| `workspace_status(self, project_id: str, repair: bool=False)` | 所属服务/类型的辅助方法。 |
| `ensure_working_directory(path: Path)` | 校验输入或修复必需的运行状态。 |
| `_workspace_checks(workspace: Path)` | 所属服务/类型的辅助方法。 |
| `delete_project(self, project_id: str)` | 删除资源或清理状态。 |
| `task_count(self, project_id: str)` | 所属服务/类型的辅助方法。 |
| `comment_count(self, task_id: int)` | 所属服务/类型的辅助方法。 |
| `list_comments(self, task_id: int)` | 列出资源集合或查询结果。 |
| `create_comment(self, task_id: int, payload: TaskCommentCreate)` | 创建资源、安装内容或追加关系。 |
| `delete_comment(self, comment_id: str)` | 删除资源或清理状态。 |
| `_project_id(name: str)` | 所属服务/类型的辅助方法。 |
| `_workspace_path(workspace: str \| None)` | 所属服务/类型的辅助方法。 |
| `generate_prefix(name: str)` | 所属服务/类型的辅助方法。 |
| `_next_global_task_number(self)` | 所属服务/类型的辅助方法。 |
| `_to_project(row)` | 转换、解析或格式化内部数据。 |
| `_legacy_default_workspace(project_id: str)` | 所属服务/类型的辅助方法。 |
| `_to_comment(row)` | 转换、解析或格式化内部数据。 |

### `pocketStudio/services/queue_service.py`

业务领域服务层，封装 agent、team、queue、project、task、schedule 等核心逻辑。

#### `QueueService`

类、数据模型、服务对象或异常类型。

| Method | 用法 |
|---|---|
| `__init__(self, db: Database, events: EventService, settings: Settings, responses: ResponseService \| None=None, plugins: PluginService \| None=None)` | Python 对象生命周期或协议方法。 |
| `enqueue(self, payload: MessageCreate)` | 队列、响应或消息流转操作。 |
| `get(self, message_id: int)` | 读取单个资源、状态或派生视图。 |
| `list(self, limit: int=100, status: MessageStatus \| None=None)` | 列出资源集合或查询结果。 |
| `find_by_client_message_id(self, client_message_id: str, limit: int=1000)` | 所属服务/类型的辅助方法。 |
| `grouped_chatroom_messages(self, limit: int=100, status: MessageStatus \| None=None)` | 所属服务/类型的辅助方法。 |
| `status(self)` | 所属服务/类型的辅助方法。 |
| `diagnostics(self, stale_threshold_seconds: int \| None=None)` | 所属服务/类型的辅助方法。 |
| `agent_status(self)` | 所属服务/类型的辅助方法。 |
| `next_queued(self, newest: bool=False)` | 所属服务/类型的辅助方法。 |
| `recover_stale_messages(self, threshold_seconds: int \| None=None)` | 队列、响应或消息流转操作。 |
| `mark_running(self, message_id: int)` | 所属服务/类型的辅助方法。 |
| `mark_done(self, message_id: int, result: str)` | 所属服务/类型的辅助方法。 |
| `mark_failed(self, message_id: int, error: str)` | 所属服务/类型的辅助方法。 |
| `list_dead(self, limit: int=100)` | 列出资源集合或查询结果。 |
| `dead_payloads(self, limit: int=100)` | 构造 API/兼容层响应或请求载荷。 |
| `retry_dead(self, message_id: int)` | 队列、响应或消息流转操作。 |
| `retry_message(self, message_id: int)` | 队列、响应或消息流转操作。 |
| `delete_dead(self, message_id: int)` | 删除资源或清理状态。 |
| `insert_agent_message(self, agent_id: str, role: str, content: str, message_id: str, sender: str='', channel: str='web', created_at: int \| None=None)` | 所属服务/类型的辅助方法。 |
| `get_agent_messages(self, agent_id: str, limit: int=100, since_id: int=0)` | 读取单个资源、状态或派生视图。 |
| `get_all_agent_messages(self, limit: int=100, since_id: int=0)` | 读取单个资源、状态或派生视图。 |
| `reset_agent(self, agent_id: str)` | 所属服务/类型的辅助方法。 |
| `recent_responses(self, limit: int=20)` | 所属服务/类型的辅助方法。 |
| `enqueue_response(self, message_id: str, channel: str, sender: str, message: str, original_message: str, agent: str \| None=None, sender_id: str \| None=None, files: list[str] \| None=None, metadata: dict \| None=None)` | 队列、响应或消息流转操作。 |
| `get_responses_for_channel(self, channel: str)` | 读取单个资源、状态或派生视图。 |
| `ack_response(self, response_id: int)` | 队列、响应或消息流转操作。 |
| `prune_acked_responses(self, older_than_ms: int=86400000)` | 队列、响应或消息流转操作。 |
| `prune_completed_messages(self, older_than_ms: int=86400000)` | 队列、响应或消息流转操作。 |
| `enqueue_responses_from_message(self, message: QueueMessage)` | 队列、响应或消息流转操作。 |
| `processing_payloads(self)` | 控制后台 worker、调度器或处理流程。 |
| `_dead_payload(message: QueueMessage)` | 构造 API/兼容层响应或请求载荷。 |
| `_target_label(target: str)` | 所属服务/类型的辅助方法。 |
| `_is_chatroom_message(message: QueueMessage)` | 所属服务/类型的辅助方法。 |
| `_combined_chatroom_payload(messages: list[QueueMessage])` | 构造 API/兼容层响应或请求载荷。 |
| `_pending_response_count(self)` | 所属服务/类型的辅助方法。 |
| `_message_summary(row)` | 所属服务/类型的辅助方法。 |
| `_timestamp_ms(value: str)` | 所属服务/类型的辅助方法。 |
| `_to_message(row)` | 转换、解析或格式化内部数据。 |
| `_to_agent_message(row)` | 转换、解析或格式化内部数据。 |
| `_to_response(row)` | 转换、解析或格式化内部数据。 |
| `_response_api_payload(response: ResponseJob)` | 构造 API/兼容层响应或请求载荷。 |
| `_prepare_team_response_text(run: dict)` | 所属服务/类型的辅助方法。 |

### `pocketStudio/services/response_service.py`

业务领域服务层，封装 agent、team、queue、project、task、schedule 等核心逻辑。

#### `PreparedResponse`

类、数据模型、服务对象或异常类型。

#### `ResponseService`

类、数据模型、服务对象或异常类型。

| Method | 用法 |
|---|---|
| `__init__(self, settings: Settings, plugins: PluginService \| None=None)` | Python 对象生命周期或协议方法。 |
| `prepare(self, response: str, existing_files: list[str] \| None=None, context: dict \| None=None)` | 所属服务/类型的辅助方法。 |
| `collect_files(response: str)` | 所属服务/类型的辅助方法。 |
| `_save_long_response(self, response: str)` | 更新或持久化已有资源。 |

### `pocketStudio/services/schedule_service.py`

业务领域服务层，封装 agent、team、queue、project、task、schedule 等核心逻辑。

#### `ScheduleService`

类、数据模型、服务对象或异常类型。

| Method | 用法 |
|---|---|
| `__init__(self, db: Database, events: EventService)` | Python 对象生命周期或协议方法。 |
| `list(self, agent_id: str \| None=None)` | 列出资源集合或查询结果。 |
| `schedule_status(self, schedule: Schedule, now: datetime \| None=None)` | 所属服务/类型的辅助方法。 |
| `next_fire_at(self, schedule: Schedule, now: datetime \| None=None)` | 所属服务/类型的辅助方法。 |
| `create(self, payload: ScheduleCreate)` | 创建资源、安装内容或追加关系。 |
| `get(self, schedule_id: str)` | 读取单个资源、状态或派生视图。 |
| `update(self, schedule_id: str, payload: ScheduleCreate)` | 更新或持久化已有资源。 |
| `delete(self, schedule_id: str)` | 删除资源或清理状态。 |
| `validate(self, payload: ScheduleCreate, now: datetime \| None=None)` | 校验输入或修复必需的运行状态。 |
| `fire(self, schedule_id: str, queue: QueueService, now: datetime \| None=None, force: bool=False)` | 控制后台 worker、调度器或处理流程。 |
| `fire_due(self, queue: QueueService, now: datetime \| None=None)` | 控制后台 worker、调度器或处理流程。 |
| `_fire(self, queue: QueueService, schedule: Schedule, now: datetime)` | 控制后台 worker、调度器或处理流程。 |
| `_validate_payload(self, payload: ScheduleCreate)` | 校验输入或修复必需的运行状态。 |
| `_ensure_label_available(self, label: str, exclude_id: str \| None=None)` | 校验输入或修复必需的运行状态。 |
| `_find_row(self, identifier: str)` | 所属服务/类型的辅助方法。 |
| `_parse_datetime(value: str)` | 转换、解析或格式化内部数据。 |
| `_cron_matches(expression: str, now: datetime)` | 所属服务/类型的辅助方法。 |
| `_field_matches(field: str, value: int, minimum: int, maximum: int)` | 所属服务/类型的辅助方法。 |
| `_field_is_valid(field: str, minimum: int, maximum: int)` | 所属服务/类型的辅助方法。 |
| `_range(value: str)` | 所属服务/类型的辅助方法。 |
| `_epoch_ms(value: datetime)` | 所属服务/类型的辅助方法。 |
| `_to_schedule(row)` | 转换、解析或格式化内部数据。 |

### `pocketStudio/services/settings_service.py`

业务领域服务层，封装 agent、team、queue、project、task、schedule 等核心逻辑。

#### `SettingsValidationError(ValueError)`

类、数据模型、服务对象或异常类型。

#### `SettingsService`

类、数据模型、服务对象或异常类型。

| Method | 用法 |
|---|---|
| `__init__(self, db: Database, settings: Settings)` | Python 对象生命周期或协议方法。 |
| `snapshot(self)` | 所属服务/类型的辅助方法。 |
| `update(self, payload: dict[str, Any])` | 更新或持久化已有资源。 |
| `preview_update(self, payload: dict[str, Any])` | 所属服务/类型的辅助方法。 |
| `validate(self, payload: dict[str, Any])` | 校验输入或修复必需的运行状态。 |
| `_validate_object(payload: dict[str, Any], key: str)` | 校验输入或修复必需的运行状态。 |
| `_validate_mapping(payload: dict[str, Any], key: str)` | 校验输入或修复必需的运行状态。 |
| `write(self, settings: dict[str, Any])` | 更新或持久化已有资源。 |
| `_file_settings(self)` | 所属服务/类型的辅助方法。 |
| `_legacy_db_settings(self)` | 所属服务/类型的辅助方法。 |
| `ensure_setup_dirs(self, settings: dict[str, Any])` | 校验输入或修复必需的运行状态。 |
| `backup_info(self)` | 所属服务/类型的辅助方法。 |
| `restore_backup(self)` | 所属服务/类型的辅助方法。 |
| `backup_path(self)` | 所属服务/类型的辅助方法。 |
| `_backup_current_settings(self)` | 所属服务/类型的辅助方法。 |
| `_merge(cls, current: Any, update: Any)` | 所属服务/类型的辅助方法。 |
| `_normalize_paths(cls, payload: dict[str, Any])` | 转换、解析或格式化内部数据。 |
| `_expand_home_path(value: str)` | 所属服务/类型的辅助方法。 |
| `_known_sections(settings: dict[str, Any])` | 所属服务/类型的辅助方法。 |
| `_diff(cls, current: Any, next_value: Any, prefix: str='')` | 所属服务/类型的辅助方法。 |
| `_repair_json(raw: str)` | 校验输入或修复必需的运行状态。 |

### `pocketStudio/services/task_service.py`

业务领域服务层，封装 agent、team、queue、project、task、schedule 等核心逻辑。

#### `TaskService`

类、数据模型、服务对象或异常类型。

| Method | 用法 |
|---|---|
| `__init__(self, db: Database, events: EventService)` | Python 对象生命周期或协议方法。 |
| `create(self, payload: TaskCreate)` | 创建资源、安装内容或追加关系。 |
| `get(self, task_id: int)` | 读取单个资源、状态或派生视图。 |
| `list(self, project_id: str \| None=None, status: str \| None=None, assignee: str \| None=None, query: str \| None=None)` | 列出资源集合或查询结果。 |
| `update(self, task_id: int, payload: TaskCreate)` | 更新或持久化已有资源。 |
| `update_status(self, task_id: int, status: str)` | 更新或持久化已有资源。 |
| `reorder(self, columns: dict[str, list[str]])` | 所属服务/类型的辅助方法。 |
| `delete(self, task_id: int)` | 删除资源或清理状态。 |
| `_to_task(row)` | 转换、解析或格式化内部数据。 |
| `_next_number(self, project_id: str \| None)` | 所属服务/类型的辅助方法。 |
| `_next_position(self, status: str)` | 所属服务/类型的辅助方法。 |

### `pocketStudio/services/team_routing.py`

业务领域服务层，封装 agent、team、queue、project、task、schedule 等核心逻辑。

| Function | 用法 |
|---|---|
| `extract_bracket_tags(text: str, prefix: str)` | 转换、解析或格式化内部数据。 |
| `strip_bracket_tags(text: str, prefix: str)` | 转换、解析或格式化内部数据。 |
| `convert_tags_to_readable(text: str, from_agent: str \| None=None)` | 转换、解析或格式化内部数据。 |
| `_convert_prefix_tags(text: str, prefix: str, readable_prefix: str)` | 转换、解析或格式化内部数据。 |

#### `BracketTag`

类、数据模型、服务对象或异常类型。

### `pocketStudio/services/team_service.py`

业务领域服务层，封装 agent、team、queue、project、task、schedule 等核心逻辑。

#### `TeamService`

类、数据模型、服务对象或异常类型。

| Method | 用法 |
|---|---|
| `__init__(self, db: Database, settings: Settings \| None=None)` | Python 对象生命周期或协议方法。 |
| `create(self, payload: TeamCreate)` | 创建资源、安装内容或追加关系。 |
| `get(self, team_id: str)` | 读取单个资源、状态或派生视图。 |
| `list(self)` | 列出资源集合或查询结果。 |
| `delete(self, team_id: str)` | 删除资源或清理状态。 |
| `add_member(self, team_id: str, agent_id: str)` | 创建资源、安装内容或追加关系。 |
| `remove_member(self, team_id: str, agent_id: str)` | 删除资源或清理状态。 |
| `set_leader(self, team_id: str, agent_id: str)` | 更新或持久化已有资源。 |
| `_sync_team_settings(self, team: Team)` | 所属服务/类型的辅助方法。 |
| `_remove_team_settings(self, team_id: str)` | 删除资源或清理状态。 |
| `_to_team(row)` | 转换、解析或格式化内部数据。 |

### `pocketStudio/services/worker_service.py`

业务领域服务层，封装 agent、team、queue、project、task、schedule 等核心逻辑。

#### `WorkerState`

类、数据模型、服务对象或异常类型。

#### `WorkerService`

类、数据模型、服务对象或异常类型。

| Method | 用法 |
|---|---|
| `__init__(self, orchestrator: Orchestrator, schedules: ScheduleService, heartbeat: HeartbeatService, events: EventService, settings: Settings)` | Python 对象生命周期或协议方法。 |
| `start(self)` | 控制后台 worker、调度器或处理流程。 |
| `async stop(self)` | 控制后台 worker、调度器或处理流程。 |
| `pause(self)` | 控制后台 worker、调度器或处理流程。 |
| `resume(self)` | 控制后台 worker、调度器或处理流程。 |
| `async restart(self)` | 控制后台 worker、调度器或处理流程。 |
| `async process_once(self, force: bool=False)` | 控制后台 worker、调度器或处理流程。 |
| `snapshot(self)` | 所属服务/类型的辅助方法。 |
| `maintenance(self, older_than_ms: int=86400000, stale_threshold_seconds: int \| None=None, prune_chats: bool=False)` | 所属服务/类型的辅助方法。 |
| `_health(self, queue_status: dict)` | 所属服务/类型的辅助方法。 |
| `async _process_fired_messages(self, messages: list[QueueMessage])` | 控制后台 worker、调度器或处理流程。 |
| `async _process_next_available(self, newest: bool=False)` | 控制后台 worker、调度器或处理流程。 |
| `_record_failure(self, exc: Exception)` | 所属服务/类型的辅助方法。 |
| `async _run(self)` | 执行 provider、编排流程、事件或外部消息处理。 |

### `pocketStudio/services/workflow_service.py`

业务领域服务层，封装 agent、team、queue、project、task、schedule 等核心逻辑。

#### `WorkflowService`

类、数据模型、服务对象或异常类型。

| Method | 用法 |
|---|---|
| `__init__(self, db: Database, teams: TeamService)` | Python 对象生命周期或协议方法。 |
| `create(self, team_id: str, payload: TeamWorkflowCreate)` | 创建资源、安装内容或追加关系。 |
| `list(self, team_id: str)` | 列出资源集合或查询结果。 |
| `get(self, team_id: str, workflow_id: str)` | 读取单个资源、状态或派生视图。 |
| `active_for_team(self, team_id: str)` | 所属服务/类型的辅助方法。 |
| `update(self, team_id: str, workflow_id: str, payload: TeamWorkflowUpdate)` | 更新或持久化已有资源。 |
| `delete(self, team_id: str, workflow_id: str)` | 删除资源或清理状态。 |
| `export_json(self, team_id: str, workflow_id: str)` | 所属服务/类型的辅助方法。 |
| `import_json(self, team_id: str, payload: dict[str, Any])` | 所属服务/类型的辅助方法。 |
| `validate(self, team_id: str, definition: WorkflowDefinition)` | 校验输入或修复必需的运行状态。 |
| `_payload_from_import_json(payload: dict[str, Any])` | 构造 API/兼容层响应或请求载荷。 |
| `_validate_definition_for_team(self, team_id: str, definition: WorkflowDefinition)` | 校验输入或修复必需的运行状态。 |
| `graph_io(definition: WorkflowDefinition)` | 所属服务/类型的辅助方法。 |
| `terminal_nodes(definition: WorkflowDefinition)` | 所属服务/类型的辅助方法。 |
| `_topological_order(definition: WorkflowDefinition)` | 所属服务/类型的辅助方法。 |
| `_disable_other_workflows(self, team_id: str, workflow_id: str)` | 所属服务/类型的辅助方法。 |
| `_to_workflow(row)` | 转换、解析或格式化内部数据。 |

### `pocketStudio/utils/tag_parser.py`

项目模块。

| Function | 用法 |
|---|---|
| `split_candidate_ids(raw_ids: str)` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `extract_tags(text: str, prefix: str)` | 转换、解析或格式化内部数据。 |
| `strip_tags(text: str, prefix: str)` | 转换、解析或格式化内部数据。 |
| `get_directed_messages(leader_output: str, member_id: str)` | 读取单个资源、状态或派生视图。 |

### `pocketStudio/visualizer.py`

包入口或应用入口。

| Function | 用法 |
|---|---|
| `json_loads(body: str)` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `json_dumps(payload: dict[str, Any])` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `normalize_agents(raw: Any)` | 转换、解析或格式化内部数据。 |
| `normalize_teams(raw: Any)` | 转换、解析或格式化内部数据。 |
| `normalize_office_events(raw: Any)` | 转换、解析或格式化内部数据。 |
| `build_agent_states(agents: dict[str, dict[str, Any]], teams: dict[str, dict[str, Any]], events: list[dict[str, Any]], team_id: str \| None=None)` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `build_flows(events: list[dict[str, Any]], team_id: str \| None=None, limit: int=8)` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `visible_agent_ids(agents: dict[str, dict[str, Any]], teams: dict[str, dict[str, Any]], team_id: str \| None=None)` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `render_team_dashboard(snapshot: VisualizerSnapshot, team_id: str \| None=None)` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `render_team_lines(teams: dict[str, dict[str, Any]], team_id: str \| None=None)` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `render_chatroom(team_id: str, messages: list[dict[str, Any]], connected: bool=True, limit: int=50)` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `format_event(event: dict[str, Any])` | 转换、解析或格式化内部数据。 |
| `compact_text(text: str, max_length: int)` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `clear_terminal()` | 删除资源或清理状态。 |
| `_enable_windows_virtual_terminal()` | 模块级辅助函数；修改前请先查看调用方和测试契约。 |
| `_clear_windows_console()` | 删除资源或清理状态。 |
| `run_team_visualizer(client: VisualizerClient, team_id: str \| None=None, interval: float=1.0, once: bool=False, event_limit: int=80, clear_screen: bool=True)` | 执行 provider、编排流程、事件或外部消息处理。 |
| `run_chatroom_viewer(client: VisualizerClient, team_id: str, interval: float=1.0, once: bool=False, send: str \| None=None, sender: str='user', limit: int=50, clear_screen: bool=True)` | 执行 provider、编排流程、事件或外部消息处理。 |

#### `AgentVisualState`

类、数据模型、服务对象或异常类型。

#### `VisualizerSnapshot`

类、数据模型、服务对象或异常类型。

#### `VisualizerClient`

类、数据模型、服务对象或异常类型。

| Method | 用法 |
|---|---|
| `__init__(self, base_url: str \| None=None, timeout: float=5.0)` | Python 对象生命周期或协议方法。 |
| `get_json(self, path: str)` | 读取单个资源、状态或派生视图。 |
| `post_json(self, path: str, payload: dict[str, Any])` | 所属服务/类型的辅助方法。 |
| `snapshot(self, team_id: str \| None=None, event_limit: int=80)` | 所属服务/类型的辅助方法。 |
| `chat_messages(self, team_id: str, limit: int=50, since: int=0)` | 所属服务/类型的辅助方法。 |
| `post_chat(self, team_id: str, message: str, sender: str='user')` | 所属服务/类型的辅助方法。 |
