from snarf.telemetry import relevance, widget_summary


def _event(nodo, ts, estado="completo", detalle=None, preview=None):
    return {
        "timestamp": ts, "nodo": nodo, "agente": "capability", "skill": f"{nodo}_tool",
        "modelo": None, "tokens_in": None, "tokens_out": None, "costo_usd": None,
        "latencia_ms": 10, "estado": estado, "conversation_id": "c1", "detalle": detalle,
        "preview": preview,
    }


def test_summarize_node_returns_none_when_no_activity():
    assert widget_summary.summarize_node("drive", [], now=1000.0) is None
    assert widget_summary.summarize_node("drive", [_event("gmail_send", 999.0)], now=1000.0) is None


def test_summarize_node_aggregates_real_fields():
    events = [
        _event("drive", 900.0, detalle="leyendo un archivo"),
        _event("drive", 990.0, estado="error"),
    ]
    summary = widget_summary.summarize_node("drive", events, now=1000.0)
    assert summary["node_id"] == "drive"
    assert summary["tier"] == "capability"
    assert summary["count_total"] == 2
    assert summary["last_timestamp"] == 990.0
    assert summary["has_error_recent"] is True
    assert summary["score"] > 0


def test_summarize_node_keeps_last_real_detalle_even_if_latest_event_has_none():
    events = [
        _event("drive", 900.0, detalle="leyendo un archivo real"),
        _event("drive", 990.0, detalle=None),
    ]
    summary = widget_summary.summarize_node("drive", events, now=1000.0)
    assert summary["last_detalle"] == "leyendo un archivo real"


def test_summarize_node_never_raises_for_any_real_node_id():
    events = [_event("drive", 990.0, detalle="algo real")]
    for node_id in relevance.DOCK_NODE_IDS:
        result = widget_summary.summarize_node(node_id, events, now=1000.0)
        assert result is None or isinstance(result, dict)


def test_all_widget_summaries_excludes_nodes_with_zero_score():
    events = [_event("drive", 990.0, detalle="real")]
    summaries = widget_summary.all_widget_summaries(events, [], now=1000.0)
    node_ids = {s["node_id"] for s in summaries}
    assert "drive" in node_ids
    assert "notion" not in node_ids  # sin actividad real, nunca aparece


def test_all_widget_summaries_sorted_by_score_descending():
    events = [_event("drive", 990.0), _event("gmail_send", 500.0)]
    summaries = widget_summary.all_widget_summaries(events, [], now=1000.0)
    scores = [s["score"] for s in summaries]
    assert scores == sorted(scores, reverse=True)


def test_all_widget_summaries_includes_real_cost_alert_never_invented():
    day_summary = [{"key": "2026-08-04", "costo_usd": 5.0, "llamadas": 10}]
    summaries = widget_summary.all_widget_summaries([], day_summary, today_key="2026-08-04", now=1000.0)
    cost_entries = [s for s in summaries if s["node_id"] == "cost"]
    assert len(cost_entries) == 1
    assert "5.00" in cost_entries[0]["last_detalle"]


def test_all_widget_summaries_no_cost_alert_below_threshold():
    day_summary = [{"key": "2026-08-04", "costo_usd": 0.10, "llamadas": 1}]
    summaries = widget_summary.all_widget_summaries([], day_summary, today_key="2026-08-04", now=1000.0)
    assert not any(s["node_id"] == "cost" for s in summaries)


def test_curation_snapshot_separates_cost_alert_from_node_summaries():
    events = [_event("drive", 990.0, detalle="real")]
    day_summary = [{"key": "2026-08-04", "costo_usd": 5.0, "llamadas": 10}]
    snapshot = widget_summary.curation_snapshot(events, day_summary, today_key="2026-08-04", now=1000.0)
    assert snapshot["cost_alert"]["node_id"] == "cost"
    assert all(s["node_id"] != "cost" for s in snapshot["summaries"])
    assert any(s["node_id"] == "drive" for s in snapshot["summaries"])


