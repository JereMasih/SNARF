"""Allowlist real del servidor MCP (ver ADR 0093/0094, KNOWLEDGE.md).

Positivo y explícito — nunca derivado por exclusión de los tools gateados.
"Solo lectura" no alcanza por sí solo: se excluyen también los tools de
lectura CRUDA de contenido personal (drive_read_file, gmail_read_message,
get_conversation, search_memory, notion_read_page) — solo entran resultados
ya agregados/filtrados. Es el primer y único segundo consumidor real de las
herramientas de Snarf (los procesos de Inteligencia Ejecutiva, ver
COGNITION.md/ADR 0094) — nada de esto reemplaza el tool-use nativo del
Orchestrator principal.
"""

MCP_EXPOSED_TOOLS: frozenset[str] = frozenset({
    "get_current_datetime",
    "measure_text_length",
    "list_conversations",
    "drive_search_knowledge",
    "knowledge_search",
    "knowledge_index_status",
    "drive_index_scan",
    "drive_index_status",
    "drive_index_catalog_unsupported",
    "gmail_summarize_inbox",
    "project_list",
    "project_get",
    "project_search",
    "notion_search",
    "notion_read_page",
    "codebase_search",
    "telemetry_cost_summary",
})

# Sub-allowlist por rol de Inteligencia Ejecutiva (ver ADR 0094, Fase E del
# plan de expansión) — acota aún más el allowlist general, según a qué rol
# sirve realmente cada tool. Cada entrada acá debe ser subconjunto de
# MCP_EXPOSED_TOOLS (ver tests/test_mcp_server.py).
ROLE_TOOL_SUBSETS: dict[str, frozenset[str]] = {
    "cto": frozenset({
        "codebase_search",
        "knowledge_index_status",
        "drive_index_status",
        "get_current_datetime",
    }),
    "coo": frozenset({
        "project_list",
        "project_get",
        "project_search",
        "list_conversations",
        "get_current_datetime",
    }),
    "research": frozenset({
        "knowledge_search",
        "drive_search_knowledge",
        "notion_search",
        "notion_read_page",
        "get_current_datetime",
    }),
    "ceo": frozenset({
        "project_list",
        "project_get",
        "knowledge_search",
        "telemetry_cost_summary",
        "get_current_datetime",
    }),
    "cfo": frozenset({
        # Solo el opex real de Snarf (ver KNOWLEDGE.md, dominio 'business'
        # vacío hoy) — deliberadamente el subset más delgado de los 7,
        # reflejo honesto de que este rol no tiene todavía una fuente real
        # de caja/ingresos del negocio del fundador.
        "telemetry_cost_summary",
        "get_current_datetime",
    }),
    "cmo": frozenset({
        "gmail_summarize_inbox",
        "knowledge_search",
        "get_current_datetime",
    }),
    "creative": frozenset({
        "knowledge_search",
        "get_current_datetime",
    }),
}
