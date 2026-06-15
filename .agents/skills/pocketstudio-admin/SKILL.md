---
name: pocketstudio-admin
description: "Operate and maintain this pocketStudio Python/FastAPI multi-agent system. Use when you need to inspect or change agents, teams, settings, providers, queue state, responses, logs, chats, tasks, projects, schedules, worker state, heartbeat state, pairing, plugins, source code, or local runtime files for this repository."
---

# pocketStudio Admin

Use this skill for administrative work on the local pocketStudio backend in this repository.

Prefer the project CLI for normal operations and the raw Python API helper for direct endpoint inspection.

## Project Identity

- Project name: `pocketStudio`
- Backend package: `pocketStudio/`
- Primary admin CLI: `python -m pocketStudio.cli`
- Local API base: `http://127.0.0.1:3777/api`
- Built-in UI: `http://127.0.0.1:3777/`
- TinyOffice frontend: `tinyoffice/`, usually served separately on `http://127.0.0.1:3000`
- Runtime home env var: `POCKETSTUDIO_POCKETSTUDIO_HOME`
- Default runtime home: `.pocketStudio/`
- Settings file: `.pocketStudio/settings.json`
- SQLite database: `.pocketStudio/pocketstudio.db`
- Agent workspaces: `.pocketStudio/workspace/<agent_id>/` unless an agent has a custom `workspace`
- Root shared skills: `.agents/skills/`
- Per-agent skills: `<agent_workspace>/.agents/skills/`

## Preferred Tools

### Project CLI

Use the built-in Python CLI first when it covers the work:

```powershell
python -m pocketStudio.cli status
python -m pocketStudio.cli daemon start
python -m pocketStudio.cli agent list
python -m pocketStudio.cli team list
python -m pocketStudio.cli task list
python -m pocketStudio.cli settings get
python -m pocketStudio.cli worker status
```

### Raw API Helper

Use the bundled API wrapper when you need direct endpoint access or to mirror frontend/backend behavior exactly:

```powershell
python <skill_dir>/scripts/ps_api.py status
python <skill_dir>/scripts/ps_api.py agents list
python <skill_dir>/scripts/ps_api.py tasks list
python <skill_dir>/scripts/ps_api.py settings get
python <skill_dir>/scripts/ps_api.py message '{"message":"@coder summarize queue health","sender":"Admin","channel":"web"}'
```

The helper uses only the Python standard library. For complex JSON bodies, pass `@path/to/file.json` or `-` for stdin.

## Safe Operating Rules

- Prefer the REST API and project CLI over direct SQLite edits.
- Do not delete runtime directories, queues, or workspaces unless explicitly asked.
- Keep file edits scoped to this repository.
- For source changes, run focused tests first, then broader tests if the change touches shared services or API contracts.

## Running The Backend

From the repository root:

```powershell
python -m uvicorn pocketStudio.main:app --host 127.0.0.1 --port 3777
```

Install and test, if needed:

```powershell
python -m pip install -e ".[test]"
python -B -m pytest tests -q -p no:cacheprovider
```

## API Basics

Use `POCKETSTUDIO_API_BASE` when you need a non-default endpoint:

```powershell
$env:POCKETSTUDIO_API_BASE = "http://127.0.0.1:3777/api"
python .agents\skills\pocketstudio-admin\scripts\ps_api.py status
```

Important endpoint groups:

- Canonical CRUD routes: `/api/agents`, `/api/teams`, `/api/tasks`, `/api/projects`, `/api/messages`, `/api/queue`, `/api/chatroom`
- Compatibility/control-plane routes: settings, schedules, worker, services, responses, logs, pairing, plugins, and custom providers

## Common Operations

### Agents

```powershell
python -m pocketStudio.cli agent list
python -m pocketStudio.cli agent add coder --name "Coder" --role "Python engineer" --provider local
python -m pocketStudio.cli agent show coder
python -m pocketStudio.cli agent workspace coder
python -m pocketStudio.cli agent repair-workspace coder
python -m pocketStudio.cli agent remove coder
python -m pocketStudio.cli agent reset coder
```

### Teams

