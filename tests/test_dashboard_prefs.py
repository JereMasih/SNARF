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


# --- Vista HUD del dashboard (rediseño radial) — campos aditivos, nunca
# tocan visible_widgets/panel_order/widget_options de arriba. La Vista
# clásica tiene que seguir comportándose exactamente igual (ver tests de
# arriba, ninguno se tocó) para que el toggle sea reversible de verdad. ---


def test_default_dashboard_view_is_classic(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard_prefs, "PREFS_DIR", tmp_path)
    prefs = dashboard_prefs.load_prefs("fundador")
    assert prefs["dashboard_view"] == "classic"


def test_save_prefs_accepts_hud_dashboard_view(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard_prefs, "PREFS_DIR", tmp_path)
    saved = dashboard_prefs.save_prefs("fundador", {"dashboard_view": "hud"})
    assert saved["dashboard_view"] == "hud"
    # Persiste de verdad, no solo en memoria (a diferencia del toggle
    # efímero del panel Cerebro).
    assert dashboard_prefs.load_prefs("fundador")["dashboard_view"] == "hud"


def test_save_prefs_rejects_invalid_dashboard_view(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard_prefs, "PREFS_DIR", tmp_path)
    saved = dashboard_prefs.save_prefs("fundador", {"dashboard_view": "trading_view"})
    assert saved["dashboard_view"] == "classic"


def test_default_hud_widget_state_covers_every_real_node_as_auto(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard_prefs, "PREFS_DIR", tmp_path)
    prefs = dashboard_prefs.load_prefs("fundador")
    assert set(prefs["hud_widget_state"].keys()) == set(dashboard_prefs.HUD_NODE_IDS)
    assert all(state == "auto" for state in prefs["hud_widget_state"].values())


def test_save_prefs_accepts_valid_hud_widget_state(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard_prefs, "PREFS_DIR", tmp_path)
    saved = dashboard_prefs.save_prefs(
        "fundador", {"hud_widget_state": {"drive": "pinned", "gmail_send": "hidden"}}
    )
    assert saved["hud_widget_state"]["drive"] == "pinned"
    assert saved["hud_widget_state"]["gmail_send"] == "hidden"
    assert saved["hud_widget_state"]["memory"] == "auto"


def test_save_prefs_rejects_invalid_hud_widget_state_value(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard_prefs, "PREFS_DIR", tmp_path)
    saved = dashboard_prefs.save_prefs("fundador", {"hud_widget_state": {"drive": "always_on_top"}})
    assert saved["hud_widget_state"]["drive"] == "auto"


def test_save_prefs_ignores_unknown_node_id_in_hud_widget_state(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard_prefs, "PREFS_DIR", tmp_path)
    saved = dashboard_prefs.save_prefs("fundador", {"hud_widget_state": {"trading": "pinned"}})
    assert "trading" not in saved["hud_widget_state"]


def test_save_prefs_accepts_valid_hud_widget_options(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard_prefs, "PREFS_DIR", tmp_path)
    saved = dashboard_prefs.save_prefs(
        "fundador", {"hud_widget_options": {"drive": {"angle": 45, "radius": 220}}}
    )
    assert saved["hud_widget_options"]["drive"] == {"angle": 45.0, "radius": 220.0}


def test_save_prefs_rejects_hud_widget_options_for_unknown_node(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard_prefs, "PREFS_DIR", tmp_path)
    saved = dashboard_prefs.save_prefs("fundador", {"hud_widget_options": {"trading": {"angle": 1, "radius": 1}}})
    assert "trading" not in saved["hud_widget_options"]


def test_save_prefs_rejects_non_numeric_and_bool_hud_widget_options(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard_prefs, "PREFS_DIR", tmp_path)
    saved = dashboard_prefs.save_prefs(
        "fundador", {"hud_widget_options": {"drive": {"angle": "north", "radius": True}}}
    )
    assert "drive" not in saved["hud_widget_options"]


def test_hud_node_ids_is_the_real_relevance_dock_node_ids(tmp_path, monkeypatch):
    # HUD_NODE_IDS tiene que ser el mismo objeto/fuente que
    # relevance.DOCK_NODE_IDS (= todos los nodos reales de brain.NODE_TIER),
    # no una copia hardcodeada que pueda quedar desalineada.
    from snarf.telemetry import relevance

    assert dashboard_prefs.HUD_NODE_IDS == relevance.DOCK_NODE_IDS


def test_classic_view_fields_unaffected_by_hud_prefs(tmp_path, monkeypatch):
    # El toggle tiene que ser reversible de verdad: guardar preferencias de
    # Vista HUD nunca debe tocar visible_widgets/panel_order/widget_options.
    monkeypatch.setattr(dashboard_prefs, "PREFS_DIR", tmp_path)
    baseline = dashboard_prefs.load_prefs("fundador")
    dashboard_prefs.save_prefs(
        "fundador",
        {
            "dashboard_view": "hud",
            "hud_widget_state": {"drive": "hidden"},
            "hud_widget_options": {"drive": {"angle": 10, "radius": 100}},
            "hud_chat_position": "right",
            "hud_sidebar_pinned": True,
        },
    )
    after = dashboard_prefs.load_prefs("fundador")
    assert after["visible_widgets"] == baseline["visible_widgets"]
    assert after["panel_order"] == baseline["panel_order"]
    assert after["widget_options"] == baseline["widget_options"]


# --- v2 del rediseño HUD: posición del chat + pin del drawer lateral ---


def test_default_hud_chat_position_is_left(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard_prefs, "PREFS_DIR", tmp_path)
    prefs = dashboard_prefs.load_prefs("fundador")
    assert prefs["hud_chat_position"] == "left"


def test_save_prefs_accepts_valid_hud_chat_position(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard_prefs, "PREFS_DIR", tmp_path)
    for position in ("left", "center", "right"):
        saved = dashboard_prefs.save_prefs("fundador", {"hud_chat_position": position})
        assert saved["hud_chat_position"] == position


def test_save_prefs_rejects_invalid_hud_chat_position(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard_prefs, "PREFS_DIR", tmp_path)
    saved = dashboard_prefs.save_prefs("fundador", {"hud_chat_position": "top"})
    assert saved["hud_chat_position"] == "left"


def test_default_hud_sidebar_pinned_is_false(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard_prefs, "PREFS_DIR", tmp_path)
    prefs = dashboard_prefs.load_prefs("fundador")
    assert prefs["hud_sidebar_pinned"] is False


def test_save_prefs_accepts_hud_sidebar_pinned_true(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard_prefs, "PREFS_DIR", tmp_path)
    saved = dashboard_prefs.save_prefs("fundador", {"hud_sidebar_pinned": True})
    assert saved["hud_sidebar_pinned"] is True
    assert dashboard_prefs.load_prefs("fundador")["hud_sidebar_pinned"] is True


def test_save_prefs_rejects_non_bool_hud_sidebar_pinned(tmp_path, monkeypatch):
    # bool es subclase de int en Python — sin este chequeo, {"hud_sidebar_pinned": 1}
    # pasaría en silencio como True.
    monkeypatch.setattr(dashboard_prefs, "PREFS_DIR", tmp_path)
    saved = dashboard_prefs.save_prefs("fundador", {"hud_sidebar_pinned": 1})
    assert saved["hud_sidebar_pinned"] is False
