import io
import json
import zipfile

from snarf.migration.chatgpt_export import (
    conversation_to_markdown,
    filter_by_title_keyword,
    load_export_zip,
    parse_conversations,
)


def _text_message(role, text, create_time=None):
    return {
        "author": {"role": role},
        "content": {"content_type": "text", "parts": [text]},
        "create_time": create_time,
    }


def _sample_conversation(conv_id="conv-1", title="Alimentación y Workout: plan semanal"):
    # Árbol real de ChatGPT: root (system, sin texto) -> user -> assistant.
    mapping = {
        "root": {"id": "root", "message": None, "parent": None, "children": ["n1"]},
        "n1": {
            "id": "n1",
            "message": _text_message("user", "Armame un plan de comidas", create_time=100.0),
            "parent": "root",
            "children": ["n2"],
        },
        "n2": {
            "id": "n2",
            "message": _text_message("assistant", "Claro, arrancamos con el desayuno...", create_time=101.0),
            "parent": "n1",
            "children": [],
        },
    }
    return {
        "id": conv_id,
        "title": title,
        "create_time": 100.0,
        "current_node": "n2",
        "mapping": mapping,
    }


def test_parse_conversations_linearizes_messages_in_chronological_order():
    conversations = parse_conversations([_sample_conversation()])
    assert len(conversations) == 1
    conv = conversations[0]
    assert conv.id == "conv-1"
    assert conv.title == "Alimentación y Workout: plan semanal"
    assert [m.role for m in conv.messages] == ["user", "assistant"]
    assert conv.messages[0].text == "Armame un plan de comidas"
    assert conv.messages[1].text == "Claro, arrancamos con el desayuno..."


def test_parse_conversations_skips_system_nodes_and_empty_content():
    raw = _sample_conversation()
    raw["mapping"]["root"]["message"] = {
        "author": {"role": "system"},
        "content": {"content_type": "text", "parts": [""]},
    }
    raw["mapping"]["root"]["children"] = ["n1"]
    conversations = parse_conversations([raw])
    assert len(conversations[0].messages) == 2  # solo user + assistant, nunca el system vacío


def test_parse_conversations_without_current_node_falls_back_to_a_leaf():
    raw = _sample_conversation()
    del raw["current_node"]
    conversations = parse_conversations([raw])
    assert [m.role for m in conversations[0].messages] == ["user", "assistant"]


def test_filter_by_title_keyword_matches_case_insensitively():
    conversations = parse_conversations(
        [_sample_conversation("c1", "High Value Men: rutina"), _sample_conversation("c2", "Otra cosa")]
    )
    matched = filter_by_title_keyword(conversations, "high value")
    assert [c.id for c in matched] == ["c1"]


def test_conversation_to_markdown_renders_speaker_labels():
    conv = parse_conversations([_sample_conversation()])[0]
    md = conversation_to_markdown(conv)
    assert md.startswith("# Alimentación y Workout: plan semanal")
    assert "**Vos:** Armame un plan de comidas" in md
    assert "**ChatGPT:** Claro, arrancamos con el desayuno..." in md


def test_load_export_zip_reads_conversations_json_from_a_real_zip(tmp_path):
    payload = [_sample_conversation()]
    zip_path = tmp_path / "export.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("conversations.json", json.dumps(payload))
        zf.writestr("user.json", json.dumps({"id": "u1"}))

    conversations = load_export_zip(str(zip_path))
    assert len(conversations) == 1
    assert conversations[0].title == "Alimentación y Workout: plan semanal"
