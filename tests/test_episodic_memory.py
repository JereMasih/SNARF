import itertools

from snarf.memory import episodic
from snarf.memory.episodic import EpisodicMemory


def make_memory(tmp_path, monkeypatch):
    """Reloj determinístico (cada llamada a time.time() avanza un paso) para
    que el orden de las entradas en los asserts sea siempre predecible."""
    counter = itertools.count()
    monkeypatch.setattr(episodic.time, "time", lambda: next(counter))
    return EpisodicMemory(path=tmp_path / "memory.jsonl", project_links_path=tmp_path / "conversation_projects.json")


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


def test_append_persists_project_id(tmp_path, monkeypatch):
    memory = make_memory(tmp_path, monkeypatch)
    memory.append("text", "hola", "r", conversation_id="c1", project_id="proj-1")
    entries = memory.recent(10, conversation_id="c1")
    assert entries[0]["project_id"] == "proj-1"


def test_append_without_project_id_defaults_to_none(tmp_path, monkeypatch):
    memory = make_memory(tmp_path, monkeypatch)
    memory.append("text", "hola", "r", conversation_id="c1")
    entries = memory.recent(10, conversation_id="c1")
    assert entries[0]["project_id"] is None


def test_list_conversations_filters_by_project_id(tmp_path, monkeypatch):
    # A diferencia de Mark I.5, el filtro ya no mira el tag histórico
    # por-entrada — mira la asociación vigente (assign_conversation).
    memory = make_memory(tmp_path, monkeypatch)
    memory.append("text", "del proyecto", "r", conversation_id="c1")
    memory.append("text", "sin proyecto", "r", conversation_id="c2")
    memory.assign_conversation("c1", "proj-1")
    convs = memory.list_conversations(project_id="proj-1")
    assert [c["conversation_id"] for c in convs] == ["c1"]


def test_assign_conversation_persists_and_is_reflected_immediately(tmp_path, monkeypatch):
    memory = make_memory(tmp_path, monkeypatch)
    assert memory.get_conversation_project("c1") is None
    result = memory.assign_conversation("c1", "proj-1")
    assert result == {"conversation_id": "c1", "from_project_id": None, "to_project_id": "proj-1"}
    assert memory.get_conversation_project("c1") == "proj-1"


def test_reassign_conversation_reports_from_and_to_for_traceability(tmp_path, monkeypatch):
    memory = make_memory(tmp_path, monkeypatch)
    memory.assign_conversation("c1", "proj-a")
    result = memory.assign_conversation("c1", "proj-b")
    assert result == {"conversation_id": "c1", "from_project_id": "proj-a", "to_project_id": "proj-b"}
    assert memory.get_conversation_project("c1") == "proj-b"


def test_reassigning_a_conversation_never_rewrites_past_history(tmp_path, monkeypatch):
    # Confirmado con el fundador: reasignar A->B nunca reescribe el historial
    # ya generado — el tag project_id de cada entrada queda tal cual quedó
    # escrito, solo cambia el comportamiento hacia adelante.
    memory = make_memory(tmp_path, monkeypatch)
    memory.assign_conversation("c1", "proj-a")
    memory.append("text", "bajo proyecto A", "r", conversation_id="c1", project_id="proj-a")
    memory.assign_conversation("c1", "proj-b")
    memory.append("text", "bajo proyecto B", "r", conversation_id="c1", project_id="proj-b")
    entries = memory.get_conversation("c1")
    assert entries[0]["project_id"] == "proj-a"
    assert entries[1]["project_id"] == "proj-b"


def test_unassign_conversation_clears_the_link(tmp_path, monkeypatch):
    memory = make_memory(tmp_path, monkeypatch)
    memory.assign_conversation("c1", "proj-1")
    result = memory.unassign_conversation("c1")
    assert result == {"conversation_id": "c1", "from_project_id": "proj-1", "to_project_id": None}
    assert memory.get_conversation_project("c1") is None


def test_list_conversations_includes_a_freshly_assigned_conversation_with_no_messages_yet(tmp_path, monkeypatch):
    # Creada desde dentro de la vista de un proyecto, antes del primer
    # mensaje — no hay nada que escanear en el log, pero ya es una
    # asociación real y debe aparecer en la lista del proyecto de una.
    memory = make_memory(tmp_path, monkeypatch)
    memory.assign_conversation("c-nueva", "proj-1")
    convs = memory.list_conversations(project_id="proj-1")
    assert [c["conversation_id"] for c in convs] == ["c-nueva"]
    assert convs[0]["title"] == "(nueva conversación)"


def test_list_conversations_unassigned_only_excludes_project_conversations(tmp_path, monkeypatch):
    memory = make_memory(tmp_path, monkeypatch)
    memory.append("text", "general", "r", conversation_id="c1")
    memory.append("text", "de proyecto", "r", conversation_id="c2")
    memory.assign_conversation("c2", "proj-1")
    general = memory.list_conversations(unassigned_only=True)
    assert [c["conversation_id"] for c in general] == ["c1"]


def test_list_conversations_without_filters_still_returns_everything(tmp_path, monkeypatch):
    # El uso conversacional (tool list_conversations, para que Snarf recuerde
    # todo) no debe perder historial solo porque una conversación tenga
    # proyecto asignado.
    memory = make_memory(tmp_path, monkeypatch)
    memory.append("text", "general", "r", conversation_id="c1")
    memory.append("text", "de proyecto", "r", conversation_id="c2")
    memory.assign_conversation("c2", "proj-1")
    all_convs = memory.list_conversations()
    assert {c["conversation_id"] for c in all_convs} == {"c1", "c2"}


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
    memory = EpisodicMemory(path=tmp_path / "memory.jsonl", project_links_path=tmp_path / "conversation_projects.json")
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
    memory = EpisodicMemory(path=tmp_path / "memory.jsonl", project_links_path=tmp_path / "conversation_projects.json")
    memory.append("text", "hoy", "respuesta", conversation_id="c1")
    stats = memory.stats()
    today_bucket = stats["activity_by_day"][-1]
    assert today_bucket["count"] == 1
