---
name: pocketstudio-admin
description: "Operate and maintain this pocketStudio Python/FastAPI multi-agent system. Use when you need to inspect or change agents, teams, settings, providers, queue state, responses, logs, chats, tasks, projects, schedules, worker state, heartbeat state, pairing, plugins, source code, or local runtime files for this repository."
---

# pocketStudio Admin

Use this skill for administrative work on the local pocketStudio backend in this repository. Prefer the REST API for runtime operations and normal code edits for source changes.

## System Identity

- Project name: `pocketStudio`
- Backend package: `pocketStudio/`
- Default API base: `http://127.0.0.1:3777/api`
- Built-in UI: `http://127.0.0.1:3777/`
- TinyOffice frontend: `tinyoffice/`, usually served separately on `http://127.0.0.1:3000`
- Runtime home env var: `POCKETSTUDIO_POCKETSTUDIO_HOME`
- Default runtime home: `.pocketStudio/`
- Settings file: `.pocketStudio/settings.json`
- SQLite database: `.pocketStudio/pocketstudio.db`
- Agent workspaces: `.pocketStudio/workspace/<agent_id>/` unless an agent has a custom `workspace`
- Root shared skills: `.agents/skills/`
- Per-agent skills: `<agent_workspace>/.agents/skills/`, mirrored for tools through `<agent_workspace>/.codex/skills/` and `<agent_workspace>/.claude/skills/`

## Safe Operating Rules

- Prefer `curl`/API calls over direct SQLite edits.
- Do not use interactive commands for automation. The `pocketstudio` CLI in this project is mostly argument-driven, but the REST API is still the safest contract.
- When editing files, keep changes scoped to this repository.
- Do not delete runtime directories, queues, or workspaces unless explicitly asked.
- For source changes, run focused tests first, then broader tests if the change touches shared services or API contracts.

## Running The Backend

From the repository root:

```powershell
D:\Coding\anaconda\envs\MultiAgent\python.exe -m uvicorn pocketStudio.main:app --host 127.0.0.1 --port 3777
```

Install/test environment, if needed:

```powershell
D:\Coding\anaconda\envs\MultiAgent\python.exe -m pip install -e ".[test]"
D:\Coding\anaconda\envs\MultiAgent\python.exe -B -m pytest tests -q -p no:cacheprovider
```

## API Basics

Use `POCKETSTUDIO_API_BASE` when you need a non-default endpoint:

```bash
API="${POCKETSTUDIO_API_BASE:-http://127.0.0.1:3777/api}"
curl -s "$API/health"
```

Important endpoint shape note:

- Canonical CRUD routes exist under `/api/agents`, `/api/teams`, `/api/tasks`, `/api/messages`, `/api/queue`, and `/api/chatroom`.
- Compatibility/control-plane routes live in `pocketStudio/api/compat.py` and include settings, projects, schedules, worker, services, responses, logs, pairing, plugins, and custom providers.

## Agents

```bash
# List agents
curl -s "$API/agents" | jq .

# Create/upsert an agent
curl -s -X POST "$API/agents" \
  -H 'Content-Type: application/json' \
  -d '{"id":"coder","name":"Coder","role":"Python engineer","provider":"local"}' | jq .

# Upsert using TinyOffice-compatible PUT shape
curl -s -X PUT "$API/agents/coder" \
  -H 'Content-Type: application/json' \
  -d '{"name":"Coder","provider":"codex","model":"gpt-5.4","system_prompt":"Write tests before changing behavior.","heartbeat":{"enabled":true,"interval":3600}}' | jq .

# Get/delete an agent
curl -s "$API/agents/coder" | jq .
curl -s -X DELETE "$API/agents/coder" | jq .
```

Agent workspace and files:

```bash
curl -s "$API/agents/coder/workspace" | jq .
curl -s -X POST "$API/agents/coder/workspace/repair" | jq .
curl -s "$API/agents/coder/system-prompt" | jq .
curl -s -X PUT "$API/agents/coder/system-prompt" -H 'Content-Type: application/json' -d '{"content":"New prompt"}' | jq .
curl -s "$API/agents/coder/memory" | jq .
curl -s "$API/agents/coder/skills" | jq .
curl -s -X POST "$API/agents/coder/skills/install" -H 'Content-Type: application/json' -d '{"ref":"reviewer"}' | jq .
curl -s "$API/agents/coder/heartbeat" | jq .
curl -s -X PUT "$API/agents/coder/heartbeat" -H 'Content-Type: application/json' -d '{"enabled":true,"interval":1800}' | jq .
```

