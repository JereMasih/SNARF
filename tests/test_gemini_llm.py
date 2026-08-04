import pytest
from google.genai import types

from snarf.capabilities.gemini_llm import MAX_TOOL_ROUNDS, GeminiLLM
from snarf.telemetry import events, usage_tracker


@pytest.fixture(autouse=True)
def _isolate_usage_tracking(tmp_path, monkeypatch):
    # llm.generate() real acá adentro dispara usage_tracker.record_generic_llm_call
    # de verdad — sin esto, cada corrida de la suite completa escribía entradas
    # sintéticas (gemini-3-pro-preview, ~10 tokens) directo en el
    # data/usage_log.jsonl y data/telemetry_events.jsonl REALES del proyecto.
    # Bug real encontrado por el fundador viéndolo ahogar su Vista HUD real.
    monkeypatch.setattr(usage_tracker, "DEFAULT_PATH", tmp_path / "usage_log.jsonl")
    monkeypatch.setattr(events, "DEFAULT_PATH", tmp_path / "telemetry_events.jsonl")


def fake_response(finish_reason, parts, usage_prompt=10, usage_candidates=5):
    content = types.Content(role="model", parts=parts)
    candidate = types.Candidate(content=content, finish_reason=finish_reason)
    usage = types.GenerateContentResponseUsageMetadata(
        prompt_token_count=usage_prompt, candidates_token_count=usage_candidates
    )
    return types.GenerateContentResponse(candidates=[candidate], usage_metadata=usage)


class FakeModels:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


class FakeClient:
    def __init__(self, responses):
        self.models = FakeModels(responses)


def make_llm(responses):
    llm = GeminiLLM.__new__(GeminiLLM)
    llm.model = "gemini-3-pro-preview"
    llm._api_key = "fake"
    llm._client = FakeClient(responses)
    return llm


def test_generate_returns_text_unchanged_when_response_completes_normally():
    llm = make_llm([fake_response("STOP", [types.Part.from_text(text="respuesta completa")])])
    result = llm.generate(system="sys", messages=[{"role": "user", "content": "hola"}])
    assert result.text == "respuesta completa"


def test_generate_appends_visible_note_when_truncated_by_max_tokens():
    llm = make_llm([fake_response("MAX_TOKENS", [types.Part.from_text(text="esto se corta a la mit")])])
    result = llm.generate(system="sys", messages=[{"role": "user", "content": "hola"}])
    assert result.text.startswith("esto se corta a la mit")
    assert "truncada" in result.text


def test_generate_passes_system_instruction_and_translates_roles():
    llm = make_llm([fake_response("STOP", [types.Part.from_text(text="ok")])])
    llm.generate(
        system="instrucciones del sistema",
        messages=[{"role": "user", "content": "hola"}, {"role": "assistant", "content": "respuesta previa"}],
    )
    call = llm._client.models.calls[0]
    assert call["config"].system_instruction == "instrucciones del sistema"
    assert [c.role for c in call["contents"]] == ["user", "model"]


def test_generate_calls_the_tool_handler_and_continues_the_loop():
    calls = []

    def tool_handler(name, args):
        calls.append((name, args))
        return {"ok": True}

    tool_call_response = fake_response("STOP", [types.Part(function_call=types.FunctionCall(name="buscar_algo", args={"query": "test"}))])
    final_response = fake_response("STOP", [types.Part.from_text(text="resultado final")])
    llm = make_llm([tool_call_response, final_response])

    result = llm.generate(
        system="sys",
        messages=[{"role": "user", "content": "hola"}],
        tools=[{"name": "buscar_algo", "description": "d", "input_schema": {"type": "object", "properties": {}}}],
        tool_handler=tool_handler,
    )
    assert calls == [("buscar_algo", {"query": "test"})]
    assert result.text == "resultado final"


def test_generate_translates_vision_image_blocks():
    import base64

    llm = make_llm([fake_response("STOP", [types.Part.from_text(text="descripción")])])
    llm.generate(
        system="sys",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "describí esto"},
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64.b64encode(b"fake").decode()}},
                ],
            }
        ],
    )
    sent_parts = llm._client.models.calls[0]["contents"][0].parts
    assert sent_parts[0].text == "describí esto"
    assert sent_parts[1].inline_data.mime_type == "image/png"
    assert sent_parts[1].inline_data.data == b"fake"


def test_generate_gives_up_after_max_tool_rounds():
    responses = [
        fake_response("STOP", [types.Part(function_call=types.FunctionCall(name="t", args={}))]) for _ in range(MAX_TOOL_ROUNDS)
    ]
    llm = make_llm(responses)
    result = llm.generate(
        system="sys",
        messages=[{"role": "user", "content": "hola"}],
        tools=[{"name": "t", "description": "d", "input_schema": {"type": "object", "properties": {}}}],
        tool_handler=lambda name, args: {},
    )
    assert "demasiadas consultas" in result.text


def test_available_is_false_without_a_client():
    llm = GeminiLLM.__new__(GeminiLLM)
    llm._client = None
    assert llm.available is False


def test_generate_raises_a_clear_error_without_a_client():
    llm = GeminiLLM.__new__(GeminiLLM)
    llm._client = None
    try:
        llm.generate(system="sys", messages=[])
        assert False, "debería haber lanzado RuntimeError"
    except RuntimeError as e:
        assert "GEMINI_API_KEY" in str(e)
