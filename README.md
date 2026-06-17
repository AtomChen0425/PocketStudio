# PocketStudio

Multi-agent, multi-team, multi-channel AI assistant runtime built with Python and FastAPI.

Run teams of AI agents with isolated workspaces, persistent queues, project tasks, chat rooms, scheduled work, heartbeat monitoring, and a browser dashboard.

![PocketStudio working dashboard](docs/assets/Working.png)

<!-- Badge placeholder: experimental -->
<!-- Badge placeholder: license -->
<!-- Badge placeholder: community -->
<!-- Video placeholder: docs/assets/PocketStudio-demo.mp4 -->

Chinese version: [README_CN.md](./docs/README_CN.md)

## Features

- Multi-agent runtime: create isolated agents with their own workspace, memory, prompts, skills, and conversation state.
- Multi-team collaboration: run teams in sequential `chain`, parallel `fanout`, or workflow-driven modes.
- LangGraph-driven workflows: configure per-team workflow graphs with start, agent, tool, end, and conditional routing nodes.
- Team chat rooms: persistent Slack-style rooms with CLI viewer, API endpoints, and agent broadcast tags.
- Multi-channel foundation: web/API messaging plus Telegram channel service and pairing controls.
- TinyOffice web portal: browser UI for agents, teams, tasks, projects, logs, settings, queue state, and runtime activity.
- Multiple AI providers: local dry-run provider, Codex, Nanobot, OpenAI-compatible endpoints, Claude, OpenCode, and custom providers.
- Durable SQLite queue: queued/running/done/failed/dead states, retries, stale recovery, response jobs, and diagnostics.
- Background worker: daemon-compatible processor for queue messages, schedules, heartbeat ticks, and maintenance.
- Projects and tasks: project-scoped workspaces, Kanban-like task states, assignees, comments, ordering, and archive support.
- Live observability: SSE events, Office-compatible event mapping, process metadata, logs, queue diagnostics, and CLI visualizer.
- Plugin hooks: incoming/outgoing message hooks and event listeners through the plugin service.
- Persistent operation: local daemon process, runtime home directory, settings, logs, and agent workspaces.

## Gallery

All current product screenshots and workflow visuals are collected here for quick browsing.

<table>
  <tr>
    <td width="50%">
      <strong>Working Dashboard</strong><br />
      <img src="docs/assets/Working.png" alt="PocketStudio working dashboard" width="100%" />
    </td>
    <td width="50%">
      <strong>TinyOffice Portal</strong><br />
      <img src="docs/assets/Office.png" alt="TinyOffice portal" width="100%" />
    </td>
  </tr>
  <tr>
    <td width="50%">
      <strong>Organization View</strong><br />
      <img src="docs/assets/Company.png" alt="Organization view" width="100%" />
    </td>
    <td width="50%">
      <strong>LangGraph Workflow Settings</strong><br />
      <img src="docs/assets/TeamSetting.png" alt="Team workflow settings" width="100%" />
    </td>
  </tr>
  <tr>
    <td width="50%">
      <strong>Agents Setting</strong><br />
      <img src="docs/assets/agents.png" alt="Agents Setting" width="100%" />
    </td>
    <td width="50%">
      <strong>Completed Work View</strong><br />
      <img src="docs/assets/Done.png" alt="Completed work view" width="100%" />
    </td>
  </tr>
</table>

## Community

This repository is a Python/FastAPI implementation inspired by TinyAGI. For upstream TinyAGI community links, see the TinyAGI project.

Contributions should keep service boundaries clear: API routes call services, orchestration remains a thin facade, and long-running provider work stays behind provider adapters.

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+ for the TinyOffice frontend
- Windows PowerShell or CMD, or a compatible shell on another OS
- Optional provider CLIs/API keys for Codex, Claude, OpenCode, Nanobot, or OpenAI-compatible providers

### Installation and First Run

