import pytest

from snarf.capabilities.anthropic_llm import LLMResponse
from snarf.core.orchestrator import HISTORY_REPLAY_MAX_CHARS, Orchestrator, _capped_for_replay
from snarf.knowledge.extraction import ExtractionResult


@pytest.fixture
def orchestrator(tmp_path, monkeypatch):
    # Aísla la memoria episódica del proyecto real: cada test corre en su
    # propio directorio temporal, nunca escribe en data/episodic_memory.jsonl.
    monkeypatch.chdir(tmp_path)
    return Orchestrator()


def test_echo_mode_without_api_key_and_persists_to_memory(orchestrator):
    response = orchestrator.handle("text", "hola snarf", conversation_id="c1")
    assert "hola snarf" in response.text
    assert "modo eco" in response.text
    assert orchestrator.memory.get_conversation("c1")[0]["response"] == response.text


def test_handle_stores_the_input_audio_id_on_the_memory_entry(orchestrator):
    orchestrator.handle("voice", "hola snarf", conversation_id="c1", input_audio_id="abc123.webm")
    assert orchestrator.memory.get_conversation("c1")[0]["input_audio_id"] == "abc123.webm"


def test_handle_stores_the_llm_speech_field_on_the_memory_entry(orchestrator, monkeypatch):
    monkeypatch.setattr(orchestrator._llm, "_client", object())  # available=True
    monkeypatch.setattr(
        orchestrator._llm,
        "generate",
        lambda **kwargs: LLMResponse(text="respuesta completa con detalle", speech="versión hablada corta"),
    )
    result = orchestrator.handle("text", "hola", conversation_id="c1")
    assert result.speech == "versión hablada corta"
    entry = orchestrator.memory.get_conversation("c1")[0]
    assert entry["response"] == "respuesta completa con detalle"
    assert entry["speech"] == "versión hablada corta"


def test_generate_conversation_title_persists_a_short_title(orchestrator, monkeypatch):
    orchestrator.handle("text", "necesito un plan para mi marca de Instagram", conversation_id="c1")
    monkeypatch.setattr(orchestrator._title_llm, "_client", object())  # available=True
    monkeypatch.setattr(
        orchestrator._title_llm, "generate", lambda **kwargs: LLMResponse(text="Plan de marca en Instagram", speech="")
    )
    orchestrator.generate_conversation_title("c1")
    assert orchestrator.memory.get_title("c1") == "Plan de marca en Instagram"


def test_generate_conversation_title_strips_quotes_and_trailing_period(orchestrator, monkeypatch):
    orchestrator.handle("text", "hola", conversation_id="c1")
    monkeypatch.setattr(orchestrator._title_llm, "_client", object())  # available=True
    monkeypatch.setattr(orchestrator._title_llm, "generate", lambda **kwargs: LLMResponse(text='"Saludo inicial."', speech=""))
    orchestrator.generate_conversation_title("c1")
    assert orchestrator.memory.get_title("c1") == "Saludo inicial"


def test_generate_conversation_title_does_nothing_when_the_cheap_llm_is_unavailable(orchestrator):
    orchestrator.handle("text", "hola", conversation_id="c1")
    orchestrator.generate_conversation_title("c1")  # _title_llm sin API key en este fixture
    assert orchestrator.memory.get_title("c1") is None


def test_generate_conversation_title_degrades_gracefully_when_the_llm_call_fails(orchestrator, monkeypatch):
    orchestrator.handle("text", "hola", conversation_id="c1")
    monkeypatch.setattr(orchestrator._title_llm, "_client", object())  # available=True

    def boom(**kwargs):
        raise RuntimeError("rate limit")

    monkeypatch.setattr(orchestrator._title_llm, "generate", boom)
    orchestrator.generate_conversation_title("c1")  # nunca debe romper
    assert orchestrator.memory.get_title("c1") is None


def test_generate_conversation_title_does_nothing_for_a_conversation_with_no_entries(orchestrator):
    orchestrator.generate_conversation_title("conversacion-inexistente")
    assert orchestrator.memory.get_title("conversacion-inexistente") is None


def test_handle_stores_the_deliverable_field_on_the_memory_entry_when_present(orchestrator, monkeypatch):
    monkeypatch.setattr(orchestrator._llm, "_client", object())  # available=True
    monkeypatch.setattr(
        orchestrator._llm,
        "generate",
        lambda **kwargs: LLMResponse(text="acá tenés el plan", speech="te armé el plan", deliverable="solo el plan, sin charla"),
    )
    result = orchestrator.handle("text", "haceme un plan", conversation_id="c1")
    assert result.deliverable == "solo el plan, sin charla"
    entry = orchestrator.memory.get_conversation("c1")[0]
    assert entry["deliverable"] == "solo el plan, sin charla"


