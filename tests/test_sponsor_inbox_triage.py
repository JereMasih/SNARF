from snarf.capabilities.anthropic_llm import LLMResponse
from snarf.specialists.sales.sponsor_inbox_triage import DEFAULT_QUERY, SponsorInboxTriageSpecialist


class FakeGmail:
    def __init__(self, messages):
        self._messages = messages
        self.calls = []

    def list_messages(self, max_results=20, query=None):
        self.calls.append({"max_results": max_results, "query": query})
        return self._messages[:max_results]


class FakeLLM:
    def __init__(self, available=True, response="triage real"):
        self.available = available
        self._response = response
        self.calls = []

    def generate(self, system, messages):
        self.calls.append((system, messages))
        return LLMResponse(text=self._response, speech=self._response)


def make_specialist(tmp_path, monkeypatch, messages=None, llm_available=True, llm_response="triage"):
    from snarf.specialists.sales import sponsor_inbox_triage as module

    monkeypatch.setattr(module, "CACHE_DIR", tmp_path / "sponsor_inbox_triage")
    gmail = FakeGmail(messages or [])
    llm = FakeLLM(available=llm_available, response=llm_response)
    return SponsorInboxTriageSpecialist(gmail, lambda: llm, "fundador"), llm, gmail


def test_cached_triage_is_none_before_any_refresh(tmp_path, monkeypatch):
    specialist, _, _ = make_specialist(tmp_path, monkeypatch)
    assert specialist.cached_triage() is None


def test_refresh_uses_the_default_sponsor_query(tmp_path, monkeypatch):
    specialist, _, gmail = make_specialist(tmp_path, monkeypatch, messages=[])
    specialist.refresh()
    assert gmail.calls[0]["query"] == DEFAULT_QUERY


def test_refresh_with_no_messages_does_not_call_llm(tmp_path, monkeypatch):
    specialist, llm, _ = make_specialist(tmp_path, monkeypatch, messages=[])
    triage = specialist.refresh()
    assert triage["message_count"] == 0
    assert llm.calls == []


def test_refresh_without_llm_available_reports_it_clearly(tmp_path, monkeypatch):
    messages = [{"id": "m1", "from": "a@b.com", "subject": "sponsor", "snippet": "..."}]
    specialist, llm, _ = make_specialist(tmp_path, monkeypatch, messages=messages, llm_available=False)
    triage = specialist.refresh()
    assert "falta configurar" in triage["triage_text"].lower()
    assert llm.calls == []


def test_refresh_calls_llm_and_persists_to_cache(tmp_path, monkeypatch):
    messages = [{"id": "m1", "from": "a@b.com", "subject": "propuesta de sponsor", "snippet": "..."}]
    specialist, llm, _ = make_specialist(tmp_path, monkeypatch, messages=messages, llm_response="oportunidad real")
    written = specialist.refresh()
    assert written["triage_text"] == "oportunidad real"
    assert specialist.cached_triage() == written


def test_handle_returns_triage_text_directly(tmp_path, monkeypatch):
    messages = [{"id": "m1", "from": "a@b.com", "subject": "x", "snippet": "y"}]
    specialist, _, _ = make_specialist(tmp_path, monkeypatch, messages=messages, llm_response="el triage")
    assert specialist.handle("interpretar", {}) == "el triage"
