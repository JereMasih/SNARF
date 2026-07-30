from snarf.runtime import personality_prefs


def test_load_prefs_returns_default_when_no_file_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(personality_prefs, "PREFS_DIR", tmp_path)
    prefs = personality_prefs.load_prefs("someone")
    assert prefs["sarcasm_level"] == 7.5


def test_save_and_load_prefs_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(personality_prefs, "PREFS_DIR", tmp_path)
    saved = personality_prefs.save_prefs("fundador", {"sarcasm_level": 3})
    assert saved["sarcasm_level"] == 3.0

    loaded = personality_prefs.load_prefs("fundador")
    assert loaded == saved


def test_save_prefs_rounds_to_nearest_half_point(tmp_path, monkeypatch):
    monkeypatch.setattr(personality_prefs, "PREFS_DIR", tmp_path)
    saved = personality_prefs.save_prefs("fundador", {"sarcasm_level": 6.7})
    assert saved["sarcasm_level"] == 6.5


def test_save_prefs_clamps_out_of_range_to_default(tmp_path, monkeypatch):
    monkeypatch.setattr(personality_prefs, "PREFS_DIR", tmp_path)
    saved = personality_prefs.save_prefs("fundador", {"sarcasm_level": 999})
    assert saved["sarcasm_level"] == personality_prefs.DEFAULT_SARCASM_LEVEL

    saved_negative = personality_prefs.save_prefs("fundador", {"sarcasm_level": -1})
    assert saved_negative["sarcasm_level"] == personality_prefs.DEFAULT_SARCASM_LEVEL


def test_save_prefs_rejects_non_numeric_and_bool(tmp_path, monkeypatch):
    # bool es subclase de int en Python — mismo gotcha ya documentado en
    # dashboard_prefs.py.
    monkeypatch.setattr(personality_prefs, "PREFS_DIR", tmp_path)
    saved_str = personality_prefs.save_prefs("fundador", {"sarcasm_level": "mucho"})
    assert saved_str["sarcasm_level"] == personality_prefs.DEFAULT_SARCASM_LEVEL

    saved_bool = personality_prefs.save_prefs("fundador", {"sarcasm_level": True})
    assert saved_bool["sarcasm_level"] == personality_prefs.DEFAULT_SARCASM_LEVEL


def test_prefs_are_isolated_per_user(tmp_path, monkeypatch):
    monkeypatch.setattr(personality_prefs, "PREFS_DIR", tmp_path)
    personality_prefs.save_prefs("fundador", {"sarcasm_level": 0})
    other = personality_prefs.load_prefs("otro_usuario")
    assert other["sarcasm_level"] == 7.5
