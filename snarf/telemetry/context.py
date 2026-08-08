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
conversation_id seteado — el campo queda `None`, nunca inventado.

`set_llm_role`/`get_llm_role`/`clear_llm_role` (ADR de esta ronda): mismo
patrón exacto, para el rol real de `llm_routing.ROLES` (`"orchestrator"`,
`"gmail_digest"`, `"dashboard_curator"`, etc.) que disparó una llamada real
al LLM — `_ResilientLLM.generate()` (`llm_routing.py`) y los dos roles de
instancia fija de Orchestrator (`handle()`/`generate_conversation_title()`)
lo setean alrededor de su propia llamada real y lo limpian en un `finally`.
Motivo real: un prompt de 82.284 tokens tumbó el server MLX local un día
real (ver ADR de esta ronda) y no había forma de saber, mirando
`usage_log.jsonl` después, qué ROL lo había generado — solo vendor/modelo/
tokens, nunca de dónde vino."""

import threading

_local = threading.local()


def set_conversation_id(conversation_id: str | None) -> None:
    _local.conversation_id = conversation_id


def get_conversation_id() -> str | None:
    return getattr(_local, "conversation_id", None)


def clear_conversation_id() -> None:
    _local.conversation_id = None


def set_llm_role(role: str | None) -> None:
    _local.llm_role = role


def get_llm_role() -> str | None:
    return getattr(_local, "llm_role", None)


def clear_llm_role() -> None:
    _local.llm_role = None


def set_request_id(request_id: str | None) -> None:
    _local.request_id = request_id


def get_request_id() -> str | None:
    return getattr(_local, "request_id", None)


def clear_request_id() -> None:
    _local.request_id = None