def test_curation_snapshot_respects_top_n():
    events = [_event(node_id, 990.0 + i, detalle="real") for i, node_id in enumerate(relevance.DOCK_NODE_IDS[:8])]
    snapshot = widget_summary.curation_snapshot(events, [], now=1000.0, top_n=3)
    assert len(snapshot["summaries"]) <= 3


def test_curation_snapshot_recent_errors_are_real_events_only():
    events = [_event("drive", 990.0, estado="error"), _event("gmail_send", 990.0, estado="completo")]
    snapshot = widget_summary.curation_snapshot(events, [], now=1000.0)
    assert len(snapshot["recent_errors"]) == 1
    assert snapshot["recent_errors"][0]["nodo"] == "drive"


def test_curation_snapshot_empty_when_nothing_real_happened():
    snapshot = widget_summary.curation_snapshot([], [], now=1000.0)
    assert snapshot == {"summaries": [], "cost_alert": None, "recent_errors": []}


def test_curation_snapshot_default_top_n_is_four():
    # Exactamente cuántos nodos reciben un size_tier que amerita curación:
    # rank 0 = large, ranks 1-3 = medium (ver widget_templates.assign_tier).
    events = [_event(node_id, 990.0 + i, detalle="real") for i, node_id in enumerate(relevance.DOCK_NODE_IDS[:8])]
    snapshot = widget_summary.curation_snapshot(events, [], now=1000.0)
    assert len(snapshot["summaries"]) + (1 if snapshot["cost_alert"] else 0) == 4


# --- v2: histograma real de actividad + tamaño de plantilla mecánico ---


def test_recent_activity_buckets_is_all_zero_without_real_events():
    buckets = widget_summary.recent_activity_buckets("drive", [], now=1000.0)
    assert buckets == [0] * 12
    assert sum(buckets) == 0


def test_recent_activity_buckets_never_fabricates_a_point_outside_the_window():
    # Un evento real pero viejo (fuera de la ventana de 12 baldes x 60s) no
    # debe aparecer en ningún balde.
    events = [_event("drive", 1000.0 - 5000, detalle="viejo")]
    buckets = widget_summary.recent_activity_buckets("drive", events, now=1000.0, bucket_seconds=60, num_buckets=12)
    assert sum(buckets) == 0


def test_recent_activity_buckets_counts_real_events_in_chronological_order():
    now = 1000.0
    events = [
        _event("drive", now - 5, detalle="reciente"),  # último balde (edad 5s)
        _event("drive", now - 700, detalle="viejo"),  # primer balde (edad 700s, dentro de 12*60=720s)
    ]
    buckets = widget_summary.recent_activity_buckets("drive", events, now=now, bucket_seconds=60, num_buckets=12)
    assert buckets[-1] == 1  # el más reciente cae en el último balde
    assert buckets[0] == 1  # el más viejo (aún dentro de la ventana) cae en el primer balde
    assert sum(buckets) == 2


def test_recent_activity_buckets_ignores_events_from_other_nodes():
    events = [_event("gmail_send", 995.0, detalle="otro nodo")]
    buckets = widget_summary.recent_activity_buckets("drive", events, now=1000.0)
    assert sum(buckets) == 0


def test_summarize_node_includes_real_activity_buckets():
    events = [_event("drive", 995.0, detalle="real")]
    summary = widget_summary.summarize_node("drive", events, now=1000.0)
    assert summary["activity_buckets"][-1] == 1


def test_all_widget_summaries_excludes_input_channel_nodes():
    # Pedido real del fundador: input_text/input_voice/input_file son el
    # CANAL por el que llega su propio mensaje — mostrarlo de vuelta como
    # widget no aporta nada, él ya sabe qué escribió.
    events = [
        _event("input_text", 990.0, detalle="hola, esto es lo que yo escribí"),
        _event("drive", 985.0, detalle="algo real de una capacidad"),
    ]
    summaries = widget_summary.all_widget_summaries(events, [], now=1000.0)
    node_ids = {s["node_id"] for s in summaries}
    assert "input_text" not in node_ids
    assert "drive" in node_ids


