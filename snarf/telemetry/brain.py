from snarf.telemetry import verbs

CENTER_NODE = "orchestrator"

# ---------------------------------------------------------------------------
# PROTOCOLO DE CRECIMIENTO DEL CEREBRO (permanente — ver ADR 0054)
#
# Cada vez que se agregue algo nuevo a Snarf que despache por acá (una tool,
# una Capacidad, un Especialista Cognitivo, un canal de entrada/salida),
# resolver ANTES de cerrar ese mismo cambio — nunca como tarea aparte para
# "después":
#
# 1. Agregar su(s) tool_name(s) reales a TOOL_TO_NODE. El test
#    test_tool_to_node_covers_every_orchestrator_tool ya revienta si se
#    olvida — eso es la red de seguridad mínima (que nada quede sin
#    mapear), no el criterio de calidad.
# 2. Preguntar: ¿un usuario que mira el grafo reconocería esto como una
#    SUBCAPACIDAD DISTINTA (algo que él pediría/notaría por separado), o es
#    solo una operación más de una capacidad que ya tiene nodo? Ante la
#    duda, preferir un nodo nuevo — el cerebro existe para mostrar
#    crecimiento real, no para quedar cómodo y prolijo con pocos nodos.
#    Ejemplo real: Proyectos (14 tools) y luego Gmail/Calendar se separaron
#    en nodos por exactamente este criterio (gestión/tareas/conversaciones,
#    lectura/organización/envío, ver/editar) — ninguno fue una decisión de
#    "hay que dividir todo", fue "¿esto es una cosa distinta?".
# 3. test_no_specialist_node_absorbs_too_many_tools pone un techo real
#    (no solo un comentario que se puede ignorar) al tier "specialist": si
#    un nodo ahí supera el límite, el test falla y OBLIGA a decidir
#    conscientemente si toca dividir, en vez de acumular en silencio como
#    pasó con Proyectos antes de ADR 0054. El tier "capability" (wrappers
#    de API cruda) no tiene ese techo automático porque ahí SÍ puede haber
#    operaciones legítimamente parecidas (CRUD de un mismo recurso) — el
#    criterio del punto 2 sigue aplicando iagual, a criterio.
# 4. Si se agrega un Especialista Cognitivo nuevo (capa distinta de una
#    Capacidad cruda, ver COGNITION.md/ADR 0003), va al tier "specialist"
#    aunque tenga una sola tool — el ejemplo real es specialist_gmail.
# 5. MASTER_MAP.md ("Regla de crecimiento") ya dice que algo nuevo primero
#    evoluciona el mapa antes de encajar a la fuerza — este protocolo es la
#    misma regla, aplicada específicamente al cerebro.
# 6. Pedido explícito del fundador (ver ADR 0149): esto no es solo "mapear
#    la tool nueva" — CUALQUIER funcionalidad nueva real de Snarf (un rol
#    nuevo, una capa de visualización, un sub-agente, lo que sea) se
#    incorpora al cerebro COMO PARTE de construirla, en el mismo cambio,
#    nunca como una tarea de UI aparte para "después". El caso real que
#    motivó esto: la junta directiva de Inteligencia Ejecutiva existía
#    hacía rondas enteras antes de tener sus 7 nodos reales (ADR 0147) —
#    ese lag es justo lo que este punto existe para evitar la próxima vez.
# ---------------------------------------------------------------------------
TOOL_TO_NODE: dict[str, str] = {
    "get_current_datetime": "utility",
    "measure_text_length": "utility",
    "telemetry_cost_summary": "utility",
    "system_introspect": "utility",
    "os_audit": "utility",
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
    # NotionSource (ADR 0173): mismo nodo 'knowledge' que la indexación de
    # Drive — son tools de indexación, no de interacción con contenido como
    # el resto de notion_* (mapeadas al nodo 'notion' más abajo).
    "notion_index_start": "knowledge",
    "notion_index_status": "knowledge",
    # Knowledge Layer generalizada (ver KNOWLEDGE.md, ADR 0093): mismo nodo
    # 'knowledge' que ya representaba la indexación de Drive — domain='code'
    # es la misma capacidad real (buscar/indexar sobre conocimiento) sirviendo
    # una fuente nueva, no algo que un usuario reconocería como una
    # subcapacidad distinta (criterio del protocolo de arriba).
    "codebase_search": "knowledge",
    "conversations_search": "knowledge",
    "knowledge_search": "knowledge",
    "knowledge_index_start": "knowledge",
    "knowledge_index_status": "knowledge",
    "drive_create_document": "documents",
    "drive_create_spreadsheet": "documents",
    "drive_create_presentation": "documents",
    "drive_update_document": "documents",
    # Gmail crudo (Capacidad, no Especialista) separado por lo que un usuario
    # reconocería como acciones distintas: leer/mirar, organizar, y enviar
    # (esta última la única con efecto real hacia afuera — "canal de
    # salida" real, no solo lectura).
    "gmail_list_messages": "gmail_read",
    "gmail_read_message": "gmail_read",
    "gmail_list_labels": "gmail_read",
    "gmail_create_label": "gmail_manage",
    "gmail_modify_message_labels": "gmail_manage",
    "gmail_delete_label": "gmail_manage",
    "gmail_send_message": "gmail_send",
    "gmail_summarize_inbox": "specialist_gmail",
    # Fase I, rama Productivity — Especialista Cognitivo nuevo, mismo
    # criterio que specialist_gmail (una sola tool, tier "specialist").
    "calendar_brief": "specialist_calendar",
    # Rutina matutina real (gmail+calendar compuestos, ver ADR de esta
    # ronda) — un usuario mirando el grafo la reconocería como algo
    # genuinamente distinto de gmail_summarize_inbox/calendar_brief (junta
    # ambos Y lee cuerpos reales), no una operación más de esos dos nodos.
    "morning_routine": "specialist_morning_routine",
    # Fase I, rama Research — una sola clase real, tres tools/modos (ver
    # snarf/specialists/research/specialist.py).
    "research_deep_dive": "specialist_research",
    "research_trend_scan": "specialist_research",
    "research_competitor_watch": "specialist_research",
    # Fase I, rama Content — una sola clase real, tres tools/modos (ver
    # snarf/specialists/content/specialist.py).
    "content_write_blog_post": "specialist_content",
    "content_write_social_post": "specialist_content",
    "content_write_newsletter": "specialist_content",
    # Fase I, rama Sales.
    "sales_sponsor_inbox_triage": "specialist_sales",
    # Fase I, rama Finance.
    "finance_books_categorize": "specialist_finance",
    "finance_monthly_pnl": "specialist_finance",
    # Fase I, rama Community.
    "community_pulse": "specialist_community",
    "community_post_message": "specialist_community",
    # Fase I, rama Agency.
    "agency_client_status": "specialist_agency",
    # Fase I, rama Ops/Custom — capability cruda (diagnóstico/backup), no un
    # Especialista Cognitivo: cae en el tier "capability", mismo criterio
    # que telemetry_cost_summary (utility).
    "ops_system_health": "utility",
    "ops_backup_now": "utility",
    "ops_process_status": "utility",
    "ops_process_restart": "utility",
    # Proyectos tenía las 14 tools de este Especialista cayendo en un único
    # nodo — de lejos el más cargado del cerebro, y el más opaco: no se veía
    # QUÉ parte de Proyectos estaba realmente activa. Separado en 3 nodos
    # reales usando el mismo tool_name que activity_log ya registraba sin
    # costo nuevo (pedido del fundador: "más nodos que se iluminen... sin
    # aumentar el costo"), agrupados por lo que el usuario reconocería como
    # subcapacidades distintas, no por implementación interna.
    "project_create": "specialist_projects_manage",
    "project_list": "specialist_projects_manage",
    "project_get": "specialist_projects_manage",
    "project_delete": "specialist_projects_manage",
    "project_set_prompt": "specialist_projects_manage",
    "project_search": "specialist_projects_manage",
    "project_add_task": "specialist_projects_tasks",
    "project_complete_task": "specialist_projects_tasks",
    "project_delete_task": "specialist_projects_tasks",
    "project_add_note": "specialist_projects_tasks",
    "project_delete_note": "specialist_projects_tasks",
    "project_assign_conversation": "specialist_projects_conversations",
    "project_unassign_conversation": "specialist_projects_conversations",
    "project_list_conversations": "specialist_projects_conversations",
    # Calendar separado en ver vs. editar — mismo criterio que Gmail: mirar
    # el calendario es una acción distinta de crear/borrar/mover algo en él.
    "calendar_list_calendars": "calendar_view",
    "calendar_list_upcoming_events": "calendar_view",
    "calendar_search_events": "calendar_view",
    "calendar_create_event": "calendar_edit",
    "calendar_create_calendar": "calendar_edit",
    "calendar_delete_calendar": "calendar_edit",
    "calendar_delete_event": "calendar_edit",
    "calendar_move_event": "calendar_edit",
    "youtube_list_subscriptions": "youtube",
    "youtube_list_liked_videos": "youtube",
    "personality_set_sarcasm": "personality",
    "profile_set_name": "personality",
    "notion_search": "notion",
    "notion_read_page": "notion",
    "notion_create_page": "notion",
    "notion_append_to_page": "notion",
    # Databases (query/crear registro/actualizar properties) son CRUD sobre
    # el mismo recurso ya representado por el nodo "notion" — mismo criterio
    # del punto 3 de arriba (tier "capability", operaciones parecidas sobre
    # un mismo recurso no ameritan nodo propio).
    "notion_get_database": "notion",
    "notion_query_database": "notion",
    "notion_create_database_item": "notion",
    "notion_update_page_properties": "notion",
    # Lectura/escritura real del cuerpo de una nota, bloque por bloque (ADR
    # 0175) — mismo criterio de CRUD sobre el nodo "notion" ya existente.
    "notion_list_blocks": "notion",
    "notion_update_block": "notion",
    "notion_update_table_cell": "notion",
    "notion_delete_block": "notion",
    # Inteligencia Ejecutiva (ver COGNITION.md, ADR 0094/0098): Especialista
    # Cognitivo nuevo (capa distinta de una Capacidad cruda, ver ADR 0003) —
    # va al tier "specialist" aunque tenga una sola tool, mismo criterio ya
    # usado para specialist_gmail.
    "executive_board_consult": "specialist_executive_board",
    # Skill Factory (Fase H, ver ADR 0095/0102) — Especialista Cognitivo
    # nuevo, mismo criterio que specialist_gmail/specialist_executive_board.
    "skill_factory_build": "specialist_skill_factory",
    "skill_factory_activate": "specialist_skill_factory",
    "skill_factory_status": "specialist_skill_factory",
}