def test_handle_leaves_deliverable_as_none_for_purely_conversational_responses(orchestrator, monkeypatch):
    monkeypatch.setattr(orchestrator._llm, "_client", object())  # available=True
    monkeypatch.setattr(
        orchestrator._llm, "generate", lambda **kwargs: LLMResponse(text="hola, todo bien", speech="hola, todo bien")
    )
    result = orchestrator.handle("text", "hola", conversation_id="c1")
    assert result.deliverable is None
    entry = orchestrator.memory.get_conversation("c1")[0]
    assert entry["deliverable"] is None


def test_handle_degrades_gracefully_when_the_llm_call_fails(orchestrator, monkeypatch):
    # Regresión: un fallo real del LLM (crédito agotado, rate limit, red)
    # tiraba un 500 crudo hasta /send en vez de degradar como /transcribe.
    monkeypatch.setattr(orchestrator._llm, "_client", object())  # available=True

    def boom(**kwargs):
        raise RuntimeError("Your credit balance is too low")

    monkeypatch.setattr(orchestrator._llm, "generate", boom)
    response = orchestrator.handle("text", "hola snarf", conversation_id="c1")
    assert "error real del LLM" in response.text
    assert "credit balance" in response.text
    assert orchestrator.memory.get_conversation("c1")[0]["response"] == response.text


def test_handle_injects_project_prompt_as_additional_system_context(orchestrator, monkeypatch):
    # Proyectos Mark II: la asociación conversación→proyecto es persistente
    # (assign_conversation), ya no un parámetro por mensaje.
    monkeypatch.setattr(orchestrator._llm, "_client", object())  # available=True
    captured = {}

    def fake_generate(system, messages, tools=None, tool_handler=None):
        captured["system"] = system
        return LLMResponse(text="respuesta", speech="respuesta")

    monkeypatch.setattr(orchestrator._llm, "generate", fake_generate)
    monkeypatch.setattr(
        orchestrator._projects, "get", lambda pid: {"id": pid, "name": "Newsletter", "prompt": "sos el asistente de este proyecto"}
    )
    orchestrator._memory.assign_conversation("c1", "proj-1")
    orchestrator.handle("text", "hola", conversation_id="c1")
    assert "Newsletter" in captured["system"]
    assert "sos el asistente de este proyecto" in captured["system"]


def test_handle_with_a_missing_project_degrades_gracefully(orchestrator, monkeypatch):
    monkeypatch.setattr(orchestrator._llm, "_client", object())
    monkeypatch.setattr(orchestrator._llm, "generate", lambda **kwargs: LLMResponse(text="respuesta", speech="respuesta"))
    monkeypatch.setattr(orchestrator._projects, "get", lambda pid: None)  # proyecto borrado/inexistente
    orchestrator._memory.assign_conversation("c1", "no-existe")
    response = orchestrator.handle("text", "hola", conversation_id="c1")
    assert response.text == "respuesta"


def test_handle_persists_project_id_on_the_memory_entry(orchestrator):
    orchestrator._memory.assign_conversation("c1", "proj-1")
    orchestrator.handle("text", "hola", conversation_id="c1")
    entry = orchestrator.memory.get_conversation("c1")[0]
    assert entry["project_id"] == "proj-1"


def test_handle_without_project_id_never_touches_projects(orchestrator):
    calls = []
    orchestrator._projects.get = lambda pid: calls.append(pid)
    orchestrator.handle("text", "hola", conversation_id="c1")
    assert calls == []


def test_reassigning_a_conversation_changes_the_prompt_used_going_forward_only(orchestrator, monkeypatch):
    # Confirmado con el fundador: reasignar A->B nunca reescribe el system
    # prompt de turnos ya generados — solo cambia el turno que viene después.
    monkeypatch.setattr(orchestrator._llm, "_client", object())
    captured = []
    monkeypatch.setattr(
        orchestrator._llm,
        "generate",
        lambda system, messages, tools=None, tool_handler=None: captured.append(system) or LLMResponse(text="ok", speech="ok"),
    )
    monkeypatch.setattr(
        orchestrator._projects,
        "get",
        lambda pid: {"id": pid, "name": pid, "prompt": f"instrucciones de {pid}"},
    )

    orchestrator._memory.assign_conversation("c1", "proj-a")
    orchestrator.handle("text", "primero", conversation_id="c1")
    orchestrator._memory.assign_conversation("c1", "proj-b")
    orchestrator.handle("text", "segundo", conversation_id="c1")

    assert "instrucciones de proj-a" in captured[0]
    assert "instrucciones de proj-b" not in captured[0]
    assert "instrucciones de proj-b" in captured[1]


