"""Evento único de telemetría (ver TELEMETRY_SCHEMA.md, Fase 0 del plan de
HUD) — reagrupa lo que activity_log/usage_log/input_log ya registran por
separado en una sola forma de dato, para que el dock HUD, la Vista HUD del
cerebro y el historial de costos no tengan que cruzar tres logs distintos
con su propia lógica de normalización repetida.

No reemplaza esos tres logs: se emite ADEMÁS, desde adentro de sus mismas
funciones record(), reusando la normalización nodo/agente que brain.py ya
tiene (mismo vocabulario que pinta el cerebro actual). Ningún campo se
inventa — lo que no se puede derivar de un dato real queda en `None`
(ver gaps documentados en TELEMETRY_SCHEMA.md).

Fase 1 del plan de observabilidad agrega: correlación real entre eventos
(event_id/parent_event_id/trace_id, ver snarf/telemetry/context.py y
spans.py), el ciclo de vida completo de un turno/tool/llm/subagente
(event_type: *.started/*.finished/*.failed, no solo el resultado final), y
un fan-out hacia consumidores adicionales (snarf/telemetry/dispatcher.py) —
la escritura a JSONL sigue siendo el piso real de durabilidad, nunca se
demota a "un subscriber más". Todo esto es aditivo: los 14 campos v1
existentes no cambian de nombre/posición/significado, y los event_type
nuevos quedan invisibles por default para cualquier consumidor viejo (ver
LEGACY_EVENT_TYPES/is_legacy más abajo) — nadie tuvo que tocar un dashboard
existente para que esta fase sea segura."""

import json
import os
import time
from pathlib import Path

from snarf.telemetry import brain, context, dispatcher

DEFAULT_PATH = Path("data/telemetry_events.jsonl")

SCHEMA_VERSION = 2

TOOL_STATUS_TO_ESTADO = {"ok": "completo", "error": "error", "unknown_tool": "error"}

# Ciclo de vida completo por tipo de span (ver spans.py). Un ".started"
# nunca lleva costo/tokens/latencia reales todavía — se completan recién en
# el ".finished"/".failed" correspondiente, mismo event_id.
WORKFLOW_STARTED = "workflow.started"
WORKFLOW_FINISHED = "workflow.finished"
WORKFLOW_FAILED = "workflow.failed"
AGENT_STARTED = "agent.started"
AGENT_FINISHED = "agent.finished"
AGENT_FAILED = "agent.failed"
TOOL_STARTED = "tool.started"
TOOL_FINISHED = "tool.finished"
TOOL_FAILED = "tool.failed"
LLM_STARTED = "llm.started"
LLM_FINISHED = "llm.finished"
LLM_FAILED = "llm.failed"
# Una sola llamada, sin ".started" — para vendors que Fase 1 no instrumenta
# a nivel de span (STT/TTS/embeddings: ElevenLabs, Groq, local, Voyage).
VENDOR_FINISHED = "vendor.finished"
INPUT_RECEIVED = "input.received"

# Allowlist positivo — mismo criterio que snarf/mcp/tools.py::MCP_EXPOSED_TOOLS:
# todo event_type NUEVO queda invisible para los consumidores legacy
# (dashboards/cost_history/relevance/widget_summary) hasta que se agregue
# acá a propósito. Un evento v1 (escrito antes de Fase 1, sin event_type)
# siempre cuenta como legacy.
LEGACY_EVENT_TYPES = frozenset({
    TOOL_FINISHED,
    TOOL_FAILED,
    LLM_FINISHED,
    LLM_FAILED,
    VENDOR_FINISHED,
    INPUT_RECEIVED,
})


def is_legacy(entry: dict) -> bool:
    event_type = entry.get("event_type")
    return event_type is None or event_type in LEGACY_EVENT_TYPES


def _target(path: Path | None) -> Path:
    return path if path is not None else DEFAULT_PATH


