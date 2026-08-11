"""Diagnóstico real del sistema (Fase I, rama Ops/Custom — ver plan de
expansión "Inteligencia Ejecutiva"). Reúne señales que ya existen y ya se
registran (disponibilidad real de LLM/Google, actividad real reciente del
Orchestrator) en un solo resultado — nunca una cifra nueva inventada, solo
lo que ya se está registrando."""

from pathlib import Path


def _dir_size_mb(path: Path) -> float:
    if not path.exists():
        return 0.0
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return total / (1024 * 1024)


def system_health(
    llm_available: bool,
    google_available: bool,
    recent_activity: list[dict],
    data_dir: Path = Path("data"),
) -> dict:
    # event_dispatcher/event_bus_redis/event_bus_n8n (Fases 2 y 4 del plan
    # de observabilidad): mismo criterio que el resto de esta función —
    # señales que ya existen y ya se registran (snarf/telemetry/
    # dispatcher.py, redis_sink.py, n8n_webhook_sink.py), nunca una cifra
    # inventada. Ambos sink.health() reportan "configured": False con
    # seguridad incluso sin nada configurado — nunca importan/llaman nada
    # real en ese caso.
    from snarf.telemetry import dispatcher, n8n_webhook_sink, redis_sink

    recent_errors = [e for e in recent_activity if e.get("status") == "error"]
    return {
        "llm_available": llm_available,
        "google_available": google_available,
        "recent_call_count": len(recent_activity),
        "recent_error_count": len(recent_errors),
        "data_dir_size_mb": round(_dir_size_mb(data_dir), 1),
        "event_dispatcher": dispatcher.stats(),
        "event_bus_redis": redis_sink.health(),
        "event_bus_n8n": n8n_webhook_sink.health(),
    }
