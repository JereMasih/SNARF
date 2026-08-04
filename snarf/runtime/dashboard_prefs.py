import json
from pathlib import Path

from snarf.telemetry import relevance

PREFS_DIR = Path("data/dashboard_prefs")

# "history" (historial de conversaciones) y "chat" (el chat con Snarf en sí)
# se suman a la lista unificada de bloques de la grilla de escritorio — antes
# vivían fuera del sistema de widgets, fijos y sin poder moverse/redimensionar.
#
# Orden por defecto (pantalla ancha de escritorio, ver ADR 0037): historial a
# la izquierda (columna angosta, alto completo); cerebro arriba centrado, con
# sistema/costo a su lado (misma fila); chat debajo del cerebro, centrado;
# conversaciones/memoria/drive/gmail/calendar/youtube forman una columna a la
# derecha que sigue bajando. El auto-flow disperso de la grilla logra esto
# solo con el orden de esta lista + los anchos de columna de DEFAULT_SPANS
# (todo lo de la derecha en col_span=3, para que quede en su propia columna
# en vez de desparramarse a lo ancho).
WIDGET_IDS = [
    "history", "brain", "system", "cost", "chat",
    "conversations", "memory", "usage", "drive", "gmail", "calendar", "youtube",
]
# Nunca se pueden ocultar, ni siquiera con un payload directo a la API — son
# el núcleo de la app, no un widget más que el fundador pueda apagar sin querer.
ALWAYS_VISIBLE_WIDGET_IDS = {"chat", "history"}
GMAIL_MAX_RESULTS_CHOICES = [5, 10, 20]

# Vista HUD del dashboard (rediseño radial) — preferencias completamente
# ADITIVAS a las de arriba, nunca las tocan ni las reemplazan: la Vista
# clásica (WIDGET_IDS/visible_widgets/panel_order/widget_options) sigue
# funcionando exactamente igual que hoy, sin tocar una línea, para que el
# fundador siempre pueda volver atrás con el toggle si la Vista HUD no lo
# convence. `HUD_NODE_IDS` es un alias directo (no una copia) de
# relevance.DOCK_NODE_IDS — crece solo cuando brain.NODE_TIER crece, mismo
# protocolo de crecimiento que ya rige el resto de la telemetría.
HUD_NODE_IDS = relevance.DOCK_NODE_IDS
HUD_WIDGET_STATE_VALUES = {"auto", "pinned", "hidden"}
DASHBOARD_VIEW_VALUES = {"classic", "hud"}
# v2 del rediseño HUD (esfera 3D + drawer lateral) — igual de aditivos que
# los de arriba. Default "left": el fundador pidió explícitamente que el
# chat arranque a la izquierda en escritorio.
HUD_CHAT_POSITION_VALUES = {"left", "center", "right"}

GRID_COLUMNS = 12
MIN_COL_SPAN, MAX_COL_SPAN = 1, GRID_COLUMNS
MIN_ROW_SPAN, MAX_ROW_SPAN = 3, 30

# Tamaño por defecto de cada bloque en la grilla de 12 columnas (filas de
# 28px). Historial (3 columnas) + cerebro/chat (6 columnas, centro) sobre 9
# columnas; las 3 columnas restantes son la columna derecha (sistema/costo
# arriba, junto al cerebro; conversaciones/memoria/capacidades de Google
# bajando debajo) — mismo col_span=3 en todos para que el auto-flow disperso
# los apile en una sola columna en vez de desparramarlos a lo ancho. Ver ADR
# 0037.
#
# Recalibrado en ADR 0041: los valores de ADR 0037 dejaban de más en los
# widgets con poco contenido real (system/conversations/memory solo muestran
# unas pocas líneas de texto) y de menos en los que muestran listas densas
# (drive con 5 archivos en formato de 2 líneas c/u). La señal real: el propio
# fundador, usando la grilla en vivo, redujo a mano system/conversations/
# memory/calendar/youtube y agrandó drive/cost — esos ajustes en vivo son la
# evidencia de qué tamaño hace falta, no una preferencia estética a ciegas.
DEFAULT_SPANS = {
    "history": {"col_span": 3, "row_span": 28},
    "brain": {"col_span": 6, "row_span": 12},
    "system": {"col_span": 3, "row_span": 5},
    "cost": {"col_span": 3, "row_span": 8},
    "chat": {"col_span": 6, "row_span": 16},
    "conversations": {"col_span": 3, "row_span": 7},
    "memory": {"col_span": 3, "row_span": 6},
    "usage": {"col_span": 3, "row_span": 9},
    "drive": {"col_span": 3, "row_span": 9},
    "gmail": {"col_span": 3, "row_span": 10},
    "calendar": {"col_span": 3, "row_span": 5},
    "youtube": {"col_span": 3, "row_span": 6},
}


def _default_prefs() -> dict:
    widget_options = {widget_id: dict(DEFAULT_SPANS[widget_id]) for widget_id in WIDGET_IDS}
    widget_options["gmail"]["max_results"] = GMAIL_MAX_RESULTS_CHOICES[0]
    return {
        "visible_widgets": {widget_id: True for widget_id in WIDGET_IDS},
        "panel_order": list(WIDGET_IDS),
        "widget_options": widget_options,
        # Default "classic": cero sorpresa, mismo criterio que el toggle ya
        # existente del panel Cerebro (`let brainView = "classic"`) — la
        # Vista HUD es algo que el fundador elige ver, nunca algo que
        # aparece solo.
        "dashboard_view": "classic",
        "hud_widget_state": {node_id: "auto" for node_id in HUD_NODE_IDS},
        "hud_widget_options": {},
        "hud_chat_position": "left",
        "hud_sidebar_pinned": False,
    }


