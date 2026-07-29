import json
from pathlib import Path

PREFS_DIR = Path("data/dashboard_prefs")

# "history" (historial de conversaciones) y "chat" (el chat con Snarf en sí)
# se suman a la lista unificada de bloques de la grilla de escritorio — antes
# vivían fuera del sistema de widgets, fijos y sin poder moverse/redimensionar.
WIDGET_IDS = [
    "history", "chat", "system", "conversations", "memory", "cost",
    "drive", "gmail", "calendar", "youtube", "brain",
]
# Nunca se pueden ocultar, ni siquiera con un payload directo a la API — son
# el núcleo de la app, no un widget más que el fundador pueda apagar sin querer.
ALWAYS_VISIBLE_WIDGET_IDS = {"chat", "history"}
GMAIL_MAX_RESULTS_CHOICES = [5, 10, 20]

GRID_COLUMNS = 12
MIN_COL_SPAN, MAX_COL_SPAN = 1, GRID_COLUMNS
MIN_ROW_SPAN, MAX_ROW_SPAN = 3, 30

# Tamaño por defecto de cada bloque en la grilla de 12 columnas (filas de
# 28px) — elegido para que la primera carga, sin nada guardado todavía, se
# parezca a la proporción de columnas fija que existía antes (280px / ~500px
# / resto), no para que se vea desordenada.
DEFAULT_SPANS = {
    "history": {"col_span": 3, "row_span": 16},
    "chat": {"col_span": 6, "row_span": 16},
    "system": {"col_span": 3, "row_span": 8},
    "cost": {"col_span": 3, "row_span": 8},
    "conversations": {"col_span": 6, "row_span": 8},
    "memory": {"col_span": 6, "row_span": 8},
    "drive": {"col_span": 4, "row_span": 8},
    "gmail": {"col_span": 4, "row_span": 8},
    "calendar": {"col_span": 4, "row_span": 8},
    "youtube": {"col_span": 4, "row_span": 8},
    "brain": {"col_span": 4, "row_span": 8},
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
