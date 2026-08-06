import json
from types import SimpleNamespace

from snarf.capabilities.anthropic_llm import MAX_CONTINUATIONS
from snarf.capabilities.openai_compatible_llm import MAX_TOOL_ROUNDS, OpenAICompatibleLLM


class FakeToolCall:
    def __init__(self, id, name, arguments):
        self.id = id
        self.function = SimpleNamespace(name=name, arguments=json.dumps(arguments))

    def model_dump(self):
        return {"id": self.id, "type": "function", "function": {"name": self.function.name, "arguments": self.function.arguments}}


def fake_response(finish_reason, content, tool_calls=None, usage=None, reasoning=None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls, reasoning=reasoning)
    return SimpleNamespace(choices=[SimpleNamespace(finish_reason=finish_reason, message=message)], usage=usage)


class FakeCompletions:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


class FakeClient:
    def __init__(self, responses):
        self.chat = SimpleNamespace(completions=FakeCompletions(responses))


def make_llm(responses):
    llm = OpenAICompatibleLLM.__new__(OpenAICompatibleLLM)
    llm.model = "gpt-5"
    llm._api_key_env = "OPENAI_API_KEY"
    llm._vendor = "openai"
    llm._api_key = "fake"
    llm._local = False
    llm._client = FakeClient(responses)
    return llm


class FakeChunk:
    """Mismo shape que un ChatCompletionChunk real de streaming (ver
    _consume_stream) — `choices` vacío + `usage` seteado simula el chunk
    final de `stream_options={"include_usage": True}`."""

    def __init__(self, content=None, reasoning=None, tool_calls=None, finish_reason=None, usage=None):
        if content is None and reasoning is None and tool_calls is None and finish_reason is None:
            self.choices = []
        else:
            delta = SimpleNamespace(content=content, reasoning=reasoning, tool_calls=tool_calls)
            self.choices = [SimpleNamespace(delta=delta, finish_reason=finish_reason)]
        self.usage = usage


class FakeToolCallDelta:
    def __init__(self, index, id=None, name=None, arguments=None):
        self.index = index
        self.id = id
        self.function = SimpleNamespace(name=name, arguments=arguments) if (name is not None or arguments is not None) else None


class FakeStreamingCompletions:
    def __init__(self, streams):
        self._streams = list(streams)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return iter(self._streams.pop(0))


class FakeStreamingClient:
    def __init__(self, streams):
        self.chat = SimpleNamespace(completions=FakeStreamingCompletions(streams))


def make_local_llm(streams):
    llm = OpenAICompatibleLLM.__new__(OpenAICompatibleLLM)
    llm.model = "mlx-community/Qwen3-4B-Instruct-2507-4bit"
    llm._api_key_env = "OPENAI_API_KEY"
    llm._vendor = "openai"
    llm._api_key = "not-needed"
    llm._local = True
    llm._client = FakeStreamingClient(streams)
    return llm


def test_generate_returns_text_unchanged_when_response_completes_normally():
    llm = make_llm([fake_response("stop", "respuesta completa")])
    result = llm.generate(system="sys", messages=[{"role": "user", "content": "hola"}])
    assert result.text == "respuesta completa"


def test_generate_captures_the_reasoning_field_when_the_provider_exposes_it():
    """Modelos locales 'thinking' (ej. Qwen3.5 vía mlx_lm.server) devuelven el
    razonamiento en un campo `reasoning` aparte de `content`, fuera del
    schema estándar de OpenAI — no debe perderse, es la fuente real del
    desplegable de 'pensamiento' en la interfaz."""
    llm = make_llm([fake_response("stop", "OK", reasoning="pensando paso a paso...")])
    result = llm.generate(system="sys", messages=[{"role": "user", "content": "hola"}])
    assert result.thinking == "pensando paso a paso..."


def test_generate_thinking_is_none_when_the_provider_does_not_expose_it():
    llm = make_llm([fake_response("stop", "OK")])
    result = llm.generate(system="sys", messages=[{"role": "user", "content": "hola"}])
    assert result.thinking is None


