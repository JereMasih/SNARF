CENTER_NODE = "orchestrator"

# Mapea cada una de las 35 herramientas reales que despacha
# Orchestrator._tool_handlers a la Capacidad que representa en el cerebro de
# Snarf. Cubierto por test_brain.py::test_tool_to_node_covers_every_tool,
# que lo compara contra la lista real de herramientas del Orchestrator —
# para que una herramienta nueva no quede sin mapear en silencio.
#
# `gmail_summarize_inbox` rutea a "specialist_gmail", no a "gmail": es el
# único Especialista Cognitivo real hoy (GmailDigestSpecialist, ADR 0025),
# una capa arquitectónica distinta de la Capacidad Gmail cruda (COGNITION.md,
# ADR 0003) — el cerebro refleja esa distinción real, no una arbitraria.
TOOL_TO_NODE: dict[str, str] = {
    "list_conversations": "memory",
    "get_conversation": "memory",
    "search_memory": "memory",
    "drive_list_files": "drive",
    "drive_read_file": "drive",
    "drive_create_folder": "drive",
    "drive_move_file": "drive",
    "drive_delete_file": "drive",
    "drive_rename_file": "drive",
    "drive_share_file": "drive",
    "drive_index_scan": "knowledge",
    "drive_index_catalog_unsupported": "knowledge",
    "drive_index_start": "knowledge",
    "drive_index_status": "knowledge",
    "drive_index_stop": "knowledge",
    "drive_search_knowledge": "knowledge",
    "drive_create_document": "documents",
    "drive_create_spreadsheet": "documents",
    "drive_create_presentation": "documents",
    "gmail_list_messages": "gmail",
    "gmail_read_message": "gmail",
    "gmail_list_labels": "gmail",
    "gmail_create_label": "gmail",
    "gmail_modify_message_labels": "gmail",
    "gmail_send_message": "gmail",
    "gmail_delete_label": "gmail",
    "gmail_summarize_inbox": "specialist_gmail",
    "project_create": "specialist_projects",
    "project_list": "specialist_projects",
    "project_get": "specialist_projects",
    "project_set_prompt": "specialist_projects",
    "project_add_task": "specialist_projects",
    "project_complete_task": "specialist_projects",
    "project_delete_task": "specialist_projects",
    "project_add_note": "specialist_projects",
    "project_delete_note": "specialist_projects",
    "project_search": "specialist_projects",
    "project_delete": "specialist_projects",
    "calendar_list_calendars": "calendar",
    "calendar_list_upcoming_events": "calendar",
    "calendar_search_events": "calendar",
    "calendar_create_event": "calendar",
    "calendar_create_calendar": "calendar",
    "calendar_delete_calendar": "calendar",
    "calendar_delete_event": "calendar",
    "calendar_move_event": "calendar",
    "youtube_list_subscriptions": "youtube",
    "youtube_list_liked_videos": "youtube",
    "personality_set_sarcasm": "personality",
}

VENDOR_TO_NODE: dict[str, str] = {"anthropic": "llm", "voyage": "knowledge"}
# ElevenLabs es un solo vendor pero dos Capacidades reales y distinguibles:
# usage_tracker ya registra el modelo real (`stt_scribe` vs `tts`,
# usage_tracker.py) — el cerebro las separa en vez de mezclarlas en un nodo
# "voz" genérico, porque el dato para separarlas ya existe.
ELEVENLABS_MODEL_TO_NODE: dict[str, str] = {"stt_scribe": "stt", "tts": "tts"}

# input_log.jsonl registra el canal real por el que algo entró a Snarf
# (/send, /transcribe, /files/upload) — el punto de entrada real, antes de
# que el Orchestrator dispatche nada. "channel" siempre es uno de estos tres.
CHANNEL_TO_NODE: dict[str, str] = {"text": "input_text", "voice": "input_voice", "file": "input_file"}

# tier agrupa cada nodo por capa real de la arquitectura de tres capas
# (COGNITION.md / ADR 0003), más el anillo de entrada — el frontend lo usa
# para dibujar un anillo distinto por capa. No es decorativo: hoy
# "specialist_gmail" es el único Especialista real; a medida que se agreguen
# más (ver Roadmaps, "arquitectura de Especialistas por dominio"), ese
# anillo va a dejar de estar casi vacío.
NODE_TIER: dict[str, str] = {
    CENTER_NODE: "orchestrator",
    "input_text": "input",
    "input_voice": "input",
    "input_file": "input",
    "specialist_gmail": "specialist",
    "specialist_projects": "specialist",
    "memory": "capability",
    "drive": "capability",
    "knowledge": "capability",
    "documents": "capability",
    "gmail": "capability",
    "calendar": "capability",
    "youtube": "capability",
    "llm": "capability",
    "stt": "capability",
    "tts": "capability",
    "personality": "capability",
}

