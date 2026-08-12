"""Replay de una ejecución real (Fase 20 del plan de observabilidad/n8n —
ver ROADMAP_OBSERVABILIDAD_MULTIUSUARIO_N8N.md, ADR 0161 — es la Fase 12 del
roadmap original, "Replay/debugging", nunca arrancada hasta ahora).

Reagrupa data/telemetry_events.jsonl (modelo de evento v2, event_id/
parent_event_id/trace_id, ADR 0135) por trace_id — nunca vuelve a ejecutar
nada ni a llamar a ningún LLM, solo reordena lo que ya pasó de verdad
(Principio VI, FOUNDATION.md: nunca presentar como real algo que no lo es).
`list_recent_traces()` lista trazas reales recientes (para que n8n pueda
ofrecer un menú de "qué ejecución mirar"); `events_for_trace()` devuelve la
secuencia completa y ordenada de una traza puntual, con el mismo verbo
temático determinístico que ya usa `/dashboard/telemetry_feed` (nunca
generado por el LLM) — para que el HUD la anime sin duplicar esa lógica."""

from pathlib import Path

from snarf.telemetry import events, verbs


def list_recent_traces(n: int = 20, path: Path | None = None) -> list[dict]:
    """Trazas reales recientes: una fila por `trace_id` que tuvo un
    `workflow.started`, con su estado final si ya cerró
    (`workflow.finished`/`failed`) y qué roles/agentes participaron
    (`agent.started` de ese mismo `trace_id`) — nunca inventa una traza que
    no tenga un evento real de inicio."""
    by_trace: dict[str, dict] = {}
    for e in events.all_events(path=path, include_lifecycle=True):
        trace_id = e.get("trace_id")
        if not trace_id:
            continue
        entry = by_trace.setdefault(
            trace_id,
            {"trace_id": trace_id, "kind": None, "started_at": None, "finished_at": None, "estado": "en_curso", "roles": []},
        )
        event_type = e.get("event_type")
        if event_type == events.WORKFLOW_STARTED:
            # El "nodo" de un evento de workflow es siempre brain.CENTER_NODE
            # ("orchestrator", ver spans.start_workflow) — el tipo real de
            # traza (ej. "executive_board", "turn") viaja en "skill".
            entry["kind"] = e.get("skill")
            entry["started_at"] = e["timestamp"]
        elif event_type in (events.WORKFLOW_FINISHED, events.WORKFLOW_FAILED):
            entry["finished_at"] = e["timestamp"]
            entry["estado"] = "error" if event_type == events.WORKFLOW_FAILED else "completo"
        elif event_type == events.AGENT_STARTED:
            # "agente" acá es el TIER ("specialist", ver brain.NODE_TIER),
            # no el rol — el rol real (ej. "cto") viaja en "skill" (ver
            # spans.start_agent: _new_span("agent", ..., skill=role)).
            role = e.get("skill") or e.get("agente")
            if role and role not in entry["roles"]:
                entry["roles"].append(role)

    traces = [t for t in by_trace.values() if t["started_at"] is not None]
    traces.sort(key=lambda t: t["started_at"], reverse=True)
    return traces[:n]


def events_for_trace(trace_id: str, path: Path | None = None) -> list[dict]:
    """Secuencia completa y ordenada por timestamp de una traza real
    puntual — todos los eventos (incluidos los de ciclo de vida) que
    comparten ese `trace_id`, con el mismo verbo temático determinístico que
    `/dashboard/telemetry_feed` (`snarf/telemetry/verbs.py`, nunca generado
    por el LLM)."""
    matching = [e for e in events.all_events(path=path, include_lifecycle=True) if e.get("trace_id") == trace_id]
    matching.sort(key=lambda e: e["timestamp"])
    return [
        {
            **e,
            "verbo": verbs.verbo_tematico(
                e.get("nodo") or "", e.get("agente") or "", e.get("estado") or "completo", skill=e.get("skill")
            ),
        }
        for e in matching
    ]
