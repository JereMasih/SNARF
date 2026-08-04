"""Agregación real por nodo para el dashboard "SNARF OS" (Vista HUD, ver ADR
del rediseño radial). No es una fuente de dato nueva — cada campo del
resultado ya viene de logs reales existentes (`events.all_events()`,
`relevance.rank_nodes()`/`dock_priority()`, `brain.NODE_TIER`). `None` es un
resultado legítimo cuando un nodo nunca tuvo actividad real: nunca se
inventa un widget con contenido de relleno (Principio VI de FOUNDATION.md).

Mismo motor de datos que ya alimenta el dock de globos contextuales del
panel Cerebro (ADR 0089) — el dashboard nuevo y los globos difieren solo en
presentación, no en de dónde sacan la información.

v2 (rediseño con profundidad 3D y plantillas, ver plan correspondiente)
suma dos cosas, ambas mecánicas — sin LLM de por medio, sin fabricar un
punto de dato: un histograma real de actividad reciente por nodo
(`recent_activity_buckets`, para el sparkline "en vivo" de los widgets con
gráfico) y el TAMAÑO de plantilla de cada widget (`size_tier`, asignado por
posición real en el ranking — ver `widget_templates.assign_tier`)."""

import time

from snarf.telemetry import brain, relevance, widget_templates


