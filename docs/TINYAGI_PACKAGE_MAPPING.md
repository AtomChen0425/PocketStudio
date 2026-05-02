# pocketStudio vs TinyAGI packages mapping

Source inspected: <https://github.com/TinyAGI/tinyagi/tree/main/packages>  
Local upstream reference commit: `2db3a03a891b302c460f624d6c5a0523b8aa3528`  
Document date: 2026-05-01

This document maps the current `pocketStudio` Python implementation to the upstream TinyAGI `packages/` workspace. It is intentionally honest about gaps: the current project is an early Python backend plus an adapted TinyOffice frontend, not yet a full feature-for-feature TinyAGI port.

Status legend:

- `Implemented`: core behavior exists locally.
- `Partial`: a compatible slice exists, but TinyAGI has more behavior.
- `Stub`: endpoint/function returns placeholder data for UI compatibility.
- `Missing`: no local implementation yet.
- `Frontend only`: covered by copied/adapted `tinyoffice/`, not Python backend.

## Package-level Summary

| TinyAGI package | Upstream purpose | Current pocketStudio counterpart | Status |
|---|---|---|---|
| `packages/core` | Core config, queue DB, routing, agent invocation, adapters, memory, pairing, plugins, schedules, response handling | `pocketStudio/core`, `pocketStudio/models.py`, `pocketStudio/services`, `pocketStudio/providers` | Partial |
| `packages/server` | HTTP API and SSE server for TinyOffice and CLI control | `pocketStudio/main.py`, `pocketStudio/api/*` | Partial |
| `packages/teams` | Team routing, group conversation, chatroom orchestration | `pocketStudio/services/orchestrator.py`, `team_service.py`, `chat_service.py` | Partial |
| `packages/channels` | Discord, Telegram, WhatsApp, SSE client channel bridges | `ChannelService` foundations only | Missing/Partial |
| `packages/main` | Long-running daemon, queue processor loop, heartbeat, channel process manager | FastAPI lifespan plus `WorkerService`; local daemon pid/log supervisor via CLI; manual `POST /api/queue/process-next` remains available | Partial |
| `packages/cli` | `tinyagi` CLI for install/start/status/agents/teams/channels/logs/pairing/schedules | `pocketStudio/cli.py`, `pocketstudio` console script | Partial |
| `packages/visualizer` | Terminal visualizers for teams and chatroom | Adapted `tinyoffice/` web UI only | Frontend only |

## `packages/core`

Upstream `@tinyagi/core` is the heart of the system. It owns persistent config, SQLite queues, agent execution, routing, events, plugins, pairing, schedules, memory, and response/file handling.

