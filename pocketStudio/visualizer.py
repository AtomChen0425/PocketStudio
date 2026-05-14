from __future__ import annotations

import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from dataclasses import field
from typing import Any


DEFAULT_API_URL = "http://127.0.0.1:3777"


@dataclass
class AgentVisualState:
    id: str
    name: str
    provider: str
    model: str
    status: str = "idle"
    last_activity: str = "idle"
    response_length: int = 0
    provider_event_type: str = ""
    tool: str = ""
    process_id: str = ""
    updated_at: int = 0


@dataclass
class VisualizerSnapshot:
    agents: dict[str, AgentVisualState]
    teams: dict[str, dict[str, Any]]
    events: list[dict[str, Any]]
    queue_status: dict[str, Any]
    flows: list[str] = field(default_factory=list)


class VisualizerClient:
    def __init__(self, base_url: str | None = None, timeout: float = 5.0) -> None:
        self.base_url = (base_url or os.getenv("POCKETSTUDIO_API_URL") or DEFAULT_API_URL).rstrip("/")
        self.timeout = timeout

    def get_json(self, path: str) -> Any:
        request = urllib.request.Request(f"{self.base_url}{path}", method="GET")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Could not reach pocketStudio API at {self.base_url}: {exc.reason}") from exc
        return json_loads(body)

    def post_json(self, path: str, payload: dict[str, Any]) -> Any:
        data = json_dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Could not reach pocketStudio API at {self.base_url}: {exc.reason}") from exc
        return json_loads(body) if body else None

    def snapshot(self, team_id: str | None = None, event_limit: int = 80) -> VisualizerSnapshot:
        agents = normalize_agents(self.get_json("/api/agents"))
        teams = normalize_teams(self.get_json("/api/teams"))
        events = normalize_office_events(self.get_json(f"/api/events/office?limit={event_limit}"))
        queue_status = self.get_json("/api/queue/status") or {}
        visual_agents = build_agent_states(agents, teams, events, team_id=team_id)
        return VisualizerSnapshot(
            agents=visual_agents,
            teams=teams,
            events=events,
            queue_status=queue_status,
            flows=build_flows(events, team_id=team_id),
        )

    def chat_messages(self, team_id: str, limit: int = 50, since: int = 0) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode({"limit": limit, "since": since})
        data = self.get_json(f"/api/chatroom/{urllib.parse.quote(team_id)}?{query}")
        return data if isinstance(data, list) else []

    def post_chat(self, team_id: str, message: str, sender: str = "user") -> Any:
        return self.post_json(f"/api/chatroom/{urllib.parse.quote(team_id)}", {"sender": sender, "message": message})


def json_loads(body: str) -> Any:
    import json

    return json.loads(body)


def json_dumps(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False)


def normalize_agents(raw: Any) -> dict[str, dict[str, Any]]:
    if isinstance(raw, dict):
        items = raw.items()
    elif isinstance(raw, list):
        items = ((str(item.get("id", "")), item) for item in raw if isinstance(item, dict))
    else:
        items = []
    return {agent_id: dict(agent) for agent_id, agent in items if agent_id and isinstance(agent, dict)}


def normalize_teams(raw: Any) -> dict[str, dict[str, Any]]:
    if isinstance(raw, dict):
        items = raw.items()
    elif isinstance(raw, list):
        items = ((str(item.get("id", "")), item) for item in raw if isinstance(item, dict))
    else:
        items = []
    teams: dict[str, dict[str, Any]] = {}
    for team_id, team in items:
        if not team_id or not isinstance(team, dict):
            continue
        normalized = dict(team)
        members = normalized.get("agent_ids") or normalized.get("agents") or []
        normalized["agents"] = [str(member) for member in members]
        normalized["leader_agent"] = str(normalized.get("leader_agent") or normalized.get("leaderAgent") or "")
        teams[team_id] = normalized
    return teams


