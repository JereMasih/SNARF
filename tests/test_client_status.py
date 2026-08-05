from snarf.capabilities.anthropic_llm import LLMResponse
from snarf.specialists.agency.client_status import ClientStatusSpecialist


class FakeProjects:
    def __init__(self, project=None):
        self._project = project

    def get(self, project_id):
        return self._project


class FakeLLM:
    def __init__(self, available=True, response="status real"):
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
        self.calls.append({"title": title, "content": content})
        return {"id": "doc-1", "title": title}


REAL_PROJECT = {
    "id": "p1",
    "name": "Sitio web de Ana",
    "tasks": [
        {"id": "t1", "text": "Diseño de home", "done": True},
        {"id": "t2", "text": "Integrar pagos", "done": False},
    ],
    "notes": [{"id": "n1", "text": "Cliente pidió cambiar el logo"}],
}


def make_specialist(project=REAL_PROJECT, llm=None, publisher=None):
    llm = llm or FakeLLM()
    return (
        ClientStatusSpecialist(FakeProjects(project), publisher or FakeDocumentPublisher(), lambda: llm, "fundador"),
        llm,
    )


def test_generate_for_an_unknown_project_reports_an_error():
    specialist, llm = make_specialist(project=None)
    result = specialist.generate("no-existe")
    assert "error" in result
    assert llm.calls == []


def test_generate_without_llm_available_degrades_honestly():
    specialist, _ = make_specialist(llm=FakeLLM(available=False))
    result = specialist.generate("p1")
    assert "falta configurar" in result["status_text"].lower()
    assert result["document"] is None


def test_generate_includes_real_tasks_and_notes_in_the_prompt():
    specialist, llm = make_specialist()
    specialist.generate("p1")
    _, messages = llm.calls[0]
    content = messages[0]["content"]
    assert "Diseño de home" in content
    assert "Integrar pagos" in content
    assert "Cliente pidió cambiar el logo" in content


def test_generate_publishes_the_document():
    publisher = FakeDocumentPublisher()
    specialist, _ = make_specialist(publisher=publisher)
    result = specialist.generate("p1")
    assert result["status_text"] == "status real"
    assert result["document"] == {"id": "doc-1", "title": "Status semanal: Sitio web de Ana"}
    assert publisher.calls[0]["content"] == "status real"


def test_handle_returns_status_text_directly():
    specialist, _ = make_specialist(llm=FakeLLM(response="el status"))
    assert specialist.handle("status", {"project_id": "p1"}) == "el status"


def test_handle_returns_the_error_for_an_unknown_project():
    specialist, _ = make_specialist(project=None)
    assert "no existe" in specialist.handle("status", {"project_id": "no-existe"})