def test_handle_unassigned_conversation_uses_no_project_prompt(orchestrator, monkeypatch):
    monkeypatch.setattr(orchestrator._llm, "_client", object())
    captured = {}
    monkeypatch.setattr(
        orchestrator._llm,
        "generate",
        lambda system, messages, tools=None, tool_handler=None: captured.update(system=system) or LLMResponse(text="ok", speech="ok"),
    )
    orchestrator._memory.assign_conversation("c1", "proj-1")
    orchestrator._memory.unassign_conversation("c1")
    orchestrator.handle("text", "hola", conversation_id="c1")
    assert "Estás trabajando dentro del proyecto" not in captured["system"]


def test_project_assign_unassign_and_list_conversations_tools(orchestrator):
    result = orchestrator._handle_tool(
        "project_assign_conversation", {"project_id": "proj-1", "conversation_id": "c1"}
    )
    assert result == {"conversation_id": "c1", "from_project_id": None, "to_project_id": "proj-1"}

    listed = orchestrator._handle_tool("project_list_conversations", {"project_id": "proj-1"})
    assert [c["conversation_id"] for c in listed] == ["c1"]

    unassigned = orchestrator._handle_tool("project_unassign_conversation", {"conversation_id": "c1"})
    assert unassigned == {"conversation_id": "c1", "from_project_id": "proj-1", "to_project_id": None}


def test_project_assign_conversation_tool_never_requires_confirmation(orchestrator):
    result = orchestrator._handle_tool(
        "project_assign_conversation", {"project_id": "proj-1", "conversation_id": "c1"}
    )
    assert result.get("status") != "pending_confirmation"


def test_handle_injects_sarcasm_instruction_at_the_default_level(orchestrator, monkeypatch):
    # Default real (7.5, pedido explícito del fundador) ya debe notarse en el
    # system prompt sin tocar ninguna configuración.
    monkeypatch.setattr(orchestrator._llm, "_client", object())
    captured = {}

    def fake_generate(system, messages, tools=None, tool_handler=None):
        captured["system"] = system
        return LLMResponse(text="respuesta", speech="respuesta")

    monkeypatch.setattr(orchestrator._llm, "generate", fake_generate)
    orchestrator.handle("text", "hola", conversation_id="c1")
    assert "7.5/10" in captured["system"]
    assert "NUNCA aplica ante una decisión" in captured["system"]


def test_handle_omits_sarcasm_instruction_at_level_zero(orchestrator, monkeypatch):
    from snarf.runtime import personality_prefs

    personality_prefs.save_prefs(orchestrator._user_id, {"sarcasm_level": 0})
    monkeypatch.setattr(orchestrator._llm, "_client", object())
    captured = {}

    def fake_generate(system, messages, tools=None, tool_handler=None):
        captured["system"] = system
        return LLMResponse(text="respuesta", speech="respuesta")

    monkeypatch.setattr(orchestrator._llm, "generate", fake_generate)
    orchestrator.handle("text", "hola", conversation_id="c1")
    # CHARACTER.md siempre menciona "Ingenio seco" (es un rasgo permanente,
    # ver ADR de esta feature) — lo que en nivel 0 no debe aparecer es la
    # instrucción de intensidad inyectada por turno.
    assert "Nivel de ingenio seco/sarcasmo configurado" not in captured["system"]


def test_handle_rereads_sarcasm_level_on_every_turn(orchestrator, monkeypatch):
    # No se cachea en __init__ como self._identity — un cambio a mitad de
    # conversación (por config o por la tool) debe reflejarse sin reiniciar.
    from snarf.runtime import personality_prefs

    monkeypatch.setattr(orchestrator._llm, "_client", object())
    captured = []
    monkeypatch.setattr(
        orchestrator._llm,
        "generate",
        lambda system, messages, tools=None, tool_handler=None: captured.append(system) or LLMResponse(text="ok", speech="ok"),
    )

    orchestrator.handle("text", "primero", conversation_id="c1")
    personality_prefs.save_prefs(orchestrator._user_id, {"sarcasm_level": 2})
    orchestrator.handle("text", "segundo", conversation_id="c1")

    assert "7.5/10" in captured[0]
    assert "2.0/10" in captured[1] or "2/10" in captured[1]


def test_personality_set_sarcasm_tool_persists_and_is_reflected_next_turn(orchestrator, monkeypatch):
    result = orchestrator._handle_tool("personality_set_sarcasm", {"level": 9})
    assert result == {"status": "updated", "sarcasm_level": 9.0}

    monkeypatch.setattr(orchestrator._llm, "_client", object())
    captured = {}
    monkeypatch.setattr(
        orchestrator._llm,
        "generate",
        lambda system, messages, tools=None, tool_handler=None: captured.update(system=system) or LLMResponse(text="ok", speech="ok"),
    )
    orchestrator.handle("text", "hola", conversation_id="c1")
    assert "9.0/10" in captured["system"]