def test_all_widget_summaries_assigns_size_tier_by_rank_never_by_llm():
    from snarf.telemetry import brain

    non_input_ids = [n for n in relevance.DOCK_NODE_IDS if brain.NODE_TIER.get(n) != "input"][:6]
    events = [_event(node_id, 990.0 + i, detalle="real") for i, node_id in enumerate(non_input_ids)]
    summaries = widget_summary.all_widget_summaries(events, [], now=1000.0)
    tiers = [s["size_tier"] for s in summaries]
    assert tiers[0] == "large"
    assert tiers[1:4] == ["medium", "medium", "medium"]
    assert all(t == "small" for t in tiers[4:])


def test_summarize_node_recent_items_are_real_and_most_recent_first():
    events = [
        _event("drive", 900.0, detalle="archivo A"),
        _event("drive", 950.0, detalle=None),  # sin detalle legible: nunca ocupa un lugar en la lista
        _event("drive", 990.0, detalle="archivo B"),
    ]
    summary = widget_summary.summarize_node("drive", events, now=1000.0)
    assert summary["recent_items"] == [
        {"timestamp": 990.0, "detalle": "archivo B", "preview": None},
        {"timestamp": 900.0, "detalle": "archivo A", "preview": None},
    ]


def test_summarize_node_recent_items_capped_at_five():
    events = [_event("drive", 900.0 + i, detalle=f"item {i}") for i in range(8)]
    summary = widget_summary.summarize_node("drive", events, now=1000.0)
    assert len(summary["recent_items"]) == 5
    assert summary["recent_items"][0]["detalle"] == "item 7"  # más reciente primero


# --- preview de documento (ADR 0092) ---------------------------------------


def test_summarize_node_last_preview_uses_the_most_recent_event_with_a_real_preview():
    preview_a = {"title": "Plan A", "link": "https://docs.google.com/document/d/a/edit", "snippet": None}
    preview_b = {"title": "Plan B", "link": "https://docs.google.com/document/d/b/edit", "snippet": None}
    events = [
        _event("drive", 900.0, detalle="leyendo A", preview=preview_a),
        _event("drive", 950.0, detalle="algo sin documento"),  # sin preview: no debe pisar preview_a
        _event("drive", 990.0, detalle="leyendo B", preview=preview_b),
    ]
    summary = widget_summary.summarize_node("drive", events, now=1000.0)
    assert summary["last_preview"] == preview_b


def test_summarize_node_last_preview_is_none_without_any_real_document():
    events = [_event("drive", 990.0, detalle="listando archivos, sin documento puntual")]
    summary = widget_summary.summarize_node("drive", events, now=1000.0)
    assert summary["last_preview"] is None


def test_summarize_node_recent_items_carry_their_own_preview():
    preview_a = {"title": "Plan A", "link": "https://docs.google.com/document/d/a/edit", "snippet": None}
    events = [
        _event("drive", 900.0, detalle="leyendo A", preview=preview_a),
        _event("drive", 990.0, detalle="listando archivos"),
    ]
    summary = widget_summary.summarize_node("drive", events, now=1000.0)
    assert summary["recent_items"][0]["preview"] is None
    assert summary["recent_items"][1]["preview"] == preview_a


def test_cost_alert_summary_never_has_a_document_preview():
    day_summary = [{"key": "2026-08-04", "costo_usd": 5.0, "llamadas": 10}]
    summaries = widget_summary.all_widget_summaries([], day_summary, today_key="2026-08-04", now=1000.0)
    cost_entry = next(s for s in summaries if s["node_id"] == "cost")
    assert cost_entry["last_preview"] is None


def test_cost_alert_summary_includes_a_real_multi_day_series_never_fabricated():
    day_summary = [
        {"key": "2026-08-01", "costo_usd": 0.5, "llamadas": 3},
        {"key": "2026-08-02", "costo_usd": 0.8, "llamadas": 4},
        {"key": "2026-08-03", "costo_usd": 5.0, "llamadas": 10},
    ]
    summaries = widget_summary.all_widget_summaries([], day_summary, today_key="2026-08-03", now=1000.0)
    cost_entry = next(s for s in summaries if s["node_id"] == "cost")
    assert cost_entry["cost_series"] == [0.5, 0.8, 5.0]
