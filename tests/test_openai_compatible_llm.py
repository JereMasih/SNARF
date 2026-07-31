import json
from types import SimpleNamespace

from snarf.capabilities.openai_compatible_llm import MAX_TOOL_ROUNDS, OpenAICompatibleLLM


class FakeToolCall:
    def __init__(self, id, name, arguments):
        self.id = id
        self.function = SimpleNamespace(name=name, arguments=json.dumps(arguments))

    def model_dump(self):
        return {"id": self.id, "type": "function", "function": {"name": self.function.name, "arguments": self.function.arguments}}


def fake_response(finish_reason, content, tool_calls=None, usage=None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
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
    llm._client = FakeClient(responses)
    return llm


def test_generate_returns_text_unchanged_when_response_completes_normally():
    llm = make_llm([fake_response("stop", "respuesta completa")])
    result = llm.generate(system="sys", messages=[{"role": "user", "content": "hola"}])
    assert result.text == "respuesta completa"


def test_generate_appends_visible_note_when_truncated_by_length():
    llm = make_llm([fake_response("length", "esto se corta a la mit")])
    result = llm.generate(system="sys", messages=[{"role": "user", "content": "hola"}])
    assert result.text.startswith("esto se corta a la mit")
    assert "truncada" in result.text


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


def test_generate_raises_a_clear_error_without_a_client():
    llm = OpenAICompatibleLLM.__new__(OpenAICompatibleLLM)
    llm._client = None
    llm._api_key_env = "XAI_API_KEY"
    try:
        llm.generate(system="sys", messages=[])
        assert False, "debería haber lanzado RuntimeError"
    except RuntimeError as e:
        assert "XAI_API_KEY" in str(e)