From this repository:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
python -m uvicorn pocketStudio.main:app --host 127.0.0.1 --port 3777 --reload
```

Or use the project Python used by this workspace:

```powershell
D:\Coding\anaconda\envs\MultiAgent\python.exe -m uvicorn pocketStudio.main:app --host 127.0.0.1 --port 3777
```

Open:

- API docs: `http://127.0.0.1:3777/docs`
- API base: `http://127.0.0.1:3777/api`

Default runtime data:

- Runtime home: `.pocketStudio/`
- Settings: `.pocketStudio/settings.json`
- SQLite database: `.pocketStudio/pocketstudio.db`
- Agent workspaces: `.pocketStudio/workspace/<agent_id>/`

### Development From Source

```powershell
python -m pip install -e ".[test]"
pocketstudio version
pocketstudio status
```

Start the local API daemon:

```powershell
pocketstudio daemon start
pocketstudio daemon status
```

Stop it:

```powershell
pocketstudio daemon stop
```

## TinyOffice Web Portal

![TinyOffice portal](docs/assets/Office.png)

<!-- Video placeholder: docs/assets/tinyoffice-walkthrough.mp4 -->

pocketStudio includes an adapted TinyOffice frontend in [tinyoffice/](./tinyoffice) for managing agents, teams, tasks, projects, settings, queue state, events, and chat rooms.

Start the backend first, then run the frontend:

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

TinyOffice areas:

- Dashboard: queue/system overview and event feed.
- Chat Console: send messages to an agent or team.
- Agents and Teams: create, edit, remove, and inspect runtime configuration.
- Tasks and Projects: project boards, task assignment, ordering, comments, and status changes.
- Logs and Events: inspect backend logs and streaming runtime events.
- Settings: inspect and update local configuration.
- Chat Rooms: persistent team rooms with dispatch status.
- Office View and Org Chart: visual views of agents, teams, and runtime activity.

![Organization view](docs/assets/Company.png)

## Commands

Commands work with the `pocketstudio` CLI after editable installation.

### Core Commands

| Command | Description | Example |
| --- | --- | --- |
| `version` | Show pocketStudio version | `pocketstudio version` |
| `status` | Show system status | `pocketstudio status` |
| `daemon start` | Start the local API daemon | `pocketstudio daemon start` |
| `daemon stop` | Stop the daemon | `pocketstudio daemon stop` |
| `daemon restart` | Restart the daemon | `pocketstudio daemon restart` |
| `logs` | Show recent log lines | `pocketstudio logs --limit 100` |
| `send` | Queue a message | `pocketstudio send "@team:dev Plan the API"` |
| `visualize` | Open live team visualizer | `pocketstudio visualize --team dev` |

### Agent Commands

| Command | Description | Example |
| --- | --- | --- |
| `agent list` | List agents | `pocketstudio agent list` |
| `agent add` | Add or update an agent | `pocketstudio agent add coder --name "Coder" --role "Python engineer" --provider local` |
| `agent show <id>` | Show agent configuration | `pocketstudio agent show coder` |
| `agent workspace <id>` | Show workspace status | `pocketstudio agent workspace coder` |
| `agent repair-workspace <id>` | Repair missing workspace files | `pocketstudio agent repair-workspace coder` |
| `agent reset <id>` | Reset agent runtime conversation | `pocketstudio agent reset coder` |
| `agent remove <id>` | Remove an agent | `pocketstudio agent remove coder` |

### Team Commands

| Command | Description | Example |
| --- | --- | --- |
| `team list` | List teams | `pocketstudio team list` |
| `team add` | Add or update a team | `pocketstudio team add dev --name "Dev Team" --agent coder --leader coder` |
| `team show <id>` | Show team configuration | `pocketstudio team show dev` |
| `team add-member <team> <agent>` | Add an agent to a team | `pocketstudio team add-member dev reviewer` |
| `team remove-member <team> <agent>` | Remove an agent from a team | `pocketstudio team remove-member dev reviewer` |
| `team set-leader <team> <agent>` | Set team leader | `pocketstudio team set-leader dev coder` |
| `team remove <id>` | Remove a team | `pocketstudio team remove dev` |

