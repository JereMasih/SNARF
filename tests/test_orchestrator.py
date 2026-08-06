import pytest

from snarf.capabilities.anthropic_llm import LLMResponse
from snarf.core.orchestrator import HISTORY_REPLAY_MAX_CHARS, Orchestrator
from snarf.knowledge.extraction import ExtractionResult
from snarf.runtime import llm_routing


@pytest.fixture
def orchestrator(tmp_path, monkeypatch):
    # Aísla la memoria episódica del proyecto real: cada test corre en su
    # propio directorio temporal, nunca escribe en data/episodic_memory.jsonl.
    monkeypatch.chdir(tmp_path)
    o = Orchestrator()
    # Bug real de hermeticidad encontrado en vivo (2026-08-05, mismo que
    # tests/test_app.py — ver ADR 0119/CHANGELOG): la mayoría de los tests de
    # este archivo nunca mockearon self._llm/_title_llm a propósito porque el
    # proveedor default de ANTES exigía una credencial real (stripeada por
    # conftest::_no_real_credentials) — `.available` daba False sola y
    # handle()/generate_conversation_title() degradaban en modo eco sin
    # llamar a nada. Desde que el default pasó a mlx_local_fast (sin
    # credencial, siempre "available"), esos mismos tests sin mockear
    # empezaron a disparar llamadas REALES contra el server local de
    # producción — confirmado con `lsof`: la suite completa colgada varios
    # minutos contra una conexión TCP real a 127.0.0.1:8991, justo cuando
    # coincide con tráfico real del fundador en el mismo server. Este default
    # restaura el comportamiento original (`.available == False`) para
    # cualquier test que no mockee `_llm`/`_title_llm` a mano — los que sí
    # necesitan una respuesta real siguen sobreescribiendo esto ellos mismos.
    monkeypatch.setattr(o._llm, "_client", None)
    monkeypatch.setattr(o._title_llm, "_client", None)
    return o


def test_echo_mode_without_api_key_and_persists_to_memory(orchestrator):
    # DEFAULT_ROUTING para "orchestrator" es mlx_local_fast (2026-08-05, ver
    # llm_routing.py) — ese proveedor no exige ninguna credencial real, así
    # que SIEMPRE cuenta como "available" (aunque no haya ningún server MLX
    # escuchando en ese puerto, ver OpenAICompatibleLLM.available). Este test
    # verifica específicamente el modo eco cuando NO hay ningún LLM
    # configurado — hay que rutear a mano a un proveedor que sí dependa de
    # una credencial (anthropic), ya borrada por conftest::_no_real_credentials,
    # para no depender del default vigente ni terminar pegándole de verdad al
    # server local real que corre en esta Mac durante los tests.
    llm_routing.save_routing({"orchestrator": {"provider": "anthropic", "model": "claude-haiku-4-5"}})
    orchestrator.refresh_llm_routing()
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


def test_handle_tags_the_llm_role_as_orchestrator_during_the_real_call_and_clears_it_after(orchestrator, monkeypatch):
    from snarf.telemetry import context

    captured = {}

    def fake_generate(**kwargs):
        captured["role_during_call"] = context.get_llm_role()
        return LLMResponse(text="respuesta", speech="")

    monkeypatch.setattr(orchestrator._llm, "_client", object())  # available=True
    monkeypatch.setattr(orchestrator._llm, "generate", fake_generate)
    orchestrator.handle("text", "hola", conversation_id="c1")

    assert captured["role_during_call"] == "orchestrator"
    assert context.get_llm_role() is None


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


def test_generate_conversation_title_tags_the_llm_role_and_clears_it_after(orchestrator, monkeypatch):
    from snarf.telemetry import context

    orchestrator.handle("text", "hola", conversation_id="c1")
    captured = {}

    def fake_generate(**kwargs):
        captured["role_during_call"] = context.get_llm_role()
        return LLMResponse(text="Título", speech="")

    monkeypatch.setattr(orchestrator._title_llm, "_client", object())  # available=True
    monkeypatch.setattr(orchestrator._title_llm, "generate", fake_generate)
    orchestrator.generate_conversation_title("c1")

    assert captured["role_during_call"] == "conversation_title"
    assert context.get_llm_role() is None


