from snarf.telemetry import replay, spans


def test_events_for_trace_returns_only_that_traces_events_in_order(tmp_path):
    path = tmp_path / "events.jsonl"
    board = spans.start_workflow("executive_board", path=path)
    with spans.active(board):
        role_span = spans.start_agent("cto", path=path)
        spans.finish(role_span, path=path)
    spans.finish(board, path=path)
    # Traza no relacionada, no debe aparecer en el replay de arriba.
    other = spans.start_workflow("turn", path=path)
    spans.finish(other, path=path)

    result = replay.events_for_trace(board.trace_id, path=path)

    assert [e["event_type"] for e in result] == [
        "workflow.started",
        "agent.started",
        "agent.finished",
        "workflow.finished",
    ]
    assert all(e["trace_id"] == board.trace_id for e in result)
    timestamps = [e["timestamp"] for e in result]
    assert timestamps == sorted(timestamps)


def test_events_for_trace_includes_the_deterministic_verb(tmp_path):
    path = tmp_path / "events.jsonl"
    span = spans.start_workflow("turn", path=path)
    spans.finish(span, path=path)

    result = replay.events_for_trace(span.trace_id, path=path)

    assert all("verbo" in e and e["verbo"] for e in result)


def test_events_for_trace_returns_empty_for_an_unknown_trace(tmp_path):
    path = tmp_path / "events.jsonl"
    span = spans.start_workflow("turn", path=path)
    spans.finish(span, path=path)

    assert replay.events_for_trace("trace-que-no-existe", path=path) == []


def test_list_recent_traces_reports_kind_and_final_state(tmp_path):
    path = tmp_path / "events.jsonl"
    board = spans.start_workflow("executive_board", path=path)
    with spans.active(board):
        role_span = spans.start_agent("cto", path=path)
        spans.finish(role_span, path=path)
    spans.finish(board, estado="completo", path=path)

    traces = replay.list_recent_traces(path=path)

    assert len(traces) == 1
    trace = traces[0]
    assert trace["trace_id"] == board.trace_id
    assert trace["kind"] == "executive_board"
    assert trace["estado"] == "completo"
    assert trace["started_at"] is not None
    assert trace["finished_at"] is not None
    assert "cto" in trace["roles"]


def test_list_recent_traces_reports_en_curso_when_never_finished(tmp_path):
    path = tmp_path / "events.jsonl"
    spans.start_workflow("executive_board", path=path)

    traces = replay.list_recent_traces(path=path)

    assert traces[0]["estado"] == "en_curso"
    assert traces[0]["finished_at"] is None


def test_list_recent_traces_orders_newest_first(tmp_path):
    path = tmp_path / "events.jsonl"
    first = spans.start_workflow("turn", path=path)
    spans.finish(first, path=path)
    second = spans.start_workflow("turn", path=path)
    spans.finish(second, path=path)

    traces = replay.list_recent_traces(path=path)

    assert [t["trace_id"] for t in traces] == [second.trace_id, first.trace_id]


def test_list_recent_traces_respects_the_limit(tmp_path):
    path = tmp_path / "events.jsonl"
    for _ in range(5):
        span = spans.start_workflow("turn", path=path)
        spans.finish(span, path=path)

    assert len(replay.list_recent_traces(n=2, path=path)) == 2
