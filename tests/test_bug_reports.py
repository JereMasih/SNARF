import pytest

from snarf.specialists.bug_reports import BugReports


class FakeMemory:
    def __init__(self, conversations=None):
        self._conversations = conversations or {}
        self.get_conversation_calls = []

    def get_conversation(self, conversation_id, limit=None):
        self.get_conversation_calls.append((conversation_id, limit))
        entries = self._conversations.get(conversation_id, [])
        return entries[-limit:] if limit else entries


def make_reports(tmp_path, monkeypatch, conversations=None, user_id="fundador"):
    monkeypatch.chdir(tmp_path)
    memory = FakeMemory(conversations)
    return BugReports(lambda: memory, user_id)


def test_create_stores_description_and_defaults_to_status_nuevo(tmp_path, monkeypatch):
    reports = make_reports(tmp_path, monkeypatch)
    record = reports.create("el documento quedó incompleto")
    assert record["description"] == "el documento quedó incompleto"
    assert record["status"] == "nuevo"
    assert record["category"] is None
    assert record["severity"] is None
    assert len(record["history"]) == 1
    assert record["history"][0]["status"] == "nuevo"


def test_create_captures_recent_turns_of_the_active_conversation(tmp_path, monkeypatch):
    turns = [
        {"input": "hola", "response": "hola Jere", "timestamp": 1.0},
        {"input": "andá a Notion", "response": "listo", "timestamp": 2.0},
    ]
    reports = make_reports(tmp_path, monkeypatch, conversations={"c1": turns})
    record = reports.create("algo salió mal", conversation_id="c1", view="chat")
    assert record["context"]["conversation_id"] == "c1"
    assert record["context"]["view"] == "chat"
    assert [t["input"] for t in record["context"]["recent_turns"]] == ["hola", "andá a Notion"]


def test_create_without_conversation_id_has_empty_context(tmp_path, monkeypatch):
    reports = make_reports(tmp_path, monkeypatch)
    record = reports.create("bug sin conversación")
    assert record["context"]["conversation_id"] is None
    assert record["context"]["recent_turns"] == []


def test_get_returns_none_for_unknown_id(tmp_path, monkeypatch):
    reports = make_reports(tmp_path, monkeypatch)
    assert reports.get("no-existe") is None


def test_get_reloads_the_saved_record_from_disk(tmp_path, monkeypatch):
    reports = make_reports(tmp_path, monkeypatch)
    created = reports.create("bug real")
    reloaded = reports.get(created["id"])
    assert reloaded == created


def test_list_reports_sorted_newest_first(tmp_path, monkeypatch):
    reports = make_reports(tmp_path, monkeypatch)
    first = reports.create("primero")
    import time

    time.sleep(0.01)
    second = reports.create("segundo")
    listed = reports.list_reports()
    assert [r["id"] for r in listed] == [second["id"], first["id"]]


def test_list_reports_filters_by_status(tmp_path, monkeypatch):
    reports = make_reports(tmp_path, monkeypatch)
    a = reports.create("a")
    reports.create("b")
    reports.update_status(a["id"], "descartado", note="duplicado")
    open_reports = reports.list_reports(status="nuevo")
    assert len(open_reports) == 1
    assert open_reports[0]["description"] == "b"


def test_update_status_appends_to_history(tmp_path, monkeypatch):
    reports = make_reports(tmp_path, monkeypatch)
    record = reports.create("bug")
    updated = reports.update_status(record["id"], "en_progreso", note="lo estoy mirando")
    assert updated["status"] == "en_progreso"
    assert updated["history"][-1] == {"timestamp": updated["history"][-1]["timestamp"], "status": "en_progreso", "note": "lo estoy mirando"}


def test_update_status_rejects_an_invalid_status(tmp_path, monkeypatch):
    reports = make_reports(tmp_path, monkeypatch)
    record = reports.create("bug")
    with pytest.raises(ValueError):
        reports.update_status(record["id"], "no_es_un_estado_real")


def test_update_status_returns_none_for_unknown_report(tmp_path, monkeypatch):
    reports = make_reports(tmp_path, monkeypatch)
    assert reports.update_status("no-existe", "resuelto") is None


def test_apply_classification_fills_fields_and_moves_to_planificado(tmp_path, monkeypatch):
    reports = make_reports(tmp_path, monkeypatch)
    record = reports.create("bug")
    classified = reports.apply_classification(record["id"], "ui", "media", "revisar el botón X")
    assert classified["category"] == "ui"
    assert classified["severity"] == "media"
    assert classified["plan"] == "revisar el botón X"
    assert classified["status"] == "planificado"


def test_resolve_sets_resolution_and_status(tmp_path, monkeypatch):
    reports = make_reports(tmp_path, monkeypatch)
    record = reports.create("bug")
    resolved = reports.resolve(record["id"], "corregido en el commit abc123")
    assert resolved["status"] == "resuelto"
    assert resolved["resolution"] == "corregido en el commit abc123"


def test_normalize_defaults_a_corrupt_status_to_nuevo(tmp_path, monkeypatch):
    reports = make_reports(tmp_path, monkeypatch)
    record = reports._normalize({"status": "algo-inventado"}, "r1")
    assert record["status"] == "nuevo"
