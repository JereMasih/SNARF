import json
import time
import uuid
from pathlib import Path

DEFAULT_PATH = Path("data/blog_posts.jsonl")


def _target(path: Path | None) -> Path:
    return path if path is not None else DEFAULT_PATH


def append(
    title: str,
    body: str,
    summary: str,
    source_ref: str,
    public: bool = False,
    tags: list[str] | None = None,
    path: Path | None = None,
) -> dict:
    """Registro append-only de un artículo del blog de Snarf (GET /vision) —
    escrito con la voz de CHARACTER.md/COGNITION.md a partir de una
    investigación real de snarf/specialists/research (`source_ref` apunta a
    esa investigación, nunca texto de relleno inventado, Principio VI de
    FOUNDATION.md). `public` arranca en False a propósito: un artículo recién
    generado no queda visible en /vision/blog hasta publicarlo a mano."""
    target = _target(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "id": str(uuid.uuid4()),
        "created_at": time.time(),
        "title": title,
        "summary": summary,
        "body": body,
        "tags": tags or [],
        "source_ref": source_ref,
        "public": public,
    }
    with target.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def _read_all(path: Path | None) -> list[dict]:
    target = _target(path)
    if not target.exists():
        return []
    content = target.read_text(encoding="utf-8").strip()
    if not content:
        return []
    return [json.loads(line) for line in content.splitlines()]


def list_public(path: Path | None = None) -> list[dict]:
    entries = [e for e in _read_all(path) if e.get("public")]
    entries.sort(key=lambda e: e["created_at"], reverse=True)
    return entries
