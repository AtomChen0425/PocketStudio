#!/usr/bin/env bash
# ps-api.sh - thin wrapper for pocketStudio API operations.
#
# Usage:
#   ps-api.sh status
#   ps-api.sh agents list|get|create|put|delete
#   ps-api.sh teams list|get|create|put|delete
#   ps-api.sh settings get|update|preview|validate
#   ps-api.sh message <json>
#   ps-api.sh tasks list|create|update|delete
#   ps-api.sh projects list|create|update|delete
#   ps-api.sh queue status|dead|processing|recover-stale
#   ps-api.sh worker status|start|stop|tick
#   ps-api.sh logs [limit]

set -euo pipefail

API_BASE="${POCKETSTUDIO_API_BASE:-http://127.0.0.1:3777/api}"

need_jq() {
    if ! command -v jq >/dev/null 2>&1; then
        echo "ERROR: jq is required for this helper." >&2
        exit 1
    fi
}

check_api() {
    if ! curl -sf "${API_BASE}/health" >/dev/null 2>&1; then
        echo "ERROR: pocketStudio API not reachable at ${API_BASE}" >&2
        echo "Start it with: python -m uvicorn pocketStudio.main:app --host 127.0.0.1 --port 3777" >&2
        exit 1
    fi
}

json_get() {
    curl -sf "$1" | jq .
}

json_send() {
    local method="$1"
    local url="$2"
    local body="${3:-{}}"
    curl -sf -X "$method" "$url" -H 'Content-Type: application/json' -d "$body" | jq .
}

need_jq
cmd="${1:-help}"
shift || true

case "$cmd" in
    status)
        check_api
        echo "=== Health ==="
        json_get "${API_BASE}/health"
        echo "=== System ==="
        json_get "${API_BASE}/status"
        echo "=== Queue ==="
        json_get "${API_BASE}/queue/status"
        ;;

    agents)
        check_api
        sub="${1:-list}"; shift || true
        case "$sub" in
            list) json_get "${API_BASE}/agents" ;;
            get) json_get "${API_BASE}/agents/$1" ;;
            create) json_send POST "${API_BASE}/agents" "$1" ;;
            put) id="$1"; shift; json_send PUT "${API_BASE}/agents/${id}" "$1" ;;
            delete) json_send DELETE "${API_BASE}/agents/$1" ;;
            *) echo "Unknown agents subcommand: $sub" >&2; exit 1 ;;
        esac
        ;;

    teams)
        check_api
        sub="${1:-list}"; shift || true
        case "$sub" in
            list) json_get "${API_BASE}/teams" ;;
            get) json_get "${API_BASE}/teams/$1" ;;
            create) json_send POST "${API_BASE}/teams" "$1" ;;
            put) id="$1"; shift; json_send PUT "${API_BASE}/teams/${id}" "$1" ;;
            delete) json_send DELETE "${API_BASE}/teams/$1" ;;
            *) echo "Unknown teams subcommand: $sub" >&2; exit 1 ;;
        esac
        ;;

    settings)
        check_api
        sub="${1:-get}"; shift || true
        case "$sub" in
            get) json_get "${API_BASE}/settings" ;;
            update) json_send PUT "${API_BASE}/settings" "$1" ;;
            preview) json_send POST "${API_BASE}/settings/preview" "$1" ;;
            validate) json_send POST "${API_BASE}/settings/validate" "$1" ;;
            *) echo "Unknown settings subcommand: $sub" >&2; exit 1 ;;
        esac
        ;;

    message)
        check_api
        json_send POST "${API_BASE}/message" "$1"
        ;;

    tasks)
        check_api
        sub="${1:-list}"; shift || true
        case "$sub" in
            list) json_get "${API_BASE}/tasks" ;;
            create) json_send POST "${API_BASE}/tasks" "$1" ;;
            update) id="$1"; shift; json_send PUT "${API_BASE}/tasks/${id}" "$1" ;;
            delete) json_send DELETE "${API_BASE}/tasks/$1" ;;
            *) echo "Unknown tasks subcommand: $sub" >&2; exit 1 ;;
        esac
        ;;

    projects)
        check_api
        sub="${1:-list}"; shift || true
        case "$sub" in
            list) json_get "${API_BASE}/projects" ;;
            create) json_send POST "${API_BASE}/projects" "$1" ;;
            update) id="$1"; shift; json_send PUT "${API_BASE}/projects/${id}" "$1" ;;
            delete) json_send DELETE "${API_BASE}/projects/$1" ;;
            *) echo "Unknown projects subcommand: $sub" >&2; exit 1 ;;
        esac
        ;;

    queue)
        check_api
        sub="${1:-status}"; shift || true
        case "$sub" in
            status) json_get "${API_BASE}/queue/status" ;;
            dead) json_get "${API_BASE}/queue/dead" ;;
            processing) json_get "${API_BASE}/queue/processing" ;;
            recover-stale) json_send POST "${API_BASE}/queue/recover-stale" ;;
            *) echo "Unknown queue subcommand: $sub" >&2; exit 1 ;;
        esac
        ;;

    worker)
        check_api
        sub="${1:-status}"; shift || true
        case "$sub" in
            status) json_get "${API_BASE}/worker/status" ;;
            start|stop|pause|resume|restart|tick) json_send POST "${API_BASE}/worker/${sub}" ;;
            *) echo "Unknown worker subcommand: $sub" >&2; exit 1 ;;
        esac
        ;;

    logs)
        check_api
        limit="${1:-50}"
        json_get "${API_BASE}/logs?limit=${limit}"
        ;;

    help|*)
        cat <<'USAGE'
ps-api.sh - pocketStudio API wrapper

Commands:
  status
  agents list|get|create|put|delete
  teams list|get|create|put|delete
  settings get|update|preview|validate
  message <json>
  tasks list|create|update|delete
  projects list|create|update|delete
  queue status|dead|processing|recover-stale
  worker status|start|stop|pause|resume|restart|tick
  logs [limit]
USAGE
        ;;
esac