| TinyAGI file | Upstream responsibility | pocketStudio mapping | Status | Notes / gaps |
|---|---|---|---|---|
| `core/src/types.ts` | Shared TypeScript types for agents, teams, messages, settings, queues, schedules, etc. | `pocketStudio/models.py` | Partial | Python models exist for agents, teams, messages, tasks, chat, events, projects, schedules, responses, pairing, and custom provider slices. Missing full TinyAGI channel and attachment types. |
| `core/src/config.ts` | `TINYAGI_HOME`, settings file, default settings, agents/teams resolution, model resolution | `pocketStudio/core/config.py`, `SettingsService`, `AgentService`, `TeamService`, `ProviderRegistry` | Partial | pocketStudio now uses `.pocketStudio/settings.json` as the primary settings store, keeps SQLite `app_settings` as a compatibility mirror/migration source, syncs agent/team CRUD into the file, and backs up/repairs common malformed JSON. New agents inherit the monitoring heartbeat interval. Env prefix is `POCKETSTUDIO_`; full npm `jsonrepair` parity remains incomplete. |
| `core/src/queues.ts` | SQLite queue schema and operations: incoming messages, processing, outgoing responses, dead messages, agent messages, chat messages, queue status, pruning/retry | `pocketStudio/core/database.py`, `QueueService`, `ChatService`, `EventService` | Partial | Has messages, responses, chat, events, retries, agent history, stale recovery, dead-letter retry/delete, per-agent queue status, response acking, and pruning. Still missing exact TinyAGI schema parity and channel delivery integrations. |
| `core/src/invoke.ts` | Spawn CLI harnesses, stream process output, kill active agent processes, invoke agents with provider adapters | `pocketStudio/providers/subprocess.py`, `pocketStudio/providers/*`, `Orchestrator._run_agent` | Partial | Basic subprocess harness, process registry, timeout, stdout line parsing, and kill hook exist. Missing richer streaming events, full process metadata, and Claude/OpenCode harnesses. |
| `core/src/adapters/types.ts` | Adapter contract for agent harnesses | `pocketStudio/providers/base.py`, `pocketStudio/providers/subprocess.py` | Partial | Basic provider request/response plus subprocess harness abstraction exists. Missing full TinyAGI streaming/process lifecycle fields. |
| `core/src/adapters/claude.ts` | Claude Code adapter | None | Missing | Needs Python adapter or subprocess harness. |
| `core/src/adapters/codex.ts` | Codex adapter | `pocketStudio/providers/codex.py` | Partial | Basic `codex exec resume --last ... --json` adapter and JSONL response extraction exist. Missing advanced resume/reset controls and full streaming event forwarding. |
| `core/src/adapters/opencode.ts` | OpenCode adapter | None | Missing | Needs Python adapter or subprocess harness. |
| `core/src/adapters/index.ts` | Adapter registry/selection | `pocketStudio/providers/registry.py` | Partial | Registry exists for `local`, built-in `openai`, built-in `codex`, SQLite-backed custom OpenAI-compatible providers, and custom Codex harness entries. Claude/OpenCode subprocess harnesses are still missing. |
| `core/src/router.ts` | Parse `@agent`/`@team`, route messages, find teams, mention handling | `Orchestrator._parse_target`, `_dispatch` | Partial | Supports direct `@agent:id`, `@team:id`, bare team id. Missing rich mention parsing, default routing, group/team membership routing, forwarding between agents. |
| `core/src/agent.ts` | Agent directory setup, AGENTS.md/system prompt, skills sync, built-in instructions | `AgentService` workspace helpers and compatibility routes | Partial | Creates workspace directories, AGENTS.md, heartbeat, SOUL placeholder, memory dir, skills dir, prompt file read/write, and prompt composition helper. Missing upstream template copying and exact Claude symlink behavior. |
| `core/src/memory.ts` | Scan agent memory directories and format memory index | `AgentService.load_memory_index`, `/api/agents/{id}/memory` | Partial | Scans markdown frontmatter for `name` and `summary`. Missing full folder tree object shape and memory skill behavior. |
| `core/src/plugins.ts` | Plugin loading and incoming/outgoing hooks/events | `PluginService`, `/api/plugins`, queue/response hook integration | Partial | JSON-config plugin discovery exists with incoming/outgoing text transforms and event broadcast records. Missing executable JS/TS/Python plugin modules, arbitrary event handlers, and full TinyAGI plugin API parity. |
| `core/src/pairing.ts` | Pairing state for external channel senders | `ChannelService`, `pocketStudio/api/compat.py`, pairing tables | Partial | Pairing persistence/API and sender enforcement for `/api/message` exist. Missing real channel clients and channel-specific delivery integration. |
| `core/src/schedules.ts` | Cron and one-shot schedules | `ScheduleService`, `WorkerService`, `pocketStudio/api/compat.py` | Partial | Schedule CRUD and worker-driven due execution exist for one-shot schedules and simple five-field cron. Missing exact Croner parity, live job registry, and richer validation. |
| `core/src/response.ts` | Long-response splitting, file tag collection, response streaming | `ResponseService`, `QueueService.enqueue_responses_from_message` | Partial | Long response preview/file persistence and `[send_file: ...]` collection exist. Missing plugin outgoing hooks, channel-specific delivery policies, and true streaming response pipeline. |
| `core/src/logging.ts` | Log file plus in-process event bus | `EventService`, `.pocketStudio/logs/pocketstudio.log`, `/api/events`, `/api/events/stream` | Partial | Events are persisted in SQLite, appended to a log file, and exposed through SSE. Missing severity-specific logging APIs and channel-specific log files. |
| `core/src/ids.ts` | Nanoid id generation | SQLite autoincrement and user-supplied ids | Partial | No shared prefixed id generator. |
| `core/src/index.ts` | Barrel exports | Python package imports | Implemented in spirit | No exact equivalent needed in Python yet. |

## `packages/server`

Upstream `@tinyagi/server` exposes the API that TinyOffice expects. pocketStudio uses FastAPI and currently implements a subset.

