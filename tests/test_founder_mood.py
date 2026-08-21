from snarf.specialists.founder_mood import FounderMood


class FakeMemory:
    def __init__(self, entries=None):
        self._entries = entries or []

    def recent(self, n=10, conversation_id=None):
        return self._entries[-n:]


class FakeLLM:
    def __init__(self, available=True, response="hecho: el fundador mencionó estar cansado.", raise_error=False):
        self.available = available
        self._response = response
        self._raise_error = raise_error
        self.calls = []

    def generate(self, system, messages):
        self.calls.append({"system": system, "messages": messages})
        if self._raise_error:
            raise RuntimeError("fallo simulado")
        from snarf.capabilities.anthropic_llm import LLMResponse

        return LLMResponse(text=self._response, speech=self._response)


def make_mood(tmp_path, monkeypatch, entries=None, llm_factory=None):
    monkeypatch.chdir(tmp_path)
    return FounderMood(FakeMemory(entries), "fundador", llm_factory=llm_factory)


def test_get_snapshot_returns_none_before_any_refresh(tmp_path, monkeypatch):
    mood = make_mood(tmp_path, monkeypatch)
    assert mood.get_snapshot() is None


def test_refresh_without_any_real_messages_says_so_explicitly(tmp_path, monkeypatch):
    mood = make_mood(tmp_path, monkeypatch, entries=[])
    snapshot = mood.refresh()
    assert "sin señales claras" in snapshot["report"]


def test_refresh_never_calls_the_llm_without_real_messages(tmp_path, monkeypatch):
    llm = FakeLLM()
    mood = make_mood(tmp_path, monkeypatch, entries=[], llm_factory=lambda: llm)
    mood.refresh()
    assert llm.calls == []


def test_refresh_sends_only_real_user_inputs_to_the_llm(tmp_path, monkeypatch):
    llm = FakeLLM(response="inferencia: parece entusiasmado con el proyecto.")
    entries = [
        {"input": "estoy re contento con como quedó esto", "response": "que bueno"},
        {"input": "sigamos con la siguiente fase", "response": "dale"},
    ]
    mood = make_mood(tmp_path, monkeypatch, entries=entries, llm_factory=lambda: llm)

    snapshot = mood.refresh()

    assert snapshot["report"] == "inferencia: parece entusiasmado con el proyecto."
    sent_content = llm.calls[0]["messages"][0]["content"]
    assert "estoy re contento con como quedó esto" in sent_content
    assert "sigamos con la siguiente fase" in sent_content
    assert isinstance(snapshot["generated_at"], float)
    assert mood.get_snapshot() == snapshot


def test_refresh_without_llm_factory_says_so_explicitly(tmp_path, monkeypatch):
    entries = [{"input": "hola", "response": "hola"}]
    mood = make_mood(tmp_path, monkeypatch, entries=entries)
    snapshot = mood.refresh()
    assert "falta configurar el modelo de lenguaje" in snapshot["report"]


def test_refresh_degrades_gracefully_on_llm_error(tmp_path, monkeypatch):
    entries = [{"input": "hola", "response": "hola"}]
    llm = FakeLLM(raise_error=True)
    mood = make_mood(tmp_path, monkeypatch, entries=entries, llm_factory=lambda: llm)
    snapshot = mood.refresh()
    assert "No se pudo generar la interpretación" in snapshot["report"]


def test_snapshot_is_namespaced_per_user(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    entries = [{"input": "hola", "response": "hola"}]
    llm = FakeLLM(response="reporte de fundador")
    FounderMood(FakeMemory(entries), "fundador", llm_factory=lambda: llm).refresh()
    llm2 = FakeLLM(response="reporte de otro")
    FounderMood(FakeMemory(entries), "otro-usuario", llm_factory=lambda: llm2).refresh()

    assert FounderMood(FakeMemory(), "fundador").get_snapshot()["report"] == "reporte de fundador"
    assert FounderMood(FakeMemory(), "otro-usuario").get_snapshot()["report"] == "reporte de otro"
