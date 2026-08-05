import pytest

from snarf.core.orchestrator import Orchestrator


@pytest.fixture
def orchestrator(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return Orchestrator()


def test_skill_factory_build_requires_confirmation_first(orchestrator):
    result = orchestrator._handle_tool(
        "skill_factory_build",
        {"branch": "research", "skill_name": "x", "description": "algo"},
    )
    assert result["status"] == "pending_confirmation"
    assert result["preview"]["skill_name"] == "x"


def test_skill_factory_build_with_confirmed_calls_the_real_specialist(orchestrator, monkeypatch):
    calls = []
    monkeypatch.setattr(
        orchestrator._skill_factory,
        "build_skill",
        lambda branch, skill_name, description, clarifying_answers: calls.append(
            (branch, skill_name, description, clarifying_answers)
        )
        or {"proposal_id": "x-123", "status": "built"},
    )

    result = orchestrator._handle_tool(
        "skill_factory_build",
        {"branch": "research", "skill_name": "x", "description": "algo", "confirmed": True},
    )

    assert result == {"proposal_id": "x-123", "status": "built"}
    assert calls == [("research", "x", "algo", None)]


def test_skill_factory_activate_requires_confirmation_first(orchestrator):
    result = orchestrator._handle_tool("skill_factory_activate", {"proposal_id": "x-123"})
    assert result["status"] == "pending_confirmation"
    assert result["preview"]["proposal_id"] == "x-123"


def test_skill_factory_activate_with_confirmed_calls_the_real_specialist(orchestrator, monkeypatch):
    monkeypatch.setattr(
        orchestrator._skill_factory, "activate", lambda proposal_id: {"proposal_id": proposal_id, "status": "activated"}
    )

    result = orchestrator._handle_tool("skill_factory_activate", {"proposal_id": "x-123", "confirmed": True})

    assert result == {"proposal_id": "x-123", "status": "activated"}


def test_skill_factory_status_never_requires_confirmation(orchestrator, monkeypatch):
    monkeypatch.setattr(orchestrator._skill_factory, "status", lambda proposal_id: {"status": "built"})

    result = orchestrator._handle_tool("skill_factory_status", {"proposal_id": "x-123"})

    assert result == {"status": "built"}


def test_skill_factory_build_and_activate_are_never_exposed_via_mcp():
    from snarf.mcp.tools import MCP_EXPOSED_TOOLS

    assert "skill_factory_build" not in MCP_EXPOSED_TOOLS
    assert "skill_factory_activate" not in MCP_EXPOSED_TOOLS
