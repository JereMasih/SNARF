from snarf.telemetry import events


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
