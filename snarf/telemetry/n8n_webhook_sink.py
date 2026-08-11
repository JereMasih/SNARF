"""Sink opcional hacia un webhook de n8n (Fase 4 del plan de multi-usuario/
observabilidad, ADR 0139) — la mitad "Snarf empuja eventos reales hacia
n8n" de la integración. n8n nunca es un segundo orquestador ni dueño de
lógica de negocio (mismo principio ya vigente para MCP, ver ADR 0093) —
esto solo transporta eventos ya reales, nunca decide nada.

Mismo criterio de resiliencia que redis_sink.py (Fase 2): nunca una
dependencia dura. Sin N8N_WEBHOOK_URL seteada, el sink ni se instala. Si
n8n está caído o el webhook falla, el fallo se traga y se cuenta acá — un
turno real de Snarf jamás se entera."""

import os
import threading

import requests

URL_ENV_VAR = "N8N_WEBHOOK_URL"
SUBSCRIBER_NAME = "n8n_webhook"
_TIMEOUT_SECONDS = 3

_lock = threading.Lock()
_configured = False
_sent = 0
_failed = 0
_last_error: str | None = None


def is_configured() -> bool:
    return bool(os.environ.get(URL_ENV_VAR))


def install(name: str = SUBSCRIBER_NAME) -> bool:
    """Registra el subscriber en el dispatcher solo si N8N_WEBHOOK_URL está
    seteada. Devuelve False, sin levantar, en cualquier otro caso — llamar
    a esto siempre es seguro, esté o no n8n configurado."""
    global _configured
    if not os.environ.get(URL_ENV_VAR):
        return False
    with _lock:
        _configured = True
    from snarf.telemetry import dispatcher

    dispatcher.subscribe(name, publish_to_webhook, mode=dispatcher.ASYNC)
    return True


def publish_to_webhook(event: dict) -> None:
    global _sent, _failed, _last_error
    url = os.environ.get(URL_ENV_VAR)
    if not url:
        return
    try:
        response = requests.post(url, json=event, timeout=_TIMEOUT_SECONDS)
        response.raise_for_status()
        with _lock:
            _sent += 1
    except Exception as exc:
        with _lock:
            _failed += 1
            _last_error = f"{type(exc).__name__}: {exc}"


def health() -> dict:
    with _lock:
        return {"configured": _configured, "sent": _sent, "failed": _failed, "last_error": _last_error}


def reset() -> None:
    """Hook de test — vuelve al estado sin configurar, sin tocar la env var
    real (eso lo maneja monkeypatch en cada test)."""
    global _configured, _sent, _failed, _last_error
    with _lock:
        _configured = False
        _sent = 0
        _failed = 0
        _last_error = None
