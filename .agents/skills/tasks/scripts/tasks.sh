#!/usr/bin/env bash
# tasks.sh - manage pocketStudio tasks through the REST API.

set -euo pipefail

API_BASE="${POCKETSTUDIO_API_BASE:-http://127.0.0.1:3777/api}"
AGENT_ID="${POCKETSTUDIO_AGENT_ID:-${TINYAGI_AGENT_ID:-}}"
AGENT_NAME="${POCKETSTUDIO_AGENT_NAME:-${AGENT_ID:-Agent}}"

usage() {
    cat <<'USAGE'
tasks.sh - manage pocketStudio tasks

Commands:
  list [--mine] [--status STATUS] [--assignee ID] [--project PROJECT_ID] [--query TEXT]
  get TASK_ID
  create --title TITLE [--description DESC] [--status STATUS] [--assignee ID] [--assignee-type TYPE] [--project PROJECT_ID]
  update TASK_ID [--title TITLE] [--description DESC] [--status STATUS] [--assignee ID] [--assignee-type TYPE] [--project PROJECT_ID] [--clear-assignee] [--clear-project]
  status TASK_ID STATUS
  delete TASK_ID
  comment TASK_ID --content MESSAGE [--author NAME] [--author-type TYPE]
  comments TASK_ID
  delete-comment COMMENT_ID
  reorder JSON_COLUMNS

Environment:
  POCKETSTUDIO_API_BASE   API base URL, default http://127.0.0.1:3777/api
  POCKETSTUDIO_AGENT_ID   Current agent id for --mine and default comment author
  POCKETSTUDIO_AGENT_NAME Optional display name for comments

Examples:
  tasks.sh list --mine --status in_progress
  tasks.sh create --title "Fix auth bug" --project platform
  tasks.sh update 123 --status review --assignee reviewer --assignee-type agent
  tasks.sh status 123 done
  tasks.sh comment 123 --content "Completed and verified with tests."
USAGE
    exit 1
}

die() {
    echo "ERROR: $*" >&2
    exit 1
}

require_jq() {
    command -v jq >/dev/null 2>&1 || die "jq is required"
}

api_get() {
    curl -sf "$1"
}

api_json() {
    local method="$1"
    local url="$2"
    local body="${3:-{}}"
    curl -sf -X "$method" "$url" -H 'Content-Type: application/json' -d "$body"
}

json_string_or_null() {
    local value="$1"
    if [[ -z "$value" ]]; then
        printf 'null'
    else
        jq -Rn --arg value "$value" '$value'
    fi
}

cmd_list() {
    require_jq
    local mine=false status="" assignee="" project="" query=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --mine) mine=true; shift ;;
            --status) status="$2"; shift 2 ;;
            --assignee) assignee="$2"; shift 2 ;;
            --project|--project-id) project="$2"; shift 2 ;;
            --query|-q) query="$2"; shift 2 ;;
            *) die "Unknown list flag: $1" ;;
        esac
    done
    if $mine; then
        [[ -n "$AGENT_ID" ]] || die "--mine requires POCKETSTUDIO_AGENT_ID"
        assignee="$AGENT_ID"
    fi

    local params=()
    [[ -n "$status" ]] && params+=("status=${status}")
    [[ -n "$assignee" ]] && params+=("assignee=${assignee}")
    [[ -n "$project" ]] && params+=("projectId=${project}")
    [[ -n "$query" ]] && params+=("q=${query}")

    local url="${API_BASE}/tasks"
    if [[ ${#params[@]} -gt 0 ]]; then
        local joined
        joined=$(IFS='&'; echo "${params[*]}")
        url="${url}?${joined}"
    fi

    local result
    result=$(api_get "$url") || die "Failed to list tasks from ${url}"
    echo "$result" | jq -r '.[] | "[\(.status)] \(.id) \(.identifier // "")  \(.title)  project=\(.projectId // "-") assignee=\(.assignee // "-") comments=\(.commentCount // 0)"'
    echo "---"
    echo "$result" | jq -r 'length | "\(.) task(s)"'
}

cmd_get() {
    require_jq
    [[ $# -ge 1 ]] || die "Task ID is required"
    api_get "${API_BASE}/tasks/$1" | jq .
}

build_task_payload() {
    local title="$1" description="$2" status="$3" assignee="$4" assignee_type="$5" project="$6" clear_assignee="$7" clear_project="$8"
    jq -n \
        --arg title "$title" \
        --arg description "$description" \
        --arg status "$status" \
        --arg assignee "$assignee" \
        --arg assigneeType "$assignee_type" \
        --arg projectId "$project" \
        --argjson clearAssignee "$clear_assignee" \
        --argjson clearProject "$clear_project" \
        '{
            title: (if $title == "" then empty else $title end),
            description: (if $description == "" then empty else $description end),
            status: (if $status == "" then empty else $status end),
            assignee: (if $clearAssignee then null elif $assignee == "" then empty else $assignee end),
            assigneeType: (if $clearAssignee then "" elif $assigneeType == "" then empty else $assigneeType end),
            projectId: (if $clearProject then null elif $projectId == "" then empty else $projectId end)
        }'
}

cmd_create() {
    require_jq
    local title="" description="" status="todo" assignee="" assignee_type="agent" project=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --title) title="$2"; shift 2 ;;
            --description) description="$2"; shift 2 ;;
            --status) status="$2"; shift 2 ;;
            --assignee) assignee="$2"; shift 2 ;;
            --assignee-type|--assigneeType) assignee_type="$2"; shift 2 ;;
            --project|--project-id|--projectId) project="$2"; shift 2 ;;
            *) die "Unknown create flag: $1" ;;
        esac
    done
    [[ -n "$title" ]] || die "--title is required"
    if [[ -z "$assignee" && -n "$AGENT_ID" ]]; then
        assignee="$AGENT_ID"
        assignee_type="agent"
    fi
    local payload
    payload=$(build_task_payload "$title" "$description" "$status" "$assignee" "$assignee_type" "$project" false false)
    api_json POST "${API_BASE}/tasks" "$payload" | jq .
}

