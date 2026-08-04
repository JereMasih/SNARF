from snarf.telemetry import events, input_log


def test_record_and_recent_roundtrip(tmp_path):
    path = tmp_path / "input.jsonl"
    input_log.record("text", path=path, events_path=tmp_path / "events.jsonl")
    entries = input_log.recent(path=path)
    assert len(entries) == 1
    assert entries[0]["channel"] == "text"
    assert entries[0]["category"] is None


def test_record_with_category_for_file_channel(tmp_path):
    path = tmp_path / "input.jsonl"
    input_log.record("file", category="image", path=path, events_path=tmp_path / "events.jsonl")
    entries = input_log.recent(path=path)
    assert entries[0]["channel"] == "file"
    assert entries[0]["category"] == "image"


def test_recent_returns_only_the_last_n_entries(tmp_path):
    path = tmp_path / "input.jsonl"
    for i in range(5):
        input_log.record("text", path=path, events_path=tmp_path / "events.jsonl")
    entries = input_log.recent(n=2, path=path)
    assert len(entries) == 2


def test_recent_with_no_entries_is_empty(tmp_path):
    path = tmp_path / "no_existe.jsonl"
    assert input_log.recent(path=path) == []


def test_record_emits_a_unified_event_per_channel(tmp_path):
    events_path = tmp_path / "events.jsonl"
    input_log.record("text", path=tmp_path / "input.jsonl", events_path=events_path)
    input_log.record("voice", path=tmp_path / "input.jsonl", events_path=events_path)
    input_log.record("file", category="image", path=tmp_path / "input.jsonl", events_path=events_path)
    emitted = events.recent(path=events_path)
    assert [e["nodo"] for e in emitted] == ["input_text", "input_voice", "input_file"]
    assert emitted[2]["skill"] == "image"
    assert all(e["agente"] == "input" for e in emitted)
    assert all(e["estado"] == "completo" for e in emitted)
