from snarf.telemetry import relevance

NOW = 1785589200.0


def _event(nodo, timestamp, estado="completo"):
    return {"nodo": nodo, "timestamp": timestamp, "estado": estado}


def test_node_with_recent_activity_outranks_a_ghost_node():
    events = [_event("drive", NOW - 60)]
    result = relevance.rank_nodes(events, ["drive", "gmail_read"], now=NOW)
    assert result[0]["nodo"] == "drive"
    assert result[1]["nodo"] == "gmail_read"
    assert result[1]["score"] == 0
    assert "sin_actividad" in result[1]["razones"]


def test_more_recent_activity_scores_higher_than_older_activity():
    events = [_event("drive", NOW - 3500), _event("gmail_read", NOW - 60)]
    result = relevance.rank_nodes(events, ["drive", "gmail_read"], now=NOW)
    assert result[0]["nodo"] == "gmail_read"


def test_frequency_within_window_increases_score_but_is_capped():
    few = [_event("drive", NOW - 60)]
    many = [_event("drive", NOW - 60 - i) for i in range(20)]
    score_few = relevance.rank_nodes(few, ["drive"], now=NOW)[0]["score"]
    score_many = relevance.rank_nodes(many, ["drive"], now=NOW)[0]["score"]
    assert score_many > score_few
    # el cap evita que un nodo ruidoso escale sin límite
    capped_extra = [_event("drive", NOW - 60 - i) for i in range(100)]
    score_capped = relevance.rank_nodes(capped_extra, ["drive"], now=NOW)[0]["score"]
    assert score_capped == score_many


def test_recent_error_boosts_score_as_an_alert():
    events = [_event("drive", NOW - 60, estado="error")]
    result = relevance.rank_nodes(events, ["drive", "gmail_read"], now=NOW)
    assert result[0]["nodo"] == "drive"
    assert "error_reciente" in result[0]["razones"]


def test_activity_outside_the_window_does_not_count_as_recent():
    events = [_event("drive", NOW - 7200)]  # 2h, fuera de la ventana de 1h
    result = relevance.rank_nodes(events, ["drive"], now=NOW)
    assert result[0]["eventos_recientes"] == 0
    assert result[0]["score"] == 0


def test_cost_alert_is_none_below_threshold():
    day_summary = [{"key": "2026-08-03", "costo_usd": 0.30, "llamadas": 5}]
    assert relevance.cost_alert(day_summary, threshold_usd=1.0, today_key="2026-08-03") is None


def test_cost_alert_fires_at_or_above_threshold():
    day_summary = [{"key": "2026-08-03", "costo_usd": 1.20, "llamadas": 10}]
    alert = relevance.cost_alert(day_summary, threshold_usd=1.0, today_key="2026-08-03")
    assert alert is not None
    assert alert["nodo"] == "cost"
    assert alert["costo_usd"] == 1.20
    assert "gasto_del_dia_sobre_umbral" in alert["razones"]


def test_cost_alert_with_no_data_is_none():
    assert relevance.cost_alert([], today_key="2026-08-03") is None


def test_dock_priority_puts_cost_alert_first_when_threshold_crossed():
    events = [_event("drive", NOW - 60), _event("gmail_read", NOW - 30)]
    day_summary = [{"key": "2026-08-03", "costo_usd": 5.0, "llamadas": 40}]
    result = relevance.dock_priority(events, ["drive", "gmail_read"], day_summary, today_key="2026-08-03", now=NOW)
    assert result[0]["nodo"] == "cost"
    assert result[0]["score"] == relevance.COST_ALERT_SCORE


def test_dock_priority_without_cost_alert_ranks_only_real_nodes():
    events = [_event("drive", NOW - 60)]
    day_summary = [{"key": "2026-08-03", "costo_usd": 0.10, "llamadas": 2}]
    result = relevance.dock_priority(events, ["drive", "gmail_read"], day_summary, today_key="2026-08-03", now=NOW)
    assert [r["nodo"] for r in result] == ["drive", "gmail_read"]
