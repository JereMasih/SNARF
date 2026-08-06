from snarf.telemetry import context


def test_llm_role_is_none_before_anything_sets_it():
    context.clear_llm_role()
    assert context.get_llm_role() is None


def test_set_llm_role_is_visible_via_get_llm_role():
    context.set_llm_role("orchestrator")
    try:
        assert context.get_llm_role() == "orchestrator"
    finally:
        context.clear_llm_role()


def test_clear_llm_role_resets_to_none():
    context.set_llm_role("gmail_digest")
    context.clear_llm_role()
    assert context.get_llm_role() is None
