"""Biblioteca de 24 plantillas visuales para los widgets de Vista HUD (v2 del
rediseño radial): 3 tamaños (chico/mediano/grande) × 8 variantes cada uno.

El TAMAÑO de un widget se asigna acá mismo, mecánicamente, a partir del
ranking real de `relevance.dock_priority()` (`assign_tier`) — nunca por el
LLM del curador, para que la jerarquía visual (más relevante = más grande)
sea siempre consistente, nunca sujeta al criterio variable de un modelo. El
curador (`snarf/specialists/dashboard_curator.py`) solo elige la VARIANTE
dentro del tamaño ya asignado.

Fuente única de verdad: tanto el prompt del curador como el render del
frontend leen de acá (el frontend vía `GET /dashboard/widget_templates`),
nunca duplicado a mano en JS — mismo criterio "protocolo de crecimiento" que
ya rige `brain.NODE_TIER`/`HUD_MINI_NODE_META`."""

SMALL = "small"
MEDIUM = "medium"
LARGE = "large"
TIER_ORDER = (SMALL, MEDIUM, LARGE)

# ---------------------------------------------------------------------------
# Chico (130-220px): lo mínimo esencial, sin análisis — para todo nodo real
# con actividad pero fuera del top curado por el LLM.
# ---------------------------------------------------------------------------
_SMALL_TEMPLATES = {
    "icon_minimal": {
        "width": 130, "height": 130, "slots": ["icon", "caption"],
        "description": "ícono + una línea, para score mínimo",
    },
    "compact": {
        "width": 190, "height": 110, "slots": ["icon", "label", "body"],
        "description": "ícono + label + una línea de cuerpo",
    },
    "standard": {
        "width": 220, "height": 150, "slots": ["label", "body", "caption"],
        "description": "título + cuerpo + caption corta (default)",
    },
    "duo_mini": {
        "width": 220, "height": 130, "slots": ["stat", "stat"],
        "description": "dos datos abreviados lado a lado",
    },
    "badge": {
        "width": 150, "height": 150, "slots": ["icon", "badge"],
        "description": "ícono grande + badge numérico (ej. \"3 nuevos\")",
    },
    "mini_chart": {
        "width": 200, "height": 150, "slots": ["chart"],
        "description": "solo sparkline, sin texto o 1 línea",
    },
    "pulse": {
        "width": 160, "height": 160, "slots": ["gauge"],
        "description": "indicador circular tipo gauge (salud/estado)",
    },
    "ticker": {
        "width": 240, "height": 110, "slots": ["ticker"],
        "description": "última línea real, estilo ticker (nodos de alta frecuencia)",
    },
}

# ---------------------------------------------------------------------------
# Mediano (240-280px): un eje real de análisis — gráfico O lista O
# comparación, nunca los tres a la vez.
# ---------------------------------------------------------------------------
_MEDIUM_TEMPLATES = {
    "standard_wide": {
        "width": 270, "height": 150, "slots": ["label", "body", "caption"],
        "description": "título + 2-3 líneas de cuerpo + caption",
    },
    "list": {
        "width": 240, "height": 220, "slots": ["label", "list"],
        "description": "lista real de 3-5 items recientes con hora",
    },
    "chart_caption": {
        "width": 270, "height": 175, "slots": ["chart", "caption"],
        "description": "sparkline/barras + caption del curador",
    },
    "duo": {
        "width": 270, "height": 160, "slots": ["stat", "stat", "caption"],
        "description": "dos métricas reales distintas lado a lado",
    },
    "timeline": {
        "width": 260, "height": 200, "slots": ["timeline"],
        "description": "mini timeline vertical real de últimos eventos",
    },
    "alert_detail": {
        "width": 260, "height": 165, "slots": ["label", "body", "caption"],
        "description": "foco en errores reales, solo si has_error_recent",
    },
    "comparison": {
        "width": 280, "height": 165, "slots": ["stat", "stat", "caption"],
        "description": "hoy vs. período anterior, solo si hay dato histórico real",
    },
    "trend_caption": {
        "width": 270, "height": 180, "slots": ["chart", "caption"],
        "description": "gráfico + narrativa más larga de \"qué está pasando\"",
    },
}

