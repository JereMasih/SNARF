from snarf.core.orchestrator import TOOLS
from snarf.telemetry import brain


def test_tool_to_node_covers_every_orchestrator_tool():
    # Regresión: si se agrega una herramienta nueva al Orchestrator y se
    # olvida mapearla acá, este test la detecta en vez de dejarla invisible
    # en silencio en el cerebro de Snarf.
    real_tool_names = {tool["name"] for tool in TOOLS}
    assert set(brain.TOOL_TO_NODE.keys()) == real_tool_names


def test_node_tier_covers_every_node_id():
    assert set(brain.NODE_TIER.keys()) == set(brain.NODE_IDS)


def test_no_specialist_node_absorbs_too_many_tools():
    """Protocolo de crecimiento del cerebro (ver el comentario al inicio de
    brain.py y ADR 0054): un nodo "specialist" con demasiadas tools quedó
    invisible sobre CUÁL subcapacidad estaba realmente activa (le pasó a
    Proyectos con 14). Este techo obliga a decidir conscientemente si toca
    dividir la próxima vez que se agregue una tool nueva, en vez de dejar
    que un nodo crezca en silencio para siempre."""
    MAX_TOOLS_PER_SPECIALIST_NODE = 8
    by_node: dict[str, int] = {}
    for tool, node in brain.TOOL_TO_NODE.items():
        by_node[node] = by_node.get(node, 0) + 1
    for node_id, tier in brain.NODE_TIER.items():
        if tier != "specialist":
            continue
        count = by_node.get(node_id, 0)
        assert count <= MAX_TOOLS_PER_SPECIALIST_NODE, (
            f"'{node_id}' tiene {count} tools — evaluar si conviene dividirlo en subcapacidades "
            f"reales (ver protocolo de crecimiento en snarf/telemetry/brain.py)"
        )


def test_snapshot_aggregates_activity_entries_into_capability_node_counts():
    entries = [
        {"timestamp": 1.0, "tool_name": "drive_list_files", "status": "ok"},
        {"timestamp": 2.0, "tool_name": "drive_read_file", "status": "ok"},
        {"timestamp": 3.0, "tool_name": "gmail_list_messages", "status": "ok"},
    ]
    result = brain.snapshot(entries, [], [], {})
    assert result["nodes"]["drive"]["count"] == 2
    assert result["nodes"]["gmail_read"]["count"] == 1
    assert result["nodes"]["orchestrator"]["count"] == 3


def test_snapshot_routes_gmail_digest_to_the_specialist_node_not_gmail():
    entries = [{"timestamp": 1.0, "tool_name": "gmail_summarize_inbox", "status": "ok"}]
    result = brain.snapshot(entries, [], [], {})
    assert result["nodes"]["specialist_gmail"]["count"] == 1
    assert result["nodes"]["gmail_read"]["count"] == 0
    assert result["nodes"]["gmail_manage"]["count"] == 0
    assert result["nodes"]["gmail_send"]["count"] == 0


def test_snapshot_routes_project_tools_to_specialist_nodes_not_drive_or_knowledge():
    entries = [
        {"timestamp": 1.0, "tool_name": "project_create", "status": "ok"},
        {"timestamp": 2.0, "tool_name": "project_add_task", "status": "ok"},
        {"timestamp": 3.0, "tool_name": "project_assign_conversation", "status": "ok"},
    ]
    result = brain.snapshot(entries, [], [], {})
    assert result["nodes"]["specialist_projects_manage"]["count"] == 1
    assert result["nodes"]["specialist_projects_tasks"]["count"] == 1
    assert result["nodes"]["specialist_projects_conversations"]["count"] == 1
    assert result["nodes"]["drive"]["count"] == 0
    assert result["nodes"]["knowledge"]["count"] == 0


def test_snapshot_counts_errors_per_node():
    entries = [
        {"timestamp": 1.0, "tool_name": "drive_list_files", "status": "ok"},
        {"timestamp": 2.0, "tool_name": "drive_list_files", "status": "error", "error": "boom"},
    ]
    result = brain.snapshot(entries, [], [], {})
    assert result["nodes"]["drive"]["count"] == 2
    assert result["nodes"]["drive"]["errors"] == 1


def test_snapshot_routes_unknown_tool_status_to_the_center_orchestrator_node():
    entries = [{"timestamp": 1.0, "tool_name": "algo_inventado_por_el_modelo", "status": "unknown_tool"}]
    result = brain.snapshot(entries, [], [], {})
    assert result["nodes"]["orchestrator"]["count"] == 1
    assert result["nodes"]["orchestrator"]["errors"] == 1
    assert result["events"][0]["node"] == "orchestrator"