```powershell
python -m pocketStudio.cli team list
python -m pocketStudio.cli team add dev --name "Dev Team" --agent coder --leader coder --max-rounds 2
python -m pocketStudio.cli team show dev
python -m pocketStudio.cli team add-member dev reviewer
python -m pocketStudio.cli team remove-member dev reviewer
python -m pocketStudio.cli team set-leader dev coder
python -m pocketStudio.cli team remove dev
```

### Tasks And Projects

```powershell
python -m pocketStudio.cli task list
python -m pocketStudio.cli task add "Fix auth bug" --status todo --project PROJECT_ID
python -m pocketStudio.cli task show 123
python -m pocketStudio.cli task update 123 --status in_progress
python -m pocketStudio.cli task comments 123
python -m pocketStudio.cli task comment 123 "Completed and verified with tests."
python -m pocketStudio.cli task remove 123

python -m pocketStudio.cli project list
python -m pocketStudio.cli project add Platform --description "Backend work" --prefix PLAT
python -m pocketStudio.cli project show PROJECT_ID
python -m pocketStudio.cli project update PROJECT_ID --status active
python -m pocketStudio.cli project workspace PROJECT_ID
python -m pocketStudio.cli project repair-workspace PROJECT_ID
python -m pocketStudio.cli project remove PROJECT_ID
```

### Queue, Worker, And Heartbeat

```powershell
python -m pocketStudio.cli queue status
python -m pocketStudio.cli queue diagnostics
python -m pocketStudio.cli queue dead
python -m pocketStudio.cli queue retry 123

python -m pocketStudio.cli worker status
python -m pocketStudio.cli worker start
python -m pocketStudio.cli worker pause
python -m pocketStudio.cli worker resume
python -m pocketStudio.cli worker maintenance

python -m pocketStudio.cli heartbeat status
python -m pocketStudio.cli heartbeat tick --agent coder --force
python -m pocketStudio.cli heartbeat clear --agent coder
```

### Settings, Providers, Pairing, And Messaging

```powershell
python -m pocketStudio.cli settings get
python -m pocketStudio.cli settings backup
python -m pocketStudio.cli settings export .pocketStudio\settings-export.json
python -m pocketStudio.cli settings import .pocketStudio\settings-import.json
python -m pocketStudio.cli settings validate .pocketStudio\settings.json
python -m pocketStudio.cli settings preview .pocketStudio\settings.json

python -m pocketStudio.cli provider list
python -m pocketStudio.cli provider custom
python -m pocketStudio.cli provider save codex-fast --name "Codex Fast" --harness codex --model gpt-5.4-mini

python -m pocketStudio.cli pairing list
python -m pocketStudio.cli pairing approve ABC123

python -m pocketStudio.cli send "@team:dev Plan a FastAPI service" --channel web --sender Web
```

## Source Code Map

- `pocketStudio/main.py`: FastAPI app creation, static UI mount, router registration, startup/shutdown lifespan
- `pocketStudio/cli.py`: Python control-plane CLI for daemon, agents, teams, tasks, projects, settings, queues, and more
- `pocketStudio/api/`: FastAPI route modules
- `pocketStudio/api/compat.py`: TinyAGI/TinyOffice compatibility and control-plane routes
- `pocketStudio/core/`: settings, database, dependency construction, IDs, JSON storage, runtime helpers
- `pocketStudio/models/`: Pydantic API/domain models
- `pocketStudio/services/`: services for agents, teams, queues, projects, tasks, schedules, worker, events, plugins, channels, heartbeat, chat, and orchestration
- `pocketStudio/providers/`: local/OpenAI-compatible/Codex/Claude/OpenCode provider adapters and subprocess harness
- `tinyoffice/`: Next.js UI
- `tests/`: pytest behavior and API compatibility tests
- `tools/generate_project_docs.py`: regenerate the Chinese and English structure/function docs after Python source changes

After changing Python functions or modules, run:

```powershell
python tools/generate_project_docs.py
```

## Useful Test Commands

```powershell
python -B -m pytest tests -q -p no:cacheprovider
python -B -m pytest tests\test_tinyagi_compat_api.py -q -p no:cacheprovider
python -B -m pytest tests\test_agent_workspace.py tests\test_orchestrator.py tests\test_subprocess_harness.py -q -p no:cacheprovider
```
