import json
from pathlib import Path

PREFS_DIR = Path("data/user_profile")

# Bug real que motivó esto: Snarf empezó a llamar al fundador por un nombre
# inventado ("Andi") sin que nadie se lo hubiera dicho — una alucinación de
# identidad, justo lo que el Principio VI de FOUNDATION.md prohíbe (nunca
# presentar como cierto lo que no se puede justificar). El nombre real del
# usuario ahora se persiste acá, atado a su user_id — el mismo user_id que
# ya identifica sus credenciales de Google (`credentials/tokens/<user_id>.json`)
# y sus preferencias (`dashboard_prefs`, `personality_prefs`). Nunca se infiere
# ni se adivina: si no está guardado, el system prompt le instruye a Snarf que
# lo pregunte, no que invente uno.
NAME_MAX_LENGTH = 80


def _default_profile() -> dict:
    return {"name": None}


def _normalize_name(raw) -> str | None:
    if not isinstance(raw, str):
        return None
    name = raw.strip()
    return name[:NAME_MAX_LENGTH] if name else None


def _normalize(raw: dict) -> dict:
    return {"name": _normalize_name(raw.get("name"))}


def _path(user_id: str) -> Path:
    return PREFS_DIR / f"{user_id}.json"


def load_profile(user_id: str) -> dict:
    path = _path(user_id)
    if not path.exists():
        return _default_profile()
    return _normalize(json.loads(path.read_text(encoding="utf-8")))


def save_profile(user_id: str, raw: dict) -> dict:
    profile = _normalize(raw)
    PREFS_DIR.mkdir(parents=True, exist_ok=True)
    _path(user_id).write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    return profile