Memory file API:

```bash
curl -s "$API/agents/coder/memory/file?path=notes/design.md" | jq .
curl -s -X PUT "$API/agents/coder/memory/file" \
  -H 'Content-Type: application/json' \
  -d '{"path":"notes/design.md","content":"---\nname: Design\nsummary: Key notes\n---\n\nBody."}' | jq .
curl -s -X DELETE "$API/agents/coder/memory/file?path=notes/design.md" | jq .
```

## Teams

```bash
curl -s "$API/teams" | jq .

curl -s -X POST "$API/teams" \
  -H 'Content-Type: application/json' \
  -d '{"id":"dev","name":"Dev Team","mode":"chain","agent_ids":["coder"],"leaderAgent":"coder","maxRounds":1}' | jq .

curl -s -X PUT "$API/teams/dev" \
  -H 'Content-Type: application/json' \
  -d '{"name":"Dev Team","agents":["coder","reviewer"],"leader_agent":"coder","max_rounds":2}' | jq .

curl -s "$API/teams/dev" | jq .
curl -s -X POST "$API/teams/dev/members/reviewer" | jq .
curl -s -X PUT "$API/teams/dev/leader/coder" | jq .
curl -s -X DELETE "$API/teams/dev/members/reviewer" | jq .
curl -s -X DELETE "$API/teams/dev" | jq .
```

## Messages And Queue

```bash
# Enqueue canonical message
curl -s -X POST "$API/messages" \
  -H 'Content-Type: application/json' \
  -d '{"target":"@agent:coder","content":"Summarize queue health","sender":"admin"}' | jq .

# Process one message by id
curl -s -X POST "$API/messages/123/process" | jq .

# Process next queued message
curl -s -X POST "$API/queue/process-next" | jq .

# TinyAGI-compatible enqueue shape
curl -s -X POST "$API/message" \
  -H 'Content-Type: application/json' \
  -d '{"message":"@coder summarize queue health","sender":"Admin","channel":"web"}' | jq .

curl -s "$API/queue" | jq .
curl -s "$API/queue/grouped" | jq .
curl -s "$API/queue/123" | jq .
curl -s -X POST "$API/queue/123/retry" | jq .
curl -s "$API/queue/status" | jq .
curl -s "$API/queue/diagnostics" | jq .
curl -s "$API/queue/agents" | jq .
curl -s "$API/queue/processing" | jq .
curl -s "$API/queue/dead" | jq .
curl -s -X POST "$API/queue/dead/123/retry" | jq .
curl -s -X DELETE "$API/queue/dead/123" | jq .
curl -s -X POST "$API/queue/recover-stale" | jq .
curl -s -X POST "$API/queue/prune-completed" | jq .
```

## Responses And Logs

```bash
curl -s "$API/responses?limit=20" | jq .
curl -s -X POST "$API/responses" \
  -H 'Content-Type: application/json' \
  -d '{"channel":"web","sender":"Admin","message":"Proactive message","originalMessage":""}' | jq .
curl -s "$API/responses/pending?channel=telegram" | jq .
curl -s "$API/responses/channel/telegram" | jq .
curl -s -X POST "$API/responses/123/ack" | jq .
curl -s -X POST "$API/responses/prune" | jq .
curl -s "$API/logs?limit=100" | jq .
curl -s "$API/logs?event_type=queue.failed&contains=timeout" | jq .
```

## Settings And Providers

