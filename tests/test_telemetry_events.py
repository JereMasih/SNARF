from snarf.telemetry import context, events, spans


def test_record_vendor_event_tags_the_real_llm_role_when_set(tmp_path):
    path = tmp_path / "events.jsonl"
    context.set_llm_role("dashboard_curator")
    try:
        events.record_vendor_event("xai", "grok-4-1-fast", 0.001, {"input_tokens": 10, "output_tokens": 5}, path=path)
    finally:
        context.clear_llm_role()
    entries = events.recent(path=path)
    assert entries[0]["llm_role"] == "dashboard_curator"


def test_record_vendor_event_llm_role_is_none_when_not_set(tmp_path):
    path = tmp_path / "events.jsonl"
    context.clear_llm_role()
    events.record_vendor_event("xai", "grok-4-1-fast", 0.001, {"input_tokens": 10, "output_tokens": 5}, path=path)
    entries = events.recent(path=path)
    assert entries[0]["llm_role"] is None


def test_record_tool_event_derives_nodo_and_agente_from_brain(tmp_path):
    path = tmp_path / "events.jsonl"
    events.record_tool_event("gmail_summarize_inbox", "ok", duration_ms=88.0, path=path)
    entries = events.recent(path=path)
    assert entries[0]["nodo"] == "specialist_gmail"
    assert entries[0]["agente"] == "specialist"
    assert entries[0]["skill"] == "gmail_summarize_inbox"
    assert entries[0]["latencia_ms"] == 88.0
    assert entries[0]["estado"] == "completo"


def test_record_tool_event_with_unmapped_tool_name_emits_nothing(tmp_path):
    path = tmp_path / "events.jsonl"
    events.record_tool_event("herramienta_sin_nodo_en_brain", "ok", path=path)
    assert events.recent(path=path) == []


def test_record_vendor_event_derives_nodo_from_vendor(tmp_path):
    path = tmp_path / "events.jsonl"
    events.record_vendor_event("voyage", "voyage-4-lite", 0.0004, {"tokens": 500}, path=path)
    entries = events.recent(path=path)
    assert entries[0]["nodo"] == "knowledge"
    assert entries[0]["modelo"] == "voyage-4-lite"
    assert entries[0]["costo_usd"] == 0.0004


def test_record_vendor_event_with_unmapped_vendor_emits_nothing(tmp_path):
    path = tmp_path / "events.jsonl"
    events.record_vendor_event("vendor_desconocido", "modelo-x", None, {}, path=path)
    assert events.recent(path=path) == []


def test_record_input_event_with_unmapped_channel_emits_nothing(tmp_path):
    path = tmp_path / "events.jsonl"
    events.record_input_event("canal_inexistente", path=path)
    assert events.recent(path=path) == []


def test_recent_with_no_entries_is_empty(tmp_path):
    assert events.recent(path=tmp_path / "no_existe.jsonl") == []


# --- Fase 1 del plan de observabilidad: schema v2, event_id, event_type ----


def test_v2_row_has_schema_version_event_id_and_origin_pid(tmp_path):
    import os

    path = tmp_path / "events.jsonl"
    events.record_tool_event("gmail_summarize_inbox", "ok", path=path)
    entry = events.recent(path=path)[0]
    assert entry["schema_version"] == 2
    assert entry["event_id"]
    assert entry["origin_pid"] == os.getpid()


def test_record_tool_event_ok_emits_tool_finished(tmp_path):
    path = tmp_path / "events.jsonl"
    events.record_tool_event("gmail_summarize_inbox", "ok", path=path)
    entry = events.recent(path=path)[0]
    assert entry["event_type"] == events.TOOL_FINISHED


def test_record_tool_event_error_emits_tool_failed(tmp_path):
    path = tmp_path / "events.jsonl"
    events.record_tool_event("gmail_summarize_inbox", "error", path=path)
    entry = events.recent(path=path)[0]
    assert entry["event_type"] == events.TOOL_FAILED


def test_all_events_hides_lifecycle_events_by_default(tmp_path):
    path = tmp_path / "events.jsonl"
    events.record_tool_event("gmail_summarize_inbox", "ok", path=path)
    events._write({"schema_version": 2, "event_type": events.TOOL_STARTED, "event_id": "x"}, path)
    assert len(events.all_events(path=path)) == 1
    assert len(events.all_events(path=path, include_lifecycle=True)) == 2


def test_recent_hides_lifecycle_events_by_default(tmp_path):
    path = tmp_path / "events.jsonl"
    events.record_tool_event("gmail_summarize_inbox", "ok", path=path)
    events._write({"schema_version": 2, "event_type": events.WORKFLOW_STARTED, "event_id": "y"}, path)
    assert len(events.recent(path=path)) == 1
    assert len(events.recent(path=path, include_lifecycle=True)) == 2


def test_v1_row_without_event_type_counts_as_legacy():
    assert events.is_legacy({"nodo": "drive"}) is True


def test_record_tool_event_span_none_still_gets_correlated_to_ambient_parent(tmp_path):
    path = tmp_path / "events.jsonl"
    context.set_conversation_id("conv-1")
    try:
        with context.span("parent-event-id", trace_id="trace-1"):
            events.record_tool_event("gmail_summarize_inbox", "ok", path=path)
    finally:
        context.clear_conversation_id()
    entry = events.recent(path=path)[0]
    assert entry["parent_event_id"] == "parent-event-id"
    assert entry["trace_id"] == "trace-1"


# --- Fase 8: HITL genérico (ADR 0143) --------------------------------------


def test_approval_requested_event_carries_the_real_preview(tmp_path):
    path = tmp_path / "events.jsonl"
    span = spans.start_tool("gmail_send_message", path=path)
    events.record_lifecycle_event(
        events.APPROVAL_REQUESTED, span, detalle="Pide confirmación: gmail_send_message",
        preview={"to": "a@b.com"}, path=path,
    )
    rows = events.all_events(path=path, include_lifecycle=True)
    approval_row = rows[-1]
    assert approval_row["event_type"] == events.APPROVAL_REQUESTED
    assert approval_row["preview"] == {"to": "a@b.com"}
    # Mismo event_id que el tool.started de este span (correlación real,
    # igual criterio que tool.finished) — comparten identidad, no la traza.
    assert approval_row["event_id"] == span.event_id
    assert approval_row["parent_event_id"] == span.parent_event_id


def test_approval_granted_event_shares_the_trace_of_its_tool_span(tmp_path):
    path = tmp_path / "events.jsonl"
    span = spans.start_tool("drive_delete_file", path=path)
    events.record_lifecycle_event(events.APPROVAL_GRANTED, span, detalle="Confirmado: drive_delete_file", path=path)
    rows = events.all_events(path=path, include_lifecycle=True)
    approval_row = rows[-1]
    assert approval_row["event_type"] == events.APPROVAL_GRANTED
    assert approval_row["trace_id"] == span.trace_id


def test_approval_events_are_invisible_to_legacy_consumers_by_default(tmp_path):
    path = tmp_path / "events.jsonl"
    span = spans.start_tool("gmail_send_message", path=path)
    events.record_lifecycle_event(events.APPROVAL_REQUESTED, span, path=path)
    # recent()/all_events() sin include_lifecycle=True es lo que ya usan
    # dashboards/cost_history existentes — no debe verse el evento nuevo.
    legacy_rows = [r for r in events.recent(path=path) if r["event_type"] == events.APPROVAL_REQUESTED]
    assert legacy_rows == []
