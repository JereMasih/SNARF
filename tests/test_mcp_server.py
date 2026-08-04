import asyncio

import pytest

from snarf.core.orchestrator import BULK_READ_GATED_TOOLS, HIGH_IMPACT_TOOLS, TOOLS, Orchestrator
from snarf.mcp.server import build_server
from snarf.mcp.tools import MCP_EXPOSED_TOOLS, ROLE_TOOL_SUBSETS


@pytest.fixture
def orchestrator(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return Orchestrator()


def _run(coro):
    return asyncio.run(coro)


def test_mcp_exposed_tools_all_exist_in_orchestrator_tools():
    real_names = {t["name"] for t in TOOLS}
    assert MCP_EXPOSED_TOOLS.issubset(real_names)


def test_mcp_exposed_tools_never_includes_a_gated_tool():
    assert MCP_EXPOSED_TOOLS.isdisjoint(HIGH_IMPACT_TOOLS)
    assert MCP_EXPOSED_TOOLS.isdisjoint(BULK_READ_GATED_TOOLS)


def test_every_role_tool_subset_is_a_subset_of_the_general_allowlist():
    for role, subset in ROLE_TOOL_SUBSETS.items():
        assert subset.issubset(MCP_EXPOSED_TOOLS), f"rol {role} expone un tool fuera del allowlist general"


def test_build_server_lists_exactly_the_allowlisted_tools(orchestrator):
    server = build_server(orchestrator)
    listed = {t.name for t in _run(server.list_tools())}
    assert listed == MCP_EXPOSED_TOOLS


def test_call_tool_rejects_a_tool_outside_the_allowlist_even_if_it_exists_in_orchestrator(orchestrator):
    server = build_server(orchestrator)
    # drive_delete_file es un tool real de HIGH_IMPACT_TOOLS — nunca se
    # registra en el servidor MCP, así que llamarlo tiene que fallar antes
    # de tocar Orchestrator._handle_tool (defensa en profundidad).
    with pytest.raises(Exception):
        _run(server.call_tool("drive_delete_file", {"file_id": "x"}))


def test_call_tool_result_matches_orchestrator_handle_tool_result_directly(orchestrator, monkeypatch):
    monkeypatch.setattr(orchestrator, "_handle_tool", lambda name, i: {"echo": name, "input": i})
    server = build_server(orchestrator)

    result = _run(server.call_tool("codebase_search", {"query": "orchestrator"}))

    direct = orchestrator._handle_tool("codebase_search", {"query": "orchestrator"})
    assert direct == {"echo": "codebase_search", "input": {"query": "orchestrator"}}
    assert direct["echo"] == "codebase_search"
    assert direct["input"]["query"] == "orchestrator"
    assert result.is_error is False


def test_call_tool_delegates_to_the_real_orchestrator_dispatch_never_a_second_implementation(orchestrator, monkeypatch):
    calls = []
    original = orchestrator._handle_tool

    def spy(name, i):
        calls.append((name, i))
        return original(name, i)

    monkeypatch.setattr(orchestrator, "_handle_tool", spy)
    server = build_server(orchestrator)

    _run(server.call_tool("get_current_datetime", {}))

    assert calls == [("get_current_datetime", {})]


def test_optional_parameters_not_provided_are_never_passed_to_the_orchestrator(orchestrator, monkeypatch):
    received = {}

    def fake_handle(name, i):
        received.update(i)
        return {}

    monkeypatch.setattr(orchestrator, "_handle_tool", fake_handle)
    server = build_server(orchestrator)

    _run(server.call_tool("codebase_search", {"query": "algo"}))

    assert "top_k" not in received
    assert received == {"query": "algo"}
