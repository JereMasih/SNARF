"""Extracción real de contenido por tool — ver TELEMETRY_SCHEMA.md (campo
`detalle`) y ADR 0089. Antes del evento unificado solo se guardaba QUÉ tool
se llamó (`skill` = `tool_name`), nunca su contenido real (a quién se le
mandó un mail, qué documento se creó, qué se buscó) — por eso el dock HUD no
podía mostrar más que un pulso genérico.

Cada extractor lee `tool_input`/`result` reales (los mismos que
`Orchestrator._handle_tool` ya tiene en scope) y devuelve un string corto o
`None` si no hay nada real que mostrar — nunca inventa contenido (Principio
VI de FOUNDATION.md). Varios tools solo tienen un ID en su input (sin nombre
legible, ej. `drive_move_file`) — para esos, el `detalle` es honestamente más
genérico (el ID acortado), no se inventa un nombre que no está disponible.

Mismo protocolo de crecimiento que TOOL_TO_NODE (snarf/telemetry/brain.py,
ver ADR 0054): un tool nuevo real agrega su entrada acá en el mismo cambio —
`test_detail_extractors_cover_every_orchestrator_tool` revienta si se
olvida."""

DETAIL_MAX_CHARS = 100

_LEFT_QUOTE = "“"
_RIGHT_QUOTE = "”"


def _truncate(value) -> str | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:DETAIL_MAX_CHARS]


def _quoted(prefix: str, value) -> str | None:
    text = _truncate(value)
    if text is None:
        return None
    return _truncate(f"{prefix} {_LEFT_QUOTE}{text}{_RIGHT_QUOTE}")


def _short_id(value) -> str | None:
    if not value:
        return None
    text = str(value)
    return text if len(text) <= 14 else text[:10] + "…"


def _is_pending(result) -> bool:
    return isinstance(result, dict) and result.get("status") == "pending_confirmation"


def _input_get(tool_input, key):
    return tool_input.get(key) if isinstance(tool_input, dict) else None


def _list_count(noun: str):
    def extractor(i, r):
        if isinstance(r, list):
            return _truncate(f"{len(r)} {noun}")
        if _is_pending(r):
            return "pendiente de confirmación (pedido grande)"
        return None

    return extractor


def _list_count_with_query(noun: str):
    def extractor(i, r):
        query = _input_get(i, "query")
        if isinstance(r, list):
            if query:
                return _truncate(f"{len(r)} {noun} para {_LEFT_QUOTE}{_truncate(query)}{_RIGHT_QUOTE}")
            return _truncate(f"{len(r)} {noun}")
        if _is_pending(r):
            if query:
                return _quoted("pendiente de confirmar:", query)
            return "pendiente de confirmación (pedido grande)"
        return None

    return extractor


def _from_input(key: str, prefix: str | None = None):
    def extractor(i, r):
        value = _input_get(i, key)
        if prefix:
            return _quoted(prefix, value)
        return _truncate(value)

    return extractor


def _from_input_id(key: str, prefix: str):
    def extractor(i, r):
        return _quoted(prefix, _short_id(_input_get(i, key)))

    return extractor


def _from_result_text(prefix: str):
    def extractor(i, r):
        if isinstance(r, str):
            return _quoted(prefix, r)
        return None

    return extractor


def _from_result_field(field: str, prefix: str):
    def extractor(i, r):
        if isinstance(r, dict):
            return _quoted(prefix, r.get(field))
        return None

    return extractor


# --- memory ------------------------------------------------------------


def _get_conversation(i, r):
    if isinstance(r, list) and r:
        first = r[0]
        snippet = first.get("input") if isinstance(first, dict) else None
        if snippet:
            return _quoted("revisando:", snippet)
        return _truncate(f"revisando {len(r)} mensajes")
    return None


# --- drive ---------------------------------------------------------------


def _drive_read_file(i, r):
    if isinstance(r, str):
        return _quoted("leyendo:", r)
    return None


