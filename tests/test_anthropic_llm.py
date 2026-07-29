from types import SimpleNamespace

from snarf.capabilities.anthropic_llm import CACHE_TTL, MAX_OUTPUT_TOKENS, AnthropicLLM


class FakeTextBlock:
    type = "text"

    def __init__(self, text):
        self.text = text


class FakeToolUseBlock:
    type = "tool_use"

    def __init__(self, id, name, input):
        self.id = id
        self.name = name
        self.input = input


def fake_response(stop_reason, text, usage=None):
    return SimpleNamespace(stop_reason=stop_reason, content=[FakeTextBlock(text)], usage=usage)


def fake_tool_use_response(tool_use_id, tool_name, tool_input):
    return SimpleNamespace(
        stop_reason="tool_use",
        content=[FakeToolUseBlock(tool_use_id, tool_name, tool_input)],
        usage=None,
    )


class FakeMessages:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


class FakeClient:
    def __init__(self, responses):
        self.messages = FakeMessages(responses)


def make_llm(responses):
    # Bypasea __init__ (que exige ANTHROPIC_API_KEY) para inyectar un cliente falso.
    llm = AnthropicLLM.__new__(AnthropicLLM)
    llm.model = "claude-sonnet-5"
    llm._api_key = "fake"
    llm._client = FakeClient(responses)
    return llm


def test_generate_returns_text_unchanged_when_response_completes_normally():
    llm = make_llm([fake_response("end_turn", "respuesta completa")])
    result = llm.generate(system="sys", messages=[{"role": "user", "content": "hola"}])
    assert result == "respuesta completa"


def test_generate_appends_visible_note_when_truncated_by_max_tokens():
    """Antes de este fix, un stop_reason == "max_tokens" se devolvía como si
    fuera una respuesta completa, sin ningún indicio de que se cortó a mitad
    de oración (ver ARCHITECTURE_AUDIT.md, hallazgo 14.1)."""
    llm = make_llm([fake_response("max_tokens", "esto se corta a la mit")])
    result = llm.generate(system="sys", messages=[{"role": "user", "content": "hola"}])
    assert result.startswith("esto se corta a la mit")
    assert "truncada" in result


def test_generate_requests_a_higher_output_limit_than_the_original_1024():
    llm = make_llm([fake_response("end_turn", "ok")])
    llm.generate(system="sys", messages=[{"role": "user", "content": "hola"}])
    assert llm._client.messages.calls[0]["max_tokens"] == MAX_OUTPUT_TOKENS
    assert MAX_OUTPUT_TOKENS > 1024


def test_generate_sends_system_prompt_with_cache_control():
    """El system prompt de Snarf (identidad) es idéntico en cada llamada;
    marcarlo como cacheable ahorra costo real en cada mensaje del chat."""
    llm = make_llm([fake_response("end_turn", "ok")])
    llm.generate(system="el prompt de identidad", messages=[{"role": "user", "content": "hola"}])
    sent_system = llm._client.messages.calls[0]["system"]
    assert sent_system == [
        {
            "type": "text",
            "text": "el prompt de identidad",
            "cache_control": {"type": "ephemeral", "ttl": CACHE_TTL},
        }
    ]


def test_generate_marks_the_last_message_as_a_cache_breakpoint():
    """El historial de conversación se reconstruye idéntico en cada turno
    (EpisodicMemory.recent), así que también es cacheable — sin esto se
    reprocesaba entero y sin descuento en cada mensaje."""
    llm = make_llm([fake_response("end_turn", "ok")])
    llm.generate(
        system="sys",
        messages=[
            {"role": "user", "content": "primer turno"},
            {"role": "assistant", "content": "respuesta previa"},
            {"role": "user", "content": "turno actual"},
        ],
    )
    sent_messages = llm._client.messages.calls[0]["messages"]
    assert sent_messages[0] == {"role": "user", "content": "primer turno"}
    assert sent_messages[-1] == {
        "role": "user",
        "content": [
            {"type": "text", "text": "turno actual", "cache_control": {"type": "ephemeral", "ttl": CACHE_TTL}}
        ],
    }


def test_generate_does_not_mutate_the_caller_supplied_messages_list():
    """El marcado de cache_control debe ser efímero por-llamada: mutar el
    dict original rompería al orchestrator, que reconstruye `messages` desde
    memoria y podría reusar esas mismas referencias."""
    llm = make_llm([fake_response("end_turn", "ok")])
    original_messages = [{"role": "user", "content": "hola"}]
    llm.generate(system="sys", messages=original_messages)
    assert original_messages == [{"role": "user", "content": "hola"}]


def test_generate_marks_each_tool_loop_round_without_leaking_cache_control_between_rounds():
    """Cada ronda del loop de herramientas reprocesaba la conversación entera
    sin cachear, incluso dentro de la misma llamada — ahora cada ronda marca
    su propio último mensaje como punto de cacheo."""
    llm = make_llm(
        [
            fake_tool_use_response("call-1", "some_tool", {}),
            fake_response("end_turn", "listo"),
        ]
    )
    result = llm.generate(
        system="sys",
        messages=[{"role": "user", "content": "hacé algo"}],
        tools=[{"name": "some_tool"}],
        tool_handler=lambda name, input: {"ok": True},
    )
    assert result == "listo"

    first_call_messages = llm._client.messages.calls[0]["messages"]
    assert first_call_messages[-1]["content"] == [
        {"type": "text", "text": "hacé algo", "cache_control": {"type": "ephemeral", "ttl": CACHE_TTL}}
    ]

    second_call_messages = llm._client.messages.calls[1]["messages"]
    # El mensaje de assistant (tool_use) del medio no lleva cache_control propio.
    assert second_call_messages[1]["content"][0].type == "tool_use"
    tool_result_block = second_call_messages[-1]["content"][-1]
    assert tool_result_block["cache_control"] == {"type": "ephemeral", "ttl": CACHE_TTL}
    assert tool_result_block["type"] == "tool_result"


def test_generate_records_token_usage_for_cost_tracking(monkeypatch):
    from snarf.capabilities import anthropic_llm as module

    recorded = []
    monkeypatch.setattr(module.usage_tracker, "record_anthropic_call", lambda *a, **k: recorded.append((a, k)))

    usage = SimpleNamespace(input_tokens=100, output_tokens=50, cache_creation_input_tokens=0, cache_read_input_tokens=0)
    llm = make_llm([fake_response("end_turn", "ok", usage=usage)])
    llm.generate(system="sys", messages=[{"role": "user", "content": "hola"}])

    assert len(recorded) == 1
    args, _ = recorded[0]
    assert args[0] == "claude-sonnet-5"
    assert args[1] == 100
    assert args[2] == 50


def test_generate_does_not_record_usage_when_response_has_no_usage_info(monkeypatch):
    from snarf.capabilities import anthropic_llm as module

    recorded = []
    monkeypatch.setattr(module.usage_tracker, "record_anthropic_call", lambda *a, **k: recorded.append((a, k)))

    llm = make_llm([fake_response("end_turn", "ok")])
    llm.generate(system="sys", messages=[{"role": "user", "content": "hola"}])

    assert recorded == []
