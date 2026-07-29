import json
import time
from pathlib import Path

DEFAULT_PATH = Path("data/input_log.jsonl")


def _target(path: Path | None) -> Path:
    return path if path is not None else DEFAULT_PATH


def record(channel: str, category: str | None = None, path: Path | None = None) -> None:
    """Registro append-only de cada entrada real de información a Snarf —
    texto, voz o archivo — con la categoría real del archivo cuando aplica
    (ver categorize_mime en snarf/knowledge/extraction.py). Base real para
    el anillo de entrada del cerebro de Snarf (ver ADR pendiente)."""
    target = _target(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    entry = {"timestamp": time.time(), "channel": channel, "category": category}
    with target.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _read_all(path: Path | None) -> list[dict]:
    target = _target(path)
    if not target.exists():
        return []
    content = target.read_text(encoding="utf-8").strip()
    if not content:
        return []
    return [json.loads(line) for line in content.splitlines()]


def recent(n: int = 100, path: Path | None = None) -> list[dict]:
    return _read_all(path)[-n:]