Team settings also include workflow mode. In workflow mode, a team can run a LangGraph-backed graph instead of only sequential `chain` or parallel `fanout` execution.

![Team workflow settings](docs/assets/TeamSetting.png)

### Chatroom Commands

| Command | Description | Example |
| --- | --- | --- |
| `chatroom <team>` | Watch a team chatroom | `pocketstudio chatroom dev` |
| `chatroom <team> --send` | Post a chatroom message | `pocketstudio chatroom dev --send "hello team"` |
| `visualize --team <id>` | Watch team runtime state | `pocketstudio visualize --team dev` |

Every team has a persistent chat room. Agents post to it using `[#team_id: message]` tags, and messages are broadcast to teammates.

API endpoints:

```text
GET  /api/chatroom/{teamId}
POST /api/chatroom/{teamId}
POST /api/teams/{teamId}/dispatch
```

### Provider and Custom Provider Commands

| Command | Description | Example |
| --- | --- | --- |
| `provider list` | List available providers | `pocketstudio provider list` |
| `provider custom` | List custom providers | `pocketstudio provider custom` |
| `provider save` | Create or update a custom provider | `pocketstudio provider save codex-fast --name "Codex Fast" --harness codex --model gpt-5.4-mini` |
| `provider remove <id>` | Remove a custom provider | `pocketstudio provider remove codex-fast` |
| `process list` | List active provider processes | `pocketstudio process list` |
| `process kill <agent>` | Kill an agent process | `pocketstudio process kill coder` |

Custom provider example:

```powershell
pocketstudio provider save local-openai `
  --name "Local OpenAI Compatible" `
  --harness openai `
  --base-url "http://127.0.0.1:8000/v1" `
  --api-key "sk-local" `
  --model "gpt-4o-mini"