def _drive_move_file(i, r):
    return _quoted("moviendo archivo", _short_id(_input_get(i, "file_id")))


# --- knowledge -------------------------------------------------------------


def _drive_index_scan(i, r):
    if isinstance(r, dict):
        return _truncate(f"escaneados {r.get('total_files', 0)} archivos")
    return None


def _drive_index_catalog_unsupported(i, r):
    if isinstance(r, dict):
        return _truncate(f"{r.get('total_files', 0)} archivos sin soporte de indexado")
    return None


def _drive_index_status(i, r):
    if isinstance(r, dict):
        if not r.get("running"):
            return _truncate(f"indexación detenida ({r.get('indexed', 0)} indexados)")
        return _truncate(f"indexando: {r.get('processed', 0)} procesados, {r.get('indexed', 0)} indexados")
    return None


def _drive_index_start(i, r):
    if isinstance(r, dict):
        status = r.get("status")
        if status == "already_running":
            return "ya está indexando"
        if status == "started":
            return "arrancó la indexación"
    return None


def _drive_index_stop(i, r):
    return "deteniendo la indexación"


# Knowledge Layer generalizada (ver KNOWLEDGE.md, ADR 0093) — mismas formas
# de resultado que sus equivalentes de drive_index_*, reusadas tal cual.
_knowledge_index_status = _drive_index_status
_knowledge_index_start = _drive_index_start


# --- documents ---------------------------------------------------------


def _drive_update_document(i, r):
    return _quoted("reescribiendo:", _input_get(i, "new_content"))


# --- gmail_read ----------------------------------------------------------


def _gmail_read_message(i, r):
    return _from_result_field("subject", "leyendo:")(i, r)


# --- gmail_manage -----------------------------------------------------


def _gmail_modify_message_labels(i, r):
    return _quoted("etiquetando mensaje", _short_id(_input_get(i, "message_id")))


# --- gmail_send ------------------------------------------------------------


def _gmail_send_message(i, r):
    to = _input_get(i, "to")
    subject = _input_get(i, "subject")
    if not to:
        return None
    if subject:
        return _truncate(f"para {to}: {_LEFT_QUOTE}{_truncate(subject)}{_RIGHT_QUOTE}")
    return _truncate(f"para {to}")


# --- calendar_view -------------------------------------------------------


def _calendar_search_events(i, r):
    return _list_count_with_query("eventos")(i, r)


# --- calendar_edit -------------------------------------------------------


def _calendar_move_event(i, r):
    return _quoted("moviendo evento", _short_id(_input_get(i, "event_id")))


# --- specialist_gmail ------------------------------------------------------


def _gmail_summarize_inbox(i, r):
    if isinstance(r, dict):
        return _truncate(f"curando {r.get('message_count', 0)} correos")
    return None


# --- specialist_calendar ----------------------------------------------


def _calendar_brief(i, r):
    if isinstance(r, dict):
        return _truncate(f"interpretando {r.get('event_count', 0)} eventos")
    return None


# --- specialist_morning_routine -----------------------------------------


def _morning_routine(i, r):
    if isinstance(r, dict):
        priority = len(r.get("priority_message_ids") or [])
        return _truncate(
            f"rutina: {r.get('message_count', 0)} correos, {r.get('event_count', 0)} eventos, "
            f"{priority} prioritarios leídos"
        )
    return None


# --- specialist_research -------------------------------------------------


def _research_topic(i, r):
    return _quoted("investigando", _input_get(i, "topic"))


# --- specialist_content ----------------------------------------------


def _content_brief(i, r):
    return _quoted("redactando", _input_get(i, "brief"))


# --- specialist_sales ---------------------------------------------------


def _sales_sponsor_inbox_triage(i, r):
    if isinstance(r, dict):
        return _truncate(f"revisando {r.get('message_count', 0)} correos")
    return None


# --- specialist_finance --------------------------------------------------


def _finance_books_categorize(i, r):
    if isinstance(r, dict):
        return _truncate(f"categorizando {r.get('transaction_count', 0)} transacciones")
    return None