NODE_IDS = list(NODE_TIER.keys())


def snapshot(
    activity_entries: list[dict],
    usage_entries: list[dict],
    input_entries: list[dict] | None = None,
    manifest_summary: dict | None = None,
    since: float | None = None,
    event_limit: int = 100,
) -> dict:
    """Reagrupa activity_log + usage_log + input_log + el manifiesto de
    indexación ya persistido en la forma nodos/eventos del cerebro de Snarf.
    Nunca inventa actividad, solo normaliza lo que ya está registrado en
    disco (Principio VI de Foundation).

    nodes["orchestrator"]["count"] representa TODO despacho por
    Orchestrator._handle_tool, y por eso se superpone con el conteo de cada
    Capacidad individual — sumar todos los nodos duplica esa cuenta. El total
    correcto de eventos es nodes["orchestrator"] + nodes["llm"] + nodes["stt"]
    + nodes["tts"] (despachos + las Capacidades que nunca pasan por
    _handle_tool)."""
    manifest_summary = manifest_summary or {}
    nodes = {node_id: {"count": 0, "errors": 0, "last_timestamp": None} for node_id in NODE_IDS}
    events: list[dict] = []

    def _touch(node_id: str, ts: float, is_error: bool) -> None:
        nodes[node_id]["count"] += 1
        if is_error:
            nodes[node_id]["errors"] += 1
        if nodes[node_id]["last_timestamp"] is None or ts > nodes[node_id]["last_timestamp"]:
            nodes[node_id]["last_timestamp"] = ts

    for entry in activity_entries:
        tool_name = entry.get("tool_name", "")
        status = entry.get("status", "")
        ts = entry["timestamp"]
        if status == "unknown_tool":
            # Falla del modelo (inventó un tool_name), no de una Capacidad —
            # el centro se toca solo, ninguna Capacidad se ve involucrada.
            _touch(CENTER_NODE, ts, is_error=True)
            events.append({"timestamp": ts, "node": CENTER_NODE, "label": tool_name, "status": status})
            continue
        node_id = TOOL_TO_NODE.get(tool_name)
        if node_id is None:
            continue
        # El centro representa TODO despacho real por _handle_tool, no solo
        # los unknown_tool — se toca en cada entrada válida, además del nodo
        # de Capacidad que corresponda.
        _touch(CENTER_NODE, ts, is_error=False)
        _touch(node_id, ts, is_error=(status == "error"))
        events.append({"timestamp": ts, "node": node_id, "label": tool_name, "status": status})

    for entry in usage_entries:
        vendor = entry.get("vendor", "")
        node_id = ELEVENLABS_MODEL_TO_NODE.get(entry.get("model", "")) if vendor == "elevenlabs" else VENDOR_TO_NODE.get(vendor)
        if node_id is None:
            continue
        ts = entry["timestamp"]
        _touch(node_id, ts, is_error=False)
        events.append(
            {
                "timestamp": ts,
                "node": node_id,
                "label": f"{vendor}:{entry.get('model', '')}",
                "status": "ok",
            }
        )

    for entry in input_entries or []:
        node_id = CHANNEL_TO_NODE.get(entry.get("channel", ""))
        if node_id is None:
            continue
        ts = entry["timestamp"]
        _touch(node_id, ts, is_error=False)
        events.append(
            {
                "timestamp": ts,
                "node": node_id,
                "label": entry.get("category") or entry.get("channel", ""),
                "status": "ok",
            }
        )

    nodes["knowledge"]["count"] += (
        manifest_summary.get("indexed", 0)
        + manifest_summary.get("error", 0)
        + manifest_summary.get("skipped_unsupported", 0)
    )
    nodes["knowledge"]["errors"] += manifest_summary.get("error", 0)

    events.sort(key=lambda ev: ev["timestamp"])
    if since is not None:
        events = [ev for ev in events if ev["timestamp"] > since]
    return {"nodes": nodes, "events": events[-event_limit:]}
