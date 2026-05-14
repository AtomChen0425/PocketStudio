from pocketStudio.visualizer import (
    VisualizerSnapshot,
    build_flows,
    build_agent_states,
    normalize_agents,
    normalize_office_events,
    normalize_teams,
    render_chatroom,
    render_team_dashboard,
    run_chatroom_viewer,
    run_team_visualizer,
)


def test_visualizer_normalizes_api_shapes_and_builds_agent_states() -> None:
    agents = normalize_agents(
        [
            {"id": "lead", "name": "Lead", "provider": "codex", "model": "gpt-5.4"},
            {"id": "coder", "name": "Coder", "provider": "local"},
        ]
    )
    teams = normalize_teams(
        [{"id": "dev", "name": "Dev", "agent_ids": ["lead", "coder"], "leaderAgent": "lead"}]
    )
    events = normalize_office_events(
        [
            {"event": "agent:invoke", "data": {"type": "agent:invoke", "agentId": "lead"}},
            {
                "event": "agent:progress",
                "data": {
                    "type": "agent:progress",
                    "agentId": "lead",
                    "providerEventType": "item.started",
                    "summary": "running tests",
                    "tool": "shell",
                    "process": {"pid": 123},
                },
            },
            {
                "event": "agent:response",
                "data": {"type": "agent:response", "agentId": "coder", "content": "done"},
            },
        ]
    )

    states = build_agent_states(agents, teams, events, team_id="dev")

    assert list(states) == ["lead", "coder"]
    assert states["lead"].status == "active"
    assert states["lead"].last_activity == "running tests"
    assert states["lead"].provider_event_type == "item.started"
    assert states["lead"].tool == "shell"
    assert states["lead"].process_id == "123"
    assert states["coder"].status == "done"
    assert states["coder"].response_length == 4
    assert teams["dev"]["agents"] == ["lead", "coder"]
    assert teams["dev"]["leader_agent"] == "lead"


def test_render_team_dashboard_includes_queue_and_recent_activity() -> None:
    snapshot = VisualizerSnapshot(
        agents=build_agent_states(
            {"lead": {"name": "Lead", "provider": "codex", "model": "gpt-5.4"}},
            {"dev": {"name": "Dev", "agents": ["lead"], "leader_agent": "lead"}},
            [{"type": "agent:progress", "agentId": "lead", "summary": "thinking in events"}],
            team_id="dev",
        ),
        teams={"dev": {"name": "Dev", "agents": ["lead"], "leader_agent": "lead"}},
        events=[
            {"type": "agent:progress", "agentId": "lead", "summary": "thinking in events"},
            {"type": "agent:mention", "teamId": "dev", "fromAgent": "lead", "toAgent": "coder"},
        ],
        queue_status={"queued": 1, "processing": 1, "completed": 2, "dead": 0, "responsesPending": 0},
        flows=["@lead -> @coder"],
    )

    rendered = render_team_dashboard(snapshot, team_id="dev")

    assert "pocketStudio Team Visualizer" in rendered
    assert "@lead" in rendered
    assert "thinking in events" in rendered
    assert "@lead -> @coder" in rendered
    assert "Queue queued=1 running=1 done=2" in rendered


def test_build_flows_includes_mentions_and_chatroom_events() -> None:
    flows = build_flows(
        [
            {"type": "agent:mention", "teamId": "dev", "fromAgent": "lead", "toAgent": "coder"},
            {"type": "team:chatroom", "teamId": "dev", "fromAgent": "coder", "delivered": 2},
            {"type": "agent:mention", "teamId": "other", "fromAgent": "x", "toAgent": "y"},
        ],
        team_id="dev",
    )

    assert flows == ["@lead -> @coder", "@coder -> #dev chatroom (2 delivered)"]


def test_render_chatroom_formats_messages() -> None:
    rendered = render_chatroom(
        "dev",
        [{"id": 1, "from_agent": "lead", "message": "hello team", "created_at": "2026-05-13T00:00:00"}],
    )

    assert "pocketStudio Chatroom #dev" in rendered
    assert "@lead: hello team" in rendered


def test_run_visualizers_clear_in_place_when_enabled(monkeypatch, capsys) -> None:
    calls = []

    class FakeClient:
        def snapshot(self, team_id=None, event_limit=80):
            return VisualizerSnapshot(agents={}, teams={}, events=[], queue_status={}, flows=[])

        def chat_messages(self, team_id, limit=50, since=0):
            return []

    monkeypatch.setattr("pocketStudio.visualizer.clear_terminal", lambda: calls.append("clear"))

    assert run_team_visualizer(FakeClient(), once=True) == 0
    assert run_chatroom_viewer(FakeClient(), "dev", once=True) == 0

    assert calls == ["clear", "clear"]
    output = capsys.readouterr().out
    assert "\x1b[2J" not in output


def test_run_visualizers_can_skip_clear(monkeypatch) -> None:
    calls = []

    class FakeClient:
        def snapshot(self, team_id=None, event_limit=80):
            return VisualizerSnapshot(agents={}, teams={}, events=[], queue_status={}, flows=[])

        def chat_messages(self, team_id, limit=50, since=0):
            return []

    monkeypatch.setattr("pocketStudio.visualizer.clear_terminal", lambda: calls.append("clear"))

    assert run_team_visualizer(FakeClient(), once=True, clear_screen=False) == 0
    assert run_chatroom_viewer(FakeClient(), "dev", once=True, clear_screen=False) == 0

    assert calls == []