def _finance_monthly_pnl(i, r):
    if isinstance(r, dict):
        return _truncate(f"P&L: neto {r.get('net', 0)}")
    return None


# --- specialist_community -------------------------------------------------


def _community_pulse(i, r):
    if isinstance(r, dict) and "member_count" in r:
        return _truncate(f"{r['member_count']} miembros, {r.get('recent_message_count', 0)} mensajes")
    return None


def _community_post_message(i, r):
    return _quoted("posteando", _input_get(i, "content"))


# --- specialist_agency -----------------------------------------------


def _agency_client_status(i, r):
    return _quoted("status para proyecto", _short_id(_input_get(i, "project_id")))


# --- specialist_executive_board --------------------------------------------


def _executive_board_consult(i, r):
    if isinstance(r, dict) and "roles" in r:
        return _truncate(f"convocando a: {', '.join(r['roles'].keys())}")
    return None


# --- specialist_skill_factory -----------------------------------------


def _skill_factory_build(i, r):
    if isinstance(r, dict) and "status" in r:
        return _truncate(f"{_input_get(i, 'skill_name')}: {r['status']}")
    return _truncate(f"construyendo {_input_get(i, 'skill_name')}")


def _skill_factory_activate(i, r):
    return _quoted("activando", _input_get(i, "proposal_id"))


# --- specialist_projects_manage ---------------------------------------


def _project_get(i, r):
    return _from_result_field("name", "revisando proyecto:")(i, r)


def _project_delete(i, r):
    return _quoted("eliminando proyecto", _short_id(_input_get(i, "project_id")))


def _project_set_prompt(i, r):
    return _quoted("definiendo instrucciones:", _input_get(i, "prompt"))


# --- specialist_projects_tasks ------------------------------------------


def _project_complete_task(i, r):
    return _quoted("completando tarea", _short_id(_input_get(i, "task_id")))


def _project_delete_task(i, r):
    return _quoted("eliminando tarea", _short_id(_input_get(i, "task_id")))


def _project_delete_note(i, r):
    return _quoted("eliminando nota", _short_id(_input_get(i, "note_id")))


# --- specialist_projects_conversations -----------------------------------


def _project_assign_conversation(i, r):
    return _quoted("asignando a proyecto", _short_id(_input_get(i, "project_id")))


def _project_unassign_conversation(i, r):
    return _quoted("desasignando conversación", _short_id(_input_get(i, "conversation_id")))


# --- utility ---------------------------------------------------------------


def _get_current_datetime(i, r):
    if isinstance(r, dict):
        return _truncate(r.get("iso"))
    return None


def _measure_text_length(i, r):
    if isinstance(r, dict):
        return _truncate(f"{r.get('characters', 0)} caracteres, {r.get('words', 0)} palabras")
    return None


def _telemetry_cost_summary(i, r):
    if isinstance(r, dict):
        return _truncate(f"${r.get('today_usd', 0):.2f} hoy, ${r.get('total_usd', 0):.2f} total real")
    return None


def _ops_system_health(i, r):
    if isinstance(r, dict):
        return _truncate(f"LLM {'ok' if r.get('llm_available') else 'caído'}, {r.get('recent_error_count', 0)} errores recientes")
    return None


def _ops_backup_now(i, r):
    if isinstance(r, dict):
        return _truncate(f"backup en {r.get('snapshot', '')}")
    return None


def _ops_process_status(i, r):
    if isinstance(r, dict) and isinstance(r.get("processes"), list):
        running = sum(1 for p in r["processes"] if p.get("running"))
        return _truncate(f"{running}/{len(r['processes'])} procesos corriendo")
    return None


def _ops_process_restart(i, r):
    label = i.get("label") if isinstance(i, dict) else None
    return _truncate(f"reiniciando {label}") if label else None


# --- notion ------------------------------------------------------------


def _notion_append_to_page(i, r):
    return _quoted("agregando a la página:", _input_get(i, "content"))