def _write(entry: dict, path: Path | None) -> None:
    target = _target(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _emit(entry: dict, path: Path | None) -> None:
    # JSONL primero, síncrono — piso real de durabilidad, nunca se demora.
    # El dispatcher (Fase 1: solo consumidores in-process; Fase 2: Redis/SSE)
    # nunca bloquea ni levanta hacia el llamador — ver dispatcher.publish().
    _write(entry, path)
    dispatcher.publish(entry)


def _event(
    nodo, agente, skill, estado, *, event_type,
    modelo=None, tokens_in=None, tokens_out=None, costo_usd=None, latencia_ms=None,
    timestamp=None, detalle=None, preview=None,
    event_id=None, parent_event_id=None, trace_id=None, attributes=None,
) -> dict:
    # conversation_id/user_id/llm_role salen del contexto de turno
    # (snarf/telemetry/context.py), nunca de un parámetro nuevo en cada
    # record_*() — Orchestrator.handle() los setea al entrar a un turno real
    # y los limpia en un finally. Eventos fuera de un turno (digest de
    # Gmail, resumen de proyecto) quedan en None, honesto: no hay turno real
    # al que atribuirlos.
    #
    # event_id/parent_event_id/trace_id: si el emisor ya tiene un Span real
    # (ver spans.py), viajan explícitos acá. Si no (llamador legacy sin
    # instrumentar, o un evento fuera de cualquier span), se completan desde
    # el contexto ambiente — event_id nuevo siempre, parent/trace heredados
    # del span activo si lo hay. Nunca queda sin event_id: es lo mínimo para
    # que cualquier evento, instrumentado a propósito o no, sea localizable.
    return {
        "schema_version": SCHEMA_VERSION,
        "timestamp": timestamp if timestamp is not None else time.time(),
        "event_id": event_id if event_id is not None else context.new_id(),
        "parent_event_id": parent_event_id if parent_event_id is not None else context.get_current_span_id(),
        "trace_id": trace_id if trace_id is not None else context.get_trace_id(),
        "event_type": event_type,
        "origin_pid": os.getpid(),
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
        "user_id": context.get_user_id(),
        "llm_role": context.get_llm_role(),
        "detalle": detalle,
        "preview": preview,
        "attributes": attributes,
    }


def record_tool_event(
    tool_name: str, status: str, duration_ms: float | None = None, timestamp: float | None = None,
    path: Path | None = None, detalle: str | None = None, preview: dict | None = None, span=None,
) -> None:
    """Un evento por cada tool que despacha el Orchestrator — llamar desde
    adentro de activity_log.record(), mismo criterio de nodo que ya usa
    brain.py para no mantener dos taxonomías paralelas. `span` (opcional,
    ver spans.py): si el chokepoint ya abrió un tool.started para esta
    misma llamada, este evento cierra ese mismo event_id (tool.finished/
    tool.failed) en vez de generar uno nuevo sin relación."""
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
    estado = TOOL_STATUS_TO_ESTADO.get(status, "error")
    event_type = TOOL_FAILED if estado == "error" else TOOL_FINISHED
    if span is not None and span.event_id:
        event_id, parent_event_id, trace_id = span.event_id, span.parent_event_id, span.trace_id
    else:
        event_id = parent_event_id = trace_id = None
    _emit(
        _event(
            nodo,
            agente,
            tool_name,
            estado,
            event_type=event_type,
            latencia_ms=duration_ms,
            timestamp=timestamp,
            detalle=detalle,
            preview=preview,
            event_id=event_id,
            parent_event_id=parent_event_id,
            trace_id=trace_id,
        ),
        path,
    )


def record_vendor_event(
    vendor: str, model: str, cost_usd: float | None, metric: dict, estado: str = "completo",
    timestamp: float | None = None, path: Path | None = None, detalle: str | None = None,
    duration_ms: float | None = None, span=None,
) -> None:
    """Un evento por cada llamada real a un vendor (LLM/STT/TTS/embeddings)
    — llamar desde adentro de usage_tracker.record(). `metric` es el mismo
    dict que usage_tracker ya arma (input_tokens/output_tokens/etc.).
    `span` (opcional, ver spans.py): cuando viene de uno de los tres
    proveedores LLM instrumentados a nivel de span (Anthropic/OpenAI-
    compatible/Gemini), este evento cierra el llm.started correspondiente
    (llm.finished/llm.failed) en vez de emitir un vendor.finished
    desconectado — STT/TTS/embeddings, sin span, siguen emitiendo
    vendor.finished como antes."""
    if vendor == "elevenlabs":
        nodo = brain.ELEVENLABS_MODEL_TO_NODE.get(model)
    elif vendor == "local":
        nodo = brain.LOCAL_MODEL_TO_NODE.get(model)
    else:
        nodo = brain.VENDOR_TO_NODE.get(vendor)
    if nodo is None:
        return
    agente = brain.NODE_TIER.get(nodo, nodo)
    if span is not None and span.event_id and span.kind == "llm":
        event_type = LLM_FAILED if estado == "error" else LLM_FINISHED
        event_id, parent_event_id, trace_id = span.event_id, span.parent_event_id, span.trace_id
    else:
        event_type = VENDOR_FINISHED
        event_id = parent_event_id = trace_id = None
    _emit(
        _event(
            nodo,
            agente,
            f"{vendor}:{model}",
            estado,
            event_type=event_type,
            modelo=model,
            tokens_in=metric.get("input_tokens"),
            tokens_out=metric.get("output_tokens"),
            costo_usd=cost_usd,
            latencia_ms=duration_ms,
            timestamp=timestamp,
            detalle=detalle,
            event_id=event_id,
            parent_event_id=parent_event_id,
            trace_id=trace_id,
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
    _emit(
        _event(nodo, agente, category or channel, "completo", event_type=INPUT_RECEIVED, timestamp=timestamp, detalle=detalle),
        path,
    )


def record_lifecycle_event(
    event_type: str, span, *, estado: str | None = None, modelo=None, tokens_in=None, tokens_out=None,
    costo_usd=None, latencia_ms=None, detalle=None, preview=None, attributes=None, path: Path | None = None,
    timestamp: float | None = None,
) -> None:
    """Emite un evento de ciclo de vida (*.started/*.finished/*.failed) para
    un Span real (ver spans.py) — usado para workflow/agent siempre, y para
    tool/llm solo en el ".started" (el cierre de tool/llm pasa por
    record_tool_event/record_vendor_event de arriba, que ya alimentan
    activity_log.jsonl/usage_log.jsonl con los datos reales de costo/
    tokens — este no duplica esa escritura). No-op sobre un span nulo
    (tool/vendor sin nodo mapeado, ver spans.NULL_SPAN): drop simétrico,
    nunca un *.started huérfano sin su cierre."""
    if not span.event_id:
        return
    if estado is None:
        if event_type.endswith(".failed"):
            estado = "error"
        elif event_type.endswith(".started"):
            estado = "en_curso"
        else:
            estado = "completo"
    _emit(
        _event(
            span.nodo,
            span.agente,
            span.skill,
            estado,
            event_type=event_type,
            modelo=modelo if modelo is not None else span.modelo,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            costo_usd=costo_usd,
            latencia_ms=latencia_ms,
            timestamp=timestamp,
            detalle=detalle,
            preview=preview,
            event_id=span.event_id,
            parent_event_id=span.parent_event_id,
            trace_id=span.trace_id,
            attributes=attributes,
        ),
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


def recent(n: int = 100, path: Path | None = None, *, include_lifecycle: bool = False) -> list[dict]:
    rows = _read_all(path)
    if not include_lifecycle:
        rows = [r for r in rows if is_legacy(r)]
    return rows[-n:]


def all_events(path: Path | None = None, *, include_lifecycle: bool = False) -> list[dict]:
    """Todos los eventos guardados — a diferencia de `recent()`, pensado
    para agregaciones (Fase 3: historial de costos por día/agente/sesión),
    donde recortar a los últimos N distorsionaría el total real."""
    rows = _read_all(path)
    if not include_lifecycle:
        rows = [r for r in rows if is_legacy(r)]
    return rows
