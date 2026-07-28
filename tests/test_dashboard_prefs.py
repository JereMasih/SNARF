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
