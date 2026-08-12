import pytest

from snarf.executive.roles import ROLE_CONFIGS
from snarf.runtime import agent_graph_registry, llm_routing, n8n_generator, prompt_registry, tool_subset_registry


@pytest.fixture(autouse=True)
def _isolated_registries(tmp_path, monkeypatch):
    monkeypatch.setattr(prompt_registry, "PROMPTS_PATH", tmp_path / "prompts.json")
    monkeypatch.setattr(tool_subset_registry, "TOOL_SUBSETS_PATH", tmp_path / "tool_subsets.json")
    monkeypatch.setattr(agent_graph_registry, "AGENT_GRAPH_PATH", tmp_path / "agent_graph.json")
    monkeypatch.setattr(llm_routing, "ROUTING_PATH", tmp_path / "llm_routing.json")
    monkeypatch.setattr(llm_routing, "ROUTING_HISTORY_PATH", tmp_path / "llm_routing_history.json")


def test_build_without_overrides_fans_out_from_empezar_to_all_seven_roles():
    workflow = build = n8n_generator.build_executive_board_workflow("editar-prompt-id")

    info_nodes = [n for n in build["nodes"] if n["type"] == "n8n-nodes-base.noOp"]
    edit_nodes = [n for n in build["nodes"] if n["type"] == "n8n-nodes-base.executeWorkflow"]
    assert len(info_nodes) == 7
    assert len(edit_nodes) == 7
    assert {n["name"] for n in info_nodes} == {c.display_name for c in ROLE_CONFIGS.values()}

    targets = {t["node"] for t in workflow["connections"]["Empezar"]["main"][0]}
    assert targets == {c.display_name for c in ROLE_CONFIGS.values()}


def test_build_without_overrides_connects_each_role_to_its_own_edit_prompt_node():
    workflow = n8n_generator.build_executive_board_workflow("editar-prompt-id")

    cto_targets = {t["node"] for t in workflow["connections"]["CTO"]["main"][0]}
    assert cto_targets == {"Editar prompt: executive_board_cto"}
    edit_node = next(n for n in workflow["nodes"] if n["name"] == "Editar prompt: executive_board_cto")
    assert edit_node["parameters"]["workflowId"]["value"] == "editar-prompt-id"


def test_build_note_reflects_the_active_tool_subset_and_routing():
    tool_subset_registry.save_new_version("cto", ["codebase_search"], default=ROLE_CONFIGS["cto"].mcp_tool_subset)
    llm_routing.save_routing_versioned("executive_cto", provider="anthropic", model="claude-haiku-4-5")

    workflow = n8n_generator.build_executive_board_workflow("editar-prompt-id")

    cto_node = next(n for n in workflow["nodes"] if n["name"] == "CTO")
    assert "codebase_search" in cto_node["notes"]
    assert "anthropic/claude-haiku-4-5" in cto_node["notes"]


def test_build_with_stages_connects_a_stage_to_the_next_one():
    agent_graph_registry.save_new_version([["cto", "coo"], ["ceo"]])

    workflow = n8n_generator.build_executive_board_workflow("editar-prompt-id")

    # Solo la primera stage arranca desde "Empezar".
    entry_targets = {t["node"] for t in workflow["connections"]["Empezar"]["main"][0]}
    assert entry_targets == {"CTO", "COO"}
    # El ancla de la stage 1 (CTO, el primer rol de esa stage) conecta con
    # CEO además de con su propio "Editar prompt".
    cto_targets = {t["node"] for t in workflow["connections"]["CTO"]["main"][0]}
    assert cto_targets == {"Editar prompt: executive_board_cto", "CEO"}


def test_build_is_idempotent_across_two_runs_with_no_changes():
    first = n8n_generator.build_executive_board_workflow("editar-prompt-id")
    second = n8n_generator.build_executive_board_workflow("editar-prompt-id")
    assert first == second


def test_push_workflow_raises_without_an_api_key(monkeypatch):
    monkeypatch.delenv("N8N_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="N8N_API_KEY"):
        n8n_generator.push_workflow({"name": "x", "nodes": [], "connections": {}, "settings": {}}, workflow_id=None)


def test_push_workflow_posts_when_there_is_no_existing_id(monkeypatch):
    calls = []

    class _Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"id": "nuevo-id"}

    def fake_post(url, json, headers, timeout):
        calls.append(("post", url, headers))
        return _Response()

    monkeypatch.setattr(n8n_generator.requests, "post", fake_post)
    workflow_id = n8n_generator.push_workflow(
        {"name": "x", "nodes": [], "connections": {}, "settings": {}}, workflow_id=None, api_key="clave-real"
    )

    assert workflow_id == "nuevo-id"
    assert calls[0][0] == "post"
    assert calls[0][2]["X-N8N-API-KEY"] == "clave-real"


def test_push_workflow_puts_when_there_is_an_existing_id(monkeypatch):
    calls = []

    class _Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"id": "id-existente"}

    def fake_put(url, json, headers, timeout):
        calls.append(("put", url))
        return _Response()

    monkeypatch.setattr(n8n_generator.requests, "put", fake_put)
    n8n_generator.push_workflow(
        {"name": "x", "nodes": [], "connections": {}, "settings": {}}, workflow_id="id-existente", api_key="clave-real"
    )

    assert calls[0] == ("put", f"{n8n_generator.N8N_BASE_URL}/api/v1/workflows/id-existente")


def test_sync_executive_board_seeds_the_branch_id_into_ids_json(monkeypatch, tmp_path):
    ids_path = tmp_path / "ids.json"
    ids_path.write_text('{"editar_prompt": "editar-prompt-id", "branches": {}}', encoding="utf-8")
    monkeypatch.setattr(n8n_generator, "IDS_PATH", ids_path)
    monkeypatch.setattr(n8n_generator, "push_workflow", lambda workflow, workflow_id, **kw: "nuevo-branch-id")

    result = n8n_generator.sync_executive_board()

    assert result == "nuevo-branch-id"
    import json

    saved = json.loads(ids_path.read_text(encoding="utf-8"))
    assert saved["branches"]["executive_board"] == "nuevo-branch-id"


def test_sync_executive_board_rejects_when_editar_prompt_id_is_missing(monkeypatch, tmp_path):
    ids_path = tmp_path / "ids.json"
    ids_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(n8n_generator, "IDS_PATH", ids_path)

    with pytest.raises(RuntimeError, match="editar_prompt"):
        n8n_generator.sync_executive_board()
