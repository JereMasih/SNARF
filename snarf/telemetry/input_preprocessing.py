"""Panel de optimización de entrada (Fase 6 del plan de HUD, ver
SESSION_STATE.md) — registro real de qué tan grande es el contexto final
enviado al LLM en cada turno, comparado contra lo que el fundador
efectivamente escribió.

Snarf no reescribe el mensaje del fundador (viaja verbatim en `messages`,
ver `Orchestrator.handle()`) — lo que sí varía turno a turno es todo lo que
viaja ALREDEDOR de ese mensaje: el system prompt (identidad + sarcasmo +
perfil + prompt de proyecto) y el historial reciente re-transmitido. Este
módulo mide eso en caracteres reales (no tokens exactos — un proxy honesto,
declarado como tal, no una estimación de tokens que Snarf no puede calcular
sin llamar al tokenizer real de cada proveedor)."""

import json
import time
from pathlib import Path

DEFAULT_PATH = Path("data/input_preprocessing_log.jsonl")


def _target(path: Path | None) -> Path:
    return path if path is not None else DEFAULT_PATH


def record(
    conversation_id: str | None,
    input_original: str,
    system_chars: int,
    history_chars: int,
    history_entries: int,
    path: Path | None = None,
) -> None:
    target = _target(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    input_chars = len(input_original)
    total_sent_chars = system_chars + history_chars + input_chars
    entry = {
        "timestamp": time.time(),
        "conversation_id": conversation_id,
        "input_original": input_original,
        "input_chars": input_chars,
        "system_chars": system_chars,
        "history_chars": history_chars,
        "history_entries": history_entries,
        "total_sent_chars": total_sent_chars,
        # Cuántos caracteres viajaron por cada uno que el fundador escribió
        # — la métrica real de "eficiencia de contexto" que pidió esta
        # fase. None cuando input_chars es 0 (nunca se divide por cero).
        "overhead_ratio": round(total_sent_chars / input_chars, 2) if input_chars else None,
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


def summary(path: Path | None = None) -> dict:
    entries = _read_all(path)
    if not entries:
        return {"turns": 0, "avg_overhead_ratio": None, "avg_total_sent_chars": None, "avg_input_chars": None}
    ratios = [e["overhead_ratio"] for e in entries if e["overhead_ratio"] is not None]
    return {
        "turns": len(entries),
        "avg_overhead_ratio": round(sum(ratios) / len(ratios), 2) if ratios else None,
        "avg_total_sent_chars": round(sum(e["total_sent_chars"] for e in entries) / len(entries)),
        "avg_input_chars": round(sum(e["input_chars"] for e in entries) / len(entries)),
    }
