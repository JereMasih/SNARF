import json
import time
from pathlib import Path

from snarf.telemetry import events

DEFAULT_PATH = Path("data/activity_log.jsonl")


def _target(path: Path | None) -> Path:
    return path if path is not None else DEFAULT_PATH


def record(
    tool_name: str,
    status: str,
    duration_ms: float | None = None,
    error: str | None = None,
    path: Path | None = None,
    events_path: Path | None = None,
    detalle: str | None = None,
    preview: dict | None = None,
) -> None:
    """Registro append-only de cada herramienta que ejecuta el Orchestrator —
    qué se ejecutó y cuándo, base real (no inventada) para el cerebro de
    Snarf y, desde Fase 1 del plan de HUD, para el evento unificado de
    TELEMETRY_SCHEMA.md (ver snarf/telemetry/events.py). `detalle` (ADR 0089)
    y `preview` (ADR 0092) son contenido real ya extraído por
    snarf/telemetry/detail.py en el propio Orchestrator — este módulo solo
    los transporta hasta el evento unificado, nunca los calcula. Ver
    Roadmaps en MASTER_MAP.md."""
    target = _target(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    timestamp = time.time()
    entry = {
        "timestamp": timestamp,
        "tool_name": tool_name,
        "status": status,
        "duration_ms": duration_ms,
        "error": error,
    }
    with target.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    events.record_tool_event(
        tool_name, status, duration_ms=duration_ms, timestamp=timestamp, path=events_path, detalle=detalle, preview=preview
    )


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