def test_generate_appends_visible_note_when_truncated_by_length():
    """Igual que en AnthropicLLM: primero se reintenta continuar
    (MAX_CONTINUATIONS veces) — la nota solo aparece si el corte persiste."""
    llm = make_llm([fake_response("length", "esto se corta a la mit") for _ in range(MAX_CONTINUATIONS + 1)])
    result = llm.generate(system="sys", messages=[{"role": "user", "content": "hola"}])
    assert result.text.startswith("esto se corta a la mit")
    assert "truncada" in result.text


def test_generate_continues_automatically_when_still_truncated_by_length():
    llm = make_llm(
        [
            fake_response("length", "primera parte, se corta"),
            fake_response("stop", " segunda parte, ahora sí termina"),
        ]
    )
    result = llm.generate(system="sys", messages=[{"role": "user", "content": "escribime algo largo"}])
    assert result.text == "primera parte, se corta segunda parte, ahora sí termina"
    assert "truncada" not in result.text
    assert len(llm._client.chat.completions.calls) == 2


def test_generate_records_a_real_duration_ms_for_non_local_providers(monkeypatch):
    # "Tiempos, data útil" al hacer click en el feed del cerebro (pedido
    # explícito) — antes duration_ms no se medía en absoluto para este
    # camino (no-streaming, proveedores cloud).
    captured = {}
    monkeypatch.setattr(
        "snarf.capabilities.openai_compatible_llm.usage_tracker.record_generic_llm_call",
        lambda *a, **kw: captured.update(kw),
    )
    llm = make_llm([fake_response("stop", "ok", usage=SimpleNamespace(prompt_tokens=10, completion_tokens=2))])
    llm.generate(system="sys", messages=[{"role": "user", "content": "hola"}])
    assert isinstance(captured["duration_ms"], float)
    assert captured["duration_ms"] >= 0


def test_generate_records_a_real_duration_ms_for_local_streaming_providers(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "snarf.capabilities.openai_compatible_llm.usage_tracker.record_generic_llm_call",
        lambda *a, **kw: captured.update(kw),
    )
    stream = [
        FakeChunk(content="hola"),
        FakeChunk(finish_reason="stop"),
        FakeChunk(usage=SimpleNamespace(prompt_tokens=5, completion_tokens=1)),
    ]
    llm = make_local_llm([stream])
    llm.generate(system="sys", messages=[{"role": "user", "content": "hola"}])
    assert isinstance(captured["duration_ms"], float)
    assert captured["duration_ms"] >= 0


def test_local_provider_builds_a_client_without_a_real_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    llm = OpenAICompatibleLLM(model="local-model", base_url="http://localhost:8080/v1", local=True)
    assert llm.available is True


def test_local_provider_uses_a_short_timeout_instead_of_the_sdk_default_of_ten_minutes():
    """Bug real evitado: un modelo local puede tardar bastante en frío (el
    prefill de un prompt grande puede llevar minutos, ver ADR de esta ronda)
    — con el timeout default de la SDK (10 min) el chat quedaría colgado
    mucho tiempo antes de caer al fallback. LOCAL_TIMEOUT_SECONDS lo corta
    mucho antes, pero con margen real por encima del peor caso en frío
    medido (no tan corto como para disparar un fallback falso apenas el
    prefijo todavía no está cacheado)."""
    from snarf.capabilities.openai_compatible_llm import LOCAL_TIMEOUT_SECONDS

    llm = OpenAICompatibleLLM(model="local-model", base_url="http://localhost:8080/v1", local=True)
    assert llm._client.timeout == LOCAL_TIMEOUT_SECONDS


