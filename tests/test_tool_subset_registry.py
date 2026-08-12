import pytest

from snarf.mcp.tools import MCP_EXPOSED_TOOLS
from snarf.runtime import tool_subset_registry


def test_get_active_subset_returns_the_default_when_never_saved(monkeypatch, tmp_path):
    monkeypatch.setattr(tool_subset_registry, "TOOL_SUBSETS_PATH", tmp_path / "tool_subsets.json")
    default = frozenset({"get_current_datetime", "codebase_search"})
    assert tool_subset_registry.get_active_subset("cto", default) == default


def test_save_new_version_seeds_v1_with_the_default_before_activating_v2(monkeypatch, tmp_path):
    monkeypatch.setattr(tool_subset_registry, "TOOL_SUBSETS_PATH", tmp_path / "tool_subsets.json")
    default = frozenset({"get_current_datetime"})

    tool_subset_registry.save_new_version("cto", ["get_current_datetime", "codebase_search"], default=default)

    versions = tool_subset_registry.history("cto", default=default)
    assert [v["version"] for v in versions] == [1, 2]
    assert versions[0]["tools"] == ["get_current_datetime"]
    assert versions[1]["tools"] == ["codebase_search", "get_current_datetime"]
    assert versions[1]["active"] is True
    assert versions[0]["active"] is False


def test_get_active_subset_returns_the_saved_version_immediately(monkeypatch, tmp_path):
    monkeypatch.setattr(tool_subset_registry, "TOOL_SUBSETS_PATH", tmp_path / "tool_subsets.json")
    default = frozenset({"get_current_datetime"})

    tool_subset_registry.save_new_version("coo", ["project_list"], default=default)

    assert tool_subset_registry.get_active_subset("coo", default=default) == frozenset({"project_list"})


def test_save_new_version_rejects_a_tool_outside_the_general_mcp_allowlist(monkeypatch, tmp_path):
    monkeypatch.setattr(tool_subset_registry, "TOOL_SUBSETS_PATH", tmp_path / "tool_subsets.json")

    with pytest.raises(ValueError):
        tool_subset_registry.save_new_version("cto", ["tool_que_no_existe"], default=frozenset())


def test_save_new_version_accepts_any_subset_of_the_general_mcp_allowlist(monkeypatch, tmp_path):
    monkeypatch.setattr(tool_subset_registry, "TOOL_SUBSETS_PATH", tmp_path / "tool_subsets.json")

    entry = tool_subset_registry.save_new_version("cfo", list(MCP_EXPOSED_TOOLS), default=frozenset())
    assert set(entry["versions"][-1]["tools"]) == MCP_EXPOSED_TOOLS


def test_rollback_reactivates_an_older_version_without_deleting_the_newer_one(monkeypatch, tmp_path):
    monkeypatch.setattr(tool_subset_registry, "TOOL_SUBSETS_PATH", tmp_path / "tool_subsets.json")
    default = frozenset({"get_current_datetime"})

    tool_subset_registry.save_new_version("cmo", ["knowledge_search"], default=default)
    tool_subset_registry.save_new_version("cmo", ["gmail_summarize_inbox"], default=default)
    tool_subset_registry.rollback("cmo", 1, default=default)

    assert tool_subset_registry.get_active_subset("cmo", default=default) == default
    versions = tool_subset_registry.history("cmo", default=default)
    assert len(versions) == 3
    assert next(v for v in versions if v["version"] == 1)["active"] is True


def test_rollback_rejects_a_version_that_never_existed(monkeypatch, tmp_path):
    monkeypatch.setattr(tool_subset_registry, "TOOL_SUBSETS_PATH", tmp_path / "tool_subsets.json")

    with pytest.raises(ValueError):
        tool_subset_registry.rollback("creative", 99, default=frozenset())


def test_history_reports_an_implicit_v1_when_nothing_was_ever_saved(monkeypatch, tmp_path):
    monkeypatch.setattr(tool_subset_registry, "TOOL_SUBSETS_PATH", tmp_path / "tool_subsets.json")
    default = frozenset({"get_current_datetime"})

    versions = tool_subset_registry.history("research", default=default)
    assert versions == [{"version": 1, "tools": ["get_current_datetime"], "created_at": None, "active": True}]


def test_saving_a_second_role_never_touches_the_first(monkeypatch, tmp_path):
    monkeypatch.setattr(tool_subset_registry, "TOOL_SUBSETS_PATH", tmp_path / "tool_subsets.json")

    tool_subset_registry.save_new_version("cto", ["codebase_search"], default=frozenset())
    tool_subset_registry.save_new_version("coo", ["project_list"], default=frozenset())

    assert tool_subset_registry.get_active_subset("cto", default=frozenset()) == frozenset({"codebase_search"})
    assert tool_subset_registry.get_active_subset("coo", default=frozenset()) == frozenset({"project_list"})
