---
name: tasks
description: "Manage pocketStudio project tasks through the local FastAPI API with the Python helper in this skill. Use when a message contains a task id or identifier, when you need to check assigned work, create follow-up work, update status, reorder tasks, delete tasks, or leave implementation notes."
---

# Tasks

Use this skill to manage pocketStudio tasks and project kanban state through the local REST API.

## Python Helper

The bundled helper is:

```bash
python <skill_dir>/scripts/tasks.py
```

It uses only the Python standard library.

Environment variables:

- `POCKETSTUDIO_API_BASE`: API base URL, default `http://127.0.0.1:3777/api`
- `POCKETSTUDIO_AGENT_ID`: current agent id; used by `--mine` and default comment author
- `POCKETSTUDIO_AGENT_NAME`: optional display name for comments
- `TINYAGI_AGENT_ID`: backward-compatible fallback for the current agent id

## API Shape

Task endpoints exposed by the backend:

- `GET /api/tasks`
- `POST /api/tasks`
- `GET /api/tasks/{task_id}`
- `PUT /api/tasks/{task_id}`
- `PATCH /api/tasks/{task_id}/status/{status}`
- `DELETE /api/tasks/{task_id}`
- `PUT /api/tasks/reorder`
- `GET /api/tasks/{task_id}/comments`
- `POST /api/tasks/{task_id}/comments`
- `DELETE /api/comments/{comment_id}`

Project endpoints are commonly used with tasks:

- `GET /api/projects`
- `POST /api/projects`
- `GET /api/projects/{project_id}`
- `PUT /api/projects/{project_id}`
- `DELETE /api/projects/{project_id}`

## Task Fields

Task create/update payload fields:

- `title`: required string
- `description`: optional string
- `status`: string, commonly `todo`, `in_progress`, `review`, `done`
- `assignee`: optional agent/team/user id
- `assigneeType`: optional assignee kind, commonly `agent`, `team`, or empty string
- `projectId`: optional project id

Responses commonly include:

- `id`: integer task id used by API routes
- `number`: project-local or global task number
- `identifier`: display identifier such as `PLAT-1` or `T-3`
- `projectId`, `sortOrder`, `commentCount`

## Workflow

If the user references a task id or identifier, finish the requested code work first, then update the task and leave a short comment summarizing changed files and verification.

Use the integer `id` when calling the API. If you only have an identifier like `PLAT-7`, list or search tasks first and find the matching integer id.

## Commands

### List Tasks

```bash
python <skill_dir>/scripts/tasks.py list
python <skill_dir>/scripts/tasks.py list --mine
python <skill_dir>/scripts/tasks.py list --status todo
python <skill_dir>/scripts/tasks.py list --assignee coder
python <skill_dir>/scripts/tasks.py list --project PROJECT_ID
python <skill_dir>/scripts/tasks.py list --query auth
python <skill_dir>/scripts/tasks.py list --mine --project PROJECT_ID --status in_progress
```

### Get A Task

```bash
python <skill_dir>/scripts/tasks.py get TASK_ID
```

### Create A Task

```bash
python <skill_dir>/scripts/tasks.py create --title "Fix auth bug"
python <skill_dir>/scripts/tasks.py create --title "Fix auth bug" --description "Login fails on mobile" --status todo
python <skill_dir>/scripts/tasks.py create --title "Review PR #42" --assignee reviewer --assignee-type agent
python <skill_dir>/scripts/tasks.py create --title "Add queue diagnostics" --project PROJECT_ID
```

### Update A Task

```bash
python <skill_dir>/scripts/tasks.py update TASK_ID --status done
python <skill_dir>/scripts/tasks.py update TASK_ID --title "Better title"
python <skill_dir>/scripts/tasks.py update TASK_ID --description "New details"
python <skill_dir>/scripts/tasks.py update TASK_ID --assignee coder --assignee-type agent
python <skill_dir>/scripts/tasks.py update TASK_ID --project PROJECT_ID
python <skill_dir>/scripts/tasks.py update TASK_ID --clear-assignee
python <skill_dir>/scripts/tasks.py update TASK_ID --clear-project
```

### Status Shortcut

```bash
python <skill_dir>/scripts/tasks.py status TASK_ID done
python <skill_dir>/scripts/tasks.py status TASK_ID review
```

### Comments

```bash
python <skill_dir>/scripts/tasks.py comment TASK_ID --content "Started: root cause appears to be queue retry state."
python <skill_dir>/scripts/tasks.py comment TASK_ID --content "Completed: fixed retry state and verified with tests."
python <skill_dir>/scripts/tasks.py comments TASK_ID
python <skill_dir>/scripts/tasks.py delete-comment COMMENT_ID
```

### Delete A Task

```bash
python <skill_dir>/scripts/tasks.py delete TASK_ID
```

### Reorder Columns

The helper accepts a JSON object mapping status columns to ordered task id lists:

```bash
python <skill_dir>/scripts/tasks.py reorder '{"todo":["1","2"],"review":["3"],"done":[]}'
```

If the JSON is easier to maintain in a file, pass `@path/to/file.json` or `-` for stdin.

## Good Practice

- Prefer `done` only after implementation and verification are complete.
- Use `projectId` to keep project work visible in the correct board.
- When blocked, leave a task comment with the blocker and keep the task in `todo` or `in_progress`.
