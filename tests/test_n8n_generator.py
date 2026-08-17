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


_AGENT_EDIT_IDS = {role: f"edit-id-{role}" for role in ROLE_CONFIGS}


def test_build_without_overrides_fans_out_from_empezar_to_all_seven_roles():
    workflow = build = n8n_generator.build_executive_board_workflow(_AGENT_EDIT_IDS)

    info_nodes = [n for n in build["nodes"] if n["type"] == "n8n-nodes-base.noOp"]
    edit_nodes = [n for n in build["nodes"] if n["type"] == "n8n-nodes-base.executeWorkflow"]
    assert len(info_nodes) == 7
    assert len(edit_nodes) == 7
    assert {n["name"] for n in info_nodes} == {c.display_name for c in ROLE_CONFIGS.values()}

    targets = {t["node"] for t in workflow["connections"]["Empezar"]["main"][0]}
    assert targets == {c.display_name for c in ROLE_CONFIGS.values()}


def test_build_without_overrides_connects_each_role_to_its_own_edit_workflow():
    workflow = n8n_generator.build_executive_board_workflow(_AGENT_EDIT_IDS)

    cto_targets = {t["node"] for t in workflow["connections"]["CTO"]["main"][0]}
    assert cto_targets == {"Editar CTO"}
    edit_node = next(n for n in workflow["nodes"] if n["name"] == "Editar CTO")
    assert edit_node["parameters"]["workflowId"]["value"] == "edit-id-cto"


def test_build_note_reflects_the_active_tool_subset_and_routing():
    tool_subset_registry.save_new_version("cto", ["codebase_search"], default=ROLE_CONFIGS["cto"].mcp_tool_subset)
    llm_routing.save_routing_versioned("executive_cto", provider="anthropic", model="claude-haiku-4-5")

    workflow = n8n_generator.build_executive_board_workflow(_AGENT_EDIT_IDS)

    cto_node = next(n for n in workflow["nodes"] if n["name"] == "CTO")
    assert "codebase_search" in cto_node["notes"]
    assert "anthropic/claude-haiku-4-5" in cto_node["notes"]


def test_build_with_stages_connects_a_stage_to_the_next_one():
    agent_graph_registry.save_new_version([["cto", "coo"], ["ceo"]])

    workflow = n8n_generator.build_executive_board_workflow(_AGENT_EDIT_IDS)

    # Solo la primera stage arranca desde "Empezar".
    entry_targets = {t["node"] for t in workflow["connections"]["Empezar"]["main"][0]}
    assert entry_targets == {"CTO", "COO"}
    # El ancla de la stage 1 (CTO, el primer rol de esa stage) conecta con
    # CEO además de con su propio editor dedicado.
    cto_targets = {t["node"] for t in workflow["connections"]["CTO"]["main"][0]}
    assert cto_targets == {"Editar CTO", "CEO"}


def test_build_is_idempotent_across_two_runs_with_no_changes():
    first = n8n_generator.build_executive_board_workflow(_AGENT_EDIT_IDS)
    second = n8n_generator.build_executive_board_workflow(_AGENT_EDIT_IDS)
    assert first == second


def test_build_agent_edit_workflow_has_the_manual_trigger_set_propose_apply_chain():
    workflow = n8n_generator.build_agent_edit_workflow("cto")

    assert workflow["name"] == "Snarf - Editar CTO"
    node_types = [n["type"] for n in workflow["nodes"]]
    assert node_types == [
        "n8n-nodes-base.manualTrigger",
        "n8n-nodes-base.set",
        "n8n-nodes-base.httpRequest",
        "n8n-nodes-base.httpRequest",
    ]
    # Encadenado sin bifurcaciones: trigger -> set -> proponer -> aplicar.
    assert workflow["connections"]["▶ Ejecutar (Test workflow)"]["main"][0][0]["node"] == "CTO"
    assert workflow["connections"]["CTO"]["main"][0][0]["node"] == "Proponer"
    assert workflow["connections"]["Proponer"]["main"][0][0]["node"] == "Aplicar"


def test_build_agent_edit_workflow_bakes_in_the_active_prompt_and_tools():
    tool_subset_registry.save_new_version("cto", ["codebase_search"], default=ROLE_CONFIGS["cto"].mcp_tool_subset)

    workflow = n8n_generator.build_agent_edit_workflow("cto")

    set_node = next(n for n in workflow["nodes"] if n["type"] == "n8n-nodes-base.set")
    assignments = {a["name"]: a["value"] for a in set_node["parameters"]["assignments"]["assignments"]}
    assert assignments["agent_id"] == "cto"
    assert assignments["tool_codebase_search"] is True
    assert assignments["tool_knowledge_search"] is False


def test_build_agent_edit_workflow_is_idempotent_across_two_runs_with_no_changes():
    first = n8n_generator.build_agent_edit_workflow("cto")
    second = n8n_generator.build_agent_edit_workflow("cto")
    assert first == second