def test_personality_set_sarcasm_tool_never_requires_confirmation(orchestrator):
    # A diferencia de las tools de alto impacto (drive_delete_file, etc.), un
    # ajuste de personalidad es reversible al instante y no toca datos de
    # terceros ni archivos — no debe pasar por el gate _pending().
    result = orchestrator._handle_tool("personality_set_sarcasm", {"level": 4})
    assert result.get("status") != "pending_confirmation"


def test_handle_asks_instead_of_inventing_a_name_when_none_is_known(orchestrator, monkeypatch):
    monkeypatch.setattr(orchestrator._llm, "_client", object())
    captured = {}

    def fake_generate(system, messages, tools=None, tool_handler=None):
        captured["system"] = system
        return LLMResponse(text="respuesta", speech="respuesta")

    monkeypatch.setattr(orchestrator._llm, "generate", fake_generate)
    orchestrator.handle("text", "hola", conversation_id="c1")
    assert "Nunca inventes ni" in captured["system"]
    assert "profile_set_name" in captured["system"]


def test_handle_addresses_the_user_by_their_saved_real_name(orchestrator, monkeypatch):
    from snarf.runtime import user_profile

    user_profile.save_profile(orchestrator._user_id, {"name": "Jere"})
    monkeypatch.setattr(orchestrator._llm, "_client", object())
    captured = {}

    def fake_generate(system, messages, tools=None, tool_handler=None):
        captured["system"] = system
        return LLMResponse(text="respuesta", speech="respuesta")

    monkeypatch.setattr(orchestrator._llm, "generate", fake_generate)
    orchestrator.handle("text", "hola", conversation_id="c1")
    assert "El nombre real de quien te está hablando es Jere" in captured["system"]
    assert "Nunca inventes ni" not in captured["system"]


def test_handle_rereads_profile_name_on_every_turn(orchestrator, monkeypatch):
    from snarf.runtime import user_profile

    monkeypatch.setattr(orchestrator._llm, "_client", object())
    captured = []
    monkeypatch.setattr(
        orchestrator._llm,
        "generate",
        lambda system, messages, tools=None, tool_handler=None: captured.append(system) or LLMResponse(text="ok", speech="ok"),
    )

    orchestrator.handle("text", "primero", conversation_id="c1")
    user_profile.save_profile(orchestrator._user_id, {"name": "Jere"})
    orchestrator.handle("text", "segundo", conversation_id="c1")

    assert "El nombre real de quien te está hablando es Jere" not in captured[0]
    assert "El nombre real de quien te está hablando es Jere" in captured[1]


def test_profile_set_name_tool_persists_and_is_reflected_next_turn(orchestrator, monkeypatch):
    result = orchestrator._handle_tool("profile_set_name", {"name": "Jere"})
    assert result == {"status": "updated", "name": "Jere"}

    monkeypatch.setattr(orchestrator._llm, "_client", object())
    captured = {}
    monkeypatch.setattr(
        orchestrator._llm,
        "generate",
        lambda system, messages, tools=None, tool_handler=None: captured.update(system=system) or LLMResponse(text="ok", speech="ok"),
    )
    orchestrator.handle("text", "hola", conversation_id="c1")
    assert "El nombre real de quien te está hablando es Jere" in captured["system"]


def test_profile_set_name_tool_never_requires_confirmation(orchestrator):
    result = orchestrator._handle_tool("profile_set_name", {"name": "Jere"})
    assert result.get("status") != "pending_confirmation"


def test_handle_tool_reports_unknown_tool(orchestrator):
    result = orchestrator._handle_tool("herramienta_inexistente", {})
    assert result == {"error": "herramienta desconocida: herramienta_inexistente"}


def test_handle_tool_catches_handler_exceptions(orchestrator, monkeypatch):
    def boom(_input):
        raise RuntimeError("fallo simulado")

    monkeypatch.setitem(orchestrator._tool_handlers, "list_conversations", boom)
    result = orchestrator._handle_tool("list_conversations", {})
    assert result == {"error": "fallo simulado"}


def test_handle_tool_records_successful_calls_in_the_activity_log(orchestrator):
    from snarf.telemetry import activity_log

    orchestrator._handle_tool("list_conversations", {})
    entries = activity_log.recent()
    assert entries[-1]["tool_name"] == "list_conversations"
    assert entries[-1]["status"] == "ok"
    assert entries[-1]["duration_ms"] >= 0


