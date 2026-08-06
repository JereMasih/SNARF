from snarf.capabilities.anthropic_llm import LLMResponse
from snarf.specialists.productivity.morning_routine import MAX_PRIORITY_READS, MorningRoutineSpecialist


class FakeGmail:
    def __init__(self, messages, bodies=None):
        self._messages = messages
        self._bodies = bodies or {}
        self.read_calls = []

    def list_messages(self, max_results=20):
        return self._messages[:max_results]

    def read_message(self, message_id):
        self.read_calls.append(message_id)
        return self._bodies.get(message_id, {"subject": "", "from": "", "date": "", "body": ""})


class FakeCalendar:
    def __init__(self, events):
        self._events = events

    def list_upcoming_events(self, max_results=10):
        return self._events[:max_results]


class FakeLLM:
    """Cola de respuestas: la primera llamada (clasificación) consume la
    primera, la segunda (síntesis, solo si hay prioritarios) consume la
    segunda — igual que el orden real en MorningRoutineSpecialist.refresh."""

    def __init__(self, available=True, responses=None):
        self.available = available
        self._responses = list(responses) if responses is not None else ["interpretación"]
        self.calls = []

    def generate(self, system, messages):
        self.calls.append((system, messages))
        index = len(self.calls) - 1
        text = self._responses[index] if index < len(self._responses) else self._responses[-1]
        return LLMResponse(text=text, speech=text)


def make_specialist(tmp_path, monkeypatch, messages=None, events=None, bodies=None, llm_available=True, responses=None):
    from snarf.specialists.productivity import morning_routine as module

    monkeypatch.setattr(module, "CACHE_DIR", tmp_path / "morning_routine")
    gmail = FakeGmail(messages or [], bodies)
    calendar = FakeCalendar(events or [])
    llm = FakeLLM(available=llm_available, responses=responses)
    return MorningRoutineSpecialist(gmail, calendar, lambda: llm, "fundador"), gmail, llm


def test_cached_routine_is_none_before_any_refresh(tmp_path, monkeypatch):
    specialist, _, _ = make_specialist(tmp_path, monkeypatch)
    assert specialist.cached_routine() is None


def test_refresh_with_nothing_at_all_does_not_call_llm(tmp_path, monkeypatch):
    specialist, gmail, llm = make_specialist(tmp_path, monkeypatch, messages=[], events=[])
    routine = specialist.refresh()
    assert routine["message_count"] == 0
    assert routine["event_count"] == 0
    assert "No hay correos ni eventos" in routine["routine_text"]
    assert llm.calls == []
    assert gmail.read_calls == []


def test_refresh_without_llm_available_reports_it_clearly(tmp_path, monkeypatch):
    messages = [{"id": "m1", "from": "a@b.com", "subject": "hola", "snippet": "..."}]
    specialist, gmail, llm = make_specialist(tmp_path, monkeypatch, messages=messages, llm_available=False)
    routine = specialist.refresh()
    assert "falta configurar" in routine["routine_text"].lower()
    assert llm.calls == []
    assert gmail.read_calls == []


def test_refresh_with_no_priority_ids_makes_a_single_llm_call(tmp_path, monkeypatch):
    messages = [{"id": "m1", "from": "a@b.com", "subject": "newsletter", "snippet": "novedades de la semana"}]
    specialist, gmail, llm = make_specialist(
        tmp_path, monkeypatch, messages=messages, responses=["texto interpretado\nPRIORITY_IDS: ninguno"]
    )
    routine = specialist.refresh()
    assert routine["routine_text"] == "texto interpretado"
    assert routine["priority_message_ids"] == []
    assert routine["priority_messages"] == []
    assert len(llm.calls) == 1
    assert gmail.read_calls == []


def test_priority_ids_line_is_never_leaked_into_the_visible_text(tmp_path, monkeypatch):
    messages = [{"id": "m1", "from": "a@b.com", "subject": "x", "snippet": "y"}]
    specialist, _, _ = make_specialist(
        tmp_path, monkeypatch, messages=messages, responses=["texto interpretado\nPRIORITY_IDS: ninguno"]
    )
    routine = specialist.refresh()
    assert "PRIORITY_IDS" not in routine["routine_text"]