# Fase 9.2 del plan de observabilidad/n8n (ver ROADMAP_OBSERVABILIDAD_MULTIUSUARIO_N8N.md, ADR 0147):
# los 7 roles reales del board de Inteligencia Ejecutiva (snarf/executive/roles.py::ROLE_CONFIGS) hoy
# colapsan en un único nodo (specialist_executive_board, ver TOOL_TO_NODE arriba) — invisibles entre sí
# pese a que la telemetría real YA los distingue (spans.start_agent(role) abre agent.started/finished
# con skill=<rol>, ver snarf/telemetry/spans.py). No entran a TOOL_TO_NODE (no despachan una tool nueva
# del Orchestrator — executive_board_consult sigue siendo la única) ni requieren nodo propio en
# activity_log; su actividad real llega vía snapshot(lifecycle_entries=...) más abajo, filtrando por
# event_type "agent.finished"/"agent.failed" (brain.py no puede importar snarf.telemetry.events — import
# circular, events.py ya importa este módulo — esos dos strings son AGENT_FINISHED/AGENT_FAILED
# mantenidos en sync a mano).
EXECUTIVE_ROLE_TO_NODE: dict[str, str] = {
    "cto": "specialist_executive_board_cto",
    "coo": "specialist_executive_board_coo",
    "research": "specialist_executive_board_research",
    "ceo": "specialist_executive_board_ceo",
    "cfo": "specialist_executive_board_cfo",
    "cmo": "specialist_executive_board_cmo",
    "creative": "specialist_executive_board_creative",
}