def test_handle_tool_records_failed_calls_in_the_activity_log(orchestrator, monkeypatch):
    from snarf.telemetry import activity_log

    def boom(_input):
        raise RuntimeError("fallo simulado")

    monkeypatch.setitem(orchestrator._tool_handlers, "list_conversations", boom)
    orchestrator._handle_tool("list_conversations", {})
    entries = activity_log.recent()
    assert entries[-1]["status"] == "error"
    assert entries[-1]["error"] == "fallo simulado"


def test_handle_tool_records_unknown_tool_calls_in_the_activity_log(orchestrator):
    from snarf.telemetry import activity_log

    orchestrator._handle_tool("herramienta_inexistente", {})
    entries = activity_log.recent()
    assert entries[-1]["status"] == "unknown_tool"


# (nombre de la tool, atributo de capacidad en Orchestrator, método real, input base)
HIGH_IMPACT_TOOLS = [
    ("gmail_send_message", "_gmail", "send_message", {"to": "a@b.com", "subject": "s", "body": "b"}),
    (
        "calendar_create_event",
        "_calendar",
        "create_event",
        {"summary": "s", "start_iso": "2026-01-01T10:00:00Z", "end_iso": "2026-01-01T11:00:00Z"},
    ),
    ("calendar_create_calendar", "_calendar", "create_calendar", {"summary": "Nuevo calendario"}),
    ("calendar_delete_calendar", "_calendar", "delete_calendar", {"calendar_id": "cal-1"}),
    ("calendar_delete_event", "_calendar", "delete_event", {"event_id": "ev-1"}),
    (
        "calendar_move_event",
        "_calendar",
        "move_event",
        {"event_id": "ev-1", "source_calendar_id": "a", "destination_calendar_id": "b"},
    ),
    ("gmail_delete_label", "_gmail", "delete_label", {"label_id": "lbl-1"}),
    ("drive_delete_file", "_drive", "delete_file", {"file_id": "f-1"}),
]


@pytest.mark.parametrize("tool_name, capability_attr, method_name, base_input", HIGH_IMPACT_TOOLS)
def test_high_impact_tool_requires_explicit_confirmation(
    orchestrator, monkeypatch, tool_name, capability_attr, method_name, base_input
):
    """Artículo VII de CONSTITUTION.md ('Prueba de Alto Impacto'): ninguna
    acción de alto impacto puede ejecutarse sin confirmación explícita en un
    paso posterior. Verifica, para las 8 herramientas de alto impacto, que
    (1) sin confirmed=True nunca se llama a la capacidad real, y
    (2) con confirmed=True sí se llama, exactamente una vez."""
    calls = []
    capability = getattr(orchestrator, capability_attr)
    monkeypatch.setattr(capability, method_name, lambda *a, **kw: calls.append((a, kw)) or {"id": "x"})

    pending = orchestrator._handle_tool(tool_name, dict(base_input))
    assert pending["status"] == "pending_confirmation"
    assert calls == []

    orchestrator._handle_tool(tool_name, {**base_input, "confirmed": True})
    assert len(calls) == 1


# (nombre de la tool, atributo de capacidad, método real, parámetro de cantidad, base_input sin ese parámetro)
BULK_READ_TOOLS = [
    ("gmail_list_messages", "_gmail", "list_messages", "max_results", {}),
    ("calendar_list_upcoming_events", "_calendar", "list_upcoming_events", "max_results", {}),
    ("calendar_search_events", "_calendar", "search_events", "max_results", {"query": "reunión"}),
    ("youtube_list_subscriptions", "_youtube", "list_subscriptions", "max_results", {}),
    ("youtube_list_liked_videos", "_youtube", "list_liked_videos", "max_results", {}),
    ("drive_list_files", "_drive", "list_files", "page_size", {}),
]


@pytest.mark.parametrize("tool_name, capability_attr, method_name, param, base_input", BULK_READ_TOOLS)
def test_bulk_read_tool_executes_directly_under_the_threshold(
    orchestrator, monkeypatch, tool_name, capability_attr, method_name, param, base_input
):
    calls = []
    capability = getattr(orchestrator, capability_attr)
    monkeypatch.setattr(capability, method_name, lambda *a, **kw: calls.append(kw) or [])
    orchestrator._handle_tool(tool_name, {**base_input, param: 20})
    assert len(calls) == 1


@pytest.mark.parametrize("tool_name, capability_attr, method_name, param, base_input", BULK_READ_TOOLS)
def test_bulk_read_tool_requires_confirmation_above_the_threshold(
    orchestrator, monkeypatch, tool_name, capability_attr, method_name, param, base_input
):
    """Bug real que motivó esto: un pedido de "barrido de mil correos" sin
    ningún tope costó $1.09 en una sola llamada real (ver ADR de esta ronda).
    Por encima del umbral, la capacidad real nunca se llama sin confirmed."""
    calls = []
    capability = getattr(orchestrator, capability_attr)
    monkeypatch.setattr(capability, method_name, lambda *a, **kw: calls.append(kw) or [])

    pending = orchestrator._handle_tool(tool_name, {**base_input, param: 1000})
    assert pending["status"] == "pending_confirmation"
    assert pending["preview"][param] == 1000
    assert calls == []


