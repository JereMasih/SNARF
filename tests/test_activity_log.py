from snarf.telemetry import activity_log


def test_record_and_recent_roundtrip(tmp_path):
    path = tmp_path / "activity.jsonl"
    activity_log.record("drive_list_files", "ok", duration_ms=12.3, path=path, events_path=tmp_path / "events.jsonl")
    entries = activity_log.recent(path=path)
    assert len(entries) == 1
    assert entries[0]["tool_name"] == "drive_list_files"
    assert entries[0]["status"] == "ok"
    assert entries[0]["duration_ms"] == 12.3


def test_recent_returns_only_the_last_n_entries(tmp_path):
    path = tmp_path / "activity.jsonl"
    for i in range(5):
        activity_log.record(f"tool_{i}", "ok", path=path, events_path=tmp_path / "events.jsonl")
    entries = activity_log.recent(n=2, path=path)
    assert [e["tool_name"] for e in entries] == ["tool_3", "tool_4"]


def test_stats_counts_calls_by_tool_and_errors(tmp_path):
    path = tmp_path / "activity.jsonl"
    events_path = tmp_path / "events.jsonl"
    activity_log.record("drive_list_files", "ok", path=path, events_path=events_path)
    activity_log.record("drive_list_files", "ok", path=path, events_path=events_path)
    activity_log.record("drive_list_files", "error", error="boom", path=path, events_path=events_path)
    activity_log.record("gmail_list_messages", "ok", path=path, events_path=events_path)

    result = activity_log.stats(path=path)

    assert result["total_calls"] == 4
    assert result["errors"] == 1
    assert result["by_tool"] == {"drive_list_files": 3, "gmail_list_messages": 1}


def test_stats_and_recent_with_no_entries_are_empty(tmp_path):
    path = tmp_path / "no_existe.jsonl"
    assert activity_log.stats(path=path) == {"total_calls": 0, "errors": 0, "by_tool": {}}
    assert activity_log.recent(path=path) == []


def test_record_emits_a_unified_telemetry_event_derived_from_brain_node(tmp_path):
    path = tmp_path / "activity.jsonl"
    events_path = tmp_path / "events.jsonl"
    activity_log.record("drive_list_files", "ok", duration_ms=142.3, path=path, events_path=events_path)
    from snarf.telemetry import events

    emitted = events.recent(path=events_path)
    assert len(emitted) == 1
    assert emitted[0]["nodo"] == "drive"
    assert emitted[0]["agente"] == "capability"
    assert emitted[0]["skill"] == "drive_list_files"
    assert emitted[0]["latencia_ms"] == 142.3
    assert emitted[0]["estado"] == "completo"


def test_record_emits_error_events_with_estado_error(tmp_path):
    path = tmp_path / "activity.jsonl"
    events_path = tmp_path / "events.jsonl"
    activity_log.record("drive_list_files", "error", error="boom", path=path, events_path=events_path)
    from snarf.telemetry import events

    emitted = events.recent(path=events_path)
    assert emitted[0]["estado"] == "error"


def test_record_routes_unknown_tool_status_to_the_orchestrator_node(tmp_path):
    path = tmp_path / "activity.jsonl"
    events_path = tmp_path / "events.jsonl"
    activity_log.record("herramienta_inventada", "unknown_tool", path=path, events_path=events_path)
    from snarf.telemetry import events

    emitted = events.recent(path=events_path)
    assert emitted[0]["nodo"] == "orchestrator"
    assert emitted[0]["estado"] == "error"
