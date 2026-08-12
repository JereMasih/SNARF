import pytest

from snarf.executive.roles import ROLE_CONFIGS
from snarf.runtime import agent_graph_registry


def test_get_active_stages_defaults_to_a_single_stage_with_every_role(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_graph_registry, "AGENT_GRAPH_PATH", tmp_path / "agent_graph.json")
    stages = agent_graph_registry.get_active_stages()
    assert len(stages) == 1
    assert set(stages[0]) == set(ROLE_CONFIGS)


def test_save_new_version_seeds_v1_with_the_default_fan_out_before_activating_v2(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_graph_registry, "AGENT_GRAPH_PATH", tmp_path / "agent_graph.json")

    agent_graph_registry.save_new_version([["cto", "coo"], ["ceo"]])

    versions = agent_graph_registry.history()
    assert [v["version"] for v in versions] == [1, 2]
    assert set(versions[0]["stages"][0]) == set(ROLE_CONFIGS)
    assert versions[1]["stages"] == [["cto", "coo"], ["ceo"]]
    assert versions[1]["active"] is True


def test_get_active_stages_returns_the_saved_version_immediately(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_graph_registry, "AGENT_GRAPH_PATH", tmp_path / "agent_graph.json")

    agent_graph_registry.save_new_version([["cto"], ["coo", "ceo"]])

    assert agent_graph_registry.get_active_stages() == [["cto"], ["coo", "ceo"]]


def test_save_new_version_rejects_an_unknown_role(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_graph_registry, "AGENT_GRAPH_PATH", tmp_path / "agent_graph.json")

    with pytest.raises(ValueError):
        agent_graph_registry.save_new_version([["rol_inventado"]])


def test_save_new_version_rejects_a_role_repeated_across_stages(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_graph_registry, "AGENT_GRAPH_PATH", tmp_path / "agent_graph.json")

    with pytest.raises(ValueError):
        agent_graph_registry.save_new_version([["cto"], ["cto"]])


def test_save_new_version_rejects_an_empty_stage(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_graph_registry, "AGENT_GRAPH_PATH", tmp_path / "agent_graph.json")

    with pytest.raises(ValueError):
        agent_graph_registry.save_new_version([["cto"], []])


def test_rollback_reactivates_an_older_version_without_deleting_the_newer_one(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_graph_registry, "AGENT_GRAPH_PATH", tmp_path / "agent_graph.json")

    agent_graph_registry.save_new_version([["cto"], ["coo"]])
    agent_graph_registry.save_new_version([["cfo"], ["cmo"]])
    agent_graph_registry.rollback("executive_board", 2)

    assert agent_graph_registry.get_active_stages() == [["cto"], ["coo"]]
    versions = agent_graph_registry.history()
    assert len(versions) == 3


def test_rollback_rejects_a_version_that_never_existed(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_graph_registry, "AGENT_GRAPH_PATH", tmp_path / "agent_graph.json")

    with pytest.raises(ValueError):
        agent_graph_registry.rollback("executive_board", 99)