@pytest.mark.parametrize("tool_name, capability_attr, method_name, param, base_input", BULK_READ_TOOLS)
def test_bulk_read_tool_confirmed_executes_with_the_exact_amount_requested(
    orchestrator, monkeypatch, tool_name, capability_attr, method_name, param, base_input
):
    """"Preguntar antes" nunca es "prohibir para siempre" (pedido explícito
    del fundador) — confirmado, se ejecuta la cantidad EXACTA pedida, sin
    recortarla en silencio."""
    calls = []
    capability = getattr(orchestrator, capability_attr)
    monkeypatch.setattr(capability, method_name, lambda *a, **kw: calls.append(kw) or [])

    orchestrator._handle_tool(tool_name, {**base_input, param: 1000, "confirmed": True})
    assert len(calls) == 1
    assert calls[0][param] == 1000


def test_capped_for_replay_leaves_short_text_unchanged():
    short = "una respuesta normal, nada raro"
    assert _capped_for_replay(short) == short


def test_capped_for_replay_truncates_and_flags_long_text():
    long_text = "x" * (HISTORY_REPLAY_MAX_CHARS + 500)
    result = _capped_for_replay(long_text)
    assert len(result) < len(long_text)
    assert result.startswith("x" * 100)
    assert "no re-pagar su costo" in result


def test_handle_caps_an_oversized_history_entry_before_replaying_it(orchestrator, monkeypatch):
    """Bug real que motivó esto: un resultado de herramienta gigante (ej. un
    barrido de mil correos) embebido en una sola respuesta se re-transmitía
    entero en CADA turno futuro de la misma conversación — una sola llamada
    re-cacheó 523.869 tokens por esto (ver ADR de esta ronda). El JSONL y la
    UI de historial siguen mostrando el original completo, solo lo que se
    re-manda al LLM se recorta."""
    monkeypatch.setattr(orchestrator._llm, "_client", object())  # available=True
    huge_response = "y" * (HISTORY_REPLAY_MAX_CHARS + 1000)
    monkeypatch.setattr(
        orchestrator._llm, "generate", lambda **kwargs: LLMResponse(text=huge_response, speech="ok")
    )
    orchestrator.handle("text", "traeme un montón de correos", conversation_id="c1")

    # El historial completo, sin tocar, sigue disponible para la UI/búsqueda.
    assert orchestrator.memory.get_conversation("c1")[0]["response"] == huge_response

    captured = {}
    monkeypatch.setattr(
        orchestrator._llm,
        "generate",
        lambda system, messages, tools=None, tool_handler=None: captured.update(messages=messages)
        or LLMResponse(text="segunda respuesta", speech="ok"),
    )
    orchestrator.handle("text", "segundo mensaje", conversation_id="c1")
    replayed_response = captured["messages"][1]["content"]
    assert len(replayed_response) < len(huge_response)
    assert "no re-pagar su costo" in replayed_response


def test_gmail_summarize_inbox_returns_cached_digest_when_present(orchestrator, monkeypatch):
    cached = {"generated_at": 1.0, "message_count": 2, "digest_text": "ya interpretado"}
    monkeypatch.setattr(orchestrator.gmail_digest, "cached_digest", lambda: cached)
    monkeypatch.setattr(orchestrator.gmail_digest, "refresh", lambda **kw: (_ for _ in ()).throw(AssertionError("no debería refrescar")))
    assert orchestrator._handle_tool("gmail_summarize_inbox", {}) == cached


def test_gmail_summarize_inbox_refreshes_when_nothing_cached(orchestrator, monkeypatch):
    fresh = {"generated_at": 2.0, "message_count": 1, "digest_text": "recién generado"}
    monkeypatch.setattr(orchestrator.gmail_digest, "cached_digest", lambda: None)
    monkeypatch.setattr(orchestrator.gmail_digest, "refresh", lambda **kw: fresh)
    assert orchestrator._handle_tool("gmail_summarize_inbox", {}) == fresh


def test_gmail_summarize_inbox_force_refresh_ignores_cache(orchestrator, monkeypatch):
    cached = {"generated_at": 1.0, "message_count": 2, "digest_text": "viejo"}
    fresh = {"generated_at": 2.0, "message_count": 3, "digest_text": "nuevo"}
    monkeypatch.setattr(orchestrator.gmail_digest, "cached_digest", lambda: cached)
    monkeypatch.setattr(orchestrator.gmail_digest, "refresh", lambda **kw: fresh)
    assert orchestrator._handle_tool("gmail_summarize_inbox", {"force_refresh": True}) == fresh


