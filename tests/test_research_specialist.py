from snarf.capabilities.anthropic_llm import LLMResponse
from snarf.specialists.research.mode import DEEP_RESEARCH_CONFIG
from snarf.specialists.research.specialist import ResearchSpecialist, _extract_video_id


class FakeWebSearch:
    def __init__(self, available=True, result=None, error=None):
        self.available = available
        self._result = result or {"answer": "respuesta real", "results": [{"title": "T", "url": "u", "content": "c"}]}
        self._error = error
        self.calls = []

    def search(self, query, max_results=5, include_answer=True):
        self.calls.append(query)
        if self._error:
            raise self._error
        return self._result


class FakeYoutube:
    def __init__(self, captions_by_id=None):
        self._captions_by_id = captions_by_id or {}

    def get_video_captions(self, video_id):
        return self._captions_by_id.get(video_id)


class FakeLLM:
    def __init__(self, available=True, response="informe real"):
        self.available = available
        self._response = response
        self.calls = []

    def generate(self, system, messages):
        self.calls.append((system, messages))
        return LLMResponse(text=self._response, speech=self._response)


class FakeDocumentPublisher:
    def __init__(self):
        self.calls = []

    def create_document(self, title, content, format="markdown", destination="drive"):
        self.calls.append({"title": title, "content": content, "format": format, "destination": destination})
        return {"id": "doc-1", "title": title}


def make_specialist(web_search=None, youtube=None, llm=None, publisher=None):
    llm = llm or FakeLLM()
    return (
        ResearchSpecialist(
            DEEP_RESEARCH_CONFIG,
            web_search or FakeWebSearch(),
            youtube or FakeYoutube(),
            publisher or FakeDocumentPublisher(),
            lambda: llm,
            "fundador",
        ),
        llm,
    )


def test_extract_video_id_from_common_url_shapes():
    assert _extract_video_id("https://www.youtube.com/watch?v=abcdefghijk") == "abcdefghijk"
    assert _extract_video_id("https://youtu.be/abcdefghijk") == "abcdefghijk"
    assert _extract_video_id("https://www.youtube.com/embed/abcdefghijk") == "abcdefghijk"
    assert _extract_video_id("no es una url de youtube") is None


def test_research_without_llm_available_degrades_honestly():
    specialist, _ = make_specialist(llm=FakeLLM(available=False))
    result = specialist.research("tema")
    assert "falta configurar" in result["report_text"].lower()
    assert result["document"] is None


def test_research_without_any_real_source_degrades_honestly():
    specialist, llm = make_specialist(web_search=FakeWebSearch(available=False))
    result = specialist.research("tema")
    assert "ninguna fuente real" in result["report_text"].lower()
    assert llm.calls == []


def test_research_uses_web_search_and_publishes_the_report():
    publisher = FakeDocumentPublisher()
    specialist, llm = make_specialist(publisher=publisher)
    result = specialist.research("inteligencia artificial")
    assert result["report_text"] == "informe real"
    assert result["document"] == {"id": "doc-1", "title": "Investigación Profunda: inteligencia artificial"}
    assert publisher.calls[0]["content"] == "informe real"
    _, messages = llm.calls[0]
    assert "inteligencia artificial" in messages[0]["content"]


def test_research_includes_youtube_captions_when_available():
    youtube = FakeYoutube(captions_by_id={"abcdefghijk": "transcripción real del video"})
    specialist, llm = make_specialist(youtube=youtube, web_search=FakeWebSearch(available=False))
    result = specialist.research("tema", video_urls=["https://youtu.be/abcdefghijk"])
    assert result["document"] is not None
    _, messages = llm.calls[0]
    assert "transcripción real del video" in messages[0]["content"]


def test_research_a_web_search_failure_never_crashes_and_is_recorded():
    specialist, llm = make_specialist(web_search=FakeWebSearch(error=RuntimeError("falla real de red")))
    result = specialist.research("tema")
    assert any(s["type"] == "error" for s in result["sources"])
    # La búsqueda falló pero no hay otra fuente real -> degrada honesto, nunca llama al LLM.
    assert llm.calls == []


def test_handle_returns_report_text_directly():
    specialist, _ = make_specialist(llm=FakeLLM(response="el informe"))
    assert specialist.handle("tema", {}) == "el informe"