def test_generate_conversation_title_does_nothing_when_the_cheap_llm_is_unavailable(orchestrator):
    # Default real de "orchestrator"/"conversation_title" es mlx_local_fast
    # (2026-08-05) — no exige credencial, así que cuenta como disponible
    # incluso en tests. Rutear a mano a anthropic (sin API key en este
    # fixture, ver conftest.py) para que _title_llm quede genuinamente no
    # disponible, sin depender de si hay un server MLX real corriendo.
    llm_routing.save_routing({
        "orchestrator": {"provider": "anthropic", "model": "claude-haiku-4-5"},
        "conversation_title": {"provider": "anthropic", "model": "claude-haiku-4-5"},
    })
    orchestrator.refresh_llm_routing()
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


def test_generate_conversation_title_uses_the_fallback_provider_when_available(orchestrator, monkeypatch):
    # ADR de esta ronda: un fallo real de proveedor no tiene por qué perder
    # el título — attempt_fallback (ya testeado a fondo en
    # tests/test_llm_routing.py) se mockea acá solo para verificar que
    # generate_conversation_title lo llama bien y usa su resultado.
    orchestrator.handle("text", "hola", conversation_id="c1")
    monkeypatch.setattr(orchestrator._title_llm, "_client", object())  # available=True
    monkeypatch.setattr(orchestrator._title_llm, "generate", lambda **kw: (_ for _ in ()).throw(RuntimeError("sin crédito")))

    calls = []

    def fake_attempt_fallback(role, entry, exc, **kwargs):
        calls.append(role)
        return LLMResponse(text="Saludo real vía respaldo", speech=""), {"provider": "xai", "model": "grok-4-1-fast"}

    monkeypatch.setattr(llm_routing, "attempt_fallback", fake_attempt_fallback)
    refreshed = []
    monkeypatch.setattr(orchestrator, "refresh_llm_routing", lambda: refreshed.append(True))

    orchestrator.generate_conversation_title("c1")

    assert calls == ["conversation_title"]
    assert refreshed == [True]
    assert orchestrator.memory.get_title("c1") == "Saludo real vía respaldo"


def test_generate_conversation_title_still_degrades_gracefully_when_the_fallback_also_fails(orchestrator, monkeypatch):
    orchestrator.handle("text", "hola", conversation_id="c1")
    monkeypatch.setattr(orchestrator._title_llm, "_client", object())
    monkeypatch.setattr(orchestrator._title_llm, "generate", lambda **kw: (_ for _ in ()).throw(RuntimeError("sin crédito")))
    monkeypatch.setattr(llm_routing, "attempt_fallback", lambda role, entry, exc, **kw: (None, None))

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


def test_handle_falls_back_automatically_when_the_configured_provider_fails(orchestrator, monkeypatch):
    # ADR de esta ronda: attempt_fallback ya está testeado a fondo en
    # tests/test_llm_routing.py — acá solo se verifica que handle() lo llama
    # bien (mismos kwargs del turno real) y usa su resultado en vez de
    # degradar al mensaje de error.
    monkeypatch.setattr(orchestrator._llm, "_client", object())  # available=True
    monkeypatch.setattr(orchestrator._llm, "generate", lambda **kw: (_ for _ in ()).throw(RuntimeError("sin crédito")))

    calls = []

    def fake_attempt_fallback(role, entry, exc, **kwargs):
        calls.append((role, "tools" in kwargs))
        return LLMResponse(text="respuesta real vía el proveedor de respaldo", speech="respuesta real"), {
            "provider": "xai",
            "model": "grok-4-1-fast",
        }

    monkeypatch.setattr(llm_routing, "attempt_fallback", fake_attempt_fallback)
    refreshed = []
    monkeypatch.setattr(orchestrator, "refresh_llm_routing", lambda: refreshed.append(True))

    response = orchestrator.handle("text", "hola snarf", conversation_id="c1")

    assert calls == [("orchestrator", True)]
    assert refreshed == [True]
    assert response.text == "respuesta real vía el proveedor de respaldo"
    assert orchestrator.memory.get_conversation("c1")[0]["response"] == response.text