def normalize_office_events(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    events: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        data = item.get("data") if isinstance(item.get("data"), dict) else {}
        event = {"event": item.get("event") or data.get("type"), **data}
        events.append(event)
    return events


def build_agent_states(
    agents: dict[str, dict[str, Any]],
    teams: dict[str, dict[str, Any]],
    events: list[dict[str, Any]],
    team_id: str | None = None,
) -> dict[str, AgentVisualState]:
    agent_ids = visible_agent_ids(agents, teams, team_id)
    states = {
        agent_id: AgentVisualState(
            id=agent_id,
            name=str(agents.get(agent_id, {}).get("name") or agent_id),
            provider=str(agents.get(agent_id, {}).get("provider") or "local"),
            model=str(agents.get(agent_id, {}).get("model") or ""),
        )
        for agent_id in agent_ids
    }
    for event in events:
        event_type = str(event.get("type") or event.get("event") or "")
        agent_id = str(event.get("agentId") or event.get("agent_id") or "")
        if not agent_id or agent_id not in states:
            continue
        state = states[agent_id]
        if event_type == "agent:invoke":
            state.status = "active"
            state.last_activity = "processing"
            state.provider_event_type = ""
            state.updated_at = int(event.get("timestamp") or 0)
        elif event_type == "agent:progress":
            state.status = "active"
            state.provider = str(event.get("provider") or state.provider)
            state.provider_event_type = str(event.get("providerEventType") or "")
            state.tool = str(event.get("tool") or "")
            process = event.get("process") if isinstance(event.get("process"), dict) else {}
            state.process_id = str(process.get("pid") or "")
            state.last_activity = compact_text(str(event.get("summary") or event.get("content") or event.get("providerEventType") or "working"), 60)
            state.updated_at = int(event.get("timestamp") or 0)
        elif event_type == "agent:response":
            state.status = "done"
            content = str(event.get("content") or "")
            state.response_length = int(event.get("responseLength") or len(content))
            state.last_activity = compact_text(content, 60) if content else "done"
            state.updated_at = int(event.get("timestamp") or 0)
        elif event_type == "message:failed":
            state.status = "error"
            state.last_activity = compact_text(str(event.get("error") or "error"), 60)
            state.updated_at = int(event.get("timestamp") or 0)
        elif event_type == "agent:mention":
            to_agent = str(event.get("toAgent") or "")
            if to_agent in states:
                states[to_agent].status = "waiting"
                states[to_agent].last_activity = f"mentioned by @{event.get('fromAgent', '')}"
                states[to_agent].updated_at = int(event.get("timestamp") or 0)
    return states


def build_flows(events: list[dict[str, Any]], team_id: str | None = None, limit: int = 8) -> list[str]:
    flows: list[str] = []
    for event in events:
        event_type = str(event.get("type") or event.get("event") or "")
        if event_type == "agent:mention":
            if team_id and str(event.get("teamId") or "") != team_id:
                continue
            flows.append(f"@{event.get('fromAgent', '')} -> @{event.get('toAgent', '')}")
        elif event_type == "team:chatroom":
            if team_id and str(event.get("teamId") or "") != team_id:
                continue
            flows.append(
                f"@{event.get('fromAgent', '')} -> #{event.get('teamId', '')} chatroom ({event.get('delivered', 0)} delivered)"
            )
    return flows[-limit:]


def visible_agent_ids(
    agents: dict[str, dict[str, Any]],
    teams: dict[str, dict[str, Any]],
    team_id: str | None = None,
) -> list[str]:
    if team_id and team_id in teams:
        return [agent_id for agent_id in teams[team_id].get("agents", []) if agent_id in agents]
    team_members: list[str] = []
    for team in teams.values():
        for agent_id in team.get("agents", []):
            if agent_id in agents and agent_id not in team_members:
                team_members.append(agent_id)
    return team_members or list(agents)


def render_team_dashboard(snapshot: VisualizerSnapshot, team_id: str | None = None) -> str:
    team = snapshot.teams.get(team_id or "") if team_id else None
    title = f"pocketStudio Team Visualizer - @{team_id} ({team.get('name', team_id)})" if team else "pocketStudio Team Visualizer - all teams"
    lines = [title, "-" * min(78, len(title) + 8)]
    if not snapshot.agents:
        lines.append("No agents to show.")
    for agent in snapshot.agents.values():
        marker = {"idle": "○", "active": "●", "done": "✓", "error": "✗", "waiting": "◔"}.get(agent.status, "○")
        model = f"/{agent.model}" if agent.model else ""
        suffix = f" ({agent.response_length} chars)" if agent.response_length else ""
        details = compact_text(" ".join(part for part in [agent.provider_event_type, f"tool:{agent.tool}" if agent.tool else "", f"pid:{agent.process_id}" if agent.process_id else ""] if part), 42)
        details = f" [{details}]" if details else ""
        lines.append(f"{marker} @{agent.id:<18} {agent.provider}{model:<18} {agent.status:<7} {agent.last_activity}{suffix}{details}")
    lines.extend(render_team_lines(snapshot.teams, team_id))
    if snapshot.flows:
        lines.extend(["", "Flow:"])
        lines.extend(f"  {flow}" for flow in snapshot.flows)
    status = snapshot.queue_status
    lines.append("-" * 78)
    lines.append(
        "Queue queued={queued} running={processing} done={completed} dead={dead} pendingResponses={responsesPending}".format(
            queued=status.get("queued", status.get("incoming", 0)),
            processing=status.get("processing", 0),
            completed=status.get("completed", 0),
            dead=status.get("dead", 0),
            responsesPending=status.get("responsesPending", 0),
        )
    )
    lines.append("Recent activity:")
    for event in snapshot.events[-12:]:
        lines.append(f"  {compact_text(format_event(event), 100)}")
    return "\n".join(lines)


def render_team_lines(teams: dict[str, dict[str, Any]], team_id: str | None = None) -> list[str]:
    selected = {team_id: teams[team_id]} if team_id and team_id in teams else teams
    lines = ["", "Teams:"]
    if not selected:
        lines.append("  No teams configured.")
        return lines
    for current_id, team in selected.items():
        members = ", ".join(f"@{agent}" for agent in team.get("agents", []))
        leader = team.get("leader_agent") or "-"
        lines.append(f"  @{current_id}: {team.get('name', current_id)} [{members}] leader=@{leader}")
    return lines


def render_chatroom(team_id: str, messages: list[dict[str, Any]], connected: bool = True, limit: int = 50) -> str:
    state = "connected" if connected else "disconnected"
    lines = [f"pocketStudio Chatroom #{team_id} - {state}", "-" * 78]
    if not messages:
        lines.append("No messages yet.")
    for message in messages[-limit:]:
        sender = str(message.get("from_agent") or message.get("sender") or "unknown")
        text = compact_text(str(message.get("message") or ""), 100)
        created = str(message.get("created_at") or "")
        lines.append(f"[{created}] @{sender}: {text}")
    lines.append("-" * 78)
    lines.append("Ctrl+C to quit. Use --send to post a message from the CLI.")
    return "\n".join(lines)


def format_event(event: dict[str, Any]) -> str:
    event_type = str(event.get("type") or event.get("event") or "event")
    if event_type == "agent:progress":
        agent = event.get("agentId", "")
        detail = event.get("summary") or event.get("content") or event.get("providerEventType") or ""
        return f"{event_type} @{agent} {detail}"
    if event_type in {"agent:invoke", "agent:response"}:
        return f"{event_type} @{event.get('agentId', '')} {event.get('content', '')}"
    if event_type == "team:chatroom":
        return f"{event_type} #{event.get('teamId', '')} from @{event.get('fromAgent', '')}"
    if event_type.startswith("message:"):
        return f"{event_type} {event.get('target', '')} {event.get('message', '')}"
    return event_type


def compact_text(text: str, max_length: int) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_length:
        return normalized
    return normalized[: max_length - 1] + "…"


def run_team_visualizer(
    client: VisualizerClient,
    team_id: str | None = None,
    interval: float = 1.0,
    once: bool = False,
    event_limit: int = 80,
    clear_screen: bool = True,
) -> int:
    while True:
        snapshot = client.snapshot(team_id=team_id, event_limit=event_limit)
        if clear_screen:
            print("\033[2J\033[H", end="")
        print(render_team_dashboard(snapshot, team_id=team_id))
        if once:
            return 0
        time.sleep(interval)


def run_chatroom_viewer(
    client: VisualizerClient,
    team_id: str,
    interval: float = 1.0,
    once: bool = False,
    send: str | None = None,
    sender: str = "user",
    limit: int = 50,
    clear_screen: bool = True,
) -> int:
    if send:
        client.post_chat(team_id, send, sender=sender)
        if once:
            return 0
    since = 0
    messages: list[dict[str, Any]] = []
    while True:
        latest = client.chat_messages(team_id, limit=limit, since=since)
        if latest:
            messages.extend(latest)
            last_id = latest[-1].get("id")
            if isinstance(last_id, int):
                since = last_id
        if clear_screen:
            print("\033[2J\033[H", end="")
        print(render_chatroom(team_id, messages, limit=limit))
        if once:
            return 0
        time.sleep(interval)