def _notion_get_database(i, r):
    return _from_input_id("database_id", "revisando database:")(i, r)


def _notion_query_database(i, r):
    return _from_input_id("database_id", "buscando en database:")(i, r)


def _notion_create_database_item(i, r):
    return _from_input_id("database_id", "creando registro en:")(i, r)


def _notion_update_page_properties(i, r):
    return _from_input_id("page_id", "actualizando propiedades de:")(i, r)


DETAIL_EXTRACTORS = {
    # utility
    "get_current_datetime": _get_current_datetime,
    "measure_text_length": _measure_text_length,
    "telemetry_cost_summary": _telemetry_cost_summary,
    "ops_system_health": _ops_system_health,
    "ops_backup_now": _ops_backup_now,
    "ops_process_status": _ops_process_status,
    "ops_process_restart": _ops_process_restart,
    # memory
    "list_conversations": _list_count("conversaciones"),
    "get_conversation": _get_conversation,
    "search_memory": _from_input("query", prefix="buscando:"),
    # drive
    "drive_list_files": _list_count_with_query("archivos"),
    "drive_read_file": _drive_read_file,
    "drive_create_folder": _from_input("name", prefix="creando carpeta"),
    "drive_move_file": _drive_move_file,
    "drive_delete_file": _from_input_id("file_id", "eliminando archivo"),
    "drive_rename_file": _from_input("new_name", prefix="renombrando a"),
    "drive_share_file": lambda i, r: _quoted("compartiendo con", _input_get(i, "email")),
    # knowledge
    "drive_index_scan": _drive_index_scan,
    "drive_index_catalog_unsupported": _drive_index_catalog_unsupported,
    "drive_index_start": _drive_index_start,
    "drive_index_status": _drive_index_status,
    "drive_index_stop": _drive_index_stop,
    "drive_search_knowledge": _from_input("query", prefix="buscando en lo indexado:"),
    "codebase_search": _from_input("query", prefix="buscando en el código:"),
    "conversations_search": _from_input("query", prefix="buscando en el historial:"),
    "knowledge_search": _from_input("query", prefix="buscando en lo indexado:"),
    "knowledge_index_start": _knowledge_index_start,
    "knowledge_index_status": _knowledge_index_status,
    # documents
    "drive_create_document": _from_input("title", prefix="redactando"),
    "drive_create_spreadsheet": _from_input("title", prefix="armando la planilla"),
    "drive_create_presentation": _from_input("title", prefix="armando la presentación"),
    "drive_update_document": _drive_update_document,
    # gmail_read
    "gmail_list_messages": _list_count_with_query("mensajes"),
    "gmail_read_message": _gmail_read_message,
    "gmail_list_labels": _list_count("etiquetas"),
    # gmail_manage
    "gmail_create_label": _from_input("name", prefix="creando etiqueta"),
    "gmail_modify_message_labels": _gmail_modify_message_labels,
    "gmail_delete_label": _from_input_id("label_id", "eliminando etiqueta"),
    # gmail_send
    "gmail_send_message": _gmail_send_message,
    # specialist_gmail
    "gmail_summarize_inbox": _gmail_summarize_inbox,
    # specialist_calendar
    "calendar_brief": _calendar_brief,
    # specialist_morning_routine
    "morning_routine": _morning_routine,
    # specialist_research
    "research_deep_dive": _research_topic,
    "research_trend_scan": _research_topic,
    "research_competitor_watch": _research_topic,
    # specialist_content
    "content_write_blog_post": _content_brief,
    "content_write_social_post": _content_brief,
    "content_write_newsletter": _content_brief,
    # specialist_sales
    "sales_sponsor_inbox_triage": _sales_sponsor_inbox_triage,
    # specialist_finance
    "finance_books_categorize": _finance_books_categorize,
    "finance_monthly_pnl": _finance_monthly_pnl,
    # specialist_community
    "community_pulse": _community_pulse,
    "community_post_message": _community_post_message,
    # specialist_agency
    "agency_client_status": _agency_client_status,
    # specialist_projects_manage
    "project_create": _from_input("name", prefix="creando proyecto"),
    "project_list": _list_count("proyectos"),
    "project_get": _project_get,
    "project_delete": _project_delete,
    "project_set_prompt": _project_set_prompt,
    "project_search": _from_input("query", prefix="buscando en el proyecto:"),
    # specialist_projects_tasks
    "project_add_task": _from_input("text", prefix="agregando tarea:"),
    "project_complete_task": _project_complete_task,
    "project_delete_task": _project_delete_task,
    "project_add_note": _from_input("text", prefix="agregando nota:"),
    "project_delete_note": _project_delete_note,
    # specialist_projects_conversations
    "project_assign_conversation": _project_assign_conversation,
    "project_unassign_conversation": _project_unassign_conversation,
    "project_list_conversations": _list_count("conversaciones"),
    # calendar_view
    "calendar_list_calendars": _list_count("calendarios"),
    "calendar_list_upcoming_events": _list_count("eventos próximos"),
    "calendar_search_events": _calendar_search_events,
    # calendar_edit
    "calendar_create_event": _from_input("summary", prefix="agendando"),
    "calendar_create_calendar": _from_input("summary", prefix="creando calendario"),
    "calendar_delete_calendar": _from_input_id("calendar_id", "eliminando calendario"),
    "calendar_delete_event": _from_input_id("event_id", "eliminando evento"),
    "calendar_move_event": _calendar_move_event,
    # youtube
    "youtube_list_subscriptions": _list_count("canales"),
    "youtube_list_liked_videos": _list_count("videos"),
    # personality
    "personality_set_sarcasm": lambda i, r: _truncate(f"nivel de sarcasmo: {_input_get(i, 'level')}"),
    "profile_set_name": _from_input("name", prefix="guardando el nombre:"),
    # notion
    "notion_search": _from_input("query", prefix="buscando:"),
    "notion_read_page": _from_result_text("leyendo:"),
    "notion_create_page": _from_input("title", prefix="creando página:"),
    "notion_append_to_page": _notion_append_to_page,
    "notion_get_database": _notion_get_database,
    "notion_query_database": _notion_query_database,
    "notion_create_database_item": _notion_create_database_item,
    "notion_update_page_properties": _notion_update_page_properties,
    # specialist_executive_board
    "executive_board_consult": _executive_board_consult,
    # specialist_skill_factory
    "skill_factory_build": _skill_factory_build,
    "skill_factory_activate": _skill_factory_activate,
    "skill_factory_status": _from_input("proposal_id", prefix="revisando"),
}


