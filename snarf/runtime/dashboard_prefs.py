import json
from pathlib import Path

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
    }


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

    return {
        "visible_widgets": visible,
        "panel_order": order,
        "widget_options": widget_options,
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