```bash
curl -s "$API/settings" | jq .
curl -s "$API/settings/export" | jq .
curl -s -X POST "$API/settings/validate" -H 'Content-Type: application/json' -d '{"settings":{"channels":{"enabled":["web"]}}}' | jq .
curl -s -X POST "$API/settings/preview" -H 'Content-Type: application/json' -d '{"settings":{"monitoring":{"heartbeat_interval":900}}}' | jq .
curl -s -X PUT "$API/settings" -H 'Content-Type: application/json' -d '{"monitoring":{"heartbeat_interval":900}}' | jq .
curl -s -X POST "$API/settings/import" -H 'Content-Type: application/json' -d '{"settings":{"models":{"provider":"codex"}}}' | jq .
curl -s "$API/settings/backup" | jq .
curl -s -X POST "$API/settings/restore-backup" | jq .

curl -s "$API/providers" | jq .
curl -s "$API/providers/diagnostics" | jq .
curl -s "$API/custom-providers" | jq .
curl -s -X PUT "$API/custom-providers/codex-fast" \
  -H 'Content-Type: application/json' \
  -d '{"name":"Codex Fast","harness":"codex","model":"gpt-5.4-mini"}' | jq .
curl -s -X DELETE "$API/custom-providers/codex-fast" | jq .
```

## Projects And Tasks

```bash
curl -s "$API/projects" | jq .
curl -s -X POST "$API/projects" \
  -H 'Content-Type: application/json' \
  -d '{"name":"Platform","description":"Backend work","prefix":"PLAT","workspace":".pocketStudio/projects/platform"}' | jq .
curl -s "$API/projects/PROJECT_ID" | jq .
curl -s -X PUT "$API/projects/PROJECT_ID" -H 'Content-Type: application/json' -d '{"status":"active"}' | jq .
curl -s "$API/projects/PROJECT_ID/workspace" | jq .
curl -s -X POST "$API/projects/PROJECT_ID/workspace/repair" | jq .
curl -s -X DELETE "$API/projects/PROJECT_ID" | jq .

curl -s "$API/tasks" | jq .
curl -s "$API/tasks?projectId=PROJECT_ID&status=todo&q=auth" | jq .
curl -s -X POST "$API/tasks" \
  -H 'Content-Type: application/json' \
  -d '{"title":"Fix auth bug","description":"Login fails","status":"todo","assignee":"coder","assigneeType":"agent","projectId":"PROJECT_ID"}' | jq .
curl -s "$API/tasks/123" | jq .
curl -s -X PUT "$API/tasks/123" -H 'Content-Type: application/json' -d '{"status":"in_progress"}' | jq .
curl -s -X PATCH "$API/tasks/123/status/done" | jq .
curl -s -X DELETE "$API/tasks/123" | jq .

curl -s "$API/tasks/123/comments" | jq .
curl -s -X POST "$API/tasks/123/comments" -H 'Content-Type: application/json' -d '{"author":"Admin","content":"Looks good."}' | jq .
curl -s -X DELETE "$API/comments/comment_abc123" | jq .
curl -s -X PUT "$API/tasks/reorder" -H 'Content-Type: application/json' -d '{"todo":["123"],"done":["124"]}' | jq .
```

## Schedules And Heartbeats

```bash
curl -s "$API/schedules" | jq .
curl -s "$API/schedules?agent=coder" | jq .
curl -s -X POST "$API/schedules/validate" \
  -H 'Content-Type: application/json' \
  -d '{"label":"daily","cron":"0 9 * * *","agentId":"coder","message":"Daily check"}' | jq .
curl -s -X POST "$API/schedules" \
  -H 'Content-Type: application/json' \
  -d '{"label":"daily","cron":"0 9 * * *","agentId":"coder","message":"Daily check","enabled":true}' | jq .
curl -s -X PUT "$API/schedules/SCHEDULE_ID" -H 'Content-Type: application/json' -d '{"label":"daily","cron":"0 10 * * *","agentId":"coder","message":"Daily check"}' | jq .
curl -s -X POST "$API/schedules/SCHEDULE_ID/fire" -H 'Content-Type: application/json' -d '{"force":true}' | jq .
curl -s -X DELETE "$API/schedules/SCHEDULE_ID" | jq .

curl -s "$API/heartbeat/status" | jq .
curl -s -X POST "$API/heartbeat/tick" -H 'Content-Type: application/json' -d '{"agentId":"coder","force":true}' | jq .
curl -s -X DELETE "$API/heartbeat/state?agent=coder" | jq .
```

## Worker, Services, Channels, Pairing

