import json
from pathlib import Path

PREFS_DIR = Path("data/personality_prefs")

# A pedido explícito del fundador: "sin configurar" acá no es "igual que
# antes" como en dashboard_prefs.py — es una intensificación deliberada del
# "Ingenio seco" de CHARACTER.md respecto al Snarf de hoy (ver CHARACTER.md
# v0.3 y el ADR de esta feature).
DEFAULT_SARCASM_LEVEL = 7.5
MIN_SARCASM_LEVEL, MAX_SARCASM_LEVEL = 0.0, 10.0
SARCASM_STEP = 0.5


def _default_prefs() -> dict:
    return {"sarcasm_level": DEFAULT_SARCASM_LEVEL}


def _normalize_sarcasm_level(raw) -> float:
    # bool es subclase de int en Python — mismo gotcha ya documentado en
    # dashboard_prefs.py: sin este chequeo, {"sarcasm_level": true} pasaría el
    # isinstance((int, float)) y se normalizaría silenciosamente a 1.0.
    if not isinstance(raw, (int, float)) or isinstance(raw, bool):
        return DEFAULT_SARCASM_LEVEL
    if not (MIN_SARCASM_LEVEL <= raw <= MAX_SARCASM_LEVEL):
        return DEFAULT_SARCASM_LEVEL
    return round(raw * 2) / 2


def _normalize(raw: dict) -> dict:
    return {"sarcasm_level": _normalize_sarcasm_level(raw.get("sarcasm_level", DEFAULT_SARCASM_LEVEL))}


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
