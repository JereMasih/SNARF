from snarf.capabilities.anthropic_llm import LLMResponse
from snarf.specialists.gmail_digest import GmailDigestSpecialist


class FakeGmail:
    def __init__(self, messages):
        self._messages = messages

    def list_messages(self, max_results=20):
        return self._messages[:max_results]


class FakeLLM:
    def __init__(self, available=True, response="respuesta interpretada"):
        self.available = available
        self._response = response
        self.calls = []

    def generate(self, system, messages):
        self.calls.append((system, messages))
        return LLMResponse(text=self._response, speech=self._response)


def make_specialist(tmp_path, monkeypatch, messages=None, llm_available=True, llm_response="interpretado"):
    from snarf.specialists import gmail_digest as module

    monkeypatch.setattr(module, "CACHE_DIR", tmp_path / "gmail_digest")
    gmail = FakeGmail(messages or [])
    llm = FakeLLM(available=llm_available, response=llm_response)
    return GmailDigestSpecialist(gmail, lambda: llm, "fundador"), llm


def test_cached_digest_is_none_before_any_refresh(tmp_path, monkeypatch):
    specialist, _ = make_specialist(tmp_path, monkeypatch)
    assert specialist.cached_digest() is None


def test_refresh_with_no_messages_does_not_call_llm(tmp_path, monkeypatch):
    specialist, llm = make_specialist(tmp_path, monkeypatch, messages=[])
    digest = specialist.refresh()
    assert digest["message_count"] == 0
    assert "No hay mensajes" in digest["digest_text"]
    assert llm.calls == []


def test_refresh_without_llm_available_reports_it_clearly(tmp_path, monkeypatch):
    messages = [{"from": "a@b.com", "subject": "hola", "snippet": "..."}]
    specialist, llm = make_specialist(tmp_path, monkeypatch, messages=messages, llm_available=False)
    digest = specialist.refresh()
    assert "falta configurar" in digest["digest_text"].lower()
    assert llm.calls == []


def test_refresh_calls_llm_with_message_listing(tmp_path, monkeypatch):
    messages = [{"from": "a@b.com", "subject": "importante", "snippet": "revisar ya"}]
    specialist, llm = make_specialist(tmp_path, monkeypatch, messages=messages, llm_response="categorizado")
    digest = specialist.refresh()
    assert digest["digest_text"] == "categorizado"
    assert digest["message_count"] == 1
    assert len(llm.calls) == 1
    _, sent_messages = llm.calls[0]
    assert "importante" in sent_messages[0]["content"]


def test_refresh_persists_to_cache_and_cached_digest_reads_it_back(tmp_path, monkeypatch):
    messages = [{"from": "a@b.com", "subject": "x", "snippet": "y"}]
    specialist, _ = make_specialist(tmp_path, monkeypatch, messages=messages)
    written = specialist.refresh()
    assert specialist.cached_digest() == written


def test_handle_returns_digest_text_directly(tmp_path, monkeypatch):
    messages = [{"from": "a@b.com", "subject": "x", "snippet": "y"}]
    specialist, _ = make_specialist(tmp_path, monkeypatch, messages=messages, llm_response="el resumen")
    assert specialist.handle("interpretar", {}) == "el resumen"


def test_refresh_records_latest_message_id_for_cheap_staleness_checks(tmp_path, monkeypatch):
    messages = [{"id": "msg-2", "from": "a@b.com", "subject": "x", "snippet": "y"}]
    specialist, _ = make_specialist(tmp_path, monkeypatch, messages=messages)
    digest = specialist.refresh()
    assert digest["latest_message_id"] == "msg-2"


def test_refresh_with_no_messages_has_no_latest_message_id(tmp_path, monkeypatch):
    specialist, _ = make_specialist(tmp_path, monkeypatch, messages=[])
    digest = specialist.refresh()
    assert digest["latest_message_id"] is None


def test_refresh_includes_structured_message_references_with_dates_and_ids(tmp_path, monkeypatch):
    messages = [
        {"id": "msg-1", "from": "a@b.com", "subject": "hola", "date": "Tue, 29 Jul 2026 10:00:00 -0300", "snippet": "x"}
    ]
    specialist, _ = make_specialist(tmp_path, monkeypatch, messages=messages)
    digest = specialist.refresh()
    assert digest["messages"] == [{"id": "msg-1", "subject": "hola", "from": "a@b.com", "date": "Tue, 29 Jul 2026 10:00:00 -0300"}]