def test_sync_agent_edit_workflows_seeds_all_seven_ids_into_ids_json(monkeypatch, tmp_path):
    ids_path = tmp_path / "ids.json"
    ids_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(n8n_generator, "IDS_PATH", ids_path)
    pushed = []

    def fake_push(workflow, workflow_id, **kw):
        pushed.append(workflow["name"])
        return f"id-for-{workflow['name']}"

    monkeypatch.setattr(n8n_generator, "push_workflow", fake_push)

    result = n8n_generator.sync_agent_edit_workflows()

    assert set(result) == set(ROLE_CONFIGS)
    assert len(pushed) == 7
    import json

    saved = json.loads(ids_path.read_text(encoding="utf-8"))
    assert saved["agent_edit"] == result


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
    import json

    ids_path = tmp_path / "ids.json"
    ids_path.write_text(json.dumps({"agent_edit": _AGENT_EDIT_IDS, "branches": {}}), encoding="utf-8")
    monkeypatch.setattr(n8n_generator, "IDS_PATH", ids_path)
    monkeypatch.setattr(n8n_generator, "push_workflow", lambda workflow, workflow_id, **kw: "nuevo-branch-id")

    result = n8n_generator.sync_executive_board()

    assert result == "nuevo-branch-id"
    import json

    saved = json.loads(ids_path.read_text(encoding="utf-8"))
    assert saved["branches"]["executive_board"] == "nuevo-branch-id"


def test_sync_executive_board_rejects_when_agent_edit_ids_are_missing(monkeypatch, tmp_path):
    ids_path = tmp_path / "ids.json"
    ids_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(n8n_generator, "IDS_PATH", ids_path)

    with pytest.raises(RuntimeError, match="agent_edit"):
        n8n_generator.sync_executive_board()


# --- Fase 24 del plan de observabilidad/n8n (ADR 0166): canvas en vivo ----


def test_build_live_turn_workflow_has_trigger_capture_respond_and_stage_chain():
    workflow = n8n_generator.build_live_turn_workflow()

    assert workflow["name"] == "Snarf - Turno en vivo"
    types_in_order = [n["type"] for n in workflow["nodes"]]
    assert types_in_order[:3] == [
        "n8n-nodes-base.webhook", "n8n-nodes-base.code", "n8n-nodes-base.respondToWebhook",
    ]
    wait_nodes = [n for n in workflow["nodes"] if n["type"] == "n8n-nodes-base.wait"]
    assert len(wait_nodes) == n8n_generator.LIVE_TURN_STAGE_COUNT
    assert [n["name"] for n in wait_nodes] == [f"Etapa {i + 1}" for i in range(n8n_generator.LIVE_TURN_STAGE_COUNT)]


def test_build_live_turn_workflow_chains_every_node_in_sequence():
    workflow = n8n_generator.build_live_turn_workflow()
    connections = workflow["connections"]

    assert connections["Webhook"]["main"][0][0]["node"] == "CapturarExecutionId"
    assert connections["CapturarExecutionId"]["main"][0][0]["node"] == "DevolverExecutionId"
    assert connections["DevolverExecutionId"]["main"][0][0]["node"] == "Etapa 1"
    for i in range(1, n8n_generator.LIVE_TURN_STAGE_COUNT):
        assert connections[f"Etapa {i}"]["main"][0][0]["node"] == f"Etapa {i + 1}"
    # La última etapa no dispara nada más — el turno termina ahí.
    assert f"Etapa {n8n_generator.LIVE_TURN_STAGE_COUNT}" not in connections


def test_build_live_turn_workflow_nodes_have_stable_webhook_ids_and_a_real_timeout():
    workflow = n8n_generator.build_live_turn_workflow()

    trigger = next(n for n in workflow["nodes"] if n["type"] == "n8n-nodes-base.webhook")
    assert trigger.get("webhookId")
    assert trigger["parameters"]["responseMode"] == "responseNode"
    assert trigger["parameters"]["path"] == n8n_generator.LIVE_TURN_WEBHOOK_PATH

    for wait_node in [n for n in workflow["nodes"] if n["type"] == "n8n-nodes-base.wait"]:
        assert wait_node.get("webhookId")
        assert wait_node["parameters"]["resume"] == "webhook"
        assert wait_node["parameters"]["httpMethod"] == "POST"
        assert wait_node["parameters"]["limitWaitTime"] is True
        assert wait_node["parameters"]["resumeAmount"] == n8n_generator.LIVE_TURN_STAGE_TIMEOUT_MINUTES


def test_build_live_turn_workflow_is_idempotent_across_two_runs_with_no_changes():
    first = n8n_generator.build_live_turn_workflow()
    second = n8n_generator.build_live_turn_workflow()
    assert first == second


def test_sync_live_turn_workflow_seeds_the_id_into_ids_json_and_cycles_activation(monkeypatch, tmp_path):
    ids_path = tmp_path / "ids.json"
    ids_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(n8n_generator, "IDS_PATH", ids_path)
    monkeypatch.setattr(n8n_generator, "push_workflow", lambda workflow, workflow_id, **kw: "nuevo-live-id")
    calls = []

    class _Response:
        def raise_for_status(self):
            pass

    def fake_post(url, headers, timeout):
        calls.append(url)
        return _Response()

    monkeypatch.setattr(n8n_generator.requests, "post", fake_post)

    result = n8n_generator.sync_live_turn_workflow(api_key="clave-real")

    assert result == "nuevo-live-id"
    import json

    saved = json.loads(ids_path.read_text(encoding="utf-8"))
    assert saved["live_turn"] == "nuevo-live-id"
    assert calls == [
        f"{n8n_generator.N8N_BASE_URL}/api/v1/workflows/nuevo-live-id/deactivate",
        f"{n8n_generator.N8N_BASE_URL}/api/v1/workflows/nuevo-live-id/activate",
    ]


def test_sync_live_turn_workflow_raises_without_an_api_key(monkeypatch, tmp_path):
    monkeypatch.delenv("N8N_API_KEY", raising=False)
    monkeypatch.setattr(n8n_generator, "IDS_PATH", tmp_path / "ids.json")

    with pytest.raises(RuntimeError, match="N8N_API_KEY"):
        n8n_generator.sync_live_turn_workflow()
