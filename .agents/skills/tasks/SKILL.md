---
name: tasks
description: "Manage pocketStudio project tasks through the local FastAPI API: list, search, create, update, reorder, delete, assign, comment on, and complete tasks. Use when a message contains a task id or task identifier, when you need to check assigned work, create follow-up work, update status, or leave implementation notes on a task."
---

# Tasks

Use this skill to manage pocketStudio tasks and project kanban state through the REST API.

## API Shape

Default API base:

```bash
API="${POCKETSTUDIO_API_BASE:-http://127.0.0.1:3777/api}"
```

Main task endpoints:

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

Project endpoints often used with tasks:

- `GET /api/projects`
- `POST /api/projects`
- `GET /api/projects/{project_id}`
- `PUT /api/projects/{project_id}`
- `DELETE /api/projects/{project_id}`

## Task Fields

Task create/update payload fields:

- `title`: required string
- `description`: optional string
- `status`: string, commonly `todo`, `in_progress`, `review`, `done`; legacy imports may also use `backlog`
- `assignee`: optional agent/team/user id
- `assigneeType`: optional assignee kind, commonly `agent`, `team`, or empty string
- `projectId`: optional project id
- `position`: optional integer sort order

Responses include:

- `id`: integer task id used by API routes
- `number`: project-local or global task number
- `identifier`: display identifier such as `PLAT-1` or `T-3`
- `projectId`, `sortOrder`, `commentCount`
- create/update responses also include an envelope: top-level task fields plus `ok` and `task`

## Automatic Task Completion

If you receive work that references a task id or identifier, finish the work first, then update the task and leave a comment.

Use an integer `id` when calling the API. If you only have an `identifier` like `PLAT-7`, list/search tasks and find the matching integer `id`.

```bash
<skill_dir>/scripts/tasks.sh list --query PLAT-7
<skill_dir>/scripts/tasks.sh update TASK_ID --status done
<skill_dir>/scripts/tasks.sh comment TASK_ID --content "Completed: brief summary of what changed and how it was verified."
```

## Helper Script

The bundled helper is:

```bash
<skill_dir>/scripts/tasks.sh
```

It requires `curl`; pretty output requires `jq`.

Environment variables:

- `POCKETSTUDIO_API_BASE`: API base URL, default `http://127.0.0.1:3777/api`
- `POCKETSTUDIO_AGENT_ID`: current agent id; used by `--mine` and default comment author
- `POCKETSTUDIO_AGENT_NAME`: optional display name for comments
- `TINYAGI_AGENT_ID`: accepted as a backward-compatible fallback for current agent id

## Commands

### List Tasks

```bash
# List all tasks
<skill_dir>/scripts/tasks.sh list

# List tasks assigned to this agent
POCKETSTUDIO_AGENT_ID=coder <skill_dir>/scripts/tasks.sh list --mine

# Filter by status, assignee, project, or query
<skill_dir>/scripts/tasks.sh list --status todo
<skill_dir>/scripts/tasks.sh list --assignee coder
<skill_dir>/scripts/tasks.sh list --project PROJECT_ID
<skill_dir>/scripts/tasks.sh list --query auth

# Combine filters
<skill_dir>/scripts/tasks.sh list --mine --project PROJECT_ID --status in_progress
```

### Get A Task

```bash
<skill_dir>/scripts/tasks.sh get TASK_ID
```

### Create A Task

```bash
# Create an unassigned task
<skill_dir>/scripts/tasks.sh create --title "Fix auth bug"

# Create with description and status
<skill_dir>/scripts/tasks.sh create --title "Fix auth bug" --description "Login fails on mobile" --status todo

# Create and assign to an agent
<skill_dir>/scripts/tasks.sh create --title "Review PR #42" --assignee reviewer --assignee-type agent

# Create under a project
<skill_dir>/scripts/tasks.sh create --title "Add queue diagnostics" --project PROJECT_ID
```

### Update A Task

```bash
# Move task to done
<skill_dir>/scripts/tasks.sh update TASK_ID --status done

# Update title/description/assignee/project
<skill_dir>/scripts/tasks.sh update TASK_ID --title "Better title"
<skill_dir>/scripts/tasks.sh update TASK_ID --description "New details"
<skill_dir>/scripts/tasks.sh update TASK_ID --assignee coder --assignee-type agent
<skill_dir>/scripts/tasks.sh update TASK_ID --project PROJECT_ID

# Clear assignee or project
<skill_dir>/scripts/tasks.sh update TASK_ID --clear-assignee
<skill_dir>/scripts/tasks.sh update TASK_ID --clear-project
```

### Status Shortcut

```bash
<skill_dir>/scripts/tasks.sh status TASK_ID done
<skill_dir>/scripts/tasks.sh status TASK_ID review
```

### Comments

```bash
# Add a progress note
<skill_dir>/scripts/tasks.sh comment TASK_ID --content "Started: root cause appears to be queue retry state."

# Add a completion note
<skill_dir>/scripts/tasks.sh comment TASK_ID --content "Completed: fixed retry state and verified with tests."

# List comments
<skill_dir>/scripts/tasks.sh comments TASK_ID

# Delete a comment
<skill_dir>/scripts/tasks.sh delete-comment COMMENT_ID
```

### Delete A Task

```bash
<skill_dir>/scripts/tasks.sh delete TASK_ID
```

### Reorder Columns

The API expects a JSON object mapping status columns to ordered task id lists:

```bash
<skill_dir>/scripts/tasks.sh reorder '{"todo":["1","2"],"review":["3"],"done":[]}'
```

## Direct Curl Examples

```bash
# List project tasks
curl -s "$API/tasks?projectId=PROJECT_ID" | jq .

# Create
curl -s -X POST "$API/tasks" \
  -H 'Content-Type: application/json' \
  -d '{"title":"Fix auth bug","status":"todo","assignee":"coder","assigneeType":"agent","projectId":"PROJECT_ID"}' | jq .

# Update
curl -s -X PUT "$API/tasks/123" \
  -H 'Content-Type: application/json' \
  -d '{"status":"review","description":"Ready for review."}' | jq .

# Patch status
curl -s -X PATCH "$API/tasks/123/status/done" | jq .

# Comment
curl -s -X POST "$API/tasks/123/comments" \
  -H 'Content-Type: application/json' \
  -d '{"author":"coder","authorType":"agent","content":"Completed and tested."}' | jq .
```

## Good Practice

- When completing a task, update `status` and add a comment describing changed files and verification.
- Use `projectId` to keep project work visible in the correct board.
- Prefer `done` only after implementation and verification are complete.
- If blocked, leave a task comment with the blocker and keep status as `todo` or `in_progress`.
