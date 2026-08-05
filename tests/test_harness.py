from snarf.runtime import harness


def test_compare_returns_one_result_per_requested_provider(monkeypatch):
    class _FakeLLM:
        available = True

        def __init__(self, model):
            self.model = model

        def generate(self, system, messages):
            return harness.LLMResponse(text=f"respuesta de {self.model}", speech="")

    monkeypatch.setattr(harness, "_build_provider", lambda provider, model: _FakeLLM(model))

    results = harness.compare("system prompt", [{"role": "user", "content": "hola"}], {"anthropic": "claude-haiku-4-5", "xai": "grok-4-1-fast"})

    assert {r.provider for r in results} == {"anthropic", "xai"}
    assert all(r.error is None for r in results)
    assert all(r.response is not None for r in results)


def test_compare_reports_unavailable_provider_without_touching_the_others(monkeypatch):
    class _UnavailableLLM:
        available = False

    class _AvailableLLM:
        available = True

        def generate(self, system, messages):
            return harness.LLMResponse(text="ok", speech="")

    def fake_build(provider, model):
        return _UnavailableLLM() if provider == "gemini" else _AvailableLLM()

    monkeypatch.setattr(harness, "_build_provider", fake_build)

    results = harness.compare("s", [], {"gemini": "gemini-3.1-flash-lite", "anthropic": "claude-haiku-4-5"})

    by_provider = {r.provider: r for r in results}
    assert by_provider["gemini"].error == "sin credencial real configurada"
    assert by_provider["gemini"].response is None
    assert by_provider["anthropic"].error is None
    assert by_provider["anthropic"].response.text == "ok"


def test_compare_reports_a_real_failure_from_one_provider_without_crashing(monkeypatch):
    class _BrokenLLM:
        available = True

        def generate(self, system, messages):
            raise RuntimeError("credit balance is too low")

    monkeypatch.setattr(harness, "_build_provider", lambda provider, model: _BrokenLLM())

    results = harness.compare("s", [], {"anthropic": "claude-haiku-4-5"})

    assert results[0].error == "credit balance is too low"
    assert results[0].response is None


def test_compare_with_no_providers_returns_an_empty_list():
    assert harness.compare("s", [], {}) == []
