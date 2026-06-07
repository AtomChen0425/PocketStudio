# pocketStudio

pocketStudio is a Python/FastAPI multi-agent orchestration backend inspired by TinyAGI. It brings agents, teams, tasks, queues, chatrooms, schedules, event streams, and local workspaces into one lightweight runtime for running collaborative AI agents on your machine.

The repository also includes an adapted TinyOffice frontend and a `pocketstudio` command-line control plane.

Chinese version: [README_CN.md](./docs/README_CN.md)

## Core Features

- Agent management: create, update, delete agents, and initialize an isolated workspace for each one.
- Skill sync: root skills from `.agents/skills/` are copied into agent workspaces and exposed through `.codex/skills` and `.claude/skills`.
- Provider adapters: supports `local`, OpenAI-compatible providers, Codex, Claude, OpenCode, and custom providers.
- Team orchestration: supports `chain` and `fanout`. In `chain` mode, the team leader plans first, members execute, and the leader summarizes member results.
- Queue system: durable SQLite message queue with running/done/failed/dead states, retries, stale-processing recovery, and response queues.
- Chatroom: team members can broadcast with `[#team: message]` or communicate through the chatroom API.
- Projects and tasks: built-in projects, tasks, comments, task ordering, and assignee management.
- Schedules and heartbeat: scheduled tasks, manual fire, agent heartbeat tick, and heartbeat state cleanup.
- Runtime progress visibility: the Codex provider maps displayable runtime events, tool calls, and progress summaries into SSE and the visualizer.
- Terminal visualizer: live in-place refresh for team runtime state and chatrooms in CMD or PowerShell.
- TinyOffice frontend: `tinyoffice/` provides a web UI for managing agents, teams, tasks, settings, and runtime state.

## Repository Layout

```text
pocketStudio/              FastAPI backend, services, providers, CLI
pocketStudio/api/          REST API routes
pocketStudio/services/     agent/team/queue/task/schedule/worker services
pocketStudio/providers/    local/openai/codex/claude/opencode provider adapters
pocketStudio/channels/     external message channels
tinyoffice/                Next.js frontend
tests/                     pytest tests
docs/                      structure docs, function index, TinyAGI mapping
tools/                     maintenance scripts such as docs generation
.agents/skills/            root shared skills
.pocketStudio/             default runtime data directory
```

## Requirements

- Python 3.11+
- Node.js 20+, only needed for the TinyOffice frontend
- Windows PowerShell or CMD

The current development environment usually uses:

```powershell
D:\Coding\anaconda\envs\MultiAgent\python.exe
```

You can also use a standard venv:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
```

## Start The Backend

Development mode:

```powershell
python -m uvicorn pocketStudio.main:app --host 127.0.0.1 --port 3777 --reload
```

Using the project Python:

```powershell
D:\Coding\anaconda\envs\MultiAgent\python.exe -m uvicorn pocketStudio.main:app --host 127.0.0.1 --port 3777
```

Open:

- API docs: http://127.0.0.1:3777/docs
- Built-in simple UI: http://127.0.0.1:3777/
- API prefix: http://127.0.0.1:3777/api

## CLI Usage

After editable installation, the `pocketstudio` command is available:

```powershell
python -m pip install -e ".[test]"
pocketstudio version
pocketstudio status
```

Common commands:

```powershell
pocketstudio daemon start
pocketstudio daemon status
pocketstudio daemon stop

pocketstudio agent list
pocketstudio agent add coder --name "Coder" --role "Python engineer" --provider local
pocketstudio team add dev --name "Dev Team" --agent coder --leader coder

