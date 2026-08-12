import pytest

from snarf.executive.roles import ROLE_CONFIGS
from snarf.runtime import (
    agent_change_proposals,
    agent_graph_registry,
    agent_registry,
    llm_routing,
    prompt_registry,
    tool_subset_registry,
)


@pytest.fixture(autouse=True)
def _isolated_registries(tmp_path, monkeypatch):
    monkeypatch.setattr(prompt_registry, "PROMPTS_PATH", tmp_path / "prompts.json")
    monkeypatch.setattr(tool_subset_registry, "TOOL_SUBSETS_PATH", tmp_path / "tool_subsets.json")
    monkeypatch.setattr(agent_graph_registry, "AGENT_GRAPH_PATH", tmp_path / "agent_graph.json")
    monkeypatch.setattr(llm_routing, "ROUTING_PATH", tmp_path / "llm_routing.json")
    monkeypatch.setattr(llm_routing, "ROUTING_HISTORY_PATH", tmp_path / "llm_routing_history.json")
    monkeypatch.setattr(agent_change_proposals, "PENDING_PATH", tmp_path / "n8n_pending_changes.json")


def test_propose_never_applies_anything():
    config = ROLE_CONFIGS["cto"]
    result = agent_change_proposals.propose("cto", {"prompt_text": "prompt nuevo"})

    assert result["diff"]["prompt_text"] == {"before": config.system_prompt, "after": "prompt nuevo"}
    # El estado activo real todavía no cambió.
    assert agent_registry.get_agent_recipe("cto")["prompt"]["active_text"] == config.system_prompt


def test_propose_rejects_an_unknown_field():
    with pytest.raises(ValueError):
        agent_change_proposals.propose("cto", {"campo_inventado": "x"})


def test_propose_rejects_an_empty_payload():
    with pytest.raises(ValueError):
        agent_change_proposals.propose("cto", {})


def test_propose_rejects_an_unknown_agent_id():
    with pytest.raises(ValueError):
        agent_change_proposals.propose("agente_inventado", {"prompt_text": "x"})


def test_apply_writes_every_proposed_field_to_the_real_registries():
    proposal = agent_change_proposals.propose(
        "coo",
        {
            "prompt_text": "prompt editado",
            "tools": ["project_list"],
            "routing": {"provider": "anthropic", "model": "claude-haiku-4-5"},
            "stages": [["coo"], ["ceo"]],
        },
    )

    recipe = agent_change_proposals.apply(proposal["change_id"])

    assert recipe["prompt"]["active_text"] == "prompt editado"
    assert recipe["tools"]["active"] == ["project_list"]
    assert recipe["routing"]["active"] == {"provider": "anthropic", "model": "claude-haiku-4-5"}
    assert recipe["stages"]["active"] == [["coo"], ["ceo"]]


def test_apply_removes_the_pending_change_once_applied():
    proposal = agent_change_proposals.propose("cfo", {"prompt_text": "x"})
    agent_change_proposals.apply(proposal["change_id"])

    with pytest.raises(ValueError, match="no existe o ya expiró"):
        agent_change_proposals.apply(proposal["change_id"])


def test_apply_rejects_an_unknown_change_id():
    with pytest.raises(ValueError, match="no existe o ya expiró"):
        agent_change_proposals.apply("no-existe")


def test_apply_rejects_an_expired_change(monkeypatch):
    monkeypatch.setattr(agent_change_proposals, "TTL_SECONDS", -1)
    proposal = agent_change_proposals.propose("cmo", {"prompt_text": "x"})

    with pytest.raises(ValueError, match="no existe o ya expiró"):
        agent_change_proposals.apply(proposal["change_id"])


def test_apply_rejects_a_stale_change_when_the_state_moved_since_propose():
    config = ROLE_CONFIGS["creative"]
    proposal = agent_change_proposals.propose("creative", {"prompt_text": "propuesta vieja"})
    # Alguien más (el cockpit del founder, u otra propuesta ya confirmada)
    # cambió el prompt real de este rol después del propose.
    prompt_registry.save_new_version("executive_board_creative", "cambio en el medio", config.system_prompt)

    with pytest.raises(agent_change_proposals.StaleChangeError):
        agent_change_proposals.apply(proposal["change_id"])


def test_apply_only_touches_fields_that_were_actually_proposed():
    config = ROLE_CONFIGS["research"]
    proposal = agent_change_proposals.propose("research", {"prompt_text": "solo el prompt"})

    recipe = agent_change_proposals.apply(proposal["change_id"])

    assert recipe["prompt"]["active_text"] == "solo el prompt"
    assert set(recipe["tools"]["active"]) == set(config.mcp_tool_subset)
