"""Contexto de conversación por thread — para que el evento unificado de
telemetría (ver TELEMETRY_SCHEMA.md/events.py) pueda agregar costo/tokens
"por sesión" (Fase 3 del plan de HUD) sin threadear un parámetro nuevo por
cada una de las ~10 funciones `record_*` de `usage_tracker.py`/
`activity_log.py`.

`threading.local()`, no un atributo de instancia de Orchestrator — mismo
criterio ya real de ADR 0041 (el `_service` cacheado de cada Capacidad
tenía la misma clase de bug: FastAPI corre cada request en un thread del
pool, y un singleton compartido pisa el estado de otro request en curso).
Orchestrator.handle() setea el conversation_id real al entrar y lo limpia
en un `finally`, así que nunca sobrevive más allá del turno que lo generó.

Eventos que no ocurren dentro de un turno de conversación real (digest de
Gmail en segundo plano, resumen de proyecto, etc.) simplemente no tienen
conversation_id seteado — el campo queda `None`, nunca inventado."""

import threading

_local = threading.local()


def set_conversation_id(conversation_id: str | None) -> None:
    _local.conversation_id = conversation_id


def get_conversation_id() -> str | None:
    return getattr(_local, "conversation_id", None)


def clear_conversation_id() -> None:
    _local.conversation_id = None
