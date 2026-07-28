import json
import time
from pathlib import Path

DEFAULT_PATH = Path("data/activity_log.jsonl")


def _target(path: Path | None) -> Path:
    return path if path is not None else DEFAULT_PATH


def record(tool_name: str, status: str, duration_ms: float | None = None, error: str | None = None, path: Path | None = None) -> None:
    """Registro append-only de cada herramienta que ejecuta el Orchestrator —
    qué se ejecutó y cuándo, base real (no inventada) para una futura
    visualización del "cerebro" de Snarf. Ver Roadmaps en MASTER_MAP.md."""
    target = _target(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": time.time(),
        "tool_name": tool_name,
        "status": status,
        "duration_ms": duration_ms,
        "error": error,
    }
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


def recent(n: int = 50, path: Path | None = None) -> list[dict]:
    return _read_all(path)[-n:]


def stats(path: Path | None = None) -> dict:
    entries = _read_all(path)
    by_tool: dict[str, int] = {}
    errors = 0
    for e in entries:
        by_tool[e["tool_name"]] = by_tool.get(e["tool_name"], 0) + 1
        if e.get("status") == "error":
            errors += 1
    return {"total_calls": len(entries), "errors": errors, "by_tool": by_tool}
