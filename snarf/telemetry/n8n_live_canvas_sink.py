"""Sink en vivo hacia el canvas "Snarf - Turno en vivo" de n8n (Fase 24 del
plan de observabilidad/n8n — ver ROADMAP_OBSERVABILIDAD_MULTIUSUARIO_N8N.md,
ADR 0166). Distinto de n8n_webhook_sink.py (ADR 0139, sin estado, manda cada
evento a una URL fija): este necesita recordar, por trace_id, en qué
ejecución real de n8n está esperando el próximo evento de ESE turno — para
que dos turnos concurrentes nunca se crucen (ver snarf/runtime/
n8n_generator.py::build_live_turn_workflow()).

Mismo criterio de resiliencia de siempre (dispatcher.py: "un subscriber
roto nunca puede tumbar un turno real"): cualquier falla (n8n caído,
trace_id desconocido, timeout de red) se traga y se cuenta en health(),
nunca se propaga. Solo dos POSTs por evento relevante — arrancar una
ejecución nueva o avanzar una existente — nunca espera una respuesta de
n8n más allá de un timeout corto, y n8n nunca llama de vuelta a Snarf
durante este camino (mismo sentido unidireccional que ya exige ADR 0164
tras el incidente real del 2026-08-12).

Importa dos constantes de snarf.runtime.n8n_generator (LIVE_TURN_WEBHOOK_PATH,
N8N_BASE_URL) — es la única forma de que el path del webhook nunca quede
desincronizado entre lo que genera el workflow real y lo que este sink
dispara. snarf.telemetry en general evita depender de snarf.runtime (ver
spans.py) pero acá el costo real de duplicar el path (y poder
desincronizarlo) es peor que esta excepción puntual — no hay ciclo de
importación real (n8n_generator.py no importa snarf.telemetry)."""

import os
import threading
import time

import requests

from snarf.runtime.n8n_generator import (
    LIVE_TURN_STAGE_COUNT,
    LIVE_TURN_STAGE_TIMEOUT_MINUTES,
    LIVE_TURN_WEBHOOK_PATH,
    N8N_BASE_URL,
)

ENABLED_ENV_VAR = "N8N_LIVE_CANVAS_ENABLED"
SUBSCRIBER_NAME = "n8n_live_canvas"
_TIMEOUT_SECONDS = 3
# Alineado al timeout real de cada nodo Wait (mismo valor que
# n8n_generator.LIVE_TURN_STAGE_TIMEOUT_MINUTES) — un trace local más viejo
# que esto ya expiró del lado de n8n también, no tiene sentido seguir
# mandándole resumes.
_MAX_AGE_SECONDS = LIVE_TURN_STAGE_TIMEOUT_MINUTES * 60
_MAX_STAGE_RESUMES = LIVE_TURN_STAGE_COUNT

_LIFECYCLE_EVENT_TYPES = frozenset(
    {
        "workflow.started", "workflow.finished", "workflow.failed",
        "agent.started", "agent.finished", "agent.failed",
        "tool.started", "tool.finished", "tool.failed",
        "llm.started", "llm.finished", "llm.failed",
    }
)

_lock = threading.Lock()
_configured = False
_started = 0
_resumed = 0
_failed = 0
_last_error: str | None = None
_traces: dict[str, dict] = {}


def is_configured() -> bool:
    return bool(os.environ.get(ENABLED_ENV_VAR))


def install(name: str = SUBSCRIBER_NAME) -> bool:
    """Registra el subscriber en el dispatcher solo si N8N_LIVE_CANVAS_ENABLED
    está seteada — el workflow real ('Snarf - Turno en vivo') tiene que
    existir ya en n8n antes de activar esto (ver
    n8n_generator.sync_live_turn_workflow(), o la Skill n8n-map-sync).
    Devuelve False, sin levantar, en cualquier otro caso."""
    global _configured
    if not os.environ.get(ENABLED_ENV_VAR):
        return False
    with _lock:
        _configured = True
    from snarf.telemetry import dispatcher

    dispatcher.subscribe(name, handle_event, mode=dispatcher.ASYNC, event_types=_LIFECYCLE_EVENT_TYPES)
    return True


def _base_url() -> str:
    return os.environ.get("N8N_BASE_URL", N8N_BASE_URL)


def _trigger_url() -> str:
    return f"{_base_url()}/webhook/{LIVE_TURN_WEBHOOK_PATH}"


def _resume_url(execution_id: str) -> str:
    return f"{_base_url()}/webhook-waiting/{execution_id}"