def test_non_local_provider_keeps_the_sdk_default_timeout(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key")
    llm = OpenAICompatibleLLM(model="gpt-5")
    # Default real de la SDK cuando no se pasa `timeout` explícito — no se
    # toca para proveedores cloud reales, solo se acota para el local.
    assert llm._client.timeout.read == 600.0


def test_local_provider_disables_the_sdks_silent_retries():
    """Bug real medido en vivo esta ronda: con el default de la SDK
    (max_retries=2), un timeout de LOCAL_TIMEOUT_SECONDS no corta ahí —
    la SDK reintenta la misma request 2 veces más antes de rendirse,
    convirtiendo el timeout "corto" en hasta 270s reales (confirmado viendo
    un segundo request idéntico en el log de mlx_lm.server). El fallback a
    Anthropic ya cumple el rol de reintento real; la SDK no debe duplicarlo."""
    llm = OpenAICompatibleLLM(model="local-model", base_url="http://localhost:8080/v1", local=True)
    assert llm._client.max_retries == 0


def test_non_local_provider_keeps_the_sdks_default_retries(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key")
    llm = OpenAICompatibleLLM(model="gpt-5")
    assert llm._client.max_retries == 2


def test_generate_prefixes_the_system_message():
    llm = make_llm([fake_response("stop", "ok")])
    llm.generate(system="instrucciones del sistema", messages=[{"role": "user", "content": "hola"}])
    sent = llm._client.chat.completions.calls[0]["messages"]
    assert sent[0] == {"role": "system", "content": "instrucciones del sistema"}


def test_generate_calls_the_tool_handler_and_continues_the_loop():
    calls = []

    def tool_handler(name, args):
        calls.append((name, args))
        return {"ok": True}

    tool_call = FakeToolCall("call-1", "buscar_algo", {"query": "test"})
    llm = make_llm(
        [
            fake_response("tool_calls", None, tool_calls=[tool_call]),
            fake_response("stop", "resultado final"),
        ]
    )
    result = llm.generate(
        system="sys",
        messages=[{"role": "user", "content": "hola"}],
        tools=[{"name": "buscar_algo", "description": "d", "input_schema": {"type": "object", "properties": {}}}],
        tool_handler=tool_handler,
    )
    assert calls == [("buscar_algo", {"query": "test"})]
    assert result.text == "resultado final"

    second_call_messages = llm._client.chat.completions.calls[1]["messages"]
    assert second_call_messages[-1] == {"role": "tool", "tool_call_id": "call-1", "content": json.dumps({"ok": True}, ensure_ascii=False)}


def test_generate_translates_tools_to_the_function_calling_shape():
    llm = make_llm([fake_response("stop", "ok")])
    llm.generate(
        system="sys",
        messages=[{"role": "user", "content": "hola"}],
        tools=[{"name": "mi_tool", "description": "descripción", "input_schema": {"type": "object", "properties": {}}}],
    )
    sent_tools = llm._client.chat.completions.calls[0]["tools"]
    assert sent_tools == [
        {"type": "function", "function": {"name": "mi_tool", "description": "descripción", "parameters": {"type": "object", "properties": {}}}}
    ]


def test_generate_translates_vision_image_blocks_to_image_url():
    llm = make_llm([fake_response("stop", "descripción de la imagen")])
    llm.generate(
        system="sys",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "describí esto"},
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "ZmFrZQ=="}},
                ],
            }
        ],
    )
    sent = llm._client.chat.completions.calls[0]["messages"][1]["content"]
    assert sent[0] == {"type": "text", "text": "describí esto"}
    assert sent[1] == {"type": "image_url", "image_url": {"url": "data:image/png;base64,ZmFrZQ=="}}


def test_generate_gives_up_after_max_tool_rounds():
    responses = [fake_response("tool_calls", None, tool_calls=[FakeToolCall("c", "t", {})]) for _ in range(MAX_TOOL_ROUNDS)]
    llm = make_llm(responses)
    result = llm.generate(
        system="sys",
        messages=[{"role": "user", "content": "hola"}],
        tools=[{"name": "t", "description": "d", "input_schema": {"type": "object", "properties": {}}}],
        tool_handler=lambda name, args: {},
    )
    assert "demasiadas consultas" in result.text


def test_available_is_false_without_a_client():
    llm = OpenAICompatibleLLM.__new__(OpenAICompatibleLLM)
    llm._client = None
    assert llm.available is False


def test_local_provider_uses_a_bigger_timeout_as_a_secondary_safety_net():
    """LOCAL_TIMEOUT_SECONDS subió de 150s a 240s esta ronda — sigue
    existiendo como red de seguridad adicional, pero el mecanismo principal
    ahora es el timeout de inactividad entre chunks del streaming (ver los
    tests de _consume_stream/generate más abajo)."""
    from snarf.capabilities.openai_compatible_llm import LOCAL_TIMEOUT_SECONDS

    assert LOCAL_TIMEOUT_SECONDS == 240.0
    llm = OpenAICompatibleLLM(model="local-model", base_url="http://localhost:8080/v1", local=True)
    assert llm._client.timeout == LOCAL_TIMEOUT_SECONDS