| TinyAGI file | Upstream responsibility | pocketStudio mapping | Status | Notes / gaps |
|---|---|---|---|---|
| `server/src/index.ts` | Hono server setup, route registration, status root | `pocketStudio/main.py` | Partial | FastAPI app exists with CORS, static UI, API routers. Missing full TinyAGI route surface. |
| `server/src/sse.ts` | Server-sent events stream | `pocketStudio/api/system.py` `/api/events/stream` | Partial | SSE exists and maps some events to TinyOffice event names. Missing full event taxonomy and replay controls. |
| `server/src/tasks-db.ts` | Tasks/projects/comments persistence helpers | `TaskService`, `ProjectService`, task/project/comment SQLite tables | Partial | Tasks, projects, comments, assignee/project fields, persisted reorder, project prefix/color generation, and TinyAGI-style task `number`/`identifier` now exist. Still missing exact separate `tasks.db` layout and JSON migration parity. |
| `server/src/routes/agents.ts` | Agent CRUD, custom provider config, settings-backed agents | `pocketStudio/api/agents.py`, `pocketStudio/api/compat.py` | Partial | Agent CRUD, heartbeat settings, reset, and custom provider compatibility routes exist. Missing exact original PUT shape and richer reset semantics for external harness sessions. |
| `server/src/routes/teams.ts` | Team CRUD and settings-backed teams | `pocketStudio/api/teams.py` | Partial | Team CRUD exists with `chain`/`fanout`, persisted `leader_agent`, compatibility `leader_agent` settings shape, and member add/remove/leader mutation routes. |
| `server/src/routes/messages.ts` | Incoming message endpoint, dispatch queue enqueue | `pocketStudio/api/messages.py` `/api/messages`, `pocketStudio/api/compat.py` `/api/message` | Partial | Local route is `/api/messages`; compatibility `/api/message` now enforces pairing for external channels and supports sticky default targets. Missing attachments and full channel metadata. |
| `server/src/routes/queue.ts` | Queue status, processing, kill, dead/retry/delete | `pocketStudio/api/messages.py`, `pocketStudio/api/compat.py`, `QueueService` | Partial | Queue list/get/process-next/status, dead retry/delete, stale recovery, processing list/kill-like reset, and pruning exist. Missing exact TinyAGI processing lifecycle and real subprocess kill. |
| `server/src/routes/agent-messages.ts` | Per-agent conversation history | `QueueService`, `pocketStudio/api/compat.py` | Partial | `agent_messages` table and route exist. Missing full upstream message metadata and channel-specific history semantics. |
| `server/src/routes/chatroom.ts` | Team chatroom messages | `pocketStudio/api/chat.py`, `ChatService` | Partial | Basic list/post exists. Missing original `from_agent` shape and team orchestration semantics. |
| `server/src/routes/chats.ts` | Chat archive/listing APIs | `ChatService.archives`, `/api/chats`, `/api/chats/{team_id}` | Partial | SQLite-backed chat archive listing and read endpoints exist. Missing Markdown file archive parity with upstream `CHATS_DIR`. |
| `server/src/routes/logs.ts` | Read log files | `EventService.log_lines`, `pocketStudio/api/compat.py` `/api/logs` | Partial | File-backed `/api/logs` exists. Missing log rotation and channel/service-specific log selection. |
| `server/src/routes/settings.ts` | GET/PUT settings | `SettingsService`, `pocketStudio/api/compat.py` `/api/settings`, `/api/settings/export`, `/api/settings/import`, `/api/setup` | Partial | Backend now persists workspace/channels/models/monitoring sections to `.pocketStudio/settings.json`, overlays live SQLite agents/teams/custom providers for responses, supports JSON import/export, and repairs common JSON mistakes with a `.bak` backup. Full `jsonrepair` parity remains incomplete. |
| `server/src/routes/services.ts` | Start/stop/restart services/channels/status | `pocketStudio/api/compat.py` service/status routes, `WorkerService`, `SettingsService` | Partial | Worker start/stop/restart/status, uptime, settings-backed channel status, and apply reporting exist. Still missing daemon process supervisor and real channel process manager. |
| `server/src/routes/pairing.ts` | Pairing state endpoints | `ChannelService`, `pocketStudio/api/compat.py`, pairing tables | Partial | Pairing list/approve/revoke/dismiss exists and `/api/message` uses `ensureSenderPaired` for external senders. Missing real channel client integration. |
| `server/src/routes/projects.ts` | Project CRUD | `ProjectService`, `pocketStudio/api/compat.py` | Partial | Project CRUD, status filtering, auto prefix/color defaults, and single-project lookup now exist. Missing exact timestamp/storage layout parity. |
| `server/src/routes/tasks.ts` | Task CRUD, comments, reorder | `pocketStudio/api/tasks.py`, `TaskService`, `ProjectService` comments | Partial | Task CRUD, comments, project/assignee filters, project-scoped task numbers, computed identifiers, and persisted reorder now exist. Missing exact string task IDs and separate task database parity. |
| `server/src/routes/schedules.ts` | Schedule CRUD | `ScheduleService`, `WorkerService`, `pocketStudio/api/compat.py` | Partial | Schedule CRUD and worker-driven due execution exist. Missing exact Croner behavior, live job registry, and complete validation parity. |

