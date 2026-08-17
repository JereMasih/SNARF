from snarf.core.orchestrator import TOOLS
from snarf.runtime import areas


def test_area_for_tool_covers_exactly_the_expected_fourteen_tools():
    # Regresión: si se agrega/saca una tool de área sin actualizar la
    # tabla, este test lo detecta en vez de dejarla ruteando mal en
    # silencio (mismo patrón que tests/test_brain.py con TOOL_TO_NODE).
    expected = {
        "agency_client_status", "calendar_brief", "morning_routine", "sales_sponsor_inbox_triage",
        "finance_books_categorize", "finance_monthly_pnl",
        "research_deep_dive", "research_trend_scan", "research_competitor_watch",
        "content_write_blog_post", "content_write_social_post", "content_write_newsletter",
        "community_pulse", "community_post_message",
    }
    assert set(areas.TOOL_TO_AREA.keys()) == expected


def test_area_for_tool_returns_the_right_area_for_each_domain():
    assert areas.area_for_tool("finance_monthly_pnl") == "administracion"
    assert areas.area_for_tool("research_deep_dive") == "i_d"
    assert areas.area_for_tool("content_write_blog_post") == "marketing"
    assert areas.area_for_tool("community_pulse") == "marketing"
    assert areas.area_for_tool("agency_client_status") == "operaciones"
    assert areas.area_for_tool("calendar_brief") == "operaciones"
    assert areas.area_for_tool("morning_routine") == "operaciones"
    assert areas.area_for_tool("sales_sponsor_inbox_triage") == "operaciones"


def test_area_for_tool_returns_none_outside_the_four_areas():
    assert areas.area_for_tool("executive_board_consult") is None
    assert areas.area_for_tool("codebase_search") is None
    assert areas.area_for_tool("not_a_real_tool") is None


def test_every_area_value_has_a_display_name():
    assert set(areas.TOOL_TO_AREA.values()) <= set(areas.AREA_DISPLAY_NAMES.keys())


def test_area_tools_are_a_subset_of_real_orchestrator_tools():
    real_tool_names = {tool["name"] for tool in TOOLS}
    assert set(areas.TOOL_TO_AREA.keys()) <= real_tool_names