pocketstudio send "@team:dev Plan a FastAPI service" --channel web --sender Web
pocketstudio queue status
pocketstudio worker tick
```

Providers and processes:

```powershell
pocketstudio provider list
pocketstudio provider custom
pocketstudio process list
pocketstudio process kill coder
```

Tasks and projects:

```powershell
pocketstudio project list
pocketstudio project add Platform --description "Backend work" --prefix PLAT
pocketstudio task list
pocketstudio task add "Wire backend" --assignee coder --assignee-type agent
```

Schedules and heartbeat:

```powershell
pocketstudio schedule list
pocketstudio schedule add --agent coder --message "Daily check" --cron "0 9 * * *"
pocketstudio heartbeat status
pocketstudio heartbeat tick --agent coder --force
```

## Visualizer

Team runtime dashboard:

```powershell
pocketstudio visualize
pocketstudio visualize --team dev
```

Snapshot mode for debugging or logs:

```powershell
pocketstudio visualize --once --no-clear
```

View and post to a chatroom:

```powershell
pocketstudio chatroom dev
pocketstudio chatroom dev --send "hello team"
```

On Windows CMD, the visualizer tries to enable Virtual Terminal. If that is unavailable, it falls back to the Windows Console API for in-place clearing, so it should not keep appending refreshed frames.

## TinyOffice Frontend

Start the backend first, then run this in a second terminal:

```powershell
cd tinyoffice
npm install
npm run dev -- --hostname 127.0.0.1 --port 3000
```

Open:

```text
http://127.0.0.1:3000
```

Build check:

```powershell
cd tinyoffice
npm run build
```

## REST API Quick Examples

Create an agent:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:3777/api/agents -ContentType application/json -Body '{"id":"coder","name":"Coder","role":"Python engineer","provider":"local"}'
```

Create a team:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:3777/api/teams -ContentType application/json -Body '{"id":"dev","name":"Dev Team","mode":"chain","agent_ids":["coder"],"leaderAgent":"coder"}'
```

Send a message:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:3777/api/messages -ContentType application/json -Body '{"target":"@team:dev","content":"Plan a FastAPI service","sender":"Web"}'
```

Process the next queued message:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:3777/api/queue/process-next
```

View mapped office events:

```powershell
Invoke-RestMethod http://127.0.0.1:3777/api/events/office
```

SSE:

```text
http://127.0.0.1:3777/api/events/stream
```

## Team Collaboration Model

Teams support two modes:

- `chain`: the leader runs first, members run in sequence, then the leader summarizes all member results.
- `fanout`: all members run concurrently, and the final output is grouped by agent.

Agents can use tags in their output to trigger team communication:

```text
[@coder: implement the API]
[@coder,reviewer: inspect queue handling]
[#dev: post this to the team chatroom]
```

`[@agent: ...]` creates directed teammate messages. `[#team: ...]` writes to the chatroom and broadcasts to other team members.

## Runtime Data

Default runtime directory:

```text
.pocketStudio/
```

Common files:

```text
.pocketStudio/settings.json
.pocketStudio/pocketStudio.db
.pocketStudio/workspace/<agent_id>/
.pocketStudio/logs/pocketstudio.log
```

Useful environment variables:

```powershell
$env:POCKETSTUDIO_POCKETSTUDIO_HOME="D:\path\to\runtime"
$env:POCKETSTUDIO_SQLITE_JOURNAL_MODE="WAL"
$env:POCKETSTUDIO_WORKER_ENABLED="true"
```

The default SQLite journal mode is `MEMORY`, which is friendlier for local Windows sandbox compatibility. For a more production-like local daemon, use `WAL`.

## Tests

Run the full test suite:

```powershell
D:\Coding\anaconda\envs\MultiAgent\python.exe -B -m pytest tests -q -p no:cacheprovider
```

Focused tests:

```powershell
D:\Coding\anaconda\envs\MultiAgent\python.exe -B -m pytest tests\test_orchestrator.py -q -p no:cacheprovider
D:\Coding\anaconda\envs\MultiAgent\python.exe -B -m pytest tests\test_visualizer.py tests\test_cli.py -q -p no:cacheprovider
```

After changing Python functions or modules, regenerate the structure and function docs:

```powershell
D:\Coding\anaconda\envs\MultiAgent\python.exe tools\generate_project_docs.py
```

## Maintenance Docs

- `docs/PROJECT_STRUCTURE_AND_FUNCTIONS.md`: Chinese project structure and function index.
- `docs/PROJECT_STRUCTURE_AND_FUNCTIONS.en.md`: English project structure and function index.