def recent_activity_buckets(
    node_id: str, events: list[dict], now: float | None = None, bucket_seconds: int = 60, num_buckets: int = 12
) -> list[int]:
    """Histograma mecánico de actividad REAL reciente — cuenta eventos reales
    del nodo en baldes de `bucket_seconds` hacia atrás desde `now`. Un balde
    sin eventos reales queda en 0, nunca interpolado ni inventado (Principio
    VI). El bucket 0 es el más viejo, el último el más reciente — orden
    cronológico, listo para graficar de izquierda a derecha."""
    now = now if now is not None else time.time()
    window_seconds = bucket_seconds * num_buckets
    buckets = [0] * num_buckets
    for e in events:
        if e.get("nodo") != node_id:
            continue
        age = now - e["timestamp"]
        if age < 0 or age > window_seconds:
            continue
        index = num_buckets - 1 - int(age // bucket_seconds)
        if 0 <= index < num_buckets:
            buckets[index] += 1
    return buckets


def summarize_node(node_id: str, events: list[dict], now: float | None = None) -> dict | None:
    now = now if now is not None else time.time()
    node_events = [e for e in events if e.get("nodo") == node_id]
    if not node_events:
        return None
    node_events.sort(key=lambda e: e["timestamp"])
    last_event = node_events[-1]
    # El evento MÁS RECIENTE con detalle real, no necesariamente el último
    # evento del nodo — un evento sin detalle (ej. un tool sin contenido
    # legible, ver detail.py) no debe pisar el último contenido real que sí
    # hubo.
    last_detalle = next((e.get("detalle") for e in reversed(node_events) if e.get("detalle")), None)
    # Igual criterio que last_detalle, pero para `preview` (ADR 0092,
    # título/link/snippet real de documento) — independiente de
    # last_detalle porque no todo evento con preview tiene el mismo evento
    # "más reciente con detalle" (son dos campos que se completan por
    # separado en detail.py).
    last_preview = next((e.get("preview") for e in reversed(node_events) if e.get("preview")), None)
    # Para las plantillas de lista/timeline (v2) — los últimos hasta 5
    # eventos reales CON detalle, más reciente primero. Mismo criterio que
    # last_detalle: un evento sin detalle legible no ocupa un lugar en la
    # lista (nunca se rellena con una fila vacía para llegar a 5).
    recent_items = [
        {"timestamp": e["timestamp"], "detalle": e["detalle"], "preview": e.get("preview")}
        for e in reversed(node_events)
        if e.get("detalle")
    ][:5]
    ranked = relevance.rank_nodes(events, [node_id], now=now)[0]
    return {
        "node_id": node_id,
        "tier": brain.NODE_TIER.get(node_id, node_id),
        "count_recent": ranked["eventos_recientes"],
        "count_total": len(node_events),
        "last_timestamp": last_event["timestamp"],
        "last_detalle": last_detalle,
        "last_preview": last_preview,
        "recent_items": recent_items,
        "has_error_recent": "error_reciente" in ranked["razones"],
        "score": ranked["score"],
        "activity_buckets": recent_activity_buckets(node_id, events, now),
    }


def _cost_alert_summary(rank_entry: dict, day_summary: list[dict]) -> dict:
    # Mismo criterio que el resto de este módulo: recorte mecánico de datos
    # reales (costo_usd/umbral_usd de relevance.cost_alert, serie real de
    # cost_history.by_day), nunca texto generado por un LLM acá.
    costo = rank_entry.get("costo_usd", 0.0)
    umbral = rank_entry.get("umbral_usd", 0.0)
    return {
        "node_id": "cost",
        "tier": "alert",
        "count_recent": rank_entry.get("eventos_recientes", 0),
        "count_total": rank_entry.get("eventos_recientes", 0),
        "last_timestamp": None,
        "last_detalle": f"gasto de hoy: ${costo:.2f} (umbral ${umbral:.2f})",
        "last_preview": None,  # el costo nunca es un documento real
        "recent_items": [],  # el costo no tiene "items" individuales — su serie real es cost_series
        "has_error_recent": False,
        "score": rank_entry["score"],
        "cost_series": [b["costo_usd"] for b in day_summary[-7:]],
    }


def all_widget_summaries(
    all_events: list[dict], day_summary: list[dict], today_key: str | None = None, now: float | None = None
) -> list[dict]:
    """Un resumen por cada nodo real con actividad relevante ahora mismo
    (`score > 0`), ordenados por score descendente — fuente única de qué se
    ve en el dashboard nuevo (`GET /dashboard/widget_summaries`). Cada
    resultado gana `size_tier` acá mismo, por posición real en el ranking
    (rank 0 = grande, ranks 1-3 = mediano, resto = chico) — nunca decidido
    por el curador (ver widget_templates.assign_tier).

    Los nodos de tier "input" (input_text/input_voice/input_file,
    brain.NODE_TIER) quedan afuera del dashboard a propósito — pedido real
    del fundador: su `detalle` es literalmente el mensaje que él mismo
    escribió/dijo, mostrárselo de vuelta como si fuera una novedad real de
    Snarf no aporta nada (él ya sabe qué mandó, está arriba en el chat).
    Siguen contando para todo lo demás (el dock de globos efímeros del
    panel Cerebro, el score real de otros nodos) — esto solo los saca de
    "qué widget se arma", no del resto de la telemetría."""
    now = now if now is not None else time.time()
    ranking = relevance.dock_priority(all_events, relevance.DOCK_NODE_IDS, day_summary, today_key=today_key, now=now)
    summaries = []
    for r in ranking:
        if r["score"] <= 0:
            continue
        if r["nodo"] == "cost":
            summaries.append(_cost_alert_summary(r, day_summary))
            continue
        if brain.NODE_TIER.get(r["nodo"]) == "input":
            continue
        summary = summarize_node(r["nodo"], all_events, now)
        if summary is not None:
            summaries.append(summary)
    for index, summary in enumerate(summaries):
        summary["size_tier"] = widget_templates.assign_tier(index)
    return summaries


def curation_snapshot(
    all_events: list[dict],
    day_summary: list[dict],
    today_key: str | None = None,
    now: float | None = None,
    top_n: int = 4,
) -> dict:
    """Entrada real para DashboardCuratorSpecialist — los mismos datos que
    `all_widget_summaries`, recortados al top-N y separados en las tres
    piezas que el Specialist tiene permitido rephrasear (nunca inventar):
    resúmenes por nodo, alerta de costo real (si hay), errores recientes
    reales. `top_n=4` por default porque es exactamente cuántos nodos reciben
    un `size_tier` que amerita curación (rank 0 = grande, ranks 1-3 =
    mediano) — los nodos chicos se muestran igual, pero con la plantilla
    default de su tamaño en vez de una elegida por el LLM."""
    now = now if now is not None else time.time()
    summaries = all_widget_summaries(all_events, day_summary, today_key=today_key, now=now)[:top_n]
    cost_alert = next((s for s in summaries if s["node_id"] == "cost"), None)
    node_summaries = [s for s in summaries if s["node_id"] != "cost"]
    recent_errors = [
        e for e in all_events if e.get("estado") == "error" and now - e["timestamp"] <= relevance.WINDOW_SECONDS
    ]
    return {"summaries": node_summaries, "cost_alert": cost_alert, "recent_errors": recent_errors}
