from snarf.executive.roles import ROLE_CONFIGS
from snarf.mcp.tools import MCP_EXPOSED_TOOLS, ROLE_TOOL_SUBSETS

EXPECTED_ROLES = {"cto", "coo", "research", "ceo", "cfo", "cmo", "creative"}


def test_role_configs_has_exactly_the_7_real_roles():
    assert set(ROLE_CONFIGS.keys()) == EXPECTED_ROLES


def test_every_role_config_key_matches_its_own_role_field():
    for key, config in ROLE_CONFIGS.items():
        assert key == config.role


def test_every_role_mcp_tool_subset_matches_the_mcp_allowlist_subset():
    # roles.py nunca duplica la lista de tools por rol — siempre reusa
    # ROLE_TOOL_SUBSETS de snarf/mcp/tools.py, una sola fuente de verdad.
    for role, config in ROLE_CONFIGS.items():
        assert config.mcp_tool_subset == ROLE_TOOL_SUBSETS[role]


def test_every_role_tool_subset_is_within_the_general_mcp_allowlist():
    for config in ROLE_CONFIGS.values():
        assert config.mcp_tool_subset.issubset(MCP_EXPOSED_TOOLS)


def test_every_role_has_a_unique_llm_routing_role():
    routing_roles = [c.llm_routing_role for c in ROLE_CONFIGS.values()]
    assert len(routing_roles) == len(set(routing_roles))
    assert all(r.startswith("executive_") for r in routing_roles)


def test_every_role_system_prompt_mentions_the_honesty_format():
    for config in ROLE_CONFIGS.values():
        assert "HEADLINE:" in config.system_prompt
        assert "BASIS:" in config.system_prompt
        assert "FUENTE:" in config.system_prompt