def test_handle_still_degrades_gracefully_when_the_fallback_also_fails(orchestrator, monkeypatch):
    monkeypatch.setattr(orchestrator._llm, "_client", object())
    monkeypatch.setattr(orchestrator._llm, "generate", lambda **kw: (_ for _ in ()).throw(RuntimeError("Your credit balance is too low")))
    monkeypatch.setattr(llm_routing, "attempt_fallback", lambda role, entry, exc, **kw: (None, None))

    response = orchestrator.handle("text", "hola snarf", conversation_id="c1")
    assert "error real del LLM" in response.text
    assert "credit balance" in response.text


def test_handle_reverts_to_local_automatically_when_the_fallback_cooldown_expired(orchestrator, monkeypatch):
    # ADR de esta ronda: maybe_revert_expired_fallback ya está testeado a
    # fondo en tests/test_llm_routing.py — acá solo se verifica que handle()
    # lo consulta ANTES de usar self._llm, y usa su resultado sin siquiera
    # llamar al proveedor de fallback vigente.
    monkeypatch.setattr(orchestrator._llm, "_client", object())  # available=True

    def boom_if_called(**kwargs):
        raise AssertionError("no debería llamar al proveedor de fallback vigente — el revert ya respondió")

    monkeypatch.setattr(orchestrator._llm, "generate", boom_if_called)

    calls = []

    def fake_maybe_revert(role, entry, **kwargs):
        calls.append((role, "tools" in kwargs))
        return LLMResponse(text="respuesta real, ya de vuelta en local", speech="ya volví"), {
            "provider": "mlx_local_fast",
            "model": "mlx-community/Qwen3-4B-Instruct-2507-4bit",
        }

    monkeypatch.setattr(llm_routing, "maybe_revert_expired_fallback", fake_maybe_revert)
    refreshed = []
    monkeypatch.setattr(orchestrator, "refresh_llm_routing", lambda: refreshed.append(True))

    response = orchestrator.handle("text", "hola snarf", conversation_id="c1")

    assert calls == [("orchestrator", True)]
    assert refreshed == [True]
    assert response.text == "respuesta real, ya de vuelta en local"


def test_generate_conversation_title_reverts_to_local_automatically_when_the_fallback_cooldown_expired(orchestrator, monkeypatch):
    orchestrator.handle("text", "hola", conversation_id="c1")
    monkeypatch.setattr(orchestrator._title_llm, "_client", object())  # available=True

    def boom_if_called(**kwargs):
        raise AssertionError("no debería llamar al proveedor de fallback vigente — el revert ya respondió")

    monkeypatch.setattr(orchestrator._title_llm, "generate", boom_if_called)

    calls = []

    def fake_maybe_revert(role, entry, **kwargs):
        calls.append(role)
        return LLMResponse(text="Título real, ya de vuelta en local", speech=""), {
            "provider": "mlx_local_fast",
            "model": "mlx-community/Qwen3-4B-Instruct-2507-4bit",
        }

    monkeypatch.setattr(llm_routing, "maybe_revert_expired_fallback", fake_maybe_revert)
    refreshed = []
    monkeypatch.setattr(orchestrator, "refresh_llm_routing", lambda: refreshed.append(True))

    orchestrator.generate_conversation_title("c1")

    assert calls == ["conversation_title"]
    assert refreshed == [True]
    assert orchestrator.memory.get_title("c1") == "Título real, ya de vuelta en local"


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


