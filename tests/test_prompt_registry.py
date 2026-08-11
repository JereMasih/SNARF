import pytest

from snarf.runtime import prompt_registry


def test_get_active_text_returns_the_default_when_never_saved(monkeypatch, tmp_path):
    monkeypatch.setattr(prompt_registry, "PROMPTS_PATH", tmp_path / "prompts.json")
    assert prompt_registry.get_active_text("gmail_digest", "texto original") == "texto original"


def test_save_new_version_seeds_v1_with_the_default_before_activating_v2(monkeypatch, tmp_path):
    monkeypatch.setattr(prompt_registry, "PROMPTS_PATH", tmp_path / "prompts.json")

    prompt_registry.save_new_version("gmail_digest", "texto editado", default="texto original")

    versions = prompt_registry.history("gmail_digest", default="texto original")
    assert [v["version"] for v in versions] == [1, 2]
    assert versions[0]["text"] == "texto original"
    assert versions[1]["text"] == "texto editado"
    assert versions[1]["active"] is True
    assert versions[0]["active"] is False


def test_get_active_text_returns_the_saved_version_immediately_no_restart_needed(monkeypatch, tmp_path):
    monkeypatch.setattr(prompt_registry, "PROMPTS_PATH", tmp_path / "prompts.json")

    prompt_registry.save_new_version("client_status", "nuevo texto real", default="default viejo")

    assert prompt_registry.get_active_text("client_status", default="default viejo") == "nuevo texto real"


def test_rollback_reactivates_an_older_version_without_deleting_the_newer_one(monkeypatch, tmp_path):
    monkeypatch.setattr(prompt_registry, "PROMPTS_PATH", tmp_path / "prompts.json")

    prompt_registry.save_new_version("books_categorize", "v2 real", default="v1 real")
    prompt_registry.save_new_version("books_categorize", "v3 real", default="v1 real")
    prompt_registry.rollback("books_categorize", 1, default="v1 real")

    assert prompt_registry.get_active_text("books_categorize", default="v1 real") == "v1 real"
    versions = prompt_registry.history("books_categorize", default="v1 real")
    assert len(versions) == 3
    assert next(v for v in versions if v["version"] == 1)["active"] is True


def test_rollback_rejects_a_version_that_never_existed(monkeypatch, tmp_path):
    monkeypatch.setattr(prompt_registry, "PROMPTS_PATH", tmp_path / "prompts.json")

    with pytest.raises(ValueError):
        prompt_registry.rollback("sponsor_inbox_triage", 99, default="lo que sea")


def test_history_reports_an_implicit_v1_when_nothing_was_ever_saved(monkeypatch, tmp_path):
    monkeypatch.setattr(prompt_registry, "PROMPTS_PATH", tmp_path / "prompts.json")

    versions = prompt_registry.history("calendar_brief", default="el default real")
    assert versions == [{"version": 1, "text": "el default real", "created_at": None, "active": True}]


def test_saving_a_second_prompt_never_touches_the_first(monkeypatch, tmp_path):
    monkeypatch.setattr(prompt_registry, "PROMPTS_PATH", tmp_path / "prompts.json")

    prompt_registry.save_new_version("gmail_digest", "editado", default="default a")
    prompt_registry.save_new_version("calendar_brief", "otro editado", default="default b")

    assert prompt_registry.get_active_text("gmail_digest", default="default a") == "editado"
    assert prompt_registry.get_active_text("calendar_brief", default="default b") == "otro editado"
