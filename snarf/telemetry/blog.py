import json
import re
import time
import unicodedata
import uuid
from pathlib import Path

DEFAULT_PATH = Path("data/blog_posts.jsonl")

_SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")


def _target(path: Path | None) -> Path:
    return path if path is not None else DEFAULT_PATH


def _slugify(title: str) -> str:
    # NFKD + descartar los caracteres combinantes de acento (categoría Mn)
    # antes de aplicar el regex — así "título"/"acentós" dan "titulo"/
    # "acentos" en vez de perder la letra entera ("t-tulo").
    ascii_title = "".join(c for c in unicodedata.normalize("NFKD", title) if not unicodedata.combining(c))
    base = _SLUG_STRIP_RE.sub("-", ascii_title.lower()).strip("-")[:80].strip("-")
    return base or "articulo"


def _unique_slug(title: str, existing: list[dict]) -> str:
    taken = {e["slug"] for e in existing if e.get("slug")}
    base = _slugify(title)
    if base not in taken:
        return base
    n = 2
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}"


def append(
    title: str,
    body: str,
    summary: str,
    source_ref: str,
    public: bool = False,
    tags: list[str] | None = None,
    cover_image: str | None = None,
    path: Path | None = None,
) -> dict:
    """Registro de un artículo del blog de Snarf (GET /vision/blog,
    home real en GET /blog) — a partir de una investigación real de
    snarf/specialists/research o escrito a mano desde el CMS
    (GET /blog/admin), nunca texto de relleno inventado (Principio VI de
    FOUNDATION.md). `public` arranca en False a propósito: un artículo
    recién creado no queda visible hasta publicarlo. `slug` se deriva del
    título una sola vez acá (nunca se recalcula en update(), para no romper
    un link ya compartido) y es único entre TODOS los artículos, publicados
    o no."""
    target = _target(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    existing = _read_all(path)
    entry = {
        "id": str(uuid.uuid4()),
        "slug": _unique_slug(title, existing),
        "created_at": time.time(),
        "updated_at": time.time(),
        "title": title,
        "summary": summary,
        "body": body,
        "tags": tags or [],
        "source_ref": source_ref,
        "public": public,
        "cover_image": cover_image,
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


def _write_all(entries: list[dict], path: Path | None) -> None:
    target = _target(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def list_public(path: Path | None = None) -> list[dict]:
    entries = [e for e in _read_all(path) if e.get("public")]
    entries.sort(key=lambda e: e["created_at"], reverse=True)
    return entries


def list_all(path: Path | None = None) -> list[dict]:
    """Todos los artículos, publicados o borrador — para el CMS
    (GET /blog/admin), nunca expuesto sin el gate de fundador."""
    entries = _read_all(path)
    entries.sort(key=lambda e: e["created_at"], reverse=True)
    return entries


def get(id_or_slug: str, path: Path | None = None) -> dict | None:
    for entry in _read_all(path):
        if entry["id"] == id_or_slug or entry.get("slug") == id_or_slug:
            return entry
    return None


_EDITABLE_FIELDS = {"title", "summary", "body", "tags", "source_ref", "public", "cover_image"}


def update(article_id: str, path: Path | None = None, **fields) -> dict | None:
    """Edita un artículo real existente por `id` — el `slug` nunca cambia acá
    (un link ya compartido no puede romperse por editar el título después).
    Devuelve `None` si `article_id` no existe; nunca inventa una entrada."""
    entries = _read_all(path)
    updated = None
    for entry in entries:
        if entry["id"] == article_id:
            for key, value in fields.items():
                if key in _EDITABLE_FIELDS:
                    entry[key] = value
            entry["updated_at"] = time.time()
            updated = entry
            break
    if updated is not None:
        _write_all(entries, path)
    return updated


def delete(article_id: str, path: Path | None = None) -> bool:
    entries = _read_all(path)
    remaining = [e for e in entries if e["id"] != article_id]
    if len(remaining) == len(entries):
        return False
    _write_all(remaining, path)
    return True