def test_capped_for_replay_leaves_short_text_unchanged(orchestrator):
    short = "una respuesta normal, nada raro"
    assert orchestrator._capped_for_replay(short) == short


def test_capped_for_replay_falls_back_to_hard_cut_when_no_summarizer_available(orchestrator):
    """En los tests nunca hay ANTHROPIC_API_KEY (ver conftest.py) — rutear
    history_compaction a mano a anthropic (default real es mlx_local_fast
    desde 2026-08-05, que no exige credencial y por eso cuenta como
    disponible incluso en tests) deja el rol no disponible y esto cae al
    corte duro de siempre, la misma garantía que existía antes de sumar el
    resumen real: nunca romper el turno si el resumen no se puede hacer."""
    llm_routing.save_routing({"history_compaction": {"provider": "anthropic", "model": "claude-haiku-4-5"}})
    long_text = "x" * (HISTORY_REPLAY_MAX_CHARS + 500)
    result = orchestrator._capped_for_replay(long_text)
    assert len(result) < len(long_text)
    assert result.startswith("x" * 100)
    assert "no re-pagar su costo" in result


def test_capped_for_replay_uses_a_real_summary_when_the_compaction_role_is_available(orchestrator, monkeypatch):
    """Con el resumen real disponible, una entrada larga se condensa fiel al
    contenido (vía el rol history_compaction) en vez de cortarse a lo bruto —
    y una segunda entrada con el MISMO texto no debe volver a llamar al LLM
    (cache en memoria por contenido)."""
    long_text = "x" * (HISTORY_REPLAY_MAX_CHARS + 500)
    calls = []

    class FakeSummarizer:
        available = True

        def generate(self, **kwargs):
            calls.append(kwargs)
            return LLMResponse(text="resumen fiel y compacto", speech="ok")

    monkeypatch.setattr(llm_routing, "build_resilient_llm", lambda role: FakeSummarizer())

    first = orchestrator._capped_for_replay(long_text)
    second = orchestrator._capped_for_replay(long_text)

    assert first == "resumen fiel y compacto"
    assert second == "resumen fiel y compacto"
    assert len(calls) == 1


def test_capped_for_replay_skips_the_llm_entirely_for_an_extreme_entry(orchestrator, monkeypatch):
    """Bug real (esta ronda): una entrada MUY grande (ej. una respuesta vieja
    con el volcado completo de un resultado de herramienta gigante) mandada
    entera al rol history_compaction tumbó el server MLX local real por
    out-of-memory de Metal (~20.800 tokens en un solo prompt, 31GB de RAM
    real). Por encima de HISTORY_COMPACTION_INPUT_MAX_CHARS, el corte duro se
    aplica directo — el LLM ni se llama, sin importar que esté disponible."""
    from snarf.core.orchestrator import HISTORY_COMPACTION_INPUT_MAX_CHARS

    calls = []

    class FakeSummarizer:
        available = True

        def generate(self, **kwargs):
            calls.append(kwargs)
            return LLMResponse(text="no debería llegar a usarse", speech="ok")

    monkeypatch.setattr(llm_routing, "build_resilient_llm", lambda role: FakeSummarizer())
    extreme_text = "z" * (HISTORY_COMPACTION_INPUT_MAX_CHARS + 1000)

    result = orchestrator._capped_for_replay(extreme_text)

    assert calls == []
    assert len(result) < len(extreme_text)
    assert "no re-pagar su costo" in result


