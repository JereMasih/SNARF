import itertools

from snarf.memory import episodic
from snarf.memory.episodic import EpisodicMemory


def make_memory(tmp_path, monkeypatch):
    """Reloj determinístico (cada llamada a time.time() avanza un paso) para
    que el orden de las entradas en los asserts sea siempre predecible."""
    counter = itertools.count()
    monkeypatch.setattr(episodic.time, "time", lambda: next(counter))
    return EpisodicMemory(path=tmp_path / "memory.jsonl")


def test_append_and_recent_roundtrip(tmp_path, monkeypatch):
    memory = make_memory(tmp_path, monkeypatch)
    memory.append("text", "hola", "respuesta", conversation_id="c1")
    entries = memory.recent(10, conversation_id="c1")
    assert len(entries) == 1
    assert entries[0]["input"] == "hola"
    assert entries[0]["response"] == "respuesta"


def test_recent_filters_by_conversation_id(tmp_path, monkeypatch):
    memory = make_memory(tmp_path, monkeypatch)
    memory.append("text", "de c1", "r1", conversation_id="c1")
    memory.append("text", "de c2", "r2", conversation_id="c2")
    entries = memory.recent(10, conversation_id="c1")
    assert [e["input"] for e in entries] == ["de c1"]


def test_recent_without_conversation_id_mixes_all_conversations(tmp_path, monkeypatch):
    """Documenta el comportamiento actual (ver ARCHITECTURE_AUDIT.md, sección 8):
    sin conversation_id, recent() no filtra nada y devuelve los últimos N
    registros de TODAS las conversaciones mezclados. Es el caso de main.py,
    que nunca pasa conversation_id."""
    memory = make_memory(tmp_path, monkeypatch)
    memory.append("text", "de c1", "r1", conversation_id="c1")
    memory.append("text", "de c2", "r2", conversation_id="c2")
    entries = memory.recent(10, conversation_id=None)
    assert [e["input"] for e in entries] == ["de c1", "de c2"]


def test_list_conversations_orders_by_last_activity_desc(tmp_path, monkeypatch):
    memory = make_memory(tmp_path, monkeypatch)
    memory.append("text", "primera", "r", conversation_id="c1")
    memory.append("text", "segunda", "r", conversation_id="c2")
    memory.append("text", "otra vez c1", "r", conversation_id="c1")
    convs = memory.list_conversations()
    assert [c["conversation_id"] for c in convs] == ["c1", "c2"]
    assert convs[0]["title"] == "primera"


def test_list_conversations_ignores_entries_without_conversation_id(tmp_path, monkeypatch):
    memory = make_memory(tmp_path, monkeypatch)
    memory.append("text", "sin id", "r", conversation_id=None)
    assert memory.list_conversations() == []


def test_get_conversation_returns_only_its_own_entries(tmp_path, monkeypatch):
    memory = make_memory(tmp_path, monkeypatch)
    memory.append("text", "a", "1", conversation_id="c1")
    memory.append("text", "b", "2", conversation_id="c2")
    entries = memory.get_conversation("c1")
    assert len(entries) == 1
    assert entries[0]["input"] == "a"


def test_search_matches_input_or_response_case_insensitive(tmp_path, monkeypatch):
    memory = make_memory(tmp_path, monkeypatch)
    memory.append("text", "hablemos de Snarf", "listo", conversation_id="c1")
    memory.append("text", "otra cosa", "mención de SNARF acá", conversation_id="c1")
    memory.append("text", "nada relacionado", "tampoco", conversation_id="c1")
    results = memory.search("snarf")
    assert len(results) == 2


def test_search_empty_query_returns_nothing(tmp_path, monkeypatch):
    memory = make_memory(tmp_path, monkeypatch)
    memory.append("text", "algo", "algo", conversation_id="c1")
    assert memory.search("   ") == []