def test_drive_read_file_delegates_to_the_content_extractor_not_raw_bytes(orchestrator, monkeypatch):
    # Regresión: antes llamaba directo a GoogleDrive.read_file_text(), que
    # decodifica cualquier binario (PDF, Word, imagen) como UTF-8 a lo
    # bruto — glifos y bytes de imagen en vez de texto real.
    received = {}

    def fake_extract(file):
        received.update(file)
        return ExtractionResult(text="contenido real extraído del pdf")

    monkeypatch.setattr(orchestrator._content_extractor, "extract", fake_extract)
    result = orchestrator._handle_tool("drive_read_file", {"file_id": "f1", "mime_type": "application/pdf"})

    assert result == "contenido real extraído del pdf"
    assert received == {"id": "f1", "mimeType": "application/pdf"}


def test_drive_read_file_reports_extraction_failure_explicitly(orchestrator, monkeypatch):
    monkeypatch.setattr(
        orchestrator._content_extractor,
        "extract",
        lambda file: ExtractionResult(skipped_reason="PDF sin texto extraíble (ni nativo ni OCR)"),
    )
    result = orchestrator._handle_tool("drive_read_file", {"file_id": "f1", "mime_type": "application/pdf"})
    assert result == {"error": "PDF sin texto extraíble (ni nativo ni OCR)"}


def test_drive_index_scan_delegates_to_the_indexer_with_the_given_query(orchestrator, monkeypatch):
    received = {}
    monkeypatch.setattr(orchestrator.drive_indexer, "scan", lambda query=None: received.update(query=query) or {"total_files": 3})
    result = orchestrator._handle_tool("drive_index_scan", {"query": "carpeta X"})
    assert result == {"total_files": 3}
    assert received == {"query": "carpeta X"}


def test_drive_index_catalog_unsupported_delegates_to_the_indexer(orchestrator, monkeypatch):
    received = {}
    monkeypatch.setattr(
        orchestrator.drive_indexer,
        "catalog_unsupported",
        lambda query=None: received.update(query=query) or {"total_files": 5},
    )
    result = orchestrator._handle_tool("drive_index_catalog_unsupported", {"query": "free_tier"})
    assert result == {"total_files": 5}
    assert received == {"query": "free_tier"}


def test_drive_index_start_delegates_to_the_indexer(orchestrator, monkeypatch):
    monkeypatch.setattr(orchestrator.drive_indexer, "start", lambda query=None: {"status": "started"})
    assert orchestrator._handle_tool("drive_index_start", {}) == {"status": "started"}


def test_drive_index_status_delegates_to_the_indexer(orchestrator, monkeypatch):
    monkeypatch.setattr(orchestrator.drive_indexer, "status", lambda: {"running": True})
    assert orchestrator._handle_tool("drive_index_status", {}) == {"running": True}


def test_drive_index_stop_delegates_to_the_indexer(orchestrator, monkeypatch):
    monkeypatch.setattr(orchestrator.drive_indexer, "stop", lambda: {"status": "stopping"})
    assert orchestrator._handle_tool("drive_index_stop", {}) == {"status": "stopping"}


def test_drive_search_knowledge_delegates_to_the_indexer(orchestrator, monkeypatch):
    monkeypatch.setattr(orchestrator.drive_indexer, "search", lambda query, top_k=5: [{"text": query, "top_k": top_k}])
    result = orchestrator._handle_tool("drive_search_knowledge", {"query": "algo", "top_k": 3})
    assert result == [{"text": "algo", "top_k": 3}]


def test_drive_create_document_delegates_to_the_publisher(orchestrator, monkeypatch):
    monkeypatch.setattr(
        orchestrator.document_publisher,
        "create_document",
        lambda title, content, format="markdown", destination="drive": {
            "id": "f1", "title": title, "format": format, "destination": destination
        },
    )
    result = orchestrator._handle_tool(
        "drive_create_document", {"title": "T", "content": "c", "format": "pdf", "destination": "device"}
    )
    assert result == {"id": "f1", "title": "T", "format": "pdf", "destination": "device"}


def test_drive_create_document_defaults_to_drive_when_destination_not_given(orchestrator, monkeypatch):
    received = {}
    monkeypatch.setattr(
        orchestrator.document_publisher,
        "create_document",
        lambda title, content, format="markdown", destination="drive": received.update(destination=destination) or {},
    )
    orchestrator._handle_tool("drive_create_document", {"title": "T", "content": "c"})
    assert received == {"destination": "drive"}


