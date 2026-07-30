from snarf.runtime import user_profile


def test_load_profile_returns_default_when_no_file_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(user_profile, "PREFS_DIR", tmp_path)
    profile = user_profile.load_profile("someone")
    assert profile["name"] is None


def test_save_and_load_profile_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(user_profile, "PREFS_DIR", tmp_path)
    saved = user_profile.save_profile("fundador", {"name": "Jere"})
    assert saved["name"] == "Jere"

    loaded = user_profile.load_profile("fundador")
    assert loaded == saved


def test_save_profile_strips_whitespace(tmp_path, monkeypatch):
    monkeypatch.setattr(user_profile, "PREFS_DIR", tmp_path)
    saved = user_profile.save_profile("fundador", {"name": "  Jere  "})
    assert saved["name"] == "Jere"


def test_save_profile_treats_blank_string_as_no_name(tmp_path, monkeypatch):
    monkeypatch.setattr(user_profile, "PREFS_DIR", tmp_path)
    saved = user_profile.save_profile("fundador", {"name": "   "})
    assert saved["name"] is None


def test_save_profile_rejects_non_string_names(tmp_path, monkeypatch):
    monkeypatch.setattr(user_profile, "PREFS_DIR", tmp_path)
    saved = user_profile.save_profile("fundador", {"name": 12345})
    assert saved["name"] is None


def test_save_profile_truncates_an_unreasonably_long_name(tmp_path, monkeypatch):
    monkeypatch.setattr(user_profile, "PREFS_DIR", tmp_path)
    saved = user_profile.save_profile("fundador", {"name": "a" * 500})
    assert len(saved["name"]) == user_profile.NAME_MAX_LENGTH


def test_profile_is_isolated_per_user(tmp_path, monkeypatch):
    monkeypatch.setattr(user_profile, "PREFS_DIR", tmp_path)
    user_profile.save_profile("fundador", {"name": "Jere"})
    other = user_profile.load_profile("otro_usuario")
    assert other["name"] is None
