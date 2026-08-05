"""Tabla determinística acción→verbo temático (ver TELEMETRY_SCHEMA.md).

Nunca generada por el LLM — es un dict plano en código, evaluado en tiempo de
consulta (no se congela en cada evento guardado) para que un cambio de
redacción no obligue a reescribir el historial ya persistido. Sigue el
registro de CHARACTER.md: ingenio seco, nunca frívolo.

Tres niveles de precisión, de más a menos específico:
1. `VERB_BY_SKILL` — un verbo propio por `skill` real (`tool_name` de
   `activity_log`, ej. "drive_delete_file" ≠ "drive_list_files" aunque
   caigan en el mismo nodo "drive"). Cubre las ~68 tools reales de hoy
   (`snarf.core.orchestrator.TOOLS`) — pedido explícito del fundador tras
   ver la Vista HUD con muy poca variedad de verbos.
2. `VERB_BY_NODE` — fallback por nodo (`brain.py`) cuando el `skill` es una
   llamada de vendor (ej. "anthropic:claude-sonnet-5", que no es una tool
   con nombre propio) o un canal de entrada.
3. `VERB_BY_AGENTE` — fallback final por tier, para cualquier nodo/skill
   nuevo que todavía no tenga entrada propia en los dos de arriba.

Un tool nuevo real que se agregue a Orchestrator sin entrada acá no rompe
nada (cae al nivel 2/3) — pero, mismo protocolo de crecimiento que
`brain.py`/ADR 0054, se espera que la entrega que agrega la tool nueva
también le sume su verbo propio acá en el mismo cambio.
`test_verb_by_skill_covers_every_orchestrator_tool` (ver tests/test_verbs.py)
lo garantiza para las tools ya existentes.
"""

VERB_BY_SKILL: dict[str, str] = {
    # utility
    "get_current_datetime": "chequeando la hora",
    "measure_text_length": "midiendo el texto",
    "telemetry_cost_summary": "revisando el gasto real",
    "ops_system_health": "revisando el estado real",
    "ops_backup_now": "haciendo un backup real",
    # memory
    "list_conversations": "hojeando conversaciones",
    "get_conversation": "releyendo",
    "search_memory": "buscando en la memoria",
    # drive (capability)
    "drive_list_files": "hojeando el Drive",
    "drive_read_file": "leyendo el archivo",
    "drive_create_folder": "creando la carpeta",
    "drive_move_file": "moviendo el archivo",
    "drive_delete_file": "borrando el archivo",
    "drive_rename_file": "renombrando",
    "drive_share_file": "compartiendo el archivo",
    # knowledge
    "drive_index_scan": "escaneando el Drive",
    "drive_index_catalog_unsupported": "catalogando lo no soportado",
    "drive_index_start": "indexando",
    "drive_index_status": "revisando el progreso",
    "drive_index_stop": "frenando la indexación",
    "drive_search_knowledge": "rastreando lo indexado",
    "codebase_search": "buscando en el propio código",
    "knowledge_search": "buscando en lo indexado",
    "knowledge_index_start": "indexando el conocimiento",
    "knowledge_index_status": "revisando el progreso",
    # documents
    "drive_create_document": "redactando el documento",
    "drive_create_spreadsheet": "armando la planilla",
    "drive_create_presentation": "armando la presentación",
    "drive_update_document": "reescribiendo el documento",
    # gmail_read
    "gmail_list_messages": "revisando la bandeja",
    "gmail_read_message": "leyendo el correo",
    "gmail_list_labels": "revisando etiquetas",
    # gmail_manage
    "gmail_create_label": "creando la etiqueta",
    "gmail_modify_message_labels": "reetiquetando",
    "gmail_delete_label": "borrando la etiqueta",
    # gmail_send
    "gmail_send_message": "despachando el correo",
    # specialist_gmail
    "gmail_summarize_inbox": "curando la bandeja",
    # specialist_calendar
    "calendar_brief": "interpretando la agenda",
    # specialist_research
    "research_deep_dive": "investigando a fondo",
    "research_trend_scan": "rastreando tendencias",
    "research_competitor_watch": "vigilando a la competencia",
    # specialist_content
    "content_write_blog_post": "redactando el post",
    "content_write_social_post": "redactando para redes",
    "content_write_newsletter": "redactando la newsletter",
    # specialist_sales
    "sales_sponsor_inbox_triage": "revisando propuestas de sponsors",
    # specialist_finance
    "finance_books_categorize": "categorizando transacciones",
    "finance_monthly_pnl": "calculando el P&L",
    # specialist_community
    "community_pulse": "tomando el pulso de la comunidad",
    "community_post_message": "posteando en Discord",
    # specialist_agency
    "agency_client_status": "armando el status del cliente",
    # specialist_projects_manage
    "project_create": "fundando el proyecto",
    "project_list": "revisando proyectos",
    "project_get": "abriendo el proyecto",
    "project_delete": "cerrando el proyecto",
    "project_set_prompt": "reescribiendo las instrucciones",
    "project_search": "buscando en el proyecto",
    # specialist_projects_tasks
    "project_add_task": "anotando la tarea",
    "project_complete_task": "tildando la tarea",
    "project_delete_task": "descartando la tarea",
    "project_add_note": "tomando nota",
    "project_delete_note": "borrando la nota",
    # specialist_projects_conversations
    "project_assign_conversation": "vinculando la conversación",
    "project_unassign_conversation": "desvinculando la conversación",
    "project_list_conversations": "revisando las conversaciones del proyecto",
    # calendar_view
    "calendar_list_calendars": "revisando calendarios",
    "calendar_list_upcoming_events": "consultando la agenda",
    "calendar_search_events": "buscando en la agenda",
    # calendar_edit
    "calendar_create_event": "agendando",
    "calendar_create_calendar": "creando el calendario",
    "calendar_delete_calendar": "borrando el calendario",
    "calendar_delete_event": "cancelando el evento",
    "calendar_move_event": "reagendando",
    # youtube
    "youtube_list_subscriptions": "revisando suscripciones",
    "youtube_list_liked_videos": "revisando favoritos",
    # personality
    "personality_set_sarcasm": "calibrando el ingenio",
    "profile_set_name": "anotando tu nombre",
    # notion
    "notion_search": "buscando en Notion",
    "notion_read_page": "leyendo la página",
    "notion_create_page": "creando la página",
    "notion_append_to_page": "sumando a la página",
    "notion_get_database": "revisando la database",
    "notion_query_database": "buscando en la database",
    "notion_create_database_item": "creando el registro",
    "notion_update_page_properties": "actualizando propiedades",
    # specialist_executive_board
    "executive_board_consult": "convocando al board",
    # specialist_skill_factory
    "skill_factory_build": "construyendo la skill",
    "skill_factory_activate": "activando la skill",
    "skill_factory_status": "revisando la construcción",
}

