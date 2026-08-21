"""Integración capstone (ver ROADMAP_SECOND_BRAIN_NOTION.md, Fase D5, ADR
0200) — prueba que el artefacto real que devuelve TeamSession (D3) es
compatible de verdad con lo que espera DocumentWriter (D4), encadenados tal
como los usaría el Orchestrator en el escenario real que motivó todo Track
D: un equipo planea las secciones de un documento, y esas secciones se
escriben verificadas a Notion. Todo con fakes — sin acceso real a Notion/LLM
desde este entorno (mismo estado honesto que D2/D3/D4)."""

from snarf.executive import team as team_module
from snarf.executive.team import TeamSession
from snarf.specialists.document_writer import DocumentWriter


class FakeLLM:
    def __init__(self, response="ok", raise_error=False, available=True):
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
    def __init__(self):
        self.pages = {}
        self.append_calls = []

    def append_to_page(self, page_id, content):
        self.append_calls.append((page_id, content))
        self.pages.setdefault(page_id, []).append(content)
        return {"status": "appended", "page_id": page_id}

    def read_page_text(self, page_id):
        return "\n\n".join(self.pages.get(page_id, []))


def _parse_outline(draft: str) -> list[dict]:
    """Mismo criterio que se le pide al Orchestrator hacer en su propia
    respuesta (ver guía de executive_team_run en SYSTEM_PREFIX): una línea
    por sección, 'Título: brief corto' — acá se reproduce a mano, sin ningún
    parser nuevo en el propio código de producción (la LLM real del
    Orchestrator es la que hace este trabajo en producción, no un parser de
    texto)."""
    sections = []
    for line in draft.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        title, _, brief = line.partition(":")
        sections.append({"title": title.strip(), "brief": brief.strip()})
    return sections


def test_a_team_approved_outline_feeds_directly_into_a_verified_document_write(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # DocumentWriter usa una ruta relativa (data/document_writes) — nunca tocar el repo real
    outline_draft = "Introducción: contexto real del proyecto\nDesarrollo: detalle técnico real\nCierre: próximos pasos reales"

    def fake_consult_role(role_config, question, llm, repo_root, upstream_context=None):
        return {"headline": "", "opinions": [], "raw": "SIN OBJECIÓN: el plan de secciones se ve bien."}

    monkeypatch.setattr(team_module, "consult_role", fake_consult_role)
    team = TeamSession(
        draft_llm_factory=lambda: FakeLLM(response=outline_draft),
        role_llm_factory_for_role=lambda role: FakeLLM(),
    )

    team_result = team.run("Planear las secciones de un documento real sobre el proyecto", roles=["cmo"])
    assert team_result["approved"] is True
    assert team_result["approved_by_exhaustion"] is False

    sections = _parse_outline(team_result["draft"])
    assert [s["title"] for s in sections] == ["Introducción", "Desarrollo", "Cierre"]

    notion = FakeNotion()
    writer_llm = FakeLLM(response="Contenido real y verificado de la sección.")
    writer = DocumentWriter(notion, lambda: writer_llm, "fundador")

    result = writer.start("page-real-1", "Documento del proyecto", sections, objective=team_result["objective"])
    write_id = result["write_id"]
    while not result["completed"]:
        result = writer.continue_write(write_id)

    assert result["completed"] is True
    assert result["sections_stuck"] == []
    assert len(notion.pages["page-real-1"]) == 3
    # El objetivo real del equipo llegó de verdad al contexto de cada
    # sección — nunca se perdió en el cruce D3 -> D4.
    assert any("Planear las secciones" in call["messages"][0]["content"] for call in writer_llm.calls)


def test_a_team_approved_by_exhaustion_outline_is_still_usable_but_should_be_flagged(tmp_path, monkeypatch):
    """approved_by_exhaustion=True significa que el equipo NO llegó a
    consenso real — el borrador igual puede usarse (nunca se descarta un
    trabajo real), pero el Orchestrator tiene que decírselo honesto al
    fundador antes de escribirlo a Notion (ver guía en SYSTEM_PREFIX).
    Este test solo confirma que el pipeline en sí no falla ni oculta esa
    señal — la decisión de avisar es responsabilidad del Orchestrator, no
    de TeamSession/DocumentWriter."""
    monkeypatch.chdir(tmp_path)  # DocumentWriter usa una ruta relativa (data/document_writes) — nunca tocar el repo real

    def fake_consult_role(role_config, question, llm, repo_root, upstream_context=None):
        return {"headline": "", "opinions": [], "raw": "BLOQUEANTE: nunca convence del todo."}

    monkeypatch.setattr(team_module, "consult_role", fake_consult_role)
    team = TeamSession(
        draft_llm_factory=lambda: FakeLLM(response="Única sección: contenido difícil de aprobar"),
        role_llm_factory_for_role=lambda role: FakeLLM(),
    )

    team_result = team.run("Planear un documento polémico", roles=["cfo"], max_rounds=2)
    assert team_result["approved_by_exhaustion"] is True

    sections = _parse_outline(team_result["draft"])
    notion = FakeNotion()
    writer = DocumentWriter(notion, lambda: FakeLLM(response="Contenido real."), "fundador")

    result = writer.start("page-real-2", "Documento polémico", sections)

    assert result["sections_stuck"] == []
    assert notion.pages["page-real-2"] == ["Contenido real."]
