from types import SimpleNamespace

from snarf.capabilities.anthropic_llm import MAX_OUTPUT_TOKENS, AnthropicLLM


class FakeTextBlock:
    type = "text"

    def __init__(self, text):
        self.text = text


def fake_response(stop_reason, text):
    return SimpleNamespace(stop_reason=stop_reason, content=[FakeTextBlock(text)])


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
        {"type": "text", "text": "el prompt de identidad", "cache_control": {"type": "ephemeral"}}
    ]
