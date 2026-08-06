import itertools

from snarf.knowledge.episodic_conversation_source import EpisodicConversationSource
from snarf.memory import episodic
from snarf.memory.episodic import EpisodicMemory


def make_memory(tmp_path, monkeypatch):
    # Mismo reloj determinístico que test_episodic_memory.py — el orden real
    # de last_activity/started_at tiene que ser predecible para los asserts.
    counter = itertools.count()
    monkeypatch.setattr(episodic.time, "time", lambda: next(counter))
    return EpisodicMemory(
        path=tmp_path / "memory.jsonl",
        project_links_path=tmp_path / "conversation_projects.json",
        titles_path=tmp_path / "conversation_titles.json",
    )


def test_domain_is_conversations():
    assert EpisodicConversationSource.domain == "conversations"


def test_iter_items_yields_one_item_per_conversation(tmp_path, monkeypatch):
    memory = make_memory(tmp_path, monkeypatch)
    memory.append("text", "hola", "hola, ¿en qué te ayudo?", conversation_id="c1")
    memory.append("text", "otra cosa", "otra respuesta", conversation_id="c2")
    source = EpisodicConversationSource(memory)

    ids = {item.id for item in source.iter_items()}

    assert ids == {"c1", "c2"}


def test_iter_items_uses_the_real_title_when_available(tmp_path, monkeypatch):
    memory = make_memory(tmp_path, monkeypatch)
    memory.append("text", "hola", "respuesta", conversation_id="c1")
    memory.set_title("c1", "Plan de marca en Instagram")
    source = EpisodicConversationSource(memory)

    item = next(iter(source.iter_items()))

    assert item.name == "Plan de marca en Instagram"


def test_iter_items_falls_back_to_the_first_message_substring_without_a_real_title(tmp_path, monkeypatch):
    # EpisodicMemory.list_conversations() ya degrada así (nunca vacío) — acá
    # solo se confirma que iter_items() no lo pisa con otra cosa.
    memory = make_memory(tmp_path, monkeypatch)
    memory.append("text", "hola, esto es una pregunta real", "respuesta", conversation_id="c1")
    source = EpisodicConversationSource(memory)

    item = next(iter(source.iter_items()))

    assert item.name == "hola, esto es una pregunta real"


def test_iter_items_carries_the_real_project_id_as_metadata(tmp_path, monkeypatch):
    memory = make_memory(tmp_path, monkeypatch)
    memory.append("text", "hola", "respuesta", conversation_id="c1")
    memory.assign_conversation("c1", "proj-1")
    source = EpisodicConversationSource(memory)

    item = next(iter(source.iter_items()))

    assert item.extra_metadata["project_id"] == "proj-1"


def test_iter_items_omits_project_id_when_unassigned(tmp_path, monkeypatch):
    # chromadb (backend real de VectorStore) rechaza None como valor de
    # metadata — omitir la clave entera es el fix, no guardar None.
    memory = make_memory(tmp_path, monkeypatch)
    memory.append("text", "hola", "respuesta", conversation_id="c1")
    source = EpisodicConversationSource(memory)

    item = next(iter(source.iter_items()))

    assert "project_id" not in item.extra_metadata


def test_modified_marker_is_the_real_last_activity(tmp_path, monkeypatch):
    memory = make_memory(tmp_path, monkeypatch)
    memory.append("text", "hola", "respuesta", conversation_id="c1")
    source = EpisodicConversationSource(memory)

    item = next(iter(source.iter_items()))

    conv = memory.list_conversations()[0]
    assert item.modified_marker == str(conv["last_activity"])


def test_modified_marker_changes_when_a_new_message_is_appended(tmp_path, monkeypatch):
    memory = make_memory(tmp_path, monkeypatch)
    memory.append("text", "primero", "respuesta 1", conversation_id="c1")
    source = EpisodicConversationSource(memory)
    marker_1 = next(iter(source.iter_items())).modified_marker

    memory.append("text", "segundo", "respuesta 2", conversation_id="c1")
    marker_2 = next(iter(source.iter_items())).modified_marker

    assert marker_1 != marker_2


def test_read_item_includes_every_real_turn_of_the_conversation(tmp_path, monkeypatch):
    memory = make_memory(tmp_path, monkeypatch)
    memory.append("text", "primera pregunta", "primera respuesta", conversation_id="c1")
    memory.append("text", "segunda pregunta", "segunda respuesta", conversation_id="c1")
    source = EpisodicConversationSource(memory)
    item = next(iter(source.iter_items()))

    text = source.read_item(item)

    assert "primera pregunta" in text
    assert "primera respuesta" in text
    assert "segunda pregunta" in text
    assert "segunda respuesta" in text


def test_read_item_never_mixes_entries_from_a_different_conversation(tmp_path, monkeypatch):
    memory = make_memory(tmp_path, monkeypatch)
    memory.append("text", "conversación uno", "respuesta uno", conversation_id="c1")
    memory.append("text", "conversación dos", "respuesta dos", conversation_id="c2")
    source = EpisodicConversationSource(memory)
    item_c1 = next(item for item in source.iter_items() if item.id == "c1")

    text = source.read_item(item_c1)

    assert "conversación dos" not in text


def test_read_item_includes_the_project_when_assigned(tmp_path, monkeypatch):
    memory = make_memory(tmp_path, monkeypatch)
    memory.append("text", "hola", "respuesta", conversation_id="c1")
    memory.assign_conversation("c1", "proj-1")
    source = EpisodicConversationSource(memory)
    item = next(iter(source.iter_items()))

    text = source.read_item(item)

    assert "proj-1" in text
