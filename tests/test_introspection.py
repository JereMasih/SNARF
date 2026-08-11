from snarf.core.orchestrator import HIGH_IMPACT_TOOLS, TOOLS
from snarf.executive.roles import ROLE_CONFIGS
from snarf.mcp.tools import MCP_EXPOSED_TOOLS
from snarf.runtime import introspection, llm_routing


def test_agents_snapshot_reports_the_real_routed_model_per_role(monkeypatch, tmp_path):
    monkeypatch.setattr(llm_routing, "ROUTING_PATH", tmp_path / "llm_routing.json")
    llm_routing.save_routing({"orchestrator": {"provider": "anthropic", "model": "claude-sonnet-5"}})

    agents = introspection.agents_snapshot()

    assert {a["role"] for a in agents} == set(llm_routing.ROLES)
    orchestrator_entry = next(a for a in agents if a["role"] == "orchestrator")
    assert orchestrator_entry["provider"] == "anthropic"
    assert orchestrator_entry["model"] == "claude-sonnet-5"


def test_agents_snapshot_tags_executive_board_roles(monkeypatch, tmp_path):
    monkeypatch.setattr(llm_routing, "ROUTING_PATH", tmp_path / "llm_routing.json")

    agents = introspection.agents_snapshot()

    cto_entry = next(a for a in agents if a["role"] == "executive_cto")
    assert cto_entry["executive_board_role"] == "cto"
    orchestrator_entry = next(a for a in agents if a["role"] == "orchestrator")
    assert orchestrator_entry["executive_board_role"] is None


def test_tools_snapshot_never_exposes_a_high_impact_tool():
    names = {t["name"] for t in introspection.tools_snapshot()}
    assert names.isdisjoint(HIGH_IMPACT_TOOLS)


def test_tools_snapshot_only_contains_names_from_the_mcp_allowlist():
    names = {t["name"] for t in introspection.tools_snapshot()}
    assert names <= MCP_EXPOSED_TOOLS


def test_tools_snapshot_returns_the_real_description_from_orchestrator_tools():
    tools_by_name = {t["name"]: t for t in TOOLS}
    snapshot = introspection.tools_snapshot()
    assert len(snapshot) > 0
    for entry in snapshot:
        assert entry["description"] == tools_by_name[entry["name"]]["description"]


def test_executive_board_snapshot_lists_all_seven_real_roles():
    board = introspection.executive_board_snapshot()
    assert {b["role"] for b in board} == set(ROLE_CONFIGS.keys())
    assert len(board) == 7


def test_system_snapshot_combines_agents_tools_board_and_active_sessions(monkeypatch, tmp_path):
    monkeypatch.setattr(llm_routing, "ROUTING_PATH", tmp_path / "llm_routing.json")

    snapshot = introspection.system_snapshot(active_user_sessions=3)

    assert snapshot["active_user_sessions"] == 3
    assert len(snapshot["agents"]) == len(llm_routing.ROLES)
    assert len(snapshot["executive_board"]) == 7
    assert isinstance(snapshot["tools"], list)
