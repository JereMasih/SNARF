"""Motor de relevancia contextual (Fase 5 del plan de HUD, ver
SESSION_STATE.md) — decide qué nodos del dock radial (Fase 2) se muestran
con más prioridad, en base a señales reales, nunca simuladas:

- **Eventos recientes**: recencia + frecuencia real de actividad por nodo
  (`data/telemetry_events.jsonl`, Fase 1).
- **Alertas pendientes**: la única noción real de "alerta" que existe hoy
  en Snarf es un error reciente (`estado == "error"`) — no hay un sistema
  de alertas separado que inventar.
- **Gasto del día sobre un umbral**: reusa `cost_history.by_day` (Fase 3).
  `DAILY_COST_ALERT_THRESHOLD_USD` es una decisión de diseño nueva de esta
  fase (no un valor que el fundador haya fijado) — declarado como tal,
  configurable.

"Tarea activa" (pedido en el prompt original de la Fase 5) no tiene hoy
ningún sistema real detrás en Snarf — no existe un tracker de "tarea
activa" fuera de Proyectos, que es un concepto distinto (organización de
archivos/notas, no una cola de tareas en curso). Se interpreta con
honestidad como el nodo con la actividad más reciente: la señal real más
cercana a "en qué está trabajando Snarf ahora mismo" que existe de verdad.
"""

import time

from snarf.telemetry import brain

# Todos los nodos reales de brain.py (ADR 0089: "globos contextuales" —
# pedido explícito del fundador de que cada skill/capacidad/especialista
# tenga su propio widget, sin dejar ninguno afuera). Antes era un
# subconjunto chico elegido a mano (Fase 2, 9 nodos) — eso dejaba fuera
# nodos reales como `documents` o `gmail_send`, justo los que aparecen en
# los ejemplos concretos que pidió mostrar (crear un documento, mandar un
# mail). Derivado de `brain.NODE_TIER` en vez de duplicado a mano: un nodo
# nuevo agregado ahí (protocolo de crecimiento, ver brain.py) entra
# automáticamente al dock en el mismo cambio, sin un tercer lugar que
# actualizar.
DOCK_NODE_IDS = list(brain.NODE_TIER.keys())

DAILY_COST_ALERT_THRESHOLD_USD = 1.00

WINDOW_SECONDS = 3600  # ventana de "actividad reciente" para recencia/frecuencia
RECENCY_WEIGHT = 40.0
FREQUENCY_WEIGHT = 6.0
FREQUENCY_CAP = 8  # más de 8 eventos en la ventana no suma más — evita que un nodo ruidoso tape al resto
ERROR_BOOST = 50.0
COST_ALERT_SCORE = 100.0  # siempre por encima de cualquier nodo real — es la prioridad más alta posible


def _node_signals(node_id: str, events: list[dict], now: float) -> dict:
    node_events = [e for e in events if e.get("nodo") == node_id]
    recent = [e for e in node_events if now - e["timestamp"] <= WINDOW_SECONDS]
    last_timestamp = max((e["timestamp"] for e in node_events), default=None)
    has_recent_error = any(e.get("estado") == "error" for e in recent)
    return {
        "nodo": node_id,
        "eventos_recientes": len(recent),
        "last_timestamp": last_timestamp,
        "alerta": has_recent_error,
    }


def _score(signals: dict, now: float) -> float:
    score = 0.0
    if signals["last_timestamp"] is not None:
        age = now - signals["last_timestamp"]
        if age <= WINDOW_SECONDS:
            score += RECENCY_WEIGHT * (1 - age / WINDOW_SECONDS)
    score += FREQUENCY_WEIGHT * min(signals["eventos_recientes"], FREQUENCY_CAP)
    if signals["alerta"]:
        score += ERROR_BOOST
    return round(score, 2)


def _reasons(signals: dict) -> list[str]:
    reasons = []
    if signals["alerta"]:
        reasons.append("error_reciente")
    if signals["eventos_recientes"] > 0:
        reasons.append("actividad_reciente")
    if signals["last_timestamp"] is None:
        reasons.append("sin_actividad")
    return reasons


def rank_nodes(events: list[dict], node_ids: list[str], now: float | None = None) -> list[dict]:
    """Ranking real de nodos por relevancia — nunca incluye un nodo que no
    esté en `node_ids` (el caller decide qué subconjunto del cerebro
    corresponde al dock, ver brain.py)."""
    now = now if now is not None else time.time()
    ranked = []
    for node_id in node_ids:
        signals = _node_signals(node_id, events, now)
        ranked.append(
            {
                "nodo": node_id,
                "score": _score(signals, now),
                "eventos_recientes": signals["eventos_recientes"],
                "last_timestamp": signals["last_timestamp"],
                "razones": _reasons(signals),
            }
        )
    ranked.sort(key=lambda r: r["score"], reverse=True)
    return ranked


def cost_alert(day_summary: list[dict], threshold_usd: float = DAILY_COST_ALERT_THRESHOLD_USD, today_key: str | None = None) -> dict | None:
    """`day_summary` es el resultado real de cost_history.by_day() — busca
    el bucket de hoy (o el último si no se especifica `today_key`, pensado
    para que el caller pase la fecha real del día en curso) y devuelve una
    entrada de prioridad máxima si el gasto ya cruzó el umbral. `None` si
    no hay alerta real (nunca se inventa una)."""
    if not day_summary:
        return None
    bucket = next((b for b in day_summary if b["key"] == today_key), day_summary[-1]) if today_key else day_summary[-1]
    if bucket["costo_usd"] < threshold_usd:
        return None
    return {
        "nodo": "cost",
        "score": COST_ALERT_SCORE,
        "eventos_recientes": bucket["llamadas"],
        "last_timestamp": None,
        "razones": ["gasto_del_dia_sobre_umbral"],
        "costo_usd": bucket["costo_usd"],
        "umbral_usd": threshold_usd,
    }


def dock_priority(events: list[dict], node_ids: list[str], day_summary: list[dict], today_key: str | None = None, now: float | None = None) -> list[dict]:
    """Ranking completo para el dock radial (Fase 2): nodos reales por
    actividad/alertas + la alerta de costo (si aplica), todo ordenado por
    `score` descendente — el primero de la lista es el que "sube de
    prioridad y se mueve al centro" (pedido explícito del fundador)."""
    ranked = rank_nodes(events, node_ids, now=now)
    alert = cost_alert(day_summary, today_key=today_key)
    if alert is not None:
        ranked.append(alert)
    ranked.sort(key=lambda r: r["score"], reverse=True)
    return ranked