# --- preview de documento (título/link/snippet real, ver ADR 0092) --------
#
# Distinto de DETAIL_EXTRACTORS de arriba: no busca cubrir todos los tools
# (la mayoría no tiene ningún documento real que previsualizar), y a
# propósito NUNCA hace una llamada de red nueva para completar un dato que
# falta (ej. el título real de `drive_read_file`, que hoy no viaja en
# `tool_input`/`result` — ver investigación en el PR de este ADR) — mismo
# principio de honestidad que el resto de este archivo: mejor un campo
# ausente que uno inventado o que agregue latencia oculta al turno del
# usuario. El link SÍ se puede armar sin red: son URLs públicas y estables
# documentadas por Google/Notion, nunca inventadas por Snarf.
PREVIEW_MAX_CHARS = 160

_DRIVE_MIME_TO_URL_TEMPLATE = {
    "application/vnd.google-apps.document": "https://docs.google.com/document/d/{id}/edit",
    "application/vnd.google-apps.spreadsheet": "https://docs.google.com/spreadsheets/d/{id}/edit",
    "application/vnd.google-apps.presentation": "https://docs.google.com/presentation/d/{id}/edit",
}


def _drive_file_link(file_id, mime_type=None) -> str | None:
    if not file_id:
        return None
    template = _DRIVE_MIME_TO_URL_TEMPLATE.get(mime_type or "")
    if template:
        return template.format(id=file_id)
    return f"https://drive.google.com/file/d/{file_id}/view"