def test_handle_caps_an_oversized_history_entry_before_replaying_it(orchestrator, monkeypatch):
    """Bug real que motivó esto: un resultado de herramienta gigante (ej. un
    barrido de mil correos) embebido en una sola respuesta se re-transmitía
    entero en CADA turno futuro de la misma conversación — una sola llamada
    re-cacheó 523.869 tokens por esto (ver ADR de esta ronda). El JSONL y la
    UI de historial siguen mostrando el original completo, solo lo que se
    re-manda al LLM se recorta.

    history_compaction ruteado a mano a anthropic (sin API key en este
    fixture) para forzar el corte duro determinístico — el default real es
    mlx_local_fast (2026-08-05), que sí está disponible y resumiría de
    verdad el texto de prueba, pegándole a un server real en vez de probar
    el camino de "no re-pagar su costo" que este test verifica."""
    llm_routing.save_routing({"history_compaction": {"provider": "anthropic", "model": "claude-haiku-4-5"}})
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


def test_calendar_brief_returns_cached_brief_when_present(orchestrator, monkeypatch):
    cached = {"generated_at": 1.0, "event_count": 2, "brief_text": "ya interpretado"}
    monkeypatch.setattr(orchestrator.calendar_brief, "cached_brief", lambda: cached)
    monkeypatch.setattr(orchestrator.calendar_brief, "refresh", lambda **kw: (_ for _ in ()).throw(AssertionError("no debería refrescar")))
    assert orchestrator._handle_tool("calendar_brief", {}) == cached


def test_calendar_brief_refreshes_when_nothing_cached(orchestrator, monkeypatch):
    fresh = {"generated_at": 2.0, "event_count": 1, "brief_text": "recién generado"}
    monkeypatch.setattr(orchestrator.calendar_brief, "cached_brief", lambda: None)
    monkeypatch.setattr(orchestrator.calendar_brief, "refresh", lambda **kw: fresh)
    assert orchestrator._handle_tool("calendar_brief", {}) == fresh


def test_calendar_brief_force_refresh_ignores_cache(orchestrator, monkeypatch):
    cached = {"generated_at": 1.0, "event_count": 2, "brief_text": "viejo"}
    fresh = {"generated_at": 2.0, "event_count": 3, "brief_text": "nuevo"}
    monkeypatch.setattr(orchestrator.calendar_brief, "cached_brief", lambda: cached)
    monkeypatch.setattr(orchestrator.calendar_brief, "refresh", lambda **kw: fresh)
    assert orchestrator._handle_tool("calendar_brief", {"force_refresh": True}) == fresh


def test_morning_routine_returns_cached_routine_when_present(orchestrator, monkeypatch):
    cached = {"generated_at": 1.0, "message_count": 2, "event_count": 1, "routine_text": "ya interpretado"}
    monkeypatch.setattr(orchestrator.morning_routine, "cached_routine", lambda: cached)
    monkeypatch.setattr(orchestrator.morning_routine, "refresh", lambda **kw: (_ for _ in ()).throw(AssertionError("no debería refrescar")))
    assert orchestrator._handle_tool("morning_routine", {}) == cached


def test_morning_routine_refreshes_when_nothing_cached(orchestrator, monkeypatch):
    fresh = {"generated_at": 2.0, "message_count": 1, "event_count": 0, "routine_text": "recién generado"}
    monkeypatch.setattr(orchestrator.morning_routine, "cached_routine", lambda: None)
    monkeypatch.setattr(orchestrator.morning_routine, "refresh", lambda **kw: fresh)
    assert orchestrator._handle_tool("morning_routine", {}) == fresh


def test_morning_routine_force_refresh_ignores_cache(orchestrator, monkeypatch):
    cached = {"generated_at": 1.0, "message_count": 2, "event_count": 1, "routine_text": "viejo"}
    fresh = {"generated_at": 2.0, "message_count": 3, "event_count": 2, "routine_text": "nuevo"}
    monkeypatch.setattr(orchestrator.morning_routine, "cached_routine", lambda: cached)
    monkeypatch.setattr(orchestrator.morning_routine, "refresh", lambda **kw: fresh)
    assert orchestrator._handle_tool("morning_routine", {"force_refresh": True}) == fresh


