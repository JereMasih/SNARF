"""Sink opcional hacia Redis Streams (Fase 2 del plan de observabilidad) —
transporte real para consumidores externos que el dispatcher in-process de
Fase 1 no puede alcanzar por sí solo: un segundo proceso (n8n, un futuro
Control Center) o el subproceso MCP de un rol de la Inteligencia Ejecutiva.

Nunca una dependencia dura, en ningún sentido:
- Sin SNARF_REDIS_URL seteada (default, y default en tests — ver
  tests/conftest.py), el paquete `redis` NI SE IMPORTA. `install()` no hace
  nada y devuelve False.
- El import de `redis` es perezoso, adentro de `install()` — un despliegue
  sin el paquete instalado nunca se entera de que este módulo existe.
- `publish_to_stream` (el callback real que corre en el worker thread del
  dispatcher) traga TODA excepción — ConnectionError, TimeoutError,
  ResponseError, lo que sea. Un turno real jamás se entera de que Redis
  está caído; el fallo queda contado acá, expuesto vía health() en
  ops_system_health (snarf/runtime/ops_health.py).

Diseño del stream (ver ADR 0136): un único stream `snarf:events`, MAXLEN
aproximado — no uno por tipo de evento, la traza/replay necesitan un log
ordenado único, los consumidores filtran por campo. Consumer groups
(XREADGROUP) para trabajo repartido (n8n, un futuro Control Center);
XREAD simple para el SSE de la propia Snarf (cada pestaña quiere ver TODO
desde su cursor, no una partición — un consumer group ahí sería el error
estándar de "dos pestañas se reparten los eventos")."""

import json
import os
import threading

STREAM_KEY = "snarf:events"
MAXLEN = 100_000
URL_ENV_VAR = "SNARF_REDIS_URL"
SUBSCRIBER_NAME = "redis_stream"

_lock = threading.Lock()
_client = None
_configured = False
_published = 0
_failed = 0
_last_error: str | None = None


def is_configured() -> bool:
    return bool(os.environ.get(URL_ENV_VAR))


def install(name: str = SUBSCRIBER_NAME) -> bool:
    """Registra el subscriber en el dispatcher solo si (a) SNARF_REDIS_URL
    está seteada y (b) el paquete `redis` está instalado. Devuelve False,
    sin levantar, en cualquier otro caso — llamar a esto siempre es seguro,
    esté o no Redis configurado."""
    global _client, _configured
    url = os.environ.get(URL_ENV_VAR)
    if not url:
        return False
    try:
        import redis
    except ImportError:
        return False
    with _lock:
        _client = redis.Redis.from_url(
            url,
            socket_connect_timeout=1,
            socket_timeout=2,
            retry_on_timeout=True,
            health_check_interval=30,
        )
        _configured = True
    from snarf.telemetry import dispatcher

    dispatcher.subscribe(name, publish_to_stream, mode=dispatcher.ASYNC)
    return True


def publish_to_stream(event: dict) -> None:
    global _published, _failed, _last_error
    with _lock:
        client = _client
    if client is None:
        return
    try:
        fields = {
            "v": "2",
            "event_type": event.get("event_type") or "",
            "trace_id": event.get("trace_id") or "",
            "nodo": event.get("nodo") or "",
            "origin_pid": str(event.get("origin_pid") or ""),
            "json": json.dumps(event, ensure_ascii=False),
        }
        client.xadd(STREAM_KEY, fields, maxlen=MAXLEN, approximate=True)
        with _lock:
            _published += 1
    except Exception as exc:
        with _lock:
            _failed += 1
            _last_error = f"{type(exc).__name__}: {exc}"


def health() -> dict:
    with _lock:
        return {
            "configured": _configured,
            "published": _published,
            "failed": _failed,
            "last_error": _last_error,
        }


def reset() -> None:
    """Hook de test — vuelve al estado sin configurar, sin tocar la env var
    real (eso lo maneja monkeypatch en cada test)."""
    global _client, _configured, _published, _failed, _last_error
    with _lock:
        _client = None
        _configured = False
        _published = 0
        _failed = 0
        _last_error = None
