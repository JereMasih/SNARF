"""Historial de costos y consumo (Fase 3 del plan de HUD, ver
SESSION_STATE.md) — agrega el evento unificado de telemetría
(TELEMETRY_SCHEMA.md/events.py) por día, por agente y por sesión
(conversation_id, ver snarf/telemetry/context.py). No agrega ninguna fuente
de datos nueva: lee data/telemetry_events.jsonl tal cual Fase 1 ya lo
guarda.

`costo_usd` puede ser `None` en un evento real (vendor sin tarifa por uso
conocida, ver ADR 0077/usage_tracker.record_elevenlabs_tts_call) — eso
significa "no se sabe", nunca "cero" (Principio VI de FOUNDATION.md). Cada
bucket separa `costo_usd` (suma solo de lo conocido) de
`llamadas_sin_costo_estimado`, igual que ya hace
usage_tracker.summarize()."""

from datetime import datetime
from zoneinfo import ZoneInfo

# Mismo valor real que snarf/core/orchestrator.py:FOUNDER_TIMEZONE —
# duplicado acá a propósito: snarf/telemetry/ no importa snarf/core (mismo
# criterio de capas que ya aplica a capabilities/specialists, ver ADR 0026).
FOUNDER_TIMEZONE = "America/Argentina/Buenos_Aires"


def _day_key(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=ZoneInfo(FOUNDER_TIMEZONE)).strftime("%Y-%m-%d")


def _new_bucket(key: str) -> dict:
    return {
        "key": key,
        "costo_usd": 0.0,
        "tokens_in": 0,
        "tokens_out": 0,
        "llamadas": 0,
        "errores": 0,
        "llamadas_sin_costo_estimado": 0,
    }


def _bucket_events(events: list[dict], key_fn) -> dict:
    buckets: dict[str, dict] = {}
    for e in events:
        key = key_fn(e)
        if key is None:
            continue
        b = buckets.setdefault(key, _new_bucket(key))
        b["llamadas"] += 1
        if e.get("estado") == "error":
            b["errores"] += 1
        if e.get("costo_usd") is None:
            b["llamadas_sin_costo_estimado"] += 1
        else:
            b["costo_usd"] += e["costo_usd"]
        b["tokens_in"] += e.get("tokens_in") or 0
        b["tokens_out"] += e.get("tokens_out") or 0
    return buckets


def by_day(events: list[dict]) -> list[dict]:
    buckets = _bucket_events(events, lambda e: _day_key(e["timestamp"]))
    return sorted(buckets.values(), key=lambda b: b["key"])


def by_agente(events: list[dict]) -> list[dict]:
    buckets = _bucket_events(events, lambda e: e.get("agente"))
    return sorted(buckets.values(), key=lambda b: b["costo_usd"], reverse=True)


def by_session(events: list[dict]) -> list[dict]:
    # Eventos sin conversation_id (digest de Gmail en segundo plano, resumen
    # de proyecto, etc.) quedan afuera a propósito — no hay sesión real a la
    # que atribuirlos, agregarlos bajo una clave "None" mentiría una sesión
    # que no existe.
    buckets = _bucket_events(events, lambda e: e.get("conversation_id"))
    return sorted(buckets.values(), key=lambda b: b["costo_usd"], reverse=True)


def summary(events: list[dict]) -> dict:
    return {"by_day": by_day(events), "by_agente": by_agente(events), "by_session": by_session(events)}