def test_morning_routine_passes_through_max_messages_and_max_events(orchestrator, monkeypatch):
    fresh = {"generated_at": 2.0, "message_count": 3, "event_count": 2, "routine_text": "nuevo"}
    captured = {}

    def fake_refresh(**kw):
        captured.update(kw)
        return fresh

    monkeypatch.setattr(orchestrator.morning_routine, "cached_routine", lambda: None)
    monkeypatch.setattr(orchestrator.morning_routine, "refresh", fake_refresh)
    orchestrator._handle_tool("morning_routine", {"max_messages": 5, "max_events": 3})
    assert captured == {"max_messages": 5, "max_events": 3}


def test_research_tools_route_to_the_correct_mode(orchestrator, monkeypatch):
    for tool_name, mode in (
        ("research_deep_dive", "deep_research"),
        ("research_trend_scan", "trend_scan"),
        ("research_competitor_watch", "competitor_watch"),
    ):
        fake_result = {"topic": "x", "report_text": f"informe de {mode}", "sources": [], "document": None}
        monkeypatch.setattr(
            orchestrator._research_specialists[mode],
            "research",
            lambda topic, video_urls=None, fake_result=fake_result: fake_result,
        )
        assert orchestrator._handle_tool(tool_name, {"topic": "x"}) == fake_result


def test_content_tools_route_to_the_correct_mode(orchestrator, monkeypatch):
    for tool_name, mode in (
        ("content_write_blog_post", "blog_post"),
        ("content_write_social_post", "social_post"),
        ("content_write_newsletter", "newsletter"),
    ):
        fake_result = {"draft_text": f"borrador de {mode}", "document": None}
        monkeypatch.setattr(
            orchestrator._content_specialists[mode],
            "draft",
            lambda brief, reference_material="", fake_result=fake_result: fake_result,
        )
        assert orchestrator._handle_tool(tool_name, {"brief": "x"}) == fake_result


def test_sales_sponsor_inbox_triage_returns_cached_when_present(orchestrator, monkeypatch):
    cached = {"generated_at": 1.0, "message_count": 2, "triage_text": "ya interpretado"}
    monkeypatch.setattr(orchestrator._sponsor_inbox_triage, "cached_triage", lambda: cached)
    monkeypatch.setattr(orchestrator._sponsor_inbox_triage, "refresh", lambda **kw: (_ for _ in ()).throw(AssertionError("no debería refrescar")))
    assert orchestrator._handle_tool("sales_sponsor_inbox_triage", {}) == cached


def test_sales_sponsor_inbox_triage_force_refresh_ignores_cache(orchestrator, monkeypatch):
    cached = {"generated_at": 1.0, "message_count": 2, "triage_text": "viejo"}
    fresh = {"generated_at": 2.0, "message_count": 3, "triage_text": "nuevo"}
    monkeypatch.setattr(orchestrator._sponsor_inbox_triage, "cached_triage", lambda: cached)
    monkeypatch.setattr(orchestrator._sponsor_inbox_triage, "refresh", lambda **kw: fresh)
    assert orchestrator._handle_tool("sales_sponsor_inbox_triage", {"force_refresh": True}) == fresh


def test_finance_books_categorize_delegates_with_the_real_file_id(orchestrator, monkeypatch):
    monkeypatch.setattr(orchestrator._books_categorize, "categorize", lambda file_id: {"file_id": file_id})
    assert orchestrator._handle_tool("finance_books_categorize", {"file_id": "sheet-1"}) == {"file_id": "sheet-1"}


def test_finance_monthly_pnl_delegates_to_the_deterministic_computation(orchestrator, monkeypatch):
    transactions = [{"amount": 10.0, "category": "x"}]
    monkeypatch.setattr(orchestrator._monthly_pnl, "compute", lambda t: {"received": t})
    assert orchestrator._handle_tool("finance_monthly_pnl", {"transactions": transactions}) == {"received": transactions}


