from snarf.specialists.document_writer import MAX_SECTION_ATTEMPTS, DocumentWriter


class FakeLLM:
    def __init__(self, available=True, response="Contenido real de la sección.", raise_error=False):
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


class FakeNotion:
    """Página real simulada: append_to_page agrega al buffer de texto real de
    la página, read_page_text lo devuelve — mismo shape que la Capacidad real
    (párrafos separados por línea en blanco)."""

    def __init__(self, append_error=False, read_error=False, verify_lag=False):
        self.pages = {}
        self.append_calls = []
        self.read_calls = 0
        self._append_error = append_error
        self._read_error = read_error
        # verify_lag: el append "sucede" pero read_page_text no lo refleja en
        # la primera lectura (simula el caso real de propagación/lectura que
        # no confirma aunque el escrito ya haya ocurrido de verdad).
        self._verify_lag = verify_lag
        self._lagged_once = False

    def append_to_page(self, page_id, content):
        self.append_calls.append((page_id, content))
        if self._append_error:
            raise RuntimeError("fallo de red simulado")
        self.pages.setdefault(page_id, []).append(content)
        return {"status": "appended", "page_id": page_id}

    def read_page_text(self, page_id):
        self.read_calls += 1
        if self._read_error:
            raise RuntimeError("fallo de lectura simulado")
        if self._verify_lag and not self._lagged_once:
            self._lagged_once = True
            return ""
        return "\n\n".join(self.pages.get(page_id, []))


def make_writer(tmp_path, monkeypatch, llm_factory=None, notion=None):
    monkeypatch.chdir(tmp_path)
    return DocumentWriter(notion or FakeNotion(), llm_factory, "fundador")


def test_start_rejects_empty_sections(tmp_path, monkeypatch):
    writer = make_writer(tmp_path, monkeypatch, llm_factory=lambda: FakeLLM())
    result = writer.start("page-1", "Doc real", [])
    assert "error" in result


def test_start_writes_and_verifies_first_section_in_the_same_call(tmp_path, monkeypatch):
    notion = FakeNotion()
    llm = FakeLLM(response="Sección uno real.")
    writer = make_writer(tmp_path, monkeypatch, llm_factory=lambda: llm, notion=notion)

    result = writer.start("page-1", "Doc real", [{"title": "Intro", "brief": "arranca fuerte"}])

    assert result["sections_total"] == 1
    assert result["sections_verified"] == 1
    assert result["completed"] is True
    assert notion.pages["page-1"] == ["Sección uno real."]


def test_continue_write_advances_one_section_per_call(tmp_path, monkeypatch):
    notion = FakeNotion()
    llm = FakeLLM(response="Contenido real.")
    writer = make_writer(tmp_path, monkeypatch, llm_factory=lambda: llm, notion=notion)

    result = writer.start("page-1", "Doc real", [{"title": "Uno"}, {"title": "Dos"}, {"title": "Tres"}])
    assert result["sections_verified"] == 1
    assert result["completed"] is False

    write_id = result["write_id"]
    result = writer.continue_write(write_id)
    assert result["sections_verified"] == 2
    assert result["completed"] is False

    result = writer.continue_write(write_id)
    assert result["sections_verified"] == 3
    assert result["completed"] is True
    assert len(notion.pages["page-1"]) == 3


def test_continue_write_on_completed_document_is_a_no_op(tmp_path, monkeypatch):
    notion = FakeNotion()
    writer = make_writer(tmp_path, monkeypatch, llm_factory=lambda: FakeLLM(), notion=notion)
    write_id = writer.start("page-1", "Doc real", [{"title": "Única"}])["write_id"]

    result = writer.continue_write(write_id)

    assert result["completed"] is True
    assert len(notion.append_calls) == 1  # nunca reescribe una sección ya verificada


def test_continue_write_with_unknown_write_id_returns_an_error(tmp_path, monkeypatch):
    writer = make_writer(tmp_path, monkeypatch, llm_factory=lambda: FakeLLM())
    result = writer.continue_write("no-existe")
    assert "error" in result


def test_status_is_read_only_and_never_advances(tmp_path, monkeypatch):
    notion = FakeNotion()
    writer = make_writer(tmp_path, monkeypatch, llm_factory=lambda: FakeLLM(), notion=notion)
    write_id = writer.start("page-1", "Doc real", [{"title": "Uno"}, {"title": "Dos"}])["write_id"]
    assert len(notion.append_calls) == 1

    status = writer.status(write_id)

    assert status["sections_verified"] == 1
    assert len(notion.append_calls) == 1  # status() no escribió nada nuevo


def test_state_survives_a_fresh_instance_same_disk(tmp_path, monkeypatch):
    notion = FakeNotion()
    writer_a = make_writer(tmp_path, monkeypatch, llm_factory=lambda: FakeLLM(), notion=notion)
    write_id = writer_a.start("page-1", "Doc real", [{"title": "Uno"}, {"title": "Dos"}])["write_id"]

    # Proceso/instancia nueva, mismo disco — simula reanudar tras un corte
    # de sesión o un reinicio del server.
    writer_b = DocumentWriter(notion, lambda: FakeLLM(response="Contenido dos."), "fundador")
    result = writer_b.continue_write(write_id)

    assert result["sections_verified"] == 2
    assert result["completed"] is True


