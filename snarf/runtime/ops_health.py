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
    recent_errors = [e for e in recent_activity if e.get("status") == "error"]
    return {
        "llm_available": llm_available,
        "google_available": google_available,
        "recent_call_count": len(recent_activity),
        "recent_error_count": len(recent_errors),
        "data_dir_size_mb": round(_dir_size_mb(data_dir), 1),
    }