def _sweep_stale(now: float) -> None:
    stale = [trace_id for trace_id, state in _traces.items() if now - state["updated_at"] > _MAX_AGE_SECONDS]
    for trace_id in stale:
        del _traces[trace_id]


_RESUME_RETRY_DELAYS_SECONDS = (0.15, 0.3, 0.6)


def _post_resume_with_retry(execution_id: str, event: dict) -> requests.Response:
    """POST al resume real, con un reintento corto y acotado solo para
    `409 Conflict` — hallazgo real verificado contra la instancia real
    (2026-08-14, ver "Sesión 2026-08-14" del roadmap): `responseMode:
    responseNode` responde con el `execution_id` real ANTES de que la
    ejecución termine de llegar/pausarse en el nodo `Wait` — un resume
    disparado apenas se recibe la respuesta puede llegar antes de que n8n
    esté listo para aceptarlo, y n8n responde 409 en ese caso (no un error
    real de Snarf, ni una ejecución perdida). Cualquier otro código de
    error, o agotar los reintentos, se propaga tal cual — sigue siendo el
    caller quien cuenta la falla real en `health()`, nunca se traga acá."""
    url = _resume_url(execution_id)
    response = requests.post(url, json=event, timeout=_TIMEOUT_SECONDS)
    for delay in _RESUME_RETRY_DELAYS_SECONDS:
        if response.status_code != 409:
            return response
        time.sleep(delay)
        response = requests.post(url, json=event, timeout=_TIMEOUT_SECONDS)
    return response


def handle_event(event: dict) -> None:
    """Un `trace_id` nuevo con `workflow.started`/`skill="turn"` arranca una
    ejecución real nueva en n8n; cualquier evento de ciclo de vida posterior
    con ese mismo `trace_id` avanza esa ejecución un nodo `Wait` (hasta
    LIVE_TURN_STAGE_COUNT veces — ver build_live_turn_workflow() para por
    qué son genéricos y acotados). El cierre real del turno
    (`workflow.finished`/`failed` de `skill="turn"`) libera el estado local
    apenas se manda, sea cual sea el nodo Wait en el que haya caído."""
    global _started, _resumed, _failed, _last_error
    trace_id = event.get("trace_id")
    if not trace_id:
        return
    now = time.time()
    with _lock:
        _sweep_stale(now)
        state = _traces.get(trace_id)

    is_turn_start = event.get("event_type") == "workflow.started" and event.get("skill") == "turn"

    if state is None:
        if not is_turn_start:
            return  # nada esperando este trace_id — no es el arranque de un turno, se ignora
        try:
            response = requests.post(_trigger_url(), json=event, timeout=_TIMEOUT_SECONDS)
            response.raise_for_status()
            execution_id = str(response.json()[0]["executionId"])
        except Exception as exc:
            with _lock:
                _failed += 1
                _last_error = f"{type(exc).__name__}: {exc}"
            return
        with _lock:
            _traces[trace_id] = {"execution_id": execution_id, "stage": 0, "updated_at": now}
            _started += 1
        return

    if is_turn_start:
        return  # ya arrancado — un segundo workflow.started de "turn" con el mismo trace_id no pasa en la práctica

    if state["stage"] >= _MAX_STAGE_RESUMES:
        return  # se acabaron los nodos Wait del canvas — el turno real sigue, solo deja de tener más etapas visibles

    try:
        response = _post_resume_with_retry(state["execution_id"], event)
        response.raise_for_status()
        with _lock:
            _resumed += 1
    except Exception as exc:
        with _lock:
            _failed += 1
            _last_error = f"{type(exc).__name__}: {exc}"
        return

    with _lock:
        state["stage"] += 1
        state["updated_at"] = now
        is_turn_end = event.get("event_type") in ("workflow.finished", "workflow.failed") and event.get("skill") == "turn"
        if is_turn_end:
            _traces.pop(trace_id, None)


def health() -> dict:
    with _lock:
        return {
            "configured": _configured, "started": _started, "resumed": _resumed,
            "failed": _failed, "last_error": _last_error, "active_traces": len(_traces),
        }


def reset() -> None:
    """Hook de test — vuelve al estado sin configurar, sin tocar la env var
    real (eso lo maneja monkeypatch en cada test)."""
    global _configured, _started, _resumed, _failed, _last_error
    with _lock:
        _configured = False
        _started = 0
        _resumed = 0
        _failed = 0
        _last_error = None
        _traces.clear()