```bash
curl -s "$API/status" | jq .
curl -s "$API/worker/status" | jq .
curl -s -X POST "$API/worker/start" | jq .
curl -s -X POST "$API/worker/stop" | jq .
curl -s -X POST "$API/worker/pause" | jq .
curl -s -X POST "$API/worker/resume" | jq .
curl -s -X POST "$API/worker/restart" | jq .
curl -s -X POST "$API/worker/tick?force=true" | jq .
curl -s -X POST "$API/worker/maintenance" | jq .

curl -s -X POST "$API/services/apply" | jq .
curl -s "$API/services/status" | jq .
curl -s -X POST "$API/services/start" | jq .
curl -s -X POST "$API/services/stop" | jq .
curl -s -X POST "$API/services/restart" | jq .
curl -s -X POST "$API/services/channel/telegram/status" | jq .
curl -s -X POST "$API/services/channel/telegram/start" | jq .
curl -s -X POST "$API/services/channel/telegram/stop" | jq .
curl -s -X POST "$API/services/channel/telegram/restart" | jq .
curl -s -X POST "$API/services/channel/telegram/tick" | jq .

curl -s "$API/pairing" | jq .
curl -s -X POST "$API/pairing/approve" -H 'Content-Type: application/json' -d '{"code":"ABC123"}' | jq .
curl -s -X DELETE "$API/pairing/telegram/SENDER_ID" | jq .
curl -s -X DELETE "$API/pairing/pending/ABC123" | jq .
```

## Plugins, Chats, Events, Processes

```bash
curl -s "$API/plugins" | jq .
curl -s -X POST "$API/plugins/reload" | jq .
curl -s "$API/chats" | jq .
curl -s "$API/chats/dev?limit=100&q=build" | jq .
curl -s "$API/chatroom/dev" | jq .
curl -s -X POST "$API/chatroom/dev" -H 'Content-Type: application/json' -d '{"message":"Hello team","sender":"Admin"}' | jq .
curl -s "$API/events?limit=100" | jq .
curl -s "$API/events/office?limit=100" | jq .
curl -s "$API/events/stream"
curl -s "$API/processes" | jq .
curl -s -X POST "$API/processes/coder/kill" | jq .
curl -s -X POST "$API/queue/processing/123/kill" | jq .
```

## Source Code Map

- `pocketStudio/main.py`: FastAPI app creation, static UI mount, router registration, startup/shutdown lifespan.
- `pocketStudio/api/`: route modules.
- `pocketStudio/api/compat.py`: TinyAGI/TinyOffice compatibility and control-plane routes.
- `pocketStudio/api/payloads.py`: shared API response shaping helpers.
- `pocketStudio/core/`: settings, database, dependency construction, IDs, JSON storage, runtime helpers.
- `pocketStudio/models.py`: Pydantic API/domain models.
- `pocketStudio/services/`: domain services for agents, teams, queues, projects, tasks, schedules, worker, events, plugins, channels, heartbeat, chat, and orchestration.
- `pocketStudio/providers/`: local/OpenAI-compatible/Codex/Claude/OpenCode provider adapters and subprocess harness.
- `pocketStudio/channels/telegram.py`: Telegram channel bridge.
- `tinyoffice/`: Next.js UI.
- `tests/`: pytest behavior and API compatibility tests.
- `docs/PROJECT_STRUCTURE_AND_FUNCTIONS.md`: generated Chinese structure/function reference.
- `docs/PROJECT_STRUCTURE_AND_FUNCTIONS.en.md`: generated English structure/function reference.

After changing Python functions or modules, run:

```powershell
D:\Coding\anaconda\envs\MultiAgent\python.exe tools\generate_project_docs.py
```

## Useful Test Commands

```powershell
D:\Coding\anaconda\envs\MultiAgent\python.exe -B -m pytest tests -q -p no:cacheprovider
D:\Coding\anaconda\envs\MultiAgent\python.exe -B -m pytest tests\test_tinyagi_compat_api.py -q -p no:cacheprovider
D:\Coding\anaconda\envs\MultiAgent\python.exe -B -m pytest tests\test_agent_workspace.py tests\test_orchestrator.py tests\test_subprocess_harness.py -q -p no:cacheprovider
```
