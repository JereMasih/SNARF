from snarf.capabilities.anthropic_llm import LLMResponse
from snarf.runtime import llm_routing, vision_demo


class FakeLLM:
    def __init__(self, response="respuesta de prueba"):
        self.available = True
        self._response = response
        self.calls = []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        return LLMResponse(text=self._response, speech=self._response)


def _isolate_turn_counts(monkeypatch):
    monkeypatch.setattr(vision_demo, "_turn_counts", {})


def test_demo_reply_calls_the_configured_llm_without_tools(monkeypatch):
    _isolate_turn_counts(monkeypatch)
    fake = FakeLLM(response="hola, soy la demo de Snarf")
    monkeypatch.setattr(llm_routing, "build_resilient_llm", lambda role: fake)

    result = vision_demo.demo_reply("lead-1", "qué podés hacer?", [])

    assert result["reply"] == "hola, soy la demo de Snarf"
    assert result["limit_reached"] is False
    assert len(fake.calls) == 1
    kwargs = fake.calls[0]
    assert "tools" not in kwargs
    assert "tool_handler" not in kwargs
    assert kwargs["system"] == vision_demo.SYSTEM_PROMPT
    assert kwargs["messages"][-1] == {"role": "user", "content": "qué podés hacer?"}


def test_demo_reply_appends_to_existing_history(monkeypatch):
    _isolate_turn_counts(monkeypatch)
    fake = FakeLLM()
    monkeypatch.setattr(llm_routing, "build_resilient_llm", lambda role: fake)
    history = [{"role": "user", "content": "hola"}, {"role": "assistant", "content": "hola, ¿en qué te ayudo?"}]

    vision_demo.demo_reply("lead-2", "contame más", history)

    assert fake.calls[0]["messages"] == history + [{"role": "user", "content": "contame más"}]


def test_demo_reply_decrements_turns_left(monkeypatch):
    _isolate_turn_counts(monkeypatch)
    monkeypatch.setattr(vision_demo, "MAX_DEMO_TURNS", 3)
    fake = FakeLLM()
    monkeypatch.setattr(llm_routing, "build_resilient_llm", lambda role: fake)

    first = vision_demo.demo_reply("lead-3", "uno", [])
    second = vision_demo.demo_reply("lead-3", "dos", [])

    assert first["turns_left"] == 2
    assert second["turns_left"] == 1


def test_demo_reply_cuts_off_at_the_turn_cap_without_calling_the_model_again(monkeypatch):
    _isolate_turn_counts(monkeypatch)
    monkeypatch.setattr(vision_demo, "MAX_DEMO_TURNS", 2)
    fake = FakeLLM()
    monkeypatch.setattr(llm_routing, "build_resilient_llm", lambda role: fake)

    vision_demo.demo_reply("lead-4", "uno", [])
    vision_demo.demo_reply("lead-4", "dos", [])
    third = vision_demo.demo_reply("lead-4", "tres", [])

    assert third["reply"] == vision_demo.CLOSING_MESSAGE
    assert third["limit_reached"] is True
    assert third["turns_left"] == 0
    assert len(fake.calls) == 2


def test_demo_reply_tracks_turns_independently_per_lead(monkeypatch):
    _isolate_turn_counts(monkeypatch)
    monkeypatch.setattr(vision_demo, "MAX_DEMO_TURNS", 1)
    fake = FakeLLM()
    monkeypatch.setattr(llm_routing, "build_resilient_llm", lambda role: fake)

    a = vision_demo.demo_reply("lead-a", "hola", [])
    b = vision_demo.demo_reply("lead-b", "hola", [])

    assert a["limit_reached"] is False
    assert b["limit_reached"] is False
    assert len(fake.calls) == 2