def test_snapshot_aggregates_usage_entries_by_vendor_and_splits_elevenlabs_by_model():
    usage = [
        {"timestamp": 1.0, "vendor": "anthropic", "model": "claude-sonnet-5"},
        {"timestamp": 2.0, "vendor": "voyage", "model": "voyage-4-lite"},
        {"timestamp": 3.0, "vendor": "elevenlabs", "model": "stt_scribe"},
        {"timestamp": 4.0, "vendor": "elevenlabs", "model": "tts"},
    ]
    result = brain.snapshot([], usage, [], {})
    assert result["nodes"]["llm"]["count"] == 1
    assert result["nodes"]["knowledge"]["count"] == 1
    assert result["nodes"]["stt"]["count"] == 1
    assert result["nodes"]["tts"]["count"] == 1


def test_snapshot_routes_alternative_llm_providers_to_the_llm_node():
    # Encontrado durante la instrumentación unificada de telemetría (Fase 1
    # del plan de HUD): estos 4 vendors ya generaban entradas reales en
    # usage_log.jsonl desde ADR 0067/0068 pero nunca tuvieron nodo — quedaban
    # invisibles en el cerebro sin que ningún test lo detectara.
    usage = [
        {"timestamp": 1.0, "vendor": "gemini", "model": "gemini-3.1-flash-lite"},
        {"timestamp": 2.0, "vendor": "openai", "model": "gpt-5"},
        {"timestamp": 3.0, "vendor": "xai", "model": "grok-4.1-fast"},
        {"timestamp": 4.0, "vendor": "groq_llama", "model": "llama-3.3-70b"},
    ]
    result = brain.snapshot([], usage, [], {})
    assert result["nodes"]["llm"]["count"] == 4


def test_snapshot_routes_groq_stt_to_the_stt_node():
    usage = [{"timestamp": 1.0, "vendor": "groq", "model": "whisper-large-v3-turbo"}]
    result = brain.snapshot([], usage, [], {})
    assert result["nodes"]["stt"]["count"] == 1


def test_snapshot_splits_local_vendor_by_model_into_stt_and_tts_nodes():
    usage = [
        {"timestamp": 1.0, "vendor": "local", "model": "faster-whisper"},
        {"timestamp": 2.0, "vendor": "local", "model": "kokoro"},
    ]
    result = brain.snapshot([], usage, [], {})
    assert result["nodes"]["stt"]["count"] == 1
    assert result["nodes"]["tts"]["count"] == 1


def test_snapshot_routes_input_entries_by_channel():
    input_entries = [
        {"timestamp": 1.0, "channel": "text"},
        {"timestamp": 2.0, "channel": "voice"},
        {"timestamp": 3.0, "channel": "file", "category": "image"},
    ]
    result = brain.snapshot([], [], input_entries, {})
    assert result["nodes"]["input_text"]["count"] == 1
    assert result["nodes"]["input_voice"]["count"] == 1
    assert result["nodes"]["input_file"]["count"] == 1
    file_event = next(e for e in result["events"] if e["node"] == "input_file")
    assert file_event["label"] == "image"


def test_snapshot_folds_manifest_counts_into_the_knowledge_node():
    manifest_summary = {"indexed": 4618, "error": 250, "skipped_unsupported": 19, "total": 4887}
    result = brain.snapshot([], [], [], manifest_summary)
    assert result["nodes"]["knowledge"]["count"] == 4887
    assert result["nodes"]["knowledge"]["errors"] == 250


def test_snapshot_tracks_last_timestamp_per_node():
    entries = [
        {"timestamp": 5.0, "tool_name": "drive_list_files", "status": "ok"},
        {"timestamp": 9.0, "tool_name": "drive_list_files", "status": "ok"},
        {"timestamp": 7.0, "tool_name": "drive_list_files", "status": "ok"},
    ]
    result = brain.snapshot(entries, [], [], {})
    assert result["nodes"]["drive"]["last_timestamp"] == 9.0
    assert result["nodes"]["orchestrator"]["last_timestamp"] == 9.0


def test_snapshot_last_timestamp_is_none_without_activity():
    result = brain.snapshot([], [], [], {})
    assert result["nodes"]["drive"]["last_timestamp"] is None


def test_snapshot_filters_events_strictly_after_since():
    entries = [
        {"timestamp": 1.0, "tool_name": "drive_list_files", "status": "ok"},
        {"timestamp": 2.0, "tool_name": "drive_list_files", "status": "ok"},
        {"timestamp": 3.0, "tool_name": "drive_list_files", "status": "ok"},
    ]
    result = brain.snapshot(entries, [], [], {}, since=2.0)
    assert [e["timestamp"] for e in result["events"]] == [3.0]


def test_snapshot_caps_events_at_event_limit():
    entries = [{"timestamp": float(i), "tool_name": "drive_list_files", "status": "ok"} for i in range(10)]
    result = brain.snapshot(entries, [], [], {}, event_limit=3)
    assert [e["timestamp"] for e in result["events"]] == [7.0, 8.0, 9.0]


def test_snapshot_with_no_data_returns_zeroed_nodes_and_empty_events():
    result = brain.snapshot([], [], [], {})
    assert result["events"] == []
    assert all(node["count"] == 0 and node["errors"] == 0 for node in result["nodes"].values())
    assert set(result["nodes"].keys()) == set(brain.NODE_IDS)
