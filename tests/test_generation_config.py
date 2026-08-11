import pytest

from snarf.runtime import generation_config

_DEFAULT = {"max_output_tokens": 16000, "temperature": None, "timeout_seconds": None, "max_continuations": 2}


def test_get_active_config_returns_the_default_when_never_saved(monkeypatch, tmp_path):
    monkeypatch.setattr(generation_config, "GENERATION_CONFIG_PATH", tmp_path / "generation_config.json")
    assert generation_config.get_active_config("orchestrator", _DEFAULT) == _DEFAULT


def test_save_new_version_seeds_v1_with_the_default_before_activating_v2(monkeypatch, tmp_path):
    monkeypatch.setattr(generation_config, "GENERATION_CONFIG_PATH", tmp_path / "generation_config.json")

    generation_config.save_new_version("orchestrator", {"max_output_tokens": 8000}, default=_DEFAULT)

    versions = generation_config.history("orchestrator", default=_DEFAULT)
    assert [v["version"] for v in versions] == [1, 2]
    assert versions[0]["max_output_tokens"] == 16000
    assert versions[1]["max_output_tokens"] == 8000
    assert versions[1]["active"] is True


def test_a_partial_override_never_resets_the_other_fields(monkeypatch, tmp_path):
    monkeypatch.setattr(generation_config, "GENERATION_CONFIG_PATH", tmp_path / "generation_config.json")

    generation_config.save_new_version("gmail_digest", {"max_output_tokens": 4000}, default=_DEFAULT)
    generation_config.save_new_version("gmail_digest", {"temperature": 0.7}, default=_DEFAULT)

    active = generation_config.get_active_config("gmail_digest", default=_DEFAULT)
    assert active["max_output_tokens"] == 4000
    assert active["temperature"] == 0.7
    assert active["max_continuations"] == 2


def test_rollback_reactivates_an_older_version_without_deleting_the_newer_one(monkeypatch, tmp_path):
    monkeypatch.setattr(generation_config, "GENERATION_CONFIG_PATH", tmp_path / "generation_config.json")

    generation_config.save_new_version("client_status", {"temperature": 0.2}, default=_DEFAULT)
    generation_config.save_new_version("client_status", {"temperature": 0.9}, default=_DEFAULT)
    generation_config.rollback("client_status", 1, default=_DEFAULT)

    active = generation_config.get_active_config("client_status", default=_DEFAULT)
    assert active == _DEFAULT
    assert len(generation_config.history("client_status", default=_DEFAULT)) == 3


def test_rollback_rejects_a_version_that_never_existed(monkeypatch, tmp_path):
    monkeypatch.setattr(generation_config, "GENERATION_CONFIG_PATH", tmp_path / "generation_config.json")

    with pytest.raises(ValueError):
        generation_config.rollback("books_categorize", 99, default=_DEFAULT)


def test_history_reports_an_implicit_v1_when_nothing_was_ever_saved(monkeypatch, tmp_path):
    monkeypatch.setattr(generation_config, "GENERATION_CONFIG_PATH", tmp_path / "generation_config.json")

    versions = generation_config.history("calendar_brief", default=_DEFAULT)
    assert len(versions) == 1
    assert versions[0]["active"] is True
    assert versions[0]["created_at"] is None
    assert {k: versions[0][k] for k in generation_config.FIELDS} == _DEFAULT


def test_saving_a_second_role_never_touches_the_first(monkeypatch, tmp_path):
    monkeypatch.setattr(generation_config, "GENERATION_CONFIG_PATH", tmp_path / "generation_config.json")

    generation_config.save_new_version("gmail_digest", {"max_output_tokens": 1000}, default=_DEFAULT)
    generation_config.save_new_version("calendar_brief", {"max_output_tokens": 2000}, default=_DEFAULT)

    assert generation_config.get_active_config("gmail_digest", default=_DEFAULT)["max_output_tokens"] == 1000
    assert generation_config.get_active_config("calendar_brief", default=_DEFAULT)["max_output_tokens"] == 2000
