import json
import time
import uuid
from pathlib import Path

DEFAULT_PATH = Path("data/leads.jsonl")


def _target(path: Path | None) -> Path:
    return path if path is not None else DEFAULT_PATH


def append(name: str, email: str, path: Path | None = None) -> dict:
    """Registro append-only de un Lead real capturado desde `POST
    /vision/lead` (botón "Hablar con Snarf" de la landing pública) — mismo
    patrón que snarf/telemetry/blog.py. Contiene PII real (nombre+email),
    nunca se commitea (ver .gitignore)."""
    target = _target(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "id": str(uuid.uuid4()),
        "created_at": time.time(),
        "name": name,
        "email": email,
    }
    with target.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def list_all(path: Path | None = None) -> list[dict]:
    target = _target(path)
    if not target.exists():
        return []
    content = target.read_text(encoding="utf-8").strip()
    if not content:
        return []
    entries = [json.loads(line) for line in content.splitlines()]
    entries.sort(key=lambda e: e["created_at"], reverse=True)
    return entries


def get(lead_id: str, path: Path | None = None) -> dict | None:
    for entry in list_all(path):
        if entry["id"] == lead_id:
            return entry
    return None