def test_refresh_reads_the_real_body_of_a_validated_priority_id_and_synthesizes(tmp_path, monkeypatch):
    messages = [
        {"id": "m1", "from": "MUN. DE CÓRDOBA", "subject": "Deuda", "snippet": "ejecución prejudicial"},
        {"id": "m2", "from": "newsletter@x.com", "subject": "novedades", "snippet": "..."},
    ]
    bodies = {"m1": {"subject": "Deuda", "from": "MUN. DE CÓRDOBA", "date": "hoy", "body": "cuerpo real completo del correo"}}
    specialist, gmail, llm = make_specialist(
        tmp_path,
        monkeypatch,
        messages=messages,
        bodies=bodies,
        responses=["clasificación inicial\nPRIORITY_IDS: m1", "versión final con el detalle real"],
    )
    routine = specialist.refresh()
    assert gmail.read_calls == ["m1"]
    assert routine["priority_message_ids"] == ["m1"]
    assert routine["priority_messages"] == [{"id": "m1", "subject": "Deuda", "from": "MUN. DE CÓRDOBA", "date": "hoy", "body": "cuerpo real completo del correo"}]
    assert routine["routine_text"] == "versión final con el detalle real"
    assert len(llm.calls) == 2
    _, synthesize_messages = llm.calls[1]
    assert "cuerpo real completo del correo" in synthesize_messages[0]["content"]


def test_refresh_never_reads_a_hallucinated_id_not_present_in_the_real_listing(tmp_path, monkeypatch):
    # Regresión directa del bug real encontrado en producción: un modelo
    # local de 4B inventó un message_id que no existía en ningún listado
    # real. Acá el modelo "clasificador" hace lo mismo — el id inventado
    # nunca debe llegar a gmail_read_message.
    messages = [{"id": "m1", "from": "a@b.com", "subject": "x", "snippet": "y"}]
    specialist, gmail, llm = make_specialist(
        tmp_path,
        monkeypatch,
        messages=messages,
        responses=["clasificación\nPRIORITY_IDS: 168902345678901234567890"],
    )
    routine = specialist.refresh()
    assert routine["priority_message_ids"] == []
    assert gmail.read_calls == []
    assert len(llm.calls) == 1  # nunca llega a la segunda pasada de síntesis


def test_refresh_caps_priority_reads_at_max_priority_reads(tmp_path, monkeypatch):
    ids = [f"m{i}" for i in range(MAX_PRIORITY_READS + 3)]
    messages = [{"id": mid, "from": "a@b.com", "subject": mid, "snippet": "..."} for mid in ids]
    priority_line = "PRIORITY_IDS: " + ", ".join(ids)
    specialist, gmail, llm = make_specialist(
        tmp_path, monkeypatch, messages=messages, responses=[f"clasificación\n{priority_line}", "final"]
    )
    routine = specialist.refresh()
    assert len(routine["priority_message_ids"]) == MAX_PRIORITY_READS
    assert len(gmail.read_calls) == MAX_PRIORITY_READS


def test_refresh_persists_to_cache_and_cached_routine_reads_it_back(tmp_path, monkeypatch):
    messages = [{"id": "m1", "from": "a@b.com", "subject": "x", "snippet": "y"}]
    specialist, _, _ = make_specialist(tmp_path, monkeypatch, messages=messages, responses=["texto\nPRIORITY_IDS: ninguno"])
    written = specialist.refresh()
    assert specialist.cached_routine() == written


def test_handle_returns_routine_text_directly(tmp_path, monkeypatch):
    specialist, _, _ = make_specialist(tmp_path, monkeypatch, messages=[], events=[])
    assert specialist.handle("interpretar", {}) == "No hay correos ni eventos próximos para armar la rutina de hoy."


def test_refresh_respects_max_messages_and_max_events_params(tmp_path, monkeypatch):
    messages = [{"id": f"m{i}", "from": "a@b.com", "subject": f"m{i}", "snippet": "..."} for i in range(5)]
    events = [{"id": f"e{i}", "summary": f"evento {i}", "start": "2026-08-06T10:00:00-03:00"} for i in range(5)]
    specialist, _, _ = make_specialist(
        tmp_path, monkeypatch, messages=messages, events=events, responses=["texto\nPRIORITY_IDS: ninguno"]
    )
    routine = specialist.refresh(max_messages=2, max_events=1)
    assert routine["message_count"] == 2
    assert routine["event_count"] == 1
