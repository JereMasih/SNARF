import pytest

from snarf.executive.roles import ROLE_CONFIGS
from snarf.runtime import agent_graph_registry, agent_registry, llm_routing, prompt_registry, tool_subset_registry


@pytest.fixture(autouse=True)
def _isolated_registries(tmp_path, monkeypatch):
    monkeypatch.setattr(prompt_registry, "PROMPTS_PATH", tmp_path / "prompts.json")
    monkeypatch.setattr(tool_subset_registry, "TOOL_SUBSETS_PATH", tmp_path / "tool_subsets.json")
    monkeypatch.setattr(agent_graph_registry, "AGENT_GRAPH_PATH", tmp_path / "agent_graph.json")
    monkeypatch.setattr(llm_routing, "ROUTING_PATH", tmp_path / "llm_routing.json")
    monkeypatch.setattr(llm_routing, "ROUTING_HISTORY_PATH", tmp_path / "llm_routing_history.json")


def test_get_agent_recipe_with_no_overrides_matches_the_hardcoded_defaults():
    recipe = agent_registry.get_agent_recipe("cto")
    config = ROLE_CONFIGS["cto"]

    assert recipe["agent_id"] == "cto"
    assert recipe["prompt"]["active_text"] == config.system_prompt
    assert set(recipe["tools"]["active"]) == set(config.mcp_tool_subset)
    assert recipe["routing"]["active"] == llm_routing.DEFAULT_ROUTING[config.llm_routing_role]
    assert len(recipe["stages"]["active"]) == 1
    assert set(recipe["stages"]["active"][0]) == set(ROLE_CONFIGS)


def test_get_agent_recipe_accepts_the_executive_board_prefixed_form():
    assert agent_registry.get_agent_recipe("executive_board_ceo")["agent_id"] == "ceo"


def test_get_agent_recipe_reflects_overrides_from_all_four_registries():
    config = ROLE_CONFIGS["coo"]
    prompt_registry.save_new_version("executive_board_coo", "prompt editado", default=config.system_prompt)
    tool_subset_registry.save_new_version("coo", ["project_list"], default=config.mcp_tool_subset)
    llm_routing.save_routing_versioned(config.llm_routing_role, provider="anthropic", model="claude-haiku-4-5")
    agent_graph_registry.save_new_version([["coo"], ["ceo"]])

    recipe = agent_registry.get_agent_recipe("coo")

    assert recipe["prompt"]["active_text"] == "prompt editado"
    assert recipe["tools"]["active"] == ["project_list"]
    assert recipe["routing"]["active"] == {"provider": "anthropic", "model": "claude-haiku-4-5"}
    assert recipe["stages"]["active"] == [["coo"], ["ceo"]]


def test_get_agent_recipe_rejects_an_unknown_agent_id():
    with pytest.raises(ValueError):
        agent_registry.get_agent_recipe("agente_inventado")
