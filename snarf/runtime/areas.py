"""Agrupación real de los 7 dominios de Specialists en 4 áreas (Fase 22 del
plan de observabilidad/n8n — ver ROADMAP_OBSERVABILIDAD_MULTIUSUARIO_N8N.md,
ADR 0165). Reagrupa lo que ya existe (agency/community/content/finance/
productivity/research/sales, ver snarf/telemetry/brain.py::TOOL_TO_NODE) —
no define especialistas nuevos, solo la etapa de ruteo real que faltaba
entre la Junta Directiva y el trabajo puntual de cada Specialist.

Lookup determinístico, a propósito — no una clasificación por LLM: la
decisión de área nunca puede discrepar de la tool que Orchestrator ya
decidió llamar (Principio VI, FOUNDATION.md), así que se deriva de la
propia tool, nunca de texto libre reinterpretado después."""

AREA_DISPLAY_NAMES: dict[str, str] = {
    "operaciones": "Operaciones",
    "administracion": "Administración",
    "i_d": "I+D",
    "marketing": "Marketing",
}

# Cobertura verificada 1:1 contra brain.TOOL_TO_NODE (ver
# tests/test_areas.py) — las tools fuera de estas 4 áreas (ej. las del
# Executive Board, Drive/Gmail/Calendar/Skill Factory) no rutean a ninguna
# área, siguen exactamente como hoy.
TOOL_TO_AREA: dict[str, str] = {
    # Operaciones: agency + los dos specialists de productivity/ + sales
    # (triage de inbox — tarea operativa, no de I+D/Marketing/Administración).
    "agency_client_status": "operaciones",
    "calendar_brief": "operaciones",
    "morning_routine": "operaciones",
    "sales_sponsor_inbox_triage": "operaciones",
    # Administración: finance.
    "finance_books_categorize": "administracion",
    "finance_monthly_pnl": "administracion",
    # I+D: research.
    "research_deep_dive": "i_d",
    "research_trend_scan": "i_d",
    "research_competitor_watch": "i_d",
    # Marketing: content + community (ambos de cara a audiencia externa).
    "content_write_blog_post": "marketing",
    "content_write_social_post": "marketing",
    "content_write_newsletter": "marketing",
    "community_pulse": "marketing",
    "community_post_message": "marketing",
}


def area_for_tool(tool_name: str) -> str | None:
    """Área real de una tool, o None si está fuera de las 4 áreas (el
    Executive Board y el resto de las capacidades de Snarf siguen sin
    ruteo de área, sin cambios)."""
    return TOOL_TO_AREA.get(tool_name)
