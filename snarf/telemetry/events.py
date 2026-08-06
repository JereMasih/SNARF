"""Evento único de telemetría (ver TELEMETRY_SCHEMA.md, Fase 0 del plan de
HUD) — reagrupa lo que activity_log/usage_log/input_log ya registran por
separado en una sola forma de dato, para que el dock HUD, la Vista HUD del
cerebro y el historial de costos no tengan que cruzar tres logs distintos
con su propia lógica de normalización repetida.

No reemplaza esos tres logs: se emite ADEMÁS, desde adentro de sus mismas
funciones record(), reusando la normalización nodo/agente que brain.py ya
tiene (mismo vocabulario que pinta el cerebro actual). Ningún campo se
inventa — lo que no se puede derivar de un dato real queda en `None`
(ver gaps documentados en TELEMETRY_SCHEMA.md)."""

import json
import time
from pathlib import Path

from snarf.telemetry import brain, context

DEFAULT_PATH = Path("data/telemetry_events.jsonl")

TOOL_STATUS_TO_ESTADO = {"ok": "completo", "error": "error", "unknown_tool": "error"}


def _target(path: Path | None) -> Path:
    return path if path is not None else DEFAULT_PATH


def _write(entry: dict, path: Path | None) -> None:
    target = _target(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _event(nodo, agente, skill, estado, modelo=None, tokens_in=None, tokens_out=None, costo_usd=None, latencia_ms=None, timestamp=None, detalle=None, preview=None) -> dict:
    # conversation_id sale del contexto por thread (snarf/telemetry/context.py),
    # nunca de un parámetro nuevo en cada record_*() — Orchestrator.handle()
    # lo setea al entrar a un turno real y lo limpia en un finally. Eventos
    # fuera de un turno (digest de Gmail, resumen de proyecto) quedan en
    # None, honesto: no hay conversación real a la que atribuirlos.
    return {
        "timestamp": timestamp if timestamp is not None else time.time(),
        "nodo": nodo,
        "agente": agente,
        "skill": skill,
        "modelo": modelo,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "costo_usd": costo_usd,
        "latencia_ms": latencia_ms,
        "estado": estado,
        "conversation_id": context.get_conversation_id(),
        # `detalle`: contenido real de qué se hizo (ver
        # snarf/telemetry/detail.py y ADR 0089) — a diferencia de `skill`
        # (identificador del tool), esto es el destinatario/título/query/etc.
        # real cuando existe; `None` si el tool no tiene contenido legible o
        # el extractor no encontró nada real (nunca se inventa).
        "detalle": detalle,
        # `preview`: previsualización real de documento cuando el tool tocó
        # uno (ver snarf/telemetry/detail.py::extract_preview y ADR 0092) —
        # `{"title", "link", "snippet"}` con lo que haya de verdad, o `None`
        # si el tool no tiene ningún documento real que mostrar. A
        # diferencia de `detalle` (siempre texto), esto queda estructurado
        # para que el frontend pueda armar una tarjeta clickeable en vez de
        # solo una línea de texto.
        "preview": preview,
    }


def record_tool_event(tool_name: str, status: str, duration_ms: float | None = None, timestamp: float | None = None, path: Path | None = None, detalle: str | None = None, preview: dict | None = None) -> None:
    """Un evento por cada tool que despacha el Orchestrator — llamar desde
    adentro de activity_log.record(), mismo criterio de nodo que ya usa
    brain.py para no mantener dos taxonomías paralelas."""
    if status == "unknown_tool":
        nodo = brain.CENTER_NODE
    else:
        nodo = brain.TOOL_TO_NODE.get(tool_name)
        if nodo is None:
            # Tool sin nodo mapeado en brain.py — no debería pasar en
            # producción (test_tool_to_node_covers_every_orchestrator_tool lo
            # garantiza), pero no inventamos un nodo acá si igual ocurriera.
            return
    agente = brain.NODE_TIER.get(nodo, nodo)
    _write(
        _event(
            nodo,
            agente,
            tool_name,
            TOOL_STATUS_TO_ESTADO.get(status, "error"),
            latencia_ms=duration_ms,
            timestamp=timestamp,
            detalle=detalle,
            preview=preview,
        ),
        path,
    )


def record_vendor_event(vendor: str, model: str, cost_usd: float | None, metric: dict, estado: str = "completo", timestamp: float | None = None, path: Path | None = None, detalle: str | None = None, duration_ms: float | None = None) -> None:
    """Un evento por cada llamada real a un vendor (LLM/STT/TTS/embeddings)
    — llamar desde adentro de usage_tracker.record(). `metric` es el mismo
    dict que usage_tracker ya arma (input_tokens/output_tokens/etc.)."""
    if vendor == "elevenlabs":
        nodo = brain.ELEVENLABS_MODEL_TO_NODE.get(model)
    elif vendor == "local":
        nodo = brain.LOCAL_MODEL_TO_NODE.get(model)
    else:
        nodo = brain.VENDOR_TO_NODE.get(vendor)
    if nodo is None:
        return
    agente = brain.NODE_TIER.get(nodo, nodo)
    _write(
        _event(
            nodo,
            agente,
            f"{vendor}:{model}",
            estado,
            modelo=model,
            tokens_in=metric.get("input_tokens"),
            tokens_out=metric.get("output_tokens"),
            costo_usd=cost_usd,
            latencia_ms=duration_ms,
            timestamp=timestamp,
            detalle=detalle,
        ),
        path,
    )


def record_input_event(channel: str, category: str | None = None, timestamp: float | None = None, path: Path | None = None, detalle: str | None = None) -> None:
    """Un evento por cada entrada real a Snarf — llamar desde adentro de
    input_log.record()."""
    nodo = brain.CHANNEL_TO_NODE.get(channel)
    if nodo is None:
        return
    agente = brain.NODE_TIER.get(nodo, nodo)
    _write(
        _event(nodo, agente, category or channel, "completo", timestamp=timestamp, detalle=detalle),
        path,
    )


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


def all_events(path: Path | None = None) -> list[dict]:
    """Todos los eventos guardados — a diferencia de `recent()`, pensado
    para agregaciones (Fase 3: historial de costos por día/agente/sesión),
    donde recortar a los últimos N distorsionaría el total real."""
    return _read_all(path)