# ---------------------------------------------------------------------------
# Grande (320-380px): multi-slot, reservado al/a los nodo(s) de mayor score
# del ciclo (rank 0, ver assign_tier). Recalibrado tras verificar con
# Playwright: los 400-560px originales no dejaban lugar real para los
# anillos mediano/chico dentro del radio seguro de una pantalla de
# escritorio típica (ver HUD_TIER_HALF_DIAGONAL en el frontend) — sigue
# siendo notoriamente más grande que mediano/chico, sin llegar a comerse la
# pantalla.
# ---------------------------------------------------------------------------
_LARGE_TEMPLATES = {
    "featured": {
        "width": 340, "height": 220, "slots": ["label", "caption", "chart"],
        "description": "hero del ciclo: título + caption completa + gráfico si hay",
    },
    "digest": {
        "width": 380, "height": 260, "slots": ["label", "list", "chart", "caption"],
        "description": "header + lista real + gráfico + caption, \"mini dashboard\"",
    },
    "deep_chart": {
        "width": 350, "height": 230, "slots": ["chart", "caption"],
        "description": "gráfico con más buckets/días + análisis",
    },
    "activity_wall": {
        "width": 340, "height": 260, "slots": ["wall"],
        "description": "mosaico de últimos N eventos reales",
    },
    "critical_alert": {
        "width": 330, "height": 220, "slots": ["label", "body", "caption"],
        "description": "alerta grande, solo si has_error_recent/cost_alert",
    },
    "narrative": {
        "width": 350, "height": 200, "slots": ["narrative"],
        "description": "caption más larga del curador, foco en \"por qué importa\"",
    },
    "multi_metric": {
        "width": 380, "height": 230, "slots": ["stat_grid"],
        "description": "grilla de 3-4 métricas reales (recent/total/score/última vez)",
    },
    "spotlight_timeline": {
        "width": 350, "height": 260, "slots": ["timeline"],
        "description": "timeline real extendido, con ícono por tipo de evento",
    },
}

WIDGET_TEMPLATES: dict[str, dict] = {}
for _template_id, _fields in _SMALL_TEMPLATES.items():
    WIDGET_TEMPLATES[_template_id] = {"id": _template_id, "tier": SMALL, **_fields}
for _template_id, _fields in _MEDIUM_TEMPLATES.items():
    WIDGET_TEMPLATES[_template_id] = {"id": _template_id, "tier": MEDIUM, **_fields}
for _template_id, _fields in _LARGE_TEMPLATES.items():
    WIDGET_TEMPLATES[_template_id] = {"id": _template_id, "tier": LARGE, **_fields}

DEFAULT_TEMPLATE_BY_TIER = {SMALL: "standard", MEDIUM: "standard_wide", LARGE: "featured"}

# Cuántos de los nodos de mayor score reciben cada tamaño — determinístico,
# nunca decidido por el LLM (Principio de legibilidad del plan v2): el
# primero (rank 0) es siempre el "hero" del ciclo; los siguientes 3 son
# medianos; el resto (todo lo que siga con score > 0) es chico.
_LARGE_RANK_CUTOFF = 1
_MEDIUM_RANK_CUTOFF = 4


def assign_tier(rank_index: int) -> str:
    """`rank_index` es la posición 0-based del widget en una lista ya
    ordenada por score real descendente (ver widget_summary.all_widget_summaries)."""
    if rank_index < _LARGE_RANK_CUTOFF:
        return LARGE
    if rank_index < _MEDIUM_RANK_CUTOFF:
        return MEDIUM
    return SMALL


def templates_for_tier(tier: str) -> dict[str, dict]:
    return {template_id: t for template_id, t in WIDGET_TEMPLATES.items() if t["tier"] == tier}