## `packages/teams`

Upstream `@tinyagi/teams` provides higher-level routing and collaboration behavior for teams.

| TinyAGI file | Upstream responsibility | pocketStudio mapping | Status | Notes / gaps |
|---|---|---|---|---|
| `teams/src/routing.ts` | Route messages to agents/teams and manage mentions | `Orchestrator._parse_target`, `_dispatch`, `_handle_team_tags`, bracket-depth parser helpers | Partial | Target parsing, leader-first ordering, bracket-depth `[@agent: ...]` mention extraction, comma-separated teammate fanout, duplicate mention suppression, chatroom broadcast fanout, internal enqueue, and parent channel/sender metadata propagation exist. |
| `teams/src/conversation.ts` | Multi-agent conversation flow | `Orchestrator._run_team`, `_run_iterative_rounds` | Partial | Chain/fanout, leader-first ordering, shared-context mention routing, mention-driven teammate follow-up messages, and controlled iterative rounds (`max_rounds`, `stop_when_idle`) exist. Missing upstream's full stateless response handler semantics and real channel delivery coupling. |
| `teams/src/chatroom.ts` | Shared team chatroom behavior | `ChatService`, `_handle_team_tags`, `_broadcast_chatroom` | Partial | Basic persistence plus bracket-depth `[#team: ...]` chatroom broadcasts from agent outputs exist, and broadcasts enqueue internal chatroom messages for the other teammates with parent channel/sender metadata. Missing full original channel outbound delivery integration. |
| `teams/src/index.ts` | Barrel exports | Python imports | Implemented in spirit | No exact Python barrel needed. |

## `packages/channels`

Upstream `@tinyagi/channels` connects external message sources to the core queue and outgoing response queue.

| TinyAGI file | Upstream responsibility | pocketStudio mapping | Status | Notes / gaps |
|---|---|---|---|---|
| `channels/src/default-agent.ts` | Default target agent logic for channels | `ChannelService` | Partial | Sticky default agent/team routing exists for compatibility `/api/message`. Missing file-backed settings parity and real channel client use. |
| `channels/src/discord.ts` | Discord bot inbound/outbound bridge, files, pairing | None | Missing | Requires Discord integration and outgoing queue. |
| `channels/src/telegram.ts` | Telegram bot inbound/outbound bridge, files, pairing | None | Missing | Requires Telegram integration and outgoing queue. |
| `channels/src/whatsapp.ts` | WhatsApp Web inbound/outbound bridge, media, pairing | None | Missing | Requires WhatsApp integration and outgoing queue. |
| `channels/src/sse-client.ts` | SSE client channel bridge | None | Missing | Backend has SSE server, not channel client. |

## `packages/main`

Upstream `@tinyagi/main` is the daemon that continuously processes queue messages, launches server, channels, and heartbeat.

| TinyAGI file | Upstream responsibility | pocketStudio mapping | Status | Notes / gaps |
|---|---|---|---|---|
| `main/src/index.ts` | Daemon entrypoint, queue loop, process messages, direct responses, shutdown | `pocketStudio/main.py`, `WorkerService`, `Orchestrator`, `/api/worker/*`, `pocketstudio daemon *` | Partial | FastAPI lifespan starts/stops a background worker that recovers stale messages, fires due schedules, and processes queued messages. CLI can start/stop/restart/status the local API process with pid/log files. Missing external process recovery and channel process orchestration. |
| `main/src/channels.ts` | Channel process manager | None | Missing | No external channel processes. |
| `main/src/heartbeat.ts` | Periodic heartbeat messages | `HeartbeatService`, `WorkerService`, `/api/heartbeat/status`, `/api/agents/{id}/heartbeat` | Partial | Heartbeat loop reads each agent workspace `heartbeat.md`, respects per-agent enabled/interval config, queues due messages, and records last sent state. Missing exact settings-file parity and richer frontend controls. |