cmd_update() {
    require_jq
    [[ $# -ge 1 ]] || die "Task ID is required"
    local task_id="$1"; shift
    local title="" description="" status="" assignee="" assignee_type="" project="" clear_assignee=false clear_project=false
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --title) title="$2"; shift 2 ;;
            --description) description="$2"; shift 2 ;;
            --status) status="$2"; shift 2 ;;
            --assignee) assignee="$2"; shift 2 ;;
            --assignee-type|--assigneeType) assignee_type="$2"; shift 2 ;;
            --project|--project-id|--projectId) project="$2"; shift 2 ;;
            --clear-assignee) clear_assignee=true; shift ;;
            --clear-project) clear_project=true; shift ;;
            *) die "Unknown update flag: $1" ;;
        esac
    done
    local payload
    payload=$(build_task_payload "$title" "$description" "$status" "$assignee" "$assignee_type" "$project" "$clear_assignee" "$clear_project")
    api_json PUT "${API_BASE}/tasks/${task_id}" "$payload" | jq .
}

cmd_status() {
    require_jq
    [[ $# -ge 2 ]] || die "Usage: tasks.sh status TASK_ID STATUS"
    api_json PATCH "${API_BASE}/tasks/$1/status/$2" | jq .
}

cmd_delete() {
    require_jq
    [[ $# -ge 1 ]] || die "Task ID is required"
    api_json DELETE "${API_BASE}/tasks/$1" | jq .
}

cmd_comment() {
    require_jq
    [[ $# -ge 1 ]] || die "Task ID is required"
    local task_id="$1"; shift
    local content="" author="$AGENT_NAME" author_type="agent"
    [[ -n "$AGENT_ID" ]] || author_type="user"
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --content) content="$2"; shift 2 ;;
            --author) author="$2"; shift 2 ;;
            --author-type|--authorType) author_type="$2"; shift 2 ;;
            *) die "Unknown comment flag: $1" ;;
        esac
    done
    [[ -n "$content" ]] || die "--content is required"
    local payload
    payload=$(jq -n --arg author "$author" --arg authorType "$author_type" --arg content "$content" '{author: $author, authorType: $authorType, content: $content}')
    api_json POST "${API_BASE}/tasks/${task_id}/comments" "$payload" | jq .
}

cmd_comments() {
    require_jq
    [[ $# -ge 1 ]] || die "Task ID is required"
    api_get "${API_BASE}/tasks/$1/comments" | jq .
}

cmd_delete_comment() {
    require_jq
    [[ $# -ge 1 ]] || die "Comment ID is required"
    api_json DELETE "${API_BASE}/comments/$1" | jq .
}

cmd_reorder() {
    require_jq
    [[ $# -ge 1 ]] || die "JSON column map is required"
    api_json PUT "${API_BASE}/tasks/reorder" "$1" | jq .
}

[[ $# -ge 1 ]] || usage
command="$1"
shift || true

case "$command" in
    list) cmd_list "$@" ;;
    get) cmd_get "$@" ;;
    create) cmd_create "$@" ;;
    update) cmd_update "$@" ;;
    status) cmd_status "$@" ;;
    delete) cmd_delete "$@" ;;
    comment) cmd_comment "$@" ;;
    comments) cmd_comments "$@" ;;
    delete-comment) cmd_delete_comment "$@" ;;
    reorder) cmd_reorder "$@" ;;
    help|-h|--help) usage ;;
    *) die "Unknown command: $command" ;;
esac
