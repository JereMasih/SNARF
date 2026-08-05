from snarf.capabilities.anthropic_llm import LLMResponse
from snarf.specialists.content.mode import BLOG_POST_CONFIG
from snarf.specialists.content.specialist import ContentSpecialist


class FakeLLM:
    def __init__(self, available=True, response="borrador real"):
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


def make_specialist(llm=None, publisher=None):
    llm = llm or FakeLLM()
    return ContentSpecialist(BLOG_POST_CONFIG, publisher or FakeDocumentPublisher(), lambda: llm, "fundador"), llm


def test_draft_without_llm_available_degrades_honestly():
    specialist, _ = make_specialist(llm=FakeLLM(available=False))
    result = specialist.draft("un post sobre X")
    assert "falta configurar" in result["draft_text"].lower()
    assert result["document"] is None


def test_draft_publishes_the_document():
    publisher = FakeDocumentPublisher()
    specialist, llm = make_specialist(publisher=publisher)
    result = specialist.draft("un post sobre productividad")
    assert result["draft_text"] == "borrador real"
    assert result["document"] == {"id": "doc-1", "title": "Post de Blog: un post sobre productividad"}
    assert publisher.calls[0]["content"] == "borrador real"
    _, messages = llm.calls[0]
    assert "un post sobre productividad" in messages[0]["content"]


def test_draft_includes_reference_material_when_provided():
    specialist, llm = make_specialist()
    specialist.draft("un post", reference_material="dato real: 500 usuarios activos")
    _, messages = llm.calls[0]
    assert "dato real: 500 usuarios activos" in messages[0]["content"]


def test_draft_without_reference_material_never_mentions_it():
    specialist, llm = make_specialist()
    specialist.draft("un post")
    _, messages = llm.calls[0]
    assert "Material de referencia" not in messages[0]["content"]


def test_handle_returns_draft_text_directly():
    specialist, _ = make_specialist(llm=FakeLLM(response="el borrador"))
    assert specialist.handle("brief", {}) == "el borrador"