def _notion_page_link(page_id) -> str | None:
    if not page_id:
        return None
    return f"https://www.notion.so/{str(page_id).replace('-', '')}"


def _preview(title=None, link=None, snippet=None) -> dict | None:
    title = _truncate(title)
    snippet = snippet.strip()[:PREVIEW_MAX_CHARS] if isinstance(snippet, str) and snippet.strip() else None
    if title is None and link is None and snippet is None:
        return None
    return {"title": title, "link": link, "snippet": snippet}


def _preview_drive_read_file(i, r):
    if not isinstance(r, str):
        return None
    return _preview(link=_drive_file_link(_input_get(i, "file_id"), _input_get(i, "mime_type")), snippet=r)


def _preview_drive_update_document(i, r):
    if not isinstance(r, dict) or r.get("status") != "updated":
        return None
    return _preview(link=_drive_file_link(_input_get(i, "file_id"), "application/vnd.google-apps.document"))


def _preview_created_document(i, r):
    if not isinstance(r, dict):
        return None
    return _preview(
        title=_input_get(i, "title"),
        link=r.get("webViewLink") or r.get("download_url"),
    )


def _preview_notion_create_page(i, r):
    if not isinstance(r, dict):
        return None
    return _preview(title=_input_get(i, "title"), link=r.get("url"))


def _preview_notion_read_page(i, r):
    if not isinstance(r, str):
        return None
    return _preview(link=_notion_page_link(_input_get(i, "page_id")), snippet=r)


PREVIEW_EXTRACTORS = {
    "drive_read_file": _preview_drive_read_file,
    "drive_update_document": _preview_drive_update_document,
    "drive_create_document": _preview_created_document,
    "drive_create_spreadsheet": _preview_created_document,
    "drive_create_presentation": _preview_created_document,
    "notion_create_page": _preview_notion_create_page,
    "notion_read_page": _preview_notion_read_page,
}


def extract_preview(tool_name: str, tool_input: dict, result: object) -> dict | None:
    """Punto de entrada de la previsualización de documento — paralelo a
    `extract()`, pero deliberadamente parcial (ver comentario de
    PREVIEW_EXTRACTORS arriba): no todo tool tiene un documento real que
    mostrar, así que no hay ningún test de cobertura total como el de
    DETAIL_EXTRACTORS. `{"title", "link", "snippet"}`, cualquiera puede ser
    `None` si ese dato en particular no está disponible de verdad."""
    extractor = PREVIEW_EXTRACTORS.get(tool_name)
    if extractor is None:
        return None
    try:
        return extractor(tool_input, result)
    except Exception:
        return None


def truncate_detalle(value) -> str | None:
    """Público — usado también por las capabilities de vendor (LLM/STT/TTS,
    ver anthropic_llm.py/gemini_llm.py/elevenlabs_*.py/kokoro_tts.py/
    *_stt.py) para truncar el texto real (transcript, texto a sintetizar,
    respuesta del modelo) antes de pasarlo como `detalle` a
    usage_tracker.record_*_call. Mismo límite y criterio que los extractors
    de tools de más arriba — nunca se llama al modelo de nuevo para esto."""
    return _truncate(value)


def extract(tool_name: str, status: str, tool_input: dict, result: object) -> str | None:
    """Punto de entrada único, llamado desde Orchestrator._handle_tool (vía
    activity_log.record). `unknown_tool` no tiene entrada en
    DETAIL_EXTRACTORS (no es un tool real registrado) — se resuelve acá con
    el único dato real disponible: el nombre inventado por el modelo."""
    if status == "unknown_tool":
        return _quoted("intentando", tool_name)
    extractor = DETAIL_EXTRACTORS.get(tool_name)
    if extractor is None:
        return None
    try:
        return extractor(tool_input, result)
    except Exception:
        # Nunca rompe el dispatch real de un tool por un detalle decorativo
        # — mismo criterio de tolerancia que el resto de la telemetría.
        return None