def _normalize_hud_widget_state(raw: dict) -> dict:
    raw_state = raw.get("hud_widget_state", {}) if isinstance(raw, dict) else {}
    if not isinstance(raw_state, dict):
        raw_state = {}
    return {
        node_id: (raw_state.get(node_id) if raw_state.get(node_id) in HUD_WIDGET_STATE_VALUES else "auto")
        for node_id in HUD_NODE_IDS
    }


def _normalize_hud_widget_options(raw: dict) -> dict:
    raw_options = raw.get("hud_widget_options", {}) if isinstance(raw, dict) else {}
    if not isinstance(raw_options, dict):
        return {}
    options = {}
    for node_id, opts in raw_options.items():
        if node_id not in HUD_NODE_IDS or not isinstance(opts, dict):
            continue
        angle, radius = opts.get("angle"), opts.get("radius")
        # bool es subclase de int — mismo chequeo ya establecido en
        # _normalize_span de acá abajo para no normalizar True/False a 1/0
        # en silencio.
        angle_ok = isinstance(angle, (int, float)) and not isinstance(angle, bool)
        radius_ok = isinstance(radius, (int, float)) and not isinstance(radius, bool)
        if angle_ok and radius_ok:
            options[node_id] = {"angle": float(angle), "radius": float(radius)}
    return options


def _normalize_span(raw_options: dict, widget_id: str) -> dict:
    defaults = DEFAULT_SPANS[widget_id]
    col_span = raw_options.get("col_span", defaults["col_span"])
    row_span = raw_options.get("row_span", defaults["row_span"])
    # bool es subclase de int en Python — sin este chequeo, {"col_span": true}
    # pasaría el isinstance(int) y se normalizaría silenciosamente a 1.
    if not isinstance(col_span, int) or isinstance(col_span, bool) or not (MIN_COL_SPAN <= col_span <= MAX_COL_SPAN):
        col_span = defaults["col_span"]
    if not isinstance(row_span, int) or isinstance(row_span, bool) or not (MIN_ROW_SPAN <= row_span <= MAX_ROW_SPAN):
        row_span = defaults["row_span"]
    return {"col_span": col_span, "row_span": row_span}


def _normalize(raw: dict) -> dict:
    defaults = _default_prefs()
    visible = {**defaults["visible_widgets"], **raw.get("visible_widgets", {})}
    visible = {widget_id: bool(visible.get(widget_id, True)) for widget_id in WIDGET_IDS}
    for widget_id in ALWAYS_VISIBLE_WIDGET_IDS:
        visible[widget_id] = True

    order = [w for w in raw.get("panel_order", []) if w in WIDGET_IDS]
    order += [w for w in WIDGET_IDS if w not in order]

    raw_options = raw.get("widget_options", {})
    widget_options = {
        widget_id: _normalize_span(raw_options.get(widget_id, {}), widget_id) for widget_id in WIDGET_IDS
    }

    raw_gmail_options = raw_options.get("gmail", {})
    gmail_max_results = raw_gmail_options.get("max_results", GMAIL_MAX_RESULTS_CHOICES[0])
    if gmail_max_results not in GMAIL_MAX_RESULTS_CHOICES:
        gmail_max_results = GMAIL_MAX_RESULTS_CHOICES[0]
    widget_options["gmail"]["max_results"] = gmail_max_results

    dashboard_view = raw.get("dashboard_view")
    if dashboard_view not in DASHBOARD_VIEW_VALUES:
        dashboard_view = "classic"

    hud_chat_position = raw.get("hud_chat_position")
    if hud_chat_position not in HUD_CHAT_POSITION_VALUES:
        hud_chat_position = "left"

    # bool es subclase de int en Python — mismo chequeo ya establecido en
    # _normalize_span/_normalize_hud_widget_options de acá arriba, para que
    # un payload no-bool (ej. 1, "true") no se cuele como True en silencio.
    hud_sidebar_pinned_raw = raw.get("hud_sidebar_pinned")
    hud_sidebar_pinned = hud_sidebar_pinned_raw if isinstance(hud_sidebar_pinned_raw, bool) else False

    return {
        "visible_widgets": visible,
        "panel_order": order,
        "widget_options": widget_options,
        "dashboard_view": dashboard_view,
        "hud_widget_state": _normalize_hud_widget_state(raw),
        "hud_widget_options": _normalize_hud_widget_options(raw),
        "hud_chat_position": hud_chat_position,
        "hud_sidebar_pinned": hud_sidebar_pinned,
    }


def _path(user_id: str) -> Path:
    return PREFS_DIR / f"{user_id}.json"


def load_prefs(user_id: str) -> dict:
    path = _path(user_id)
    if not path.exists():
        return _default_prefs()
    return _normalize(json.loads(path.read_text(encoding="utf-8")))


def save_prefs(user_id: str, raw: dict) -> dict:
    prefs = _normalize(raw)
    PREFS_DIR.mkdir(parents=True, exist_ok=True)
    _path(user_id).write_text(json.dumps(prefs, ensure_ascii=False, indent=2), encoding="utf-8")
    return prefs
