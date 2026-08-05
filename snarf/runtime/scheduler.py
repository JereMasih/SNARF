"""Scheduling por hora de reloj real (Fase I, rama Productivity — ver plan de
expansión "Inteligencia Ejecutiva"). Los loops periódicos de hoy (backup,
purga de audio, curación del dashboard) son todos de intervalo fijo desde el
arranque del proceso — una rutina real que deba dispararse a una hora de
reloj concreta (ej. las 8:00 de la mañana) necesita otra cosa. Sin motor de
cron nuevo: un único cálculo real, agnóstico de para qué se use."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def next_run_at(hour: int, minute: int, tz: str, now: datetime | None = None) -> float:
    """Próximo timestamp real (epoch, UTC) en que ocurre hour:minute en la
    zona horaria `tz` — hoy mismo si todavía no pasó, mañana si ya pasó.
    `now`, si se pasa, se convierte a `tz` antes de comparar — un `now` en
    otra zona (ej. UTC) nunca debe interpretarse como si ya estuviera en
    hora local de `tz`."""
    zone = ZoneInfo(tz)
    now = (now or datetime.now(zone)).astimezone(zone)
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate.timestamp()
