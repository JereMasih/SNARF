import json
from pathlib import Path

PREFS_DIR = Path("data/dashboard_prefs")

WIDGET_IDS = ["system", "conversations", "memory", "cost", "drive", "gmail", "calendar", "youtube"]
GMAIL_MAX_RESULTS_CHOICES = [5, 10, 20]


def _default_prefs() -> dict:
    return {
        "visible_widgets": {widget_id: True for widget_id in WIDGET_IDS},
        "panel_order": list(WIDGET_IDS),
        "widget_options": {"gmail": {"max_results": GMAIL_MAX_RESULTS_CHOICES[0]}},
    }


def _normalize(raw: dict) -> dict:
    defaults = _default_prefs()
    visible = {**defaults["visible_widgets"], **raw.get("visible_widgets", {})}
    visible = {widget_id: bool(visible.get(widget_id, True)) for widget_id in WIDGET_IDS}

    order = [w for w in raw.get("panel_order", []) if w in WIDGET_IDS]
    order += [w for w in WIDGET_IDS if w not in order]

    raw_gmail_options = raw.get("widget_options", {}).get("gmail", {})
    gmail_max_results = raw_gmail_options.get("max_results", GMAIL_MAX_RESULTS_CHOICES[0])
    if gmail_max_results not in GMAIL_MAX_RESULTS_CHOICES:
        gmail_max_results = GMAIL_MAX_RESULTS_CHOICES[0]

    return {
        "visible_widgets": visible,
        "panel_order": order,
        "widget_options": {"gmail": {"max_results": gmail_max_results}},
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