def test_community_pulse_delegates_with_the_real_message_limit(orchestrator, monkeypatch):
    monkeypatch.setattr(orchestrator._community_pulse, "pulse", lambda message_limit: {"limit": message_limit})
    assert orchestrator._handle_tool("community_pulse", {"message_limit": 5}) == {"limit": 5}


def test_community_post_message_requires_confirmation_first(orchestrator):
    result = orchestrator._handle_tool("community_post_message", {"content": "hola"})
    assert result["status"] == "pending_confirmation"
    assert result["preview"]["content"] == "hola"


def test_community_post_message_with_confirmed_calls_discord(orchestrator, monkeypatch):
    monkeypatch.setattr(orchestrator._discord, "send_message", lambda content: {"id": "m1", "content": content})
    result = orchestrator._handle_tool("community_post_message", {"content": "hola", "confirmed": True})
    assert result == {"id": "m1", "content": "hola"}


def test_ops_system_health_reflects_real_orchestrator_state(orchestrator, monkeypatch):
    monkeypatch.setattr(orchestrator._llm, "_client", object())
    result = orchestrator._handle_tool("ops_system_health", {"n": 10})
    assert result["llm_available"] is True
    assert "recent_call_count" in result


def test_ops_backup_now_triggers_a_real_backup(orchestrator, monkeypatch, tmp_path):
    # data_backup.backup_now() resuelve sus paths default (DATA_DIR/
    # BACKUP_DIR) al momento de DEFINIRSE la función, no en cada llamada —
    # monkeypatchear esas constantes de módulo no alcanza para aislar el
    # test del disco real. Se parchea la función en sí.
    from snarf.runtime import data_backup

    fake_snapshot = tmp_path / "snap1"
    monkeypatch.setattr(data_backup, "backup_now", lambda: fake_snapshot)
    result = orchestrator._handle_tool("ops_backup_now", {})
    assert result == {"snapshot": str(fake_snapshot)}


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


# --- Knowledge Layer generalizada (ver KNOWLEDGE.md, ADR 0093) -------------


class _FakeDomainIndexer:
    def __init__(self, search_result=None):
        self.search_calls = []
        self.start_called = False
        self._status = {"running": False}
        self._search_result = search_result if search_result is not None else [{"text": "resultado real"}]

    def search(self, query, top_k=5, where=None):
        self.search_calls.append((query, top_k, where))
        return self._search_result

    def start(self):
        self.start_called = True
        return {"status": "started"}

    def status(self):
        return self._status


def test_knowledge_search_with_domain_personal_delegates_to_the_drive_indexer(orchestrator, monkeypatch):
    fake = _FakeDomainIndexer()
    monkeypatch.setattr(orchestrator, "_drive_indexer", fake)

    result = orchestrator._handle_tool("knowledge_search", {"query": "impuestos", "domain": "personal"})

    assert fake.search_calls == [("impuestos", 5, None)]
    assert result == [{"text": "resultado real"}]


def test_knowledge_search_with_domain_code_delegates_to_the_code_indexer(orchestrator, monkeypatch):
    fake = _FakeDomainIndexer()
    monkeypatch.setattr(orchestrator, "_code_indexer", fake)

    result = orchestrator._handle_tool("knowledge_search", {"query": "orchestrator", "domain": "code", "top_k": 3})

    assert fake.search_calls == [("orchestrator", 3, None)]
    assert result == [{"text": "resultado real"}]


def test_knowledge_search_with_a_domain_without_a_real_source_reports_it_explicitly_instead_of_inventing(orchestrator):
    result = orchestrator._handle_tool("knowledge_search", {"query": "caja real", "domain": "business"})

    assert "error" in result
    assert "business" in result["error"]


def test_codebase_search_always_uses_the_code_indexer(orchestrator, monkeypatch):
    fake = _FakeDomainIndexer()
    monkeypatch.setattr(orchestrator, "_code_indexer", fake)

    result = orchestrator._handle_tool("codebase_search", {"query": "orchestrator"})

    assert fake.search_calls == [("orchestrator", 5, None)]
    assert result == [{"text": "resultado real"}]


