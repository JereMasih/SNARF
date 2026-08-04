from snarf.telemetry import cost_history

# 2026-08-01 10:00 y 2026-08-02 10:00, America/Argentina/Buenos_Aires (UTC-3)
TS_DAY_1 = 1785589200.0
TS_DAY_2 = 1785675600.0


def _event(**overrides):
    base = {
        "timestamp": TS_DAY_1,
        "nodo": "drive",
        "agente": "capability",
        "skill": "drive_list_files",
        "modelo": None,
        "tokens_in": None,
        "tokens_out": None,
        "costo_usd": None,
        "latencia_ms": None,
        "estado": "completo",
        "conversation_id": None,
    }
    base.update(overrides)
    return base


def test_by_day_groups_by_calendar_day_in_founder_timezone():
    events = [
        _event(timestamp=TS_DAY_1, costo_usd=0.01),
        _event(timestamp=TS_DAY_1, costo_usd=0.02),
        _event(timestamp=TS_DAY_2, costo_usd=0.05),
    ]
    result = cost_history.by_day(events)
    assert [b["key"] for b in result] == ["2026-08-01", "2026-08-02"]
    assert result[0]["costo_usd"] == 0.03
    assert result[0]["llamadas"] == 2
    assert result[1]["costo_usd"] == 0.05


def test_by_agente_sums_cost_and_tokens_per_agente():
    events = [
        _event(agente="capability", costo_usd=0.01, tokens_in=100, tokens_out=50),
        _event(agente="capability", costo_usd=0.02, tokens_in=200, tokens_out=80),
        _event(agente="specialist", costo_usd=0.10, tokens_in=10, tokens_out=5),
    ]
    result = cost_history.by_agente(events)
    assert result[0]["key"] == "specialist"  # ordenado por costo desc
    assert result[0]["costo_usd"] == 0.10
    capability = next(b for b in result if b["key"] == "capability")
    assert capability["costo_usd"] == 0.03
    assert capability["tokens_in"] == 300
    assert capability["tokens_out"] == 130


def test_by_session_excludes_events_without_conversation_id():
    events = [
        _event(conversation_id="c1", costo_usd=0.01),
        _event(conversation_id="c1", costo_usd=0.02),
        _event(conversation_id=None, costo_usd=0.5),  # digest en background, sin sesión real
    ]
    result = cost_history.by_session(events)
    assert len(result) == 1
    assert result[0]["key"] == "c1"
    assert result[0]["costo_usd"] == 0.03


def test_unknown_cost_is_never_treated_as_zero():
    events = [
        _event(costo_usd=None),
        _event(costo_usd=0.02),
    ]
    result = cost_history.by_day(events)
    assert result[0]["costo_usd"] == 0.02
    assert result[0]["llamadas_sin_costo_estimado"] == 1
    assert result[0]["llamadas"] == 2


def test_errores_counted_per_bucket():
    events = [
        _event(estado="error"),
        _event(estado="completo"),
    ]
    result = cost_history.by_day(events)
    assert result[0]["errores"] == 1
    assert result[0]["llamadas"] == 2


def test_summary_returns_all_three_breakdowns():
    events = [_event(conversation_id="c1")]
    result = cost_history.summary(events)
    assert set(result.keys()) == {"by_day", "by_agente", "by_session"}


def test_empty_events_return_empty_breakdowns():
    assert cost_history.summary([]) == {"by_day": [], "by_agente": [], "by_session": []}