## `packages/cli`

Upstream `@tinyagi/cli` provides the `tinyagi` command. pocketStudio now has a basic HTTP-backed `pocketstudio` CLI.

| TinyAGI file | Upstream responsibility | pocketStudio mapping | Status | Notes / gaps |
|---|---|---|---|---|
| `cli/bin/tinyagi.mjs` | CLI executable | `pocketStudio/cli.py`, `pyproject.toml` console script | Partial | `pocketstudio` command exists after package install. |
| `cli/src/daemon.ts` | start/stop/status/restart/open office | `pocketstudio daemon *`, `pocketstudio status`, `pocketstudio worker *` | Partial | Local API daemon process supervisor exists with pid/log files and `uvicorn pocketStudio.main:app` spawning. Missing browser open command and richer process recovery. |
| `cli/src/install.ts` | installer/bootstrap | None | Missing | No install flow. |
| `cli/src/agent.ts` | agent add/remove/list/show/provider/reset/custom providers | `pocketstudio agent *`, FastAPI agent endpoints | Partial | CLI covers list/add/show/remove/reset. Missing richer interactive provider selection. |
| `cli/src/team.ts` | team add/remove/list/show/member management | `pocketstudio team *`, FastAPI team endpoints | Partial | CLI covers list/add/show/remove, `--leader`, `--max-rounds`, `--keep-alive`, add-member, remove-member, and set-leader. |
| `cli/src/channel.ts` | channel start/stop/restart | None | Missing | Depends on channel process manager. |
| `cli/src/messaging.ts` | send messages, reset channel queues, setup channels | `pocketstudio send` | Partial | CLI can send messages. No channel setup/reset commands. |
| `cli/src/logs.ts` | log viewing | `pocketstudio logs`, `/api/logs` | Partial | CLI log viewing exists. Missing follow/tail streaming and service-specific log selection. |
| Settings CLI commands | Settings inspection/import/export | `pocketstudio settings get/export/import` | Partial | CLI can read, export, and import settings JSON through the API. Missing interactive setup and exact settings file editing. |
| `cli/src/pairing.ts` | approve/list/revoke pairings | `pocketstudio pairing *` | Partial | CLI covers list/approve/revoke. |
| `cli/src/provider.ts` | provider/model config commands | `pocketstudio provider *` | Partial | CLI covers list/custom/save/remove for custom providers. Missing interactive flow. |
| `cli/src/schedule.ts` | schedule list/create/delete | `pocketstudio schedule *` | Partial | CLI covers list/add/remove. |
| Task/project CLI commands | TinyOffice/control-plane task and project operations | `pocketstudio task *`, `pocketstudio project *` | Partial | CLI now covers task list/show/add/update/comments/comment/reorder/remove and project list/show/add/update/remove. |
| `cli/src/shared.ts` | shared settings/prompt helpers | `Settings`, README | Partial/Missing | No interactive prompts. |
| `cli/src/update.ts` | update command | None | Missing | Out of scope for backend. |
| `cli/src/version.ts` | version command | package metadata only | Missing | No CLI version command. |

## `packages/visualizer`

Upstream `@tinyagi/visualizer` provides terminal visualizations. The current project instead copied/adapted the web `tinyoffice/` frontend.

| TinyAGI file | Upstream responsibility | pocketStudio mapping | Status | Notes / gaps |
|---|---|---|---|---|
| `visualizer/src/team-visualizer.tsx` | Ink terminal team visualizer | `tinyoffice/` web UI | Frontend only | No terminal visualizer. |
| `visualizer/src/chatroom-viewer.tsx` | Ink terminal chatroom viewer | `tinyoffice/` web UI and `ChatService` | Frontend only/Partial | No terminal viewer. |

## Copied TinyOffice Frontend

Although not under `packages/`, `tinyoffice/` is also part of the upstream repository. The current project includes a copied Next.js TinyOffice frontend in `tinyoffice/` and adapts it to the local Python API mostly through `tinyoffice/src/lib/api.ts`.

| Upstream TinyOffice area | pocketStudio mapping | Status |
|---|---|---|
| Office scene and dashboard pages | `tinyoffice/src/app/*`, `tinyoffice/src/components/*` | Copied/adapted |
| API client | `tinyoffice/src/lib/api.ts` | Adapted with real agent/settings/task/project/comment/schedule/control-plane calls and compatibility transforms |
| Static assets | `tinyoffice/public/*` | Copied |
| Built-in simple static UI | `pocketStudio/static/*` | Separate fallback UI, not upstream TinyOffice |