VERB_BY_NODE: dict[str, str] = {
    "orchestrator": "orquestando",
    "llm": "pontificando",
    "specialist_gmail": "curando",
    "specialist_calendar": "revisando la agenda",
    "specialist_research": "investigando",
    "specialist_content": "redactando",
    "specialist_sales": "cazando oportunidades",
    "specialist_finance": "haciendo números",
    "specialist_community": "escuchando a la comunidad",
    "specialist_agency": "reportando al cliente",
    "specialist_projects_manage": "archivando",
    "specialist_projects_tasks": "anotando",
    "specialist_projects_conversations": "enlazando",
    "specialist_executive_board": "consultando al board",
    "specialist_skill_factory": "fabricando la skill",
    "memory": "rebobinando",
    "drive": "hojeando",
    "knowledge": "rastreando",
    "documents": "redactando",
    "gmail_read": "espiando el buzón",
    "gmail_manage": "ordenando",
    "gmail_send": "despachando el correo",
    "calendar_view": "consultando la agenda",
    "calendar_edit": "reagendando",
    "youtube": "hojeando el feed",
    "notion": "hojeando Notion",
    "personality": "calibrándose",
    "utility": "verificando el dato",
    "stt": "escuchando",
    "tts": "hablando",
    "input_text": "tomando nota",
    "input_voice": "prestando oído",
    "input_file": "recibiendo el archivo",
}

# Fallback por `agente` (tier) cuando un `nodo` nuevo todavía no tiene
# entrada propia en VERB_BY_NODE — mismo protocolo de crecimiento que
# brain.py/ADR 0054: un nodo real nuevo evoluciona esta tabla en el mismo
# cambio, este fallback es la red de seguridad mientras tanto, no el destino
# final.
VERB_BY_AGENTE: dict[str, str] = {
    "orchestrator": "orquestando",
    "input": "recibiendo",
    "specialist": "delegando",
    "capability": "operando",
}

ESTADO_MODIFIER: dict[str, str] = {
    "error": "tropezando con",
    "truncado": "conteniéndose en",
}


def verbo_tematico(nodo: str, agente: str, estado: str = "completo", skill: str | None = None) -> str:
    """Verbo temático para un evento real, siguiendo TELEMETRY_SCHEMA.md.
    Prioridad: verbo propio del `skill` (tool real) > verbo del `nodo` >
    verbo genérico del `agente`. `estado != "completo"` antepone el
    modificador correspondiente (nunca reemplaza el verbo base — sigue
    identificando qué subcapacidad real estaba activa)."""
    base = (VERB_BY_SKILL.get(skill) if skill else None) or VERB_BY_NODE.get(nodo) or VERB_BY_AGENTE.get(agente, "operando")
    modifier = ESTADO_MODIFIER.get(estado)
    return f"{modifier} {base}" if modifier else base
