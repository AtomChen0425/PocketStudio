# TinyAGI Python

A FastAPI backend that reimplements the core TinyAGI/TinyClaw ideas in Python:

- durable SQLite queue with retry and dead-letter states
- isolated agent definitions and workspaces
- team orchestration through chain and fan-out execution
- provider adapter interface for local, OpenAI-compatible, and future CLI/provider backends
- chat rooms, task board, settings, and event stream APIs for a web dashboard

## Run

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
uvicorn pocketStudio.main:app --reload --port 3777
```

API docs: http://localhost:3777/docs
TinyOffice UI: http://localhost:3777/

## Upstream TinyOffice Frontend

The upstream TinyAGI `tinyoffice/` frontend has been copied into this project and adapted to call the local Python API.

Run the backend in one terminal:

```powershell
D:\Coding\anaconda\envs\MultiAgent\python.exe -m uvicorn pocketStudio.main:app --host 127.0.0.1 --port 3777
```

Run TinyOffice in a second terminal:

```powershell
cd D:\Coding\Git_repositories\TinyAgiPython\tinyoffice
npm run dev -- --hostname 127.0.0.1 --port 3000
```

Open http://127.0.0.1:3000.

## Minimal Usage

```powershell
Invoke-RestMethod -Method Post http://localhost:3777/api/agents -ContentType application/json -Body '{"id":"coder","name":"Coder","role":"Python engineer","provider":"local"}'
Invoke-RestMethod -Method Post http://localhost:3777/api/teams -ContentType application/json -Body '{"id":"dev","name":"Dev Team","mode":"chain","agent_ids":["coder"]}'
Invoke-RestMethod -Method Post http://localhost:3777/api/messages -ContentType application/json -Body '{"target":"@team:dev","content":"Plan a FastAPI service"}'
Invoke-RestMethod http://localhost:3777/api/queue
```

Data is stored under `.tinyagi/` by default. Override with `TINYAGI_HOME`.
The default SQLite journal mode is `MEMORY` for broad Windows sandbox compatibility; set `TINYAGI_SQLITE_JOURNAL_MODE=WAL` for a production-like local daemon.
