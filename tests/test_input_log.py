from snarf.telemetry import input_log


def test_record_and_recent_roundtrip(tmp_path):
    path = tmp_path / "input.jsonl"
    input_log.record("text", path=path)
    entries = input_log.recent(path=path)
    assert len(entries) == 1
    assert entries[0]["channel"] == "text"
    assert entries[0]["category"] is None


def test_record_with_category_for_file_channel(tmp_path):
    path = tmp_path / "input.jsonl"
    input_log.record("file", category="image", path=path)
    entries = input_log.recent(path=path)
    assert entries[0]["channel"] == "file"
    assert entries[0]["category"] == "image"


def test_recent_returns_only_the_last_n_entries(tmp_path):
    path = tmp_path / "input.jsonl"
    for i in range(5):
        input_log.record("text", path=path)
    entries = input_log.recent(n=2, path=path)
    assert len(entries) == 2


def test_recent_with_no_entries_is_empty(tmp_path):
    path = tmp_path / "no_existe.jsonl"
    assert input_log.recent(path=path) == []
