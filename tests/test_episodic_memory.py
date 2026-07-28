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


def test_stats_on_empty_memory(tmp_path):
    memory = EpisodicMemory(path=tmp_path / "memory.jsonl")
    stats = memory.stats()
    assert stats["total_messages"] == 0
    assert stats["total_conversations"] == 0
    assert stats["oldest_timestamp"] is None
    assert stats["newest_timestamp"] is None
    assert len(stats["activity_by_day"]) == 14
    assert all(day["count"] == 0 for day in stats["activity_by_day"])


def test_stats_counts_messages_and_conversations(tmp_path, monkeypatch):
    memory = make_memory(tmp_path, monkeypatch)
    memory.append("text", "a", "1", conversation_id="c1")
    memory.append("text", "b", "2", conversation_id="c1")
    memory.append("text", "c", "3", conversation_id="c2")
    stats = memory.stats()
    assert stats["total_messages"] == 3
    assert stats["total_conversations"] == 2
    assert stats["oldest_timestamp"] == 0
    assert stats["newest_timestamp"] == 2


def test_stats_activity_by_day_counts_todays_messages(tmp_path):
    memory = EpisodicMemory(path=tmp_path / "memory.jsonl")
    memory.append("text", "hoy", "respuesta", conversation_id="c1")
    stats = memory.stats()
    today_bucket = stats["activity_by_day"][-1]
    assert today_bucket["count"] == 1
