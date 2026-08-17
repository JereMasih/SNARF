"""Contexto de turno/traza — para que el evento unificado de telemetría (ver
TELEMETRY_SCHEMA.md/events.py) pueda agregar costo/tokens "por sesión" y,
desde Fase 1 del plan de observabilidad, correlacionar eventos entre sí
(event_id/parent_event_id/trace_id) sin threadear un parámetro nuevo por
cada una de las funciones `record_*` de `usage_tracker.py`/`activity_log.py`.

`contextvars.ContextVar`, no `threading.local()` (cambio real de Fase 1,
motivo concreto, no estilo): FastAPI corre cada request síncrono en un
worker de threadpool que SÍ copia el `contextvars.Context` del caller (así
lo hace anyio), pero NO copia `threading.local()` — y el fan-out de la
Inteligencia Ejecutiva (`ThreadPoolExecutor`, ver snarf/executive/
specialist.py) tampoco propaga ninguno de los dos por sí solo, necesita
`contextvars.copy_context()` explícito. `threading.local()` además comparte
un único slot entre las corutinas en un mismo loop de eventos (ver los
`asyncio.create_task` de background en app.py) — con `ContextVar` cada
`Task`/`Context` tiene su propio valor aislado.

Orchestrator.handle() setea el conversation_id/user_id/trace real al entrar
y los limpia en un `finally`, así que nunca sobreviven más allá del turno
que los generó. Eventos que no ocurren dentro de un turno de conversación
real (digest de Gmail en segundo plano, resumen de proyecto, etc.)
simplemente no tienen estos valores seteados — quedan en `None`, nunca
inventados."""

import os
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

_conversation_id: ContextVar[str | None] = ContextVar("snarf_conversation_id", default=None)
_llm_role: ContextVar[str | None] = ContextVar("snarf_llm_role", default=None)
_request_id: ContextVar[str | None] = ContextVar("snarf_request_id", default=None)
_user_id: ContextVar[str | None] = ContextVar("snarf_user_id", default=None)
_trace_id: ContextVar[str | None] = ContextVar("snarf_trace_id", default=None)
_span_id: ContextVar[str | None] = ContextVar("snarf_span_id", default=None)
_board_consulted: ContextVar[bool] = ContextVar("snarf_board_consulted", default=False)


def set_conversation_id(conversation_id: str | None) -> None:
    _conversation_id.set(conversation_id)


def get_conversation_id() -> str | None:
    return _conversation_id.get()


def clear_conversation_id() -> None:
    _conversation_id.set(None)


def set_llm_role(role: str | None) -> None:
    _llm_role.set(role)


def get_llm_role() -> str | None:
    return _llm_role.get()


def clear_llm_role() -> None:
    _llm_role.set(None)


@contextmanager
def scoped_llm_role(role: str | None) -> Iterator[None]:
    """Como set_llm_role/clear_llm_role, pero restaura el valor anterior al
    salir en vez de limpiar a None — corrige un bug real de anidamiento: una
    llamada LLM de specialist (vía _ResilientLLM.generate, llm_routing.py)
    hecha DENTRO de un turno de Orchestrator.handle() (que ya seteó
    llm_role="orchestrator") borraba el rol a None para el resto del turno
    en vez de devolverlo a "orchestrator" cuando terminaba."""
    token = _llm_role.set(role)
    try:
        yield
    finally:
        _llm_role.reset(token)


def set_request_id(request_id: str | None) -> None:
    _request_id.set(request_id)


def get_request_id() -> str | None:
    return _request_id.get()


def clear_request_id() -> None:
    _request_id.set(None)


def set_user_id(user_id: str | None) -> None:
    _user_id.set(user_id)


def get_user_id() -> str | None:
    return _user_id.get()


def clear_user_id() -> None:
    _user_id.set(None)


def set_board_consulted(value: bool) -> None:
    _board_consulted.set(value)


def get_board_consulted() -> bool:
    return _board_consulted.get()


def clear_board_consulted() -> None:
    _board_consulted.set(False)


def get_trace_id() -> str | None:
    return _trace_id.get()


def get_current_span_id() -> str | None:
    return _span_id.get()


@contextmanager
def span(event_id: str, *, trace_id: str | None = None) -> Iterator[None]:
    """Hace de `event_id` el padre de todo evento emitido dentro del bloque
    (ver snarf/telemetry/spans.py). Restaura el valor anterior al salir
    (nunca lo limpia a None), así que anidar spans (turno -> tool -> llm) da
    la jerarquía correcta sin que cada emisor tenga que pasar
    parent_event_id a mano."""
    span_token = _span_id.set(event_id)
    trace_token = _trace_id.set(trace_id) if trace_id is not None else None
    try:
        yield
    finally:
        _span_id.reset(span_token)
        if trace_token is not None:
            _trace_id.reset(trace_token)


def new_id() -> str:
    return uuid.uuid4().hex


TRACE_ENV_VAR = "SNARF_TRACE_ID"
PARENT_ENV_VAR = "SNARF_PARENT_EVENT_ID"


def env_for_child_process() -> dict[str, str]:
    """Variables de entorno para propagar la traza activa a un subproceso
    real (ver snarf/executive/process.py) — el único modo real de cruzar ese
    límite de proceso: el entorno de un subproceso MCP no hereda
    contextvars, solo lo que se le pase explícito en `env=`. Diccionario
    vacío (nunca inventa una traza) cuando no hay ninguna activa."""
    env: dict[str, str] = {}
    trace_id = get_trace_id()
    if trace_id:
        env[TRACE_ENV_VAR] = trace_id
    parent_id = get_current_span_id()
    if parent_id:
        env[PARENT_ENV_VAR] = parent_id
    return env


def adopt_from_env(source: dict | None = None) -> None:
    """Adopta trace_id/parent_event_id reales de las variables de entorno
    (ver env_for_child_process) — para que un subproceso hijo (mcp_server.py)
    arranque con la traza real del proceso padre en vez de una propia sin
    relación. Nunca inventa: si las variables no están, ambos quedan None."""
    env = source if source is not None else os.environ
    trace_id = env.get(TRACE_ENV_VAR)
    parent_id = env.get(PARENT_ENV_VAR)
    if trace_id:
        _trace_id.set(trace_id)
    if parent_id:
        _span_id.set(parent_id)