def test_generate_streams_for_local_providers_and_accumulates_content():
    """Bug real que esto evita: sin streaming, el timeout de httpx cubre
    TODA la generación de una — con streaming pasa a cubrir solo la
    inactividad entre chunks, así que una respuesta lenta pero que sigue
    progresando ya no dispara un fallback falso."""
    stream = [
        FakeChunk(content="Hola"),
        FakeChunk(content=" mundo"),
        FakeChunk(finish_reason="stop"),
        FakeChunk(usage=SimpleNamespace(prompt_tokens=10, completion_tokens=2)),
    ]
    llm = make_local_llm([stream])
    result = llm.generate(system="sys", messages=[{"role": "user", "content": "hola"}])
    assert result.text == "Hola mundo"
    assert llm._client.chat.completions.calls[0]["stream"] is True
    assert llm._client.chat.completions.calls[0]["stream_options"] == {"include_usage": True}


def test_generate_streams_reasoning_separately_from_content_for_local_providers():
    stream = [
        FakeChunk(reasoning="pensando..."),
        FakeChunk(content="respuesta"),
        FakeChunk(finish_reason="stop"),
    ]
    llm = make_local_llm([stream])
    result = llm.generate(system="sys", messages=[{"role": "user", "content": "hola"}])
    assert result.text == "respuesta"
    assert result.thinking == "pensando..."


def test_generate_reassembles_a_streamed_tool_call_and_invokes_the_handler():
    calls = []

    def tool_handler(name, args):
        calls.append((name, args))
        return {"ok": True}

    first_stream = [
        FakeChunk(tool_calls=[FakeToolCallDelta(0, id="call-1", name="buscar_algo")]),
        FakeChunk(tool_calls=[FakeToolCallDelta(0, arguments='{"query"')]),
        FakeChunk(tool_calls=[FakeToolCallDelta(0, arguments=': "test"}')]),
        FakeChunk(finish_reason="tool_calls"),
    ]
    second_stream = [FakeChunk(content="resultado final"), FakeChunk(finish_reason="stop")]
    llm = make_local_llm([first_stream, second_stream])
    result = llm.generate(
        system="sys",
        messages=[{"role": "user", "content": "hola"}],
        tools=[{"name": "buscar_algo", "description": "d", "input_schema": {"type": "object", "properties": {}}}],
        tool_handler=tool_handler,
    )
    assert calls == [("buscar_algo", {"query": "test"})]
    assert result.text == "resultado final"


def test_generate_gives_up_after_max_tool_rounds_when_streaming():
    stream = [
        FakeChunk(tool_calls=[FakeToolCallDelta(0, id="c", name="t", arguments="{}")]),
        FakeChunk(finish_reason="tool_calls"),
    ]
    llm = make_local_llm([stream for _ in range(MAX_TOOL_ROUNDS)])
    result = llm.generate(
        system="sys",
        messages=[{"role": "user", "content": "hola"}],
        tools=[{"name": "t", "description": "d", "input_schema": {"type": "object", "properties": {}}}],
        tool_handler=lambda name, args: {},
    )
    assert "demasiadas consultas" in result.text


def test_generate_continues_automatically_when_still_truncated_by_length_while_streaming():
    first_stream = [FakeChunk(content="primera parte, se corta"), FakeChunk(finish_reason="length")]
    second_stream = [FakeChunk(content=" segunda parte, ahora sí termina"), FakeChunk(finish_reason="stop")]
    llm = make_local_llm([first_stream, second_stream])
    result = llm.generate(system="sys", messages=[{"role": "user", "content": "escribime algo largo"}])
    assert result.text == "primera parte, se corta segunda parte, ahora sí termina"
    assert "truncada" not in result.text
    assert len(llm._client.chat.completions.calls) == 2


def test_generate_raises_a_clear_error_without_a_client():
    llm = OpenAICompatibleLLM.__new__(OpenAICompatibleLLM)
    llm._client = None
    llm._api_key_env = "XAI_API_KEY"
    try:
        llm.generate(system="sys", messages=[])
        assert False, "debería haber lanzado RuntimeError"
    except RuntimeError as e:
        assert "XAI_API_KEY" in str(e)