# Primera (y a propósito única) jerarquía padre/hijo real del cerebro — el resto de la taxonomía es
# plana adrede (protocolo de crecimiento de arriba). El frontend usa esto para dibujar los 7 roles como
# un sub-cluster orbitando specialist_executive_board, nunca sueltos en el anillo principal de
# especialistas (eso los volvería indistinguibles del resto, el problema real que motivó esta ADR).
NODE_PARENT: dict[str, str] = {node_id: "specialist_executive_board" for node_id in EXECUTIVE_ROLE_TO_NODE.values()}

# gemini/openai/xai/groq_llama son los 4 proveedores de LLM alternativos a
# Anthropic (ADR 0067/0068, snarf/runtime/llm_routing.py) — todos ruteables
# al mismo rol de conversación/especialista, así que caen en el mismo nodo
# "llm" que Anthropic (la Capacidad que representan es la misma desde la
# perspectiva de un usuario mirando el grafo: "razonando", no "cuál
# proveedor"). "groq" (STT, ver voice/providers/groq_stt.py) cae en "stt".
# Encontrado durante la instrumentación unificada de telemetría (Fase 1 del
# plan de HUD, ver SESSION_STATE.md): estos vendors ya generaban entradas
# reales en usage_log.jsonl desde ADR 0056/0067/0068 pero nunca tuvieron nodo
# — quedaban invisibles en el cerebro sin que ningún test lo detectara.
VENDOR_TO_NODE: dict[str, str] = {
    "anthropic": "llm",
    "gemini": "llm",
    "openai": "llm",
    "xai": "llm",
    "groq_llama": "llm",
    "groq": "stt",
    "voyage": "knowledge",
}
# ElevenLabs es un solo vendor pero dos Capacidades reales y distinguibles:
# usage_tracker ya registra el modelo real (`stt_scribe` vs `tts`,
# usage_tracker.py) — el cerebro las separa en vez de mezclarlas en un nodo
# "voz" genérico, porque el dato para separarlas ya existe.
ELEVENLABS_MODEL_TO_NODE: dict[str, str] = {"stt_scribe": "stt", "tts": "tts"}
# "local" es un vendor (ver usage_tracker.record_local_stt_call/
# record_kokoro_tts_call) que también cubre dos Capacidades distintas según
# el modelo — mismo criterio que ElevenLabs arriba.
LOCAL_MODEL_TO_NODE: dict[str, str] = {"faster-whisper": "stt", "kokoro": "tts"}

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
    "specialist_calendar": "specialist",
    "specialist_morning_routine": "specialist",
    "specialist_research": "specialist",
    "specialist_content": "specialist",
    "specialist_sales": "specialist",
    "specialist_finance": "specialist",
    "specialist_community": "specialist",
    "specialist_agency": "specialist",
    "specialist_projects_manage": "specialist",
    "specialist_projects_tasks": "specialist",
    "specialist_projects_conversations": "specialist",
    "specialist_executive_board": "specialist",
    "specialist_executive_board_cto": "specialist",
    "specialist_executive_board_coo": "specialist",
    "specialist_executive_board_research": "specialist",
    "specialist_executive_board_ceo": "specialist",
    "specialist_executive_board_cfo": "specialist",
    "specialist_executive_board_cmo": "specialist",
    "specialist_executive_board_creative": "specialist",
    "specialist_skill_factory": "specialist",
    "memory": "capability",
    "drive": "capability",
    "knowledge": "capability",
    "documents": "capability",
    "gmail_read": "capability",
    "gmail_manage": "capability",
    "gmail_send": "capability",
    "calendar_view": "capability",
    "calendar_edit": "capability",
    "youtube": "capability",
    "llm": "capability",
    "stt": "capability",
    "tts": "capability",
    "personality": "capability",
    "utility": "capability",
    "notion": "capability",
}

