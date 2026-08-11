from snarf.telemetry import events, spans


def test_start_tool_then_finish_emits_two_rows_sharing_event_id(tmp_path):
    path = tmp_path / "events.jsonl"
    span = spans.start_tool("gmail_summarize_inbox", path=path)
    spans.finish(span, estado="completo", path=path)
    rows = events.all_events(path=path, include_lifecycle=True)
    assert len(rows) == 2
    assert rows[0]["event_type"] == events.TOOL_STARTED
    assert rows[1]["event_type"] == events.TOOL_FINISHED
    assert rows[0]["event_id"] == rows[1]["event_id"] == span.event_id


def test_start_llm_then_fail_emits_failed_with_reason(tmp_path):
    path = tmp_path / "events.jsonl"
    span = spans.start_llm("anthropic", "claude-sonnet-5", path=path)
    spans.fail(span, reason="APIConnectionError", path=path)
    rows = events.all_events(path=path, include_lifecycle=True)
    assert rows[1]["event_type"] == events.LLM_FAILED
    assert rows[1]["estado"] == "error"
    assert rows[1]["detalle"] == "APIConnectionError"


def test_nested_spans_share_trace_id_and_correlate_parent(tmp_path):
    path = tmp_path / "events.jsonl"
    tool_span = spans.start_tool("gmail_summarize_inbox", path=path)
    with spans.active(tool_span):
        llm_span = spans.start_llm("anthropic", "claude-sonnet-5", path=path)
    spans.finish(llm_span, path=path)
    spans.finish(tool_span, path=path)

    assert llm_span.parent_event_id == tool_span.event_id
    assert llm_span.trace_id == tool_span.trace_id


def test_unmapped_tool_name_returns_null_span_and_emits_nothing(tmp_path):
    path = tmp_path / "events.jsonl"
    span = spans.start_tool("herramienta_sin_nodo_en_brain", path=path)
    assert span is spans.NULL_SPAN
    spans.finish(span, path=path)  # no-op, no debe levantar
    spans.fail(span, reason="algo", path=path)  # no-op, no debe levantar
    assert events.all_events(path=path, include_lifecycle=True) == []


def test_unmapped_vendor_returns_null_span_and_emits_nothing(tmp_path):
    path = tmp_path / "events.jsonl"
    span = spans.start_llm("vendor_desconocido", "modelo-x", path=path)
    assert span is spans.NULL_SPAN
    assert events.all_events(path=path, include_lifecycle=True) == []


def test_start_workflow_is_its_own_trace_root(tmp_path):
    path = tmp_path / "events.jsonl"
    span = spans.start_workflow("turn", path=path)
    assert span.trace_id == span.event_id
    assert span.parent_event_id is None


def test_active_on_null_span_is_a_harmless_noop():
    with spans.active(spans.NULL_SPAN) as span:
        assert span is spans.NULL_SPAN