def test_writes_are_namespaced_per_user(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    notion = FakeNotion()
    writer_founder = DocumentWriter(notion, lambda: FakeLLM(), "fundador")
    writer_other = DocumentWriter(notion, lambda: FakeLLM(), "otro-usuario")
    write_id = writer_founder.start("page-1", "Doc real", [{"title": "Uno"}])["write_id"]

    assert writer_other.status(write_id) == {"error": f"no existe ninguna escritura con id {write_id}."}
    assert writer_founder.status(write_id)["sections_verified"] == 1


def test_generation_failure_never_writes_to_notion_and_marks_failed_after_max_attempts(tmp_path, monkeypatch):
    notion = FakeNotion()
    writer = make_writer(tmp_path, monkeypatch, llm_factory=lambda: FakeLLM(raise_error=True), notion=notion)
    write_id = writer.start("page-1", "Doc real", [{"title": "Uno"}])["write_id"]

    for _ in range(MAX_SECTION_ATTEMPTS - 1):
        writer.continue_write(write_id)

    result = writer.status(write_id)
    assert result["sections_stuck"] == ["Uno"]
    assert result["completed"] is False
    assert notion.append_calls == []  # nunca escribió nada real sin contenido generado


def test_generation_without_llm_factory_never_writes_and_marks_failed(tmp_path, monkeypatch):
    notion = FakeNotion()
    writer = make_writer(tmp_path, monkeypatch, llm_factory=None, notion=notion)
    write_id = writer.start("page-1", "Doc real", [{"title": "Uno"}])["write_id"]

    for _ in range(MAX_SECTION_ATTEMPTS - 1):
        writer.continue_write(write_id)

    result = writer.status(write_id)
    assert result["sections_stuck"] == ["Uno"]
    assert notion.append_calls == []


def test_append_failure_retries_without_duplicating_and_marks_failed_after_max_attempts(tmp_path, monkeypatch):
    notion = FakeNotion(append_error=True)
    writer = make_writer(tmp_path, monkeypatch, llm_factory=lambda: FakeLLM(), notion=notion)
    write_id = writer.start("page-1", "Doc real", [{"title": "Uno"}])["write_id"]

    for _ in range(MAX_SECTION_ATTEMPTS - 1):
        writer.continue_write(write_id)

    result = writer.status(write_id)
    assert result["sections_stuck"] == ["Uno"]
    assert len(notion.append_calls) == MAX_SECTION_ATTEMPTS


def test_verify_read_failure_never_reappends_and_marks_unverified_after_max_attempts(tmp_path, monkeypatch):
    notion = FakeNotion(read_error=True)
    writer = make_writer(tmp_path, monkeypatch, llm_factory=lambda: FakeLLM(response="Único contenido real."), notion=notion)
    write_id = writer.start("page-1", "Doc real", [{"title": "Uno"}])["write_id"]

    for _ in range(MAX_SECTION_ATTEMPTS - 1):
        writer.continue_write(write_id)

    result = writer.status(write_id)
    assert result["sections_stuck"] == ["Uno"]
    # El append real sucedió una sola vez — nunca se reintenta el append
    # cuando lo que falla es solo releer/verificar.
    assert len(notion.append_calls) == 1
    assert notion.pages["page-1"] == ["Único contenido real."]


def test_verify_mismatch_that_resolves_on_a_later_read_gets_verified_without_reappending(tmp_path, monkeypatch):
    notion = FakeNotion(verify_lag=True)
    writer = make_writer(
        tmp_path, monkeypatch, llm_factory=lambda: FakeLLM(response="Contenido con lag real."), notion=notion
    )

    result = writer.start("page-1", "Doc real", [{"title": "Uno"}])
    assert result["sections_verified"] == 0  # primera lectura no lo confirmó (lag simulado)
    assert len(notion.append_calls) == 1

    result = writer.continue_write(result["write_id"])

    assert result["sections_verified"] == 1
    assert result["completed"] is True
    assert len(notion.append_calls) == 1  # nunca reescribió, solo volvió a leer


def test_prompt_for_a_section_never_includes_the_full_content_of_previous_sections(tmp_path, monkeypatch):
    llm = FakeLLM(response="Contenido real.")
    notion = FakeNotion()
    writer = make_writer(tmp_path, monkeypatch, llm_factory=lambda: llm, notion=notion)
    write_id = writer.start(
        "page-1", "Doc real", [{"title": "Uno", "brief": "primero"}, {"title": "Dos", "brief": "segundo"}]
    )["write_id"]
    writer.continue_write(write_id)  # procesa "Dos", ya con "Uno" verificado

    # La sección "Dos" recibe el TÍTULO de "Uno" (ya verificada) para
    # coherencia, pero nunca su contenido completo — mismo criterio de
    # contexto acotado por sección que evita el límite de tokens.
    second_prompt = llm.calls[1]["messages"][0]["content"]
    assert "Uno" in second_prompt
    assert "Contenido real." not in second_prompt
