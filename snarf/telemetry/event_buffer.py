"""Buffer in-process acotado de los últimos eventos reales (Fase 2 del plan
de observabilidad) — para que `GET /events/stream` (ver app.py) funcione
incluso sin Redis configurado (ver redis_sink.py). Un subscriber más del
dispatcher de Fase 1 (`snarf/telemetry/dispatcher.py`), nunca la fuente de
verdad — esa sigue siendo `telemetry_events.jsonl`. Efímero a propósito: se
pierde en cada reinicio del proceso, igual que cualquier cola en memoria."""

import collections
import threading

MAX_EVENTS = 500
SUBSCRIBER_NAME = "event_buffer"

_lock = threading.Lock()
_buffer: collections.deque = collections.deque(maxlen=MAX_EVENTS)
_seq = 0


def _append(event: dict) -> None:
    global _seq
    with _lock:
        _seq += 1
        _buffer.append((_seq, event))


def install(name: str = SUBSCRIBER_NAME) -> None:
    from snarf.telemetry import dispatcher

    dispatcher.subscribe(name, _append, mode=dispatcher.ASYNC)


def since(last_seq: int | None) -> list[tuple[int, dict]]:
    """Eventos con seq > last_seq, en orden de llegada. `last_seq=None`
    devuelve todo lo que haya en el buffer ahora mismo (reconexión sin
    cursor real, o el arranque de una pestaña nueva)."""
    with _lock:
        snapshot = list(_buffer)
    if last_seq is None:
        return snapshot
    return [(seq, event) for seq, event in snapshot if seq > last_seq]


def latest_seq() -> int | None:
    with _lock:
        return _buffer[-1][0] if _buffer else None


def reset() -> None:
    """Hook de test — vacía el buffer y reinicia el cursor."""
    global _seq
    with _lock:
        _buffer.clear()
        _seq = 0