def test_drive_create_spreadsheet_delegates_to_the_publisher(orchestrator, monkeypatch):
    monkeypatch.setattr(
        orchestrator.document_publisher,
        "create_spreadsheet",
        lambda title, rows, format="xlsx", destination="drive": {"id": "f2", "rows": rows, "destination": destination},
    )
    result = orchestrator._handle_tool("drive_create_spreadsheet", {"title": "T", "rows": [["a", "b"]]})
    assert result == {"id": "f2", "rows": [["a", "b"]], "destination": "drive"}


def test_drive_create_presentation_delegates_to_the_publisher(orchestrator, monkeypatch):
    monkeypatch.setattr(
        orchestrator.document_publisher,
        "create_presentation",
        lambda title, slides, format="pptx", destination="drive": {
            "id": "f3", "slides": slides, "destination": destination
        },
    )
    result = orchestrator._handle_tool(
        "drive_create_presentation", {"title": "T", "slides": [{"title": "s1"}], "destination": "device"}
    )
    assert result == {"id": "f3", "slides": [{"title": "s1"}], "destination": "device"}


def test_handle_tags_telemetry_events_with_the_real_conversation_id(orchestrator, monkeypatch):
    # Fase 3 del plan de HUD (historial de costos "por sesión") depende de
    # que el evento unificado quede taggeado con el conversation_id real del
    # turno que lo generó — ver snarf/telemetry/context.py.
    from snarf.telemetry import events

    monkeypatch.setattr(orchestrator._llm, "_client", object())

    def fake_generate(system, messages, tools=None, tool_handler=None):
        tool_handler("list_conversations", {})
        return LLMResponse(text="ok", speech="ok")

    monkeypatch.setattr(orchestrator._llm, "generate", fake_generate)

    orchestrator.handle("text", "hola", conversation_id="conv-real-42")

    entries = events.recent()
    tool_event = next(e for e in entries if e["skill"] == "list_conversations")
    assert tool_event["conversation_id"] == "conv-real-42"


def test_conversation_context_is_cleared_after_handle_returns(orchestrator):
    from snarf.telemetry import context

    orchestrator.handle("text", "hola", conversation_id="conv-1")
    assert context.get_conversation_id() is None


def test_conversation_context_is_cleared_even_if_the_llm_raises(orchestrator, monkeypatch):
    from snarf.telemetry import context

    monkeypatch.setattr(orchestrator._llm, "_client", object())

    def boom(system, messages, tools=None, tool_handler=None):
        raise RuntimeError("fallo simulado del LLM")

    monkeypatch.setattr(orchestrator._llm, "generate", boom)

    orchestrator.handle("text", "hola", conversation_id="conv-2")
    assert context.get_conversation_id() is None


def test_background_tool_calls_outside_a_conversation_turn_have_no_conversation_id(orchestrator):
    from snarf.telemetry import events

    orchestrator._handle_tool("list_conversations", {})
    entries = events.recent()
    assert entries[-1]["conversation_id"] is None


def test_handle_records_input_preprocessing_with_real_sizes(orchestrator, monkeypatch):
    from snarf.telemetry import input_preprocessing

    monkeypatch.setattr(orchestrator._llm, "_client", object())
    monkeypatch.setattr(
        orchestrator._llm, "generate",
        lambda system, messages, tools=None, tool_handler=None: LLMResponse(text="ok", speech="ok"),
    )

    orchestrator.handle("text", "hola snarf, esto es un mensaje corto", conversation_id="c1")

    entries = input_preprocessing.recent()
    entry = entries[-1]
    assert entry["conversation_id"] == "c1"
    assert entry["input_original"] == "hola snarf, esto es un mensaje corto"
    assert entry["input_chars"] == len("hola snarf, esto es un mensaje corto")
    assert entry["system_chars"] > 0
    assert entry["history_chars"] == 0  # primer turno de la conversación, sin historial que replicar
    assert entry["history_entries"] == 0
    assert entry["total_sent_chars"] == entry["system_chars"] + entry["input_chars"]
    assert entry["overhead_ratio"] > 1  # el system prompt solo ya es mucho más grande que el mensaje


def test_handle_input_preprocessing_counts_replayed_history_on_a_second_turn(orchestrator, monkeypatch):
    from snarf.telemetry import input_preprocessing

    monkeypatch.setattr(orchestrator._llm, "_client", object())
    monkeypatch.setattr(
        orchestrator._llm, "generate",
        lambda system, messages, tools=None, tool_handler=None: LLMResponse(text="respuesta uno", speech="ok"),
    )
    orchestrator.handle("text", "primero", conversation_id="c1")
    orchestrator.handle("text", "segundo", conversation_id="c1")

    entries = input_preprocessing.recent()
    second = entries[-1]
    assert second["history_entries"] == 1
    assert second["history_chars"] == len("primero") + len("respuesta uno")
