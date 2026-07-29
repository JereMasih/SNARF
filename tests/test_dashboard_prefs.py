from snarf.runtime import dashboard_prefs


def test_load_prefs_returns_defaults_when_no_file_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard_prefs, "PREFS_DIR", tmp_path)
    prefs = dashboard_prefs.load_prefs("someone")
    assert prefs["panel_order"] == dashboard_prefs.WIDGET_IDS
    assert all(prefs["visible_widgets"][w] is True for w in dashboard_prefs.WIDGET_IDS)


def test_save_and_load_prefs_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard_prefs, "PREFS_DIR", tmp_path)
    saved = dashboard_prefs.save_prefs(
        "fundador",
        {"visible_widgets": {"drive": False}, "panel_order": ["gmail", "system"]},
    )
    assert saved["visible_widgets"]["drive"] is False
    assert saved["visible_widgets"]["gmail"] is True

    loaded = dashboard_prefs.load_prefs("fundador")
    assert loaded == saved


def test_save_prefs_ignores_unknown_widget_ids(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard_prefs, "PREFS_DIR", tmp_path)
    saved = dashboard_prefs.save_prefs(
        "fundador",
        {"visible_widgets": {"trading": True}, "panel_order": ["trading", "system"]},
    )
    assert "trading" not in saved["visible_widgets"]
    assert "trading" not in saved["panel_order"]
    assert saved["panel_order"][0] == "system"


def test_save_prefs_fills_missing_ids_in_panel_order(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard_prefs, "PREFS_DIR", tmp_path)
    saved = dashboard_prefs.save_prefs("fundador", {"panel_order": ["youtube"]})
    assert saved["panel_order"][0] == "youtube"
    assert set(saved["panel_order"]) == set(dashboard_prefs.WIDGET_IDS)


def test_prefs_are_isolated_per_user(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard_prefs, "PREFS_DIR", tmp_path)
    dashboard_prefs.save_prefs("fundador", {"visible_widgets": {"drive": False}})
    other = dashboard_prefs.load_prefs("otro_usuario")
    assert other["visible_widgets"]["drive"] is True


def test_default_prefs_have_gmail_max_results(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard_prefs, "PREFS_DIR", tmp_path)
    prefs = dashboard_prefs.load_prefs("fundador")
    assert prefs["widget_options"]["gmail"]["max_results"] == 5


def test_save_prefs_accepts_valid_gmail_max_results(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard_prefs, "PREFS_DIR", tmp_path)
    saved = dashboard_prefs.save_prefs("fundador", {"widget_options": {"gmail": {"max_results": 20}}})
    assert saved["widget_options"]["gmail"]["max_results"] == 20


def test_save_prefs_rejects_invalid_gmail_max_results(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard_prefs, "PREFS_DIR", tmp_path)
    saved = dashboard_prefs.save_prefs("fundador", {"widget_options": {"gmail": {"max_results": 999}}})
    assert saved["widget_options"]["gmail"]["max_results"] == 5


def test_chat_and_history_are_always_visible_by_default(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard_prefs, "PREFS_DIR", tmp_path)
    prefs = dashboard_prefs.load_prefs("fundador")
    assert "chat" in dashboard_prefs.WIDGET_IDS
    assert "history" in dashboard_prefs.WIDGET_IDS
    assert prefs["visible_widgets"]["chat"] is True
    assert prefs["visible_widgets"]["history"] is True


def test_visible_widgets_cannot_hide_chat_or_history(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard_prefs, "PREFS_DIR", tmp_path)
    saved = dashboard_prefs.save_prefs(
        "fundador", {"visible_widgets": {"chat": False, "history": False}}
    )
    assert saved["visible_widgets"]["chat"] is True
    assert saved["visible_widgets"]["history"] is True


def test_default_prefs_include_span_for_every_widget(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard_prefs, "PREFS_DIR", tmp_path)
    prefs = dashboard_prefs.load_prefs("fundador")
    for widget_id in dashboard_prefs.WIDGET_IDS:
        options = prefs["widget_options"][widget_id]
        assert dashboard_prefs.MIN_COL_SPAN <= options["col_span"] <= dashboard_prefs.MAX_COL_SPAN
        assert dashboard_prefs.MIN_ROW_SPAN <= options["row_span"] <= dashboard_prefs.MAX_ROW_SPAN


def test_save_prefs_accepts_valid_span(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard_prefs, "PREFS_DIR", tmp_path)
    saved = dashboard_prefs.save_prefs(
        "fundador", {"widget_options": {"memory": {"col_span": 5, "row_span": 12}}}
    )
    assert saved["widget_options"]["memory"] == {"col_span": 5, "row_span": 12}


def test_save_prefs_clamps_out_of_range_span(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard_prefs, "PREFS_DIR", tmp_path)
    saved = dashboard_prefs.save_prefs(
        "fundador", {"widget_options": {"memory": {"col_span": 999, "row_span": -3}}}
    )
    assert saved["widget_options"]["memory"] == dashboard_prefs.DEFAULT_SPANS["memory"]


def test_save_prefs_rejects_non_integer_and_bool_span(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard_prefs, "PREFS_DIR", tmp_path)
    saved = dashboard_prefs.save_prefs(
        "fundador", {"widget_options": {"memory": {"col_span": "wide", "row_span": True}}}
    )
    assert saved["widget_options"]["memory"] == dashboard_prefs.DEFAULT_SPANS["memory"]


def test_save_prefs_preserves_gmail_max_results_alongside_span(tmp_path, monkeypatch):
    # Regresión del bug real: _normalize() reconstruía widget_options a mano,
    # hardcodeado solo a la clave "gmail" — cualquier otro widget se perdía
    # en silencio. Ahora gmail conserva su max_results Y otro widget conserva
    # su span, guardados en la misma llamada.
    monkeypatch.setattr(dashboard_prefs, "PREFS_DIR", tmp_path)
    saved = dashboard_prefs.save_prefs(
        "fundador",
        {"widget_options": {
            "gmail": {"max_results": 20, "col_span": 5, "row_span": 9},
            "drive": {"col_span": 6, "row_span": 10},
        }},
    )
    assert saved["widget_options"]["gmail"]["max_results"] == 20
    assert saved["widget_options"]["gmail"]["col_span"] == 5
    assert saved["widget_options"]["gmail"]["row_span"] == 9
    assert saved["widget_options"]["drive"] == {"col_span": 6, "row_span": 10}
