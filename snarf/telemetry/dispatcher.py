"""Pub/sub in-process de eventos de telemetría (Fase 1 del plan de
observabilidad). La escritura a JSONL NO pasa por acá — sigue siendo
síncrona e inline dentro de events.py, porque es el piso real de
durabilidad y varios tests existentes (test_activity_log.py,
test_telemetry_events.py, test_usage_tracker.py) pasan un `path=` por
llamada y asertan el archivo inmediatamente después; un dispatcher
asincrónico rompería esa garantía. Este módulo es solo para consumidores
ADICIONALES (Fase 2: Redis, SSE) — un subscriber roto o lento nunca puede
frenar ni romper un turno real.

Deliberadamente `queue.Queue` (no `asyncio.Queue`): hay publishers sin
ningún event loop corriendo (main.py, mcp_server.py, el ThreadPoolExecutor
de la Inteligencia Ejecutiva) — `queue.Queue` es la única primitiva segura
para los cuatro orígenes reales de un evento (request FastAPI, background
task async, subproceso MCP, CLI de voz/texto)."""

import atexit
import os
import queue
import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

Subscriber = Callable[[dict], None]

SYNC = "sync"
ASYNC = "async"
MAX_QUEUE = 10_000


@dataclass(frozen=True)
class Subscription:
    name: str
    callback: Subscriber
    mode: str
    event_types: frozenset[str] | None = None


@dataclass
class _SubscriberStats:
    delivered: int = 0
    errors: int = 0
    last_error: str | None = None


_lock = threading.Lock()
_subscriptions: dict[str, Subscription] = {}
_stats: dict[str, _SubscriberStats] = {}
_published = 0
_dropped = 0

_queue: "queue.Queue[dict] | None" = None
_worker: threading.Thread | None = None


def _record_delivery(name: str) -> None:
    _stats.setdefault(name, _SubscriberStats()).delivered += 1


def _record_error(name: str, exc: Exception) -> None:
    stats = _stats.setdefault(name, _SubscriberStats())
    stats.errors += 1
    stats.last_error = f"{type(exc).__name__}: {exc}"


def _deliver(sub: Subscription, event: dict) -> None:
    if sub.event_types is not None and event.get("event_type") not in sub.event_types:
        return
    try:
        sub.callback(event)
        with _lock:
            _record_delivery(sub.name)
    except Exception as exc:  # nunca propaga: un subscriber roto no puede tumbar un turno real
        with _lock:
            _record_error(sub.name, exc)


def _worker_loop(q: "queue.Queue[dict]") -> None:
    while True:
        event = q.get()
        if event is None:  # sentinel de shutdown
            q.task_done()
            return
        with _lock:
            async_subs = [s for s in _subscriptions.values() if s.mode == ASYNC]
        for sub in async_subs:
            _deliver(sub, event)
        q.task_done()


def _ensure_worker() -> "queue.Queue[dict]":
    global _queue, _worker
    with _lock:
        if _queue is None:
            _queue = queue.Queue(maxsize=MAX_QUEUE)
        if _worker is None or not _worker.is_alive():
            _worker = threading.Thread(target=_worker_loop, args=(_queue,), daemon=True, name="snarf-telemetry-dispatcher")
            _worker.start()
        return _queue


def subscribe(name: str, callback: Subscriber, *, mode: str = ASYNC, event_types: Iterable[str] | None = None) -> Subscription:
    sub = Subscription(name=name, callback=callback, mode=mode, event_types=frozenset(event_types) if event_types is not None else None)
    with _lock:
        _subscriptions[name] = sub
        _stats.setdefault(name, _SubscriberStats())
    if mode == ASYNC:
        _ensure_worker()
    return sub


def unsubscribe(name: str) -> bool:
    with _lock:
        return _subscriptions.pop(name, None) is not None


def subscribers() -> tuple[Subscription, ...]:
    with _lock:
        return tuple(_subscriptions.values())


def publish(event: dict) -> None:
    """Nunca levanta, nunca bloquea un turno real. Subscribers sync corren
    inline (tragando cualquier excepción); subscribers async van a una cola
    acotada — si está llena se descarta el evento nuevo (nunca se espera)."""
    global _published, _dropped
    with _lock:
        _published += 1
        sync_subs = [s for s in _subscriptions.values() if s.mode == SYNC]
        has_async = any(s.mode == ASYNC for s in _subscriptions.values())
    for sub in sync_subs:
        _deliver(sub, event)
    if not has_async:
        return
    q = _ensure_worker()
    try:
        q.put_nowait(event)
    except queue.Full:
        with _lock:
            _dropped += 1


def stats() -> dict:
    with _lock:
        return {
            "published": _published,
            "dropped": _dropped,
            "by_subscriber": {
                name: {"delivered": s.delivered, "errors": s.errors, "last_error": s.last_error}
                for name, s in _stats.items()
            },
        }


def drain(timeout: float = 2.0) -> bool:
    """Hook de test/shutdown: espera a que la cola async quede vacía.
    Devuelve True si drenó dentro del timeout."""
    with _lock:
        q = _queue
    if q is None:
        return True
    try:
        q.join()
        return True
    except Exception:
        return False


def reset() -> None:
    """Hook de test: saca todos los subscribers y limpia stats — no toca el
    worker/la cola (se reusan entre tests, más barato que recrearlos)."""
    global _published, _dropped
    with _lock:
        _subscriptions.clear()
        _stats.clear()
        _published = 0
        _dropped = 0


def stop(timeout: float = 2.0) -> None:
    global _queue, _worker
    drain(timeout)
    with _lock:
        q, w = _queue, _worker
        _queue = None
        _worker = None
    if q is not None:
        try:
            q.put_nowait(None)
        except queue.Full:
            pass
    if w is not None:
        w.join(timeout=timeout)


def _reset_worker_after_fork() -> None:
    # Evita heredar un worker thread muerto + una cola potencialmente
    # medio-lockeada en un proceso hijo forkeado (no aplica a spawn/MCP
    # subproceso, que arranca en limpio de cualquier forma).
    global _queue, _worker
    _queue = None
    _worker = None


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_reset_worker_after_fork)

atexit.register(stop)
