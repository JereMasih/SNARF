from snarf.telemetry import context


def test_get_conversation_id_is_none_by_default():
    context.clear_conversation_id()
    assert context.get_conversation_id() is None


def test_set_and_get_conversation_id_roundtrip():
    context.set_conversation_id("conv-123")
    assert context.get_conversation_id() == "conv-123"
    context.clear_conversation_id()
    assert context.get_conversation_id() is None


# --- Fase 22 del plan de observabilidad/n8n (ADR 0165) ------------------


def test_get_board_consulted_is_false_by_default():
    context.clear_board_consulted()
    assert context.get_board_consulted() is False


def test_set_and_get_board_consulted_roundtrip():
    context.set_board_consulted(True)
    assert context.get_board_consulted() is True
    context.clear_board_consulted()
    assert context.get_board_consulted() is False


# --- Fase 1 del plan de observabilidad ---------------------------------


def test_scoped_llm_role_restores_the_outer_role_on_exit():
    context.set_llm_role("orchestrator")
    try:
        with context.scoped_llm_role("gmail_digest"):
            assert context.get_llm_role() == "gmail_digest"
        assert context.get_llm_role() == "orchestrator"
    finally:
        context.clear_llm_role()


def test_scoped_llm_role_restores_none_when_nothing_was_set_before():
    context.clear_llm_role()
    with context.scoped_llm_role("gmail_digest"):
        assert context.get_llm_role() == "gmail_digest"
    assert context.get_llm_role() is None


def test_span_makes_event_id_the_parent_and_restores_previous_on_exit():
    assert context.get_current_span_id() is None
    with context.span("root-span", trace_id="trace-1"):
        assert context.get_current_span_id() == "root-span"
        assert context.get_trace_id() == "trace-1"
        with context.span("child-span"):
            assert context.get_current_span_id() == "child-span"
            # Sin trace_id explícito, un span hijo hereda la traza ambiente.
            assert context.get_trace_id() == "trace-1"
        assert context.get_current_span_id() == "root-span"
        assert context.get_trace_id() == "trace-1"
    assert context.get_current_span_id() is None
    assert context.get_trace_id() is None


def test_new_id_returns_distinct_values():
    assert context.new_id() != context.new_id()


def test_env_for_child_process_is_empty_without_an_active_trace():
    assert context.get_trace_id() is None
    assert context.env_for_child_process() == {}


def test_env_for_child_process_carries_trace_and_parent_when_active():
    with context.span("event-123", trace_id="trace-456"):
        env = context.env_for_child_process()
    assert env == {context.TRACE_ENV_VAR: "trace-456", context.PARENT_ENV_VAR: "event-123"}


def test_adopt_from_env_seeds_trace_and_parent_from_a_dict():
    context.adopt_from_env({context.TRACE_ENV_VAR: "trace-789", context.PARENT_ENV_VAR: "event-999"})
    try:
        assert context.get_trace_id() == "trace-789"
        assert context.get_current_span_id() == "event-999"
    finally:
        context._trace_id.set(None)
        context._span_id.set(None)


def test_adopt_from_env_never_invents_a_trace_when_absent():
    context.adopt_from_env({})
    assert context.get_trace_id() is None
    assert context.get_current_span_id() is None


def test_two_asyncio_tasks_on_one_loop_keep_independent_conversation_ids():
    """threading.local() (versión pre-Fase-1) comparte un único slot entre
    corutinas de un mismo loop de eventos — contextvars.ContextVar da a
    cada Task su propio valor aislado, que es justo el caso real de los
    asyncio.create_task de background en app.py."""
    import asyncio

    results = {}

    async def _run(name, delay):
        context.set_conversation_id(name)
        await asyncio.sleep(delay)
        results[name] = context.get_conversation_id()

    async def _main():
        await asyncio.gather(_run("conv-A", 0.01), _run("conv-B", 0.0))

    asyncio.run(_main())
    assert results == {"conv-A": "conv-A", "conv-B": "conv-B"}


def test_copy_context_run_in_a_threadpool_preserves_trace_and_span():
    import contextvars
    from concurrent.futures import ThreadPoolExecutor

    def _read_current():
        return context.get_current_span_id(), context.get_trace_id()

    with context.span("parent-event", trace_id="trace-xyz"):
        ctx = contextvars.copy_context()
        with ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(ctx.run, _read_current).result()

    assert result == ("parent-event", "trace-xyz")