```

### Pairing Commands

Use sender pairing to control which external senders may message agents.

| Command | Description | Example |
| --- | --- | --- |
| `pairing list` | Show pending and approved senders | `pocketstudio pairing list` |
| `pairing approve <code>` | Approve a sender by code | `pocketstudio pairing approve ABC123` |
| `pairing revoke <channel> <sender>` | Remove a sender | `pocketstudio pairing revoke telegram 1234567` |

### Messaging and In-Chat Routing

```powershell
pocketstudio send "Hello"
pocketstudio send "@agent:coder fix the queue issue"
pocketstudio send "@team:dev plan the refactor"
```

Agents can route work to teammates or chat rooms in their responses:

```text
[@coder: implement the API]
[@coder,reviewer: inspect queue handling]
[#dev: post this to the team chatroom]
```

### Queue, Worker, Schedule, and Heartbeat Commands

| Command | Description | Example |
| --- | --- | --- |
| `queue status` | Show queue counts | `pocketstudio queue status` |
| `queue diagnostics` | Inspect queue health | `pocketstudio queue diagnostics` |
| `queue dead` | List dead messages | `pocketstudio queue dead` |
| `queue retry <id>` | Retry a failed/dead message | `pocketstudio queue retry 12` |
| `worker status` | Show worker state | `pocketstudio worker status` |
| `worker start` | Start background worker | `pocketstudio worker start` |
| `worker pause` | Pause background worker | `pocketstudio worker pause` |
| `worker resume` | Resume background worker | `pocketstudio worker resume` |
| `worker maintenance` | Run maintenance tasks | `pocketstudio worker maintenance` |
| `schedule list` | List schedules | `pocketstudio schedule list` |
| `schedule add` | Add recurring or one-time work | `pocketstudio schedule add --agent coder --message "Daily check" --cron "0 9 * * *"` |
| `heartbeat status` | Show heartbeat state | `pocketstudio heartbeat status` |
| `heartbeat tick` | Force heartbeat processing | `pocketstudio heartbeat tick --agent coder --force` |

### Project and Task Commands

| Command | Description | Example |
| --- | --- | --- |
| `project list` | List projects | `pocketstudio project list` |
| `project add` | Create a project | `pocketstudio project add Platform --description "Backend work" --prefix PLAT` |
| `project workspace <id>` | Show project workspace | `pocketstudio project workspace PROJECT_ID` |
| `task list` | List tasks | `pocketstudio task list` |
| `task add` | Create a task | `pocketstudio task add "Wire backend" --assignee coder --assignee-type agent` |
| `task update` | Update task fields | `pocketstudio task update 123 --status in_progress` |
| `task comment` | Add task comment | `pocketstudio task comment 123 "Implemented and tested"` |
| `task reorder` | Reorder a status column | `pocketstudio task reorder todo 3 7 9` |

### Settings Commands

| Command | Description | Example |
| --- | --- | --- |
| `settings get` | Show settings | `pocketstudio settings get` |
| `settings backup` | Create settings backup | `pocketstudio settings backup` |
| `settings export <path>` | Export settings | `pocketstudio settings export .pocketStudio\settings-export.json` |
| `settings import <path>` | Import settings | `pocketstudio settings import .pocketStudio\settings-export.json` |
| `settings validate <path>` | Validate settings JSON | `pocketstudio settings validate .pocketStudio\settings.json` |
| `settings preview <path>` | Preview import changes | `pocketstudio settings preview .pocketStudio\settings.json` |

## Using Agents

Use explicit targets to route messages:

```text
@agent:coder fix the authentication bug
@team:dev plan the backend migration
help me with this
```

Agent configuration is stored in SQLite and mirrored into settings where applicable. Each agent has:

- Separate workspace directory under `.pocketStudio/workspace/<agent_id>/` by default.
- Its own `AGENTS.md`, `heartbeat.md`, `.pocketStudio/SOUL.md`, and `memory/` folder.
- Synced skills from `.agents/skills/`.
- Provider configuration such as `local`, `codex`, `nanobot`, or custom providers.
- Independent reset and provider runtime state.

Example agent setup:

```powershell
pocketstudio agent add coder --name "Coder" --role "Python engineer" --provider local
pocketstudio agent add reviewer --name "Reviewer" --role "Reviews code" --provider local
pocketstudio team add dev --name "Development Team" --agent coder --leader coder
pocketstudio team add-member dev reviewer
pocketstudio send "@team:dev Review and improve the API"
```

### LangGraph Workflows

pocketStudio now supports LangGraph-driven team workflows. A team can execute a graph of workflow nodes instead of only running a simple chain or fan-out.

Workflow mode supports:

- Start, agent, tool, and end nodes.
- Directed edges between workflow nodes.
- Conditional edges routed from JSON output or text matching.
- Python routing functions for advanced branching.
- Per-node input templates with upstream predecessor output.
- Project workspace injection for workflow agent runs.

The workflow executor lives in `WorkflowService`, while `Orchestrator` stays a thin queue dispatch facade.

## Architecture

### Message Flow Diagram

```text
Message Channels
  Web, API, CLI, Telegram, compatibility channel adapters
        |
        | enqueue()
        v
.pocketStudio/pocketstudio.db (SQLite)
  messages: queued -> running -> done / failed / dead
  responses: pending -> acked
  agent_messages: per-agent conversation records
        |
        | WorkerService / manual process
        v
Orchestrator facade
  target parse -> agent/team/workflow dispatch
        |
        +------------+------------+
        v            v            v
   AgentService  TeamService  WorkflowService
        |            |            |
        v            v            v
 ProviderRegistry  ChatService  QueueService
        |
        v
 provider adapter process/API call
```

Workflow teams enter the `WorkflowService` path, where LangGraph compiles the active workflow definition, invokes agent nodes through `AgentService`, records queue history through `QueueService`, and posts final team output through `ChatService`.

### Key Services

- `pocketStudio/main.py`: FastAPI application, routers, static UI, lifespan hooks.
- `pocketStudio/api/`: REST API and compatibility routes.
- `pocketStudio/services/orchestrator.py`: thin queue dispatch facade.
- `pocketStudio/services/agent_service.py`: agent CRUD, workspace setup, system prompts, runtime invocation.
- `pocketStudio/services/team_service.py`: team CRUD, member routing rules, chain/fanout helper logic.
- `pocketStudio/services/workflow_service.py`: workflow CRUD, validation, LangGraph execution.
- `pocketStudio/services/chat_service.py`: chatroom messages, dispatch tracking, team broadcast fan-out.
- `pocketStudio/services/queue_service.py`: durable queue, response jobs, dead-letter and diagnostics.
- `pocketStudio/providers/`: provider adapters and subprocess process registry.
- `tinyoffice/`: Next.js web portal.

### Repository Structure

```text
TinyAgiPython/
|-- pocketStudio/                  # FastAPI backend package
|   |-- api/                       # REST routes
|   |-- channels/                  # Channel integrations
|   |-- core/                      # Settings, database, dependencies
|   |-- models/                    # Pydantic models
|   |-- providers/                 # Local, Codex, Claude, OpenCode, Nanobot adapters
|   |-- services/                  # Agents, teams, queue, chat, workflow, worker
|   `-- visualizer.py              # CLI visualizer and chatroom viewer
|-- tinyoffice/                    # TinyOffice frontend
|-- tests/                         # Pytest suite
|-- docs/                          # Generated structure docs and mapping notes
|-- tools/                         # Maintenance scripts
|-- .agents/skills/                # Root shared skills
`-- .pocketStudio/                 # Runtime data, created locally
```

## Configuration

### Settings File Reference

Default settings path:

```text
.pocketStudio/settings.json
```

Representative structure:

```json
{
  "agents": {
    "coder": {
      "name": "Coder",
      "provider": "local",
      "model": "",
      "working_directory": ".pocketStudio/workspace/coder",
      "system_prompt": "Python engineer"
    }
  },
  "teams": {
    "dev": {
      "name": "Development Team",
      "agents": ["coder", "reviewer"],
      "leader_agent": "coder",
      "mode": "chain",
      "max_rounds": 1,
      "stop_when_idle": true
    }
  },
  "monitoring": {
    "heartbeat_interval": 3600
  }
}
```

Useful environment variables:

```powershell
$env:POCKETSTUDIO_POCKETSTUDIO_HOME="D:\path\to\runtime"
$env:POCKETSTUDIO_SQLITE_JOURNAL_MODE="WAL"
$env:POCKETSTUDIO_WORKER_ENABLED="true"
```

### Heartbeat Configuration

Edit an agent heartbeat prompt:

```powershell
notepad .pocketStudio\workspace\coder\heartbeat.md
```

Default heartbeat intent:

```markdown
Check for:
1. Pending tasks
2. Errors
3. Unread messages

Take action if needed.
```

### Runtime Directory Structure

```text
.pocketStudio/
|-- settings.json
|-- pocketstudio.db
|-- logs/
|   `-- pocketstudio.log
|-- files/
|-- workspace/
|   |-- coder/
|   |   |-- AGENTS.md
|   |   |-- heartbeat.md
|   |   |-- memory/
|   |   `-- .pocketStudio/
|   |       `-- SOUL.md
|   `-- reviewer/
`-- channels/
```

## Use Cases

### Personal AI Assistant

```text
You: "Check my project queue every morning"
pocketStudio: schedules a heartbeat or scheduled task for the chosen agent
[Next run] Agent reviews tasks, messages, and runtime state, then reports back
```

### Multi-Agent Workflow

```text
@agent:coder implement the API changes
@agent:writer document the new endpoints
@agent:reviewer review the implementation notes
```

### Team Collaboration

```text
@team:dev fix the auth bug

Flow:
1. Team leader receives the request.
2. Leader directs work with [@coder: ...] and [@reviewer: ...].
3. Teammates run with isolated workspaces.
4. Leader summarizes results for the user.
```

Teams support sequential chains, parallel fan-out, controlled iterative mention rounds, persistent chat rooms, and workflow graphs.

### Project-Based Work

```powershell
pocketstudio project add Website --description "Landing page refresh" --prefix WEB
pocketstudio task add "Review hero copy" --project PROJECT_ID --assignee writer --assignee-type agent
pocketstudio send "@team:dev Work on PROJECT_ID tasks"
```

![Completed work view](docs/assets/Done.png)

## Documentation

- [docs/README_CN.md](./docs/README_CN.md): Chinese README.
- [docs/PROJECT_STRUCTURE_AND_FUNCTIONS.md](./docs/PROJECT_STRUCTURE_AND_FUNCTIONS.md): Chinese structure and function index.
- [docs/PROJECT_STRUCTURE_AND_FUNCTIONS.en.md](./docs/PROJECT_STRUCTURE_AND_FUNCTIONS.en.md): English structure and function index.
- [docs/TINYAGI_PACKAGE_MAPPING.md](./docs/TINYAGI_PACKAGE_MAPPING.md): TinyAGI-to-pocketStudio mapping notes.
- [tinyoffice/](./tinyoffice): TinyOffice frontend source.

Regenerate structure docs after Python source changes:

```powershell
D:\Coding\anaconda\envs\MultiAgent\python.exe tools\generate_project_docs.py
```

## Testing

Run the full test suite:

```powershell
D:\Coding\anaconda\envs\MultiAgent\python.exe -B -m pytest tests -q -p no:cacheprovider
```

Focused tests:

```powershell
D:\Coding\anaconda\envs\MultiAgent\python.exe -B -m pytest tests\test_orchestrator.py -q -p no:cacheprovider
D:\Coding\anaconda\envs\MultiAgent\python.exe -B -m pytest tests\test_workflow_service.py tests\test_team_service.py -q -p no:cacheprovider
D:\Coding\anaconda\envs\MultiAgent\python.exe -B -m pytest tests\test_visualizer.py tests\test_cli.py -q -p no:cacheprovider
```

Build TinyOffice:

```powershell
cd tinyoffice
npm run build
```

## Troubleshooting

Quick checks:

```powershell
pocketstudio status
pocketstudio queue diagnostics
pocketstudio worker status
pocketstudio logs --limit 200
```

Common issues:

- Messages stuck: check `pocketstudio queue diagnostics`, then retry with `pocketstudio queue retry <id>`.
- Agent not found: run `pocketstudio agent list` and verify the target uses `@agent:<id>`.
- Team routing not working: run `pocketstudio team show <id>` and verify members and leader.
- Provider process hung: inspect `pocketstudio process list`, then use `pocketstudio process kill <agent>`.
- Workspace missing files: run `pocketstudio agent repair-workspace <id>`.
- Settings problem: run `pocketstudio settings validate .pocketStudio\settings.json`.

Need deeper backend state:

```powershell
Invoke-RestMethod http://127.0.0.1:3777/api/queue/diagnostics
Invoke-RestMethod http://127.0.0.1:3777/api/events/office
```

SSE stream:

```text
http://127.0.0.1:3777/api/events/stream
```

## Credits

- Inspired by [TinyAGI](https://github.com/TinyAGI/tinyagi).
- Built with FastAPI, Pydantic, SQLite, LangGraph, and provider adapters for local and CLI-backed agents.
- TinyOffice frontend adapted for the pocketStudio runtime.

## License

MIT

---

pocketStudio: a local, service-oriented runtime for collaborative AI agents.
