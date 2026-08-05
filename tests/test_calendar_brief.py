from snarf.capabilities.anthropic_llm import LLMResponse
from snarf.specialists.productivity.calendar_brief import CalendarBriefSpecialist


class FakeCalendar:
    def __init__(self, events):
        self._events = events

    def list_upcoming_events(self, max_results=10, calendar_id="primary"):
        return self._events[:max_results]


class FakeLLM:
    def __init__(self, available=True, response="resumen interpretado"):
        self.available = available
        self._response = response
        self.calls = []

    def generate(self, system, messages):
        self.calls.append((system, messages))
        return LLMResponse(text=self._response, speech=self._response)


def make_specialist(tmp_path, monkeypatch, events=None, llm_available=True, llm_response="resumen"):
    from snarf.specialists.productivity import calendar_brief as module

    monkeypatch.setattr(module, "CACHE_DIR", tmp_path / "calendar_brief")
    calendar = FakeCalendar(events or [])
    llm = FakeLLM(available=llm_available, response=llm_response)
    return CalendarBriefSpecialist(calendar, lambda: llm, "fundador"), llm


def test_cached_brief_is_none_before_any_refresh(tmp_path, monkeypatch):
    specialist, _ = make_specialist(tmp_path, monkeypatch)
    assert specialist.cached_brief() is None


def test_refresh_with_no_events_does_not_call_llm(tmp_path, monkeypatch):
    specialist, llm = make_specialist(tmp_path, monkeypatch, events=[])
    brief = specialist.refresh()
    assert brief["event_count"] == 0
    assert "No hay eventos" in brief["brief_text"]
    assert llm.calls == []


def test_refresh_without_llm_available_reports_it_clearly(tmp_path, monkeypatch):
    events = [{"id": "e1", "summary": "Reunión", "start": "2026-08-05T10:00:00-03:00"}]
    specialist, llm = make_specialist(tmp_path, monkeypatch, events=events, llm_available=False)
    brief = specialist.refresh()
    assert "falta configurar" in brief["brief_text"].lower()
    assert llm.calls == []


def test_refresh_calls_llm_with_event_listing(tmp_path, monkeypatch):
    events = [{"id": "e1", "summary": "Reunión importante", "start": "2026-08-05T10:00:00-03:00", "location": "Oficina"}]
    specialist, llm = make_specialist(tmp_path, monkeypatch, events=events, llm_response="resumen real")
    brief = specialist.refresh()
    assert brief["brief_text"] == "resumen real"
    assert brief["event_count"] == 1
    _, sent_messages = llm.calls[0]
    assert "Reunión importante" in sent_messages[0]["content"]
    assert "Oficina" in sent_messages[0]["content"]


def test_refresh_persists_to_cache_and_cached_brief_reads_it_back(tmp_path, monkeypatch):
    events = [{"id": "e1", "summary": "x", "start": "2026-08-05T10:00:00-03:00"}]
    specialist, _ = make_specialist(tmp_path, monkeypatch, events=events)
    written = specialist.refresh()
    assert specialist.cached_brief() == written


def test_handle_returns_brief_text_directly(tmp_path, monkeypatch):
    events = [{"id": "e1", "summary": "x", "start": "2026-08-05T10:00:00-03:00"}]
    specialist, _ = make_specialist(tmp_path, monkeypatch, events=events, llm_response="el resumen")
    assert specialist.handle("interpretar", {}) == "el resumen"


def test_refresh_respects_max_results_from_context(tmp_path, monkeypatch):
    events = [{"id": f"e{i}", "summary": f"evento {i}", "start": "2026-08-05T10:00:00-03:00"} for i in range(5)]
    specialist, _ = make_specialist(tmp_path, monkeypatch, events=events)
    brief = specialist.refresh(max_results=2)
    assert brief["event_count"] == 2