NODE_IDS = list(NODE_TIER.keys())


def snapshot(
    activity_entries: list[dict],
    usage_entries: list[dict],
    input_entries: list[dict] | None = None,
    manifest_summary: dict | None = None,
    since: float | None = None,
    event_limit: int = 100,
    lifecycle_entries: list[dict] | None = None,
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
    _handle_tool). Fase 9.2 (ADR 0147): nodes["specialist_executive_board"]
    ahora se superpone también, legítimamente, con sus 7 hijos
    (specialist_executive_board_<rol>) — un despacho real de
    executive_board_consult vía activity_entries, más el fan-out interno a
    cada rol vía lifecycle_entries, nunca 8 despachos reales del
    Orchestrator.

    `lifecycle_entries` (opcional, Fase 9.2): filas reales de
    data/telemetry_events.jsonl con event_type "agent.finished"/
    "agent.failed" (ver snarf/telemetry/events.py — nunca importado acá
    directo, import circular real: events.py ya importa este módulo, los
    dos strings de abajo son AGENT_FINISHED/AGENT_FAILED mantenidos en
    sync a mano) — hoy la única fuente real de actividad por rol del board
    de Inteligencia Ejecutiva (ver EXECUTIVE_ROLE_TO_NODE arriba)."""
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
        if vendor == "elevenlabs":
            node_id = ELEVENLABS_MODEL_TO_NODE.get(entry.get("model", ""))
        elif vendor == "local":
            node_id = LOCAL_MODEL_TO_NODE.get(entry.get("model", ""))
        else:
            node_id = VENDOR_TO_NODE.get(vendor)
        if node_id is None:
            continue
        ts = entry["timestamp"]
        _touch(node_id, ts, is_error=False)
        events.append(
            {
                "timestamp": ts,
                "node": node_id,
                # Pedido explícito: "openai:mlx-comunity/qwen.... no aporta"
                # — string crudo vendor:model reemplazado por algo legible
                # solo para el nodo llm (ver verbs.resumen_llm). stt/tts
                # siguen mostrando vendor:model tal cual, no se pidió cambiar
                # eso y esos strings sí son legibles ("elevenlabs:tts").
                "label": verbs.resumen_llm(entry.get("model", "")) if node_id == "llm" else f"{vendor}:{entry.get('model', '')}",
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

    # Fase 9.2 (ADR 0147): actividad real por rol del board ejecutivo —
    # nunca vuelve a tocar CENTER_NODE (el Orchestrator ya se contó una
    # sola vez arriba, vía activity_entries, por el despacho real de
    # executive_board_consult; los 7 roles son fan-out interno, no 7
    # despachos nuevos). Solo cuenta en finalización, mismo criterio que
    # activity_entries/usage_entries (nunca ".started").
    for entry in lifecycle_entries or []:
        if entry.get("nodo") != "specialist_executive_board":
            continue
        event_type = entry.get("event_type")
        if event_type not in ("agent.finished", "agent.failed"):
            continue
        node_id = EXECUTIVE_ROLE_TO_NODE.get(entry.get("skill"))
        if node_id is None:
            continue
        ts = entry["timestamp"]
        _touch(node_id, ts, is_error=(event_type == "agent.failed"))
        events.append(
            {
                "timestamp": ts,
                "node": node_id,
                "label": entry.get("skill", ""),
                "status": "error" if event_type == "agent.failed" else "ok",
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
