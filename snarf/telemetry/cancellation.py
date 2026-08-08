"""Registro en memoria de pedidos `/send` en curso, para poder frenar una
generación real a mitad de camino (ver ADR de esta ronda). Vive en el
proceso de `app.py` — válido mientras Snarf corra con un solo worker de
uvicorn (como hoy); si algún día corre con `--workers > 1`, `/cancel` podría
no llegar al proceso que está generando la respuesta.

`register`/`finish` delimitan la vida real de un `request_id` (desde que
entra a `POST /send` hasta que `orchestrator.handle()` retorna). `cancel()`
solo marca un id que está activo — devuelve False para un id ya terminado o
inexistente, nunca finge éxito."""

import threading

_lock = threading.Lock()
_active: set[str] = set()
_cancelled: set[str] = set()


def register(request_id: str) -> None:
    with _lock:
        _active.add(request_id)


def cancel(request_id: str) -> bool:
    with _lock:
        if request_id not in _active:
            return False
        _cancelled.add(request_id)
        return True


def is_cancelled(request_id: str | None) -> bool:
    if not request_id:
        return False
    with _lock:
        return request_id in _cancelled


def finish(request_id: str) -> None:
    with _lock:
        _active.discard(request_id)
        _cancelled.discard(request_id)