## Current Python Backend Coverage

The current Python backend has these implemented slices:

- FastAPI app and CORS/static hosting: `pocketStudio/main.py`
- SQLite schema and lightweight database wrapper: `pocketStudio/core/database.py`
- Settings/env/home paths, primary `.pocketStudio/settings.json` persistence, and JSON import/export: `pocketStudio/core/config.py`, `pocketStudio/services/settings_service.py`
- Pydantic data contracts: `pocketStudio/models.py`
- Agent CRUD: `pocketStudio/services/agent_service.py`, `pocketStudio/api/agents.py`
- Team CRUD with leader support: `pocketStudio/services/team_service.py`, `pocketStudio/api/teams.py`
- Message queue CRUD/status/process-next: `pocketStudio/services/queue_service.py`, `pocketStudio/api/messages.py`
- Chain/fanout/leader orchestration and teammate mention enqueue: `pocketStudio/services/orchestrator.py`
- Local echo, OpenAI-compatible provider abstraction, and SQLite-backed custom provider registry: `pocketStudio/providers/*`
- Chatroom persistence: `pocketStudio/services/chat_service.py`, `pocketStudio/api/chat.py`
- TinyAGI-style task/project CRUD: `pocketStudio/services/task_service.py`, `pocketStudio/services/project_service.py`, `pocketStudio/api/tasks.py`
- Persisted event stream and SSE compatibility: `pocketStudio/services/event_service.py`, `pocketStudio/api/system.py`
- TinyOffice/TinyAGI compatibility endpoints: `pocketStudio/api/compat.py`
- Project/comment persistence: `pocketStudio/services/project_service.py`
- Schedule persistence: `pocketStudio/services/schedule_service.py`
- Per-agent message history and response projection: `pocketStudio/services/queue_service.py`
- Long-response/file-tag response preparation: `pocketStudio/services/response_service.py`
- Background queue worker daemon: `pocketStudio/services/worker_service.py`

## Highest-priority Missing Backend Work

To move toward a more complete Python rewrite of TinyAGI, the next backend milestones should be:

1. Full TinyAGI-compatible settings service: `/api/settings` now uses `.pocketStudio/settings.json` as the primary store, mirrors legacy SQLite app settings, syncs agent/team CRUD into the file, supports JSON import/export, and repairs common malformed JSON with backup; full npm `jsonrepair` behavior still needs parity.
2. Queue parity: queue status, outgoing responses, response acking, responses projection, agent message history, dead-letter retry/delete, stale recovery, per-agent status, and pruning now exist; exact schema parity and channel delivery integrations still need work.
3. Background daemon loop: continuous queue processing, stale recovery, worker control routes, uptime status, and CLI pid/log process supervision now exist; richer process recovery and channel process orchestration still need work.
4. Real agent harness adapters: subprocess abstraction and basic Codex adapter now exist; Claude/OpenCode adapters, richer streaming, reset/resume controls, and full kill/process metadata still need work.
5. Agent workspace parity: AGENTS.md/system prompt files, placeholder skill install, workspace initialization, and memory index loading now exist; upstream template syncing, real skill registry, and exact Claude/OpenCode workspace conventions still need work.
6. Projects/tasks/comments parity: projects, comments, task project/assignee fields, project prefix/color defaults, TinyAGI-style task numbers/identifiers, filters, and persisted reorder now exist; exact string task IDs, separate `tasks.db`, and JSON migration behavior still need parity.
7. Schedules and heartbeat: schedule CRUD, due execution, heartbeat loop with per-agent overrides, and default heartbeat interval assignment for newly created agents now exist; exact Croner parity and settings-file parity are still incomplete.
8. Pairing and channels: pairing persistence/API, sender enforcement, and sticky default target routing now exist; Discord/Telegram/WhatsApp/SSE client bridges and outbound delivery are still missing.
9. Plugin runtime: basic JSON-config incoming/outgoing hooks and event broadcast records exist; executable plugin modules and full hook API parity are still missing.
10. CLI: basic `pocketstudio` command exists for daemon/status/send/logs/settings/queue/worker/agent/team/provider/schedule/pairing/task/project, including local daemon start/stop/status/restart, task update/comment/reorder, and project update flows; channel setup, browser open, and interactive flows remain incomplete.