def test_knowledge_index_start_with_domain_code_starts_the_code_indexer(orchestrator, monkeypatch):
    fake = _FakeDomainIndexer()
    monkeypatch.setattr(orchestrator, "_code_indexer", fake)

    result = orchestrator._handle_tool("knowledge_index_start", {"domain": "code"})

    assert fake.start_called is True
    assert result == {"status": "started"}


def test_knowledge_index_start_with_domain_personal_reports_the_real_alternative_instead_of_starting_anything(orchestrator, monkeypatch):
    fake = _FakeDomainIndexer()
    monkeypatch.setattr(orchestrator, "_drive_indexer", fake)

    result = orchestrator._handle_tool("knowledge_index_start", {"domain": "personal"})

    assert fake.start_called is False
    assert "drive_index_start" in result["error"]


def test_knowledge_index_status_with_domain_code_reads_the_code_indexer(orchestrator, monkeypatch):
    fake = _FakeDomainIndexer()
    fake._status = {"running": True, "processed": 3}
    monkeypatch.setattr(orchestrator, "_code_indexer", fake)

    result = orchestrator._handle_tool("knowledge_index_status", {"domain": "code"})

    assert result == {"running": True, "processed": 3}


def test_knowledge_index_status_with_an_unsupported_domain_reports_it_explicitly(orchestrator):
    result = orchestrator._handle_tool("knowledge_index_status", {"domain": "marketing"})

    assert "error" in result


# --- dominio 'conversations' (ADR de esta ronda, mismo precedente que 'code') ---


def test_knowledge_search_with_domain_conversations_delegates_to_the_conversations_indexer(orchestrator, monkeypatch):
    fake = _FakeDomainIndexer()
    monkeypatch.setattr(orchestrator, "_conversations_indexer", fake)

    result = orchestrator._handle_tool("knowledge_search", {"query": "el plan de marca", "domain": "conversations"})

    assert fake.search_calls == [("el plan de marca", 5, None)]
    assert result == [{"text": "resultado real"}]


def test_conversations_search_without_project_id_searches_the_whole_history(orchestrator, monkeypatch):
    fake = _FakeDomainIndexer()
    monkeypatch.setattr(orchestrator, "_conversations_indexer", fake)

    result = orchestrator._handle_tool("conversations_search", {"query": "el plan de marca"})

    assert fake.search_calls == [("el plan de marca", 5, None)]
    assert result == [{"text": "resultado real"}]


def test_conversations_search_with_project_id_filters_by_it(orchestrator, monkeypatch):
    fake = _FakeDomainIndexer()
    monkeypatch.setattr(orchestrator, "_conversations_indexer", fake)

    orchestrator._handle_tool("conversations_search", {"query": "estado del cliente", "project_id": "proj-1", "top_k": 3})

    assert fake.search_calls == [("estado del cliente", 3, {"project_id": "proj-1"})]


def test_knowledge_index_start_with_domain_conversations_starts_the_conversations_indexer(orchestrator, monkeypatch):
    fake = _FakeDomainIndexer()
    monkeypatch.setattr(orchestrator, "_conversations_indexer", fake)

    result = orchestrator._handle_tool("knowledge_index_start", {"domain": "conversations"})

    assert fake.start_called is True
    assert result == {"status": "started"}


def test_knowledge_index_status_with_domain_conversations_reads_the_conversations_indexer(orchestrator, monkeypatch):
    fake = _FakeDomainIndexer()
    fake._status = {"running": True, "processed": 7}
    monkeypatch.setattr(orchestrator, "_conversations_indexer", fake)

    result = orchestrator._handle_tool("knowledge_index_status", {"domain": "conversations"})

    assert result == {"running": True, "processed": 7}


def test_conversations_indexer_property_returns_the_real_instance(orchestrator):
    assert orchestrator.conversations_indexer is orchestrator._conversations_indexer
