"""Ciclo de vida de un span de telemetría (Fase 1 del plan de
observabilidad): abre un evento `*.started`, hace que todo lo que pase
dentro quede correlacionado como su hijo (`spans.active`), y lo cierra con
`*.finished`/`*.failed` compartiendo el mismo `event_id`.

Vive en snarf/telemetry/ (no snarf/core/ ni snarf/runtime/) a propósito:
tests/test_architecture_boundaries.py prohíbe que snarf/capabilities/* o
snarf/specialists/* importen snarf.core/snarf.runtime, y
snarf/capabilities/anthropic_llm.py ya importa hoy de snarf.telemetry
(context, usage_tracker) — este módulo sigue esa misma regla, así que
puede usarse desde cualquier capa sin violar el boundary real.

Resuelve `nodo`/`agente` vía la misma taxonomía de brain.py que ya usa
events.py — si un tool/vendor no tiene nodo mapeado, start_tool/start_llm
devuelven NULL_SPAN y ni el .started ni el .finished/.failed se emiten
(drop simétrico: nunca un evento de ciclo de vida huérfano)."""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from snarf.telemetry import brain, context, events


@dataclass(frozen=True)
class Span:
    kind: str  # "workflow" | "agent" | "tool" | "llm"
    event_id: str
    parent_event_id: str | None
    trace_id: str | None
    started_at: float
    nodo: str | None
    agente: str | None
    skill: str
    modelo: str | None = None

    def duration_ms(self) -> float:
        return (time.monotonic() - self.started_at) * 1000


NULL_SPAN = Span(kind="", event_id="", parent_event_id=None, trace_id=None, started_at=0.0, nodo=None, agente=None, skill="")

_FINISHED_EVENT_TYPE = {
    "workflow": events.WORKFLOW_FINISHED,
    "agent": events.AGENT_FINISHED,
    "tool": events.TOOL_FINISHED,
    "llm": events.LLM_FINISHED,
}
_FAILED_EVENT_TYPE = {
    "workflow": events.WORKFLOW_FAILED,
    "agent": events.AGENT_FAILED,
    "tool": events.TOOL_FAILED,
    "llm": events.LLM_FAILED,
}


def _new_span(kind: str, nodo: str | None, skill: str, *, modelo: str | None = None) -> Span:
    if nodo is None:
        return NULL_SPAN
    event_id = context.new_id()
    ambient_trace_id = context.get_trace_id()
    return Span(
        kind=kind,
        event_id=event_id,
        parent_event_id=context.get_current_span_id(),
        # Un span sin traza ambiente es la raíz de una traza nueva — su
        # propio event_id pasa a ser el trace_id (convención estándar).
        trace_id=ambient_trace_id if ambient_trace_id is not None else event_id,
        started_at=time.monotonic(),
        nodo=nodo,
        agente=brain.NODE_TIER.get(nodo, nodo),
        skill=skill,
        modelo=modelo,
    )


def start_workflow(kind: str, *, detalle: str | None = None, path: Path | None = None) -> Span:
    span = _new_span("workflow", brain.CENTER_NODE, kind)
    events.record_lifecycle_event(events.WORKFLOW_STARTED, span, detalle=detalle, path=path)
    return span


def start_agent(role: str, *, path: Path | None = None) -> Span:
    span = _new_span("agent", "specialist_executive_board", role)
    events.record_lifecycle_event(events.AGENT_STARTED, span, attributes={"role": role}, path=path)
    return span


def start_tool(tool_name: str, *, detalle: str | None = None, path: Path | None = None) -> Span:
    nodo = brain.CENTER_NODE if tool_name is None else brain.TOOL_TO_NODE.get(tool_name)
    span = _new_span("tool", nodo, tool_name)
    if span.event_id:
        events.record_lifecycle_event(events.TOOL_STARTED, span, detalle=detalle, path=path)
    return span


def start_llm(vendor: str, model: str, *, path: Path | None = None) -> Span:
    nodo = brain.VENDOR_TO_NODE.get(vendor)
    span = _new_span("llm", nodo, f"{vendor}:{model}", modelo=model)
    if span.event_id:
        events.record_lifecycle_event(events.LLM_STARTED, span, path=path)
    return span


def finish(
    span: Span, *, estado: str = "completo", detalle: str | None = None, preview: dict | None = None,
    attributes: dict | None = None, path: Path | None = None,
) -> None:
    if not span.event_id:
        return
    events.record_lifecycle_event(
        _FINISHED_EVENT_TYPE[span.kind], span, estado=estado, detalle=detalle, preview=preview,
        attributes=attributes, latencia_ms=span.duration_ms(), path=path,
    )


def fail(span: Span, *, reason: str, path: Path | None = None) -> None:
    if not span.event_id:
        return
    events.record_lifecycle_event(
        _FAILED_EVENT_TYPE[span.kind], span, estado="error", detalle=reason, latencia_ms=span.duration_ms(), path=path,
    )


@contextmanager
def active(span: Span) -> Iterator[Span]:
    """Hace de `span` el padre de todo evento (y de todo llm_role
    anidado, ver context.scoped_llm_role) emitido dentro del bloque. No-op
    sobre NULL_SPAN — nada que correlacionar."""
    if not span.event_id:
        yield span
        return
    with context.span(span.event_id, trace_id=span.trace_id):
        yield span
