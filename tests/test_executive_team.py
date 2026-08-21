import pytest

from snarf.executive import team as team_module
from snarf.executive.team import TeamSession, _parse_objections


class FakeLLM:
    def __init__(self, available=True, response="Borrador real del objetivo.", raise_error=False):
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


def make_session(monkeypatch, draft_llm=None, critique_responses=None, role_llm_factory=None):
    """critique_responses: dict role -> raw text que consult_role() debería
    devolver para ese rol (mismo shape real que consult_role: {headline,
    opinions, raw})."""
    draft_llm = draft_llm or FakeLLM()
    critique_responses = critique_responses or {}

    def fake_consult_role(role_config, question, llm, repo_root, upstream_context=None):
        raw = critique_responses.get(role_config.role, "SIN OBJECIÓN: todo bien.")
        return {"headline": raw.splitlines()[0] if raw else "", "opinions": [], "raw": raw}

    monkeypatch.setattr(team_module, "consult_role", fake_consult_role)
    return TeamSession(
        draft_llm_factory=lambda: draft_llm,
        role_llm_factory_for_role=role_llm_factory or (lambda role: FakeLLM()),
    )


def test_run_rejects_unknown_roles(monkeypatch):
    session = make_session(monkeypatch)
    result = session.run("objetivo real", roles=["no-existe"])
    assert "error" in result
    assert "no-existe" in result["error"]


def test_run_rejects_empty_roles(monkeypatch):
    session = make_session(monkeypatch)
    result = session.run("objetivo real", roles=[])
    assert "error" in result


def test_run_rejects_max_rounds_below_one(monkeypatch):
    session = make_session(monkeypatch)
    result = session.run("objetivo real", roles=["cmo"], max_rounds=0)
    assert "error" in result


def test_run_approves_on_the_first_round_without_blocking_objections(monkeypatch):
    session = make_session(monkeypatch, critique_responses={"cmo": "SIN OBJECIÓN: se ve bien."})
    result = session.run("lanzar campaña real", roles=["cmo"], max_rounds=3)

    assert result["approved"] is True
    assert result["approved_by_exhaustion"] is False
    assert len(result["rounds"]) == 1


def test_run_revises_draft_after_a_blocking_objection_then_approves(monkeypatch):
    call_count = {"n": 0}

    def fake_consult_role(role_config, question, llm, repo_root, upstream_context=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return {"headline": "", "opinions": [], "raw": "BLOQUEANTE: falta el presupuesto real."}
        return {"headline": "", "opinions": [], "raw": "SIN OBJECIÓN: ahora sí."}

    monkeypatch.setattr(team_module, "consult_role", fake_consult_role)
    draft_calls = []
    draft_llm = FakeLLM()

    class TrackingDraftLLM(FakeLLM):
        def generate(self, system, messages):
            draft_calls.append(messages[0]["content"])
            return super().generate(system, messages)

    session = TeamSession(
        draft_llm_factory=lambda: TrackingDraftLLM(response="Borrador v2, con presupuesto."),
        role_llm_factory_for_role=lambda role: FakeLLM(),
    )
    result = session.run("armar campaña", roles=["cmo"], max_rounds=3)

    assert result["approved"] is True
    assert result["approved_by_exhaustion"] is False
    assert len(result["rounds"]) == 2
    # El segundo borrador se generó incorporando la objeción real de la
    # primera ronda, no de la nada.
    assert "falta el presupuesto real" in draft_calls[1]


def test_run_approves_by_exhaustion_when_objections_never_resolve(monkeypatch):
    def fake_consult_role(role_config, question, llm, repo_root, upstream_context=None):
        return {"headline": "", "opinions": [], "raw": "BLOQUEANTE: sigue sin convencerme."}

    monkeypatch.setattr(team_module, "consult_role", fake_consult_role)
    session = TeamSession(
        draft_llm_factory=lambda: FakeLLM(),
        role_llm_factory_for_role=lambda role: FakeLLM(),
    )
    result = session.run("objetivo difícil", roles=["cfo"], max_rounds=2)

    assert result["approved"] is True
    assert result["approved_by_exhaustion"] is True
    assert len(result["rounds"]) == 2


def test_run_never_blocks_on_sugerencia_only_objections(monkeypatch):
    session = make_session(monkeypatch, critique_responses={"cmo": "SUGERENCIA: podría ser más corto."})
    result = session.run("objetivo real", roles=["cmo"], max_rounds=3)
    assert result["approved"] is True
    assert result["approved_by_exhaustion"] is False
    assert len(result["rounds"]) == 1


def test_run_with_multiple_roles_needs_all_clear_to_approve(monkeypatch):
    session = make_session(
        monkeypatch,
        critique_responses={
            "cmo": "SIN OBJECIÓN: bien.",
            "creative": "BLOQUEANTE: el tono no encaja con la marca.",
        },
    )
    result = session.run("objetivo real", roles=["cmo", "creative"], max_rounds=1)
    # max_rounds=1 agotado con una objeción real sin resolver todavía.
    assert result["approved_by_exhaustion"] is True


def test_generate_draft_without_llm_available_says_so_explicitly(monkeypatch):
    session = make_session(monkeypatch, draft_llm=FakeLLM(available=False))
    result = session.run("objetivo real", roles=["cmo"], max_rounds=1)
    assert "falta configurar el modelo de lenguaje" in result["draft"]


def test_generate_draft_degrades_gracefully_on_llm_error(monkeypatch):
    session = make_session(monkeypatch, draft_llm=FakeLLM(raise_error=True))
    result = session.run("objetivo real", roles=["cmo"], max_rounds=1)
    assert "No se pudo generar el borrador" in result["draft"]


def test_no_role_has_authority_over_another_critiques_run_independently(monkeypatch):
    # Cada consult_role real ya corre en su propio proceso, sin visibilidad
    # entre roles (mismo invariante que el board, ADR 0094) — acá se
    # confirma que TeamSession no le pasa la crítica de un rol como
    # contexto al otro dentro de la MISMA ronda (solo entre rondas, vía
    # regeneración del borrador).
    seen_questions = []

    def fake_consult_role(role_config, question, llm, repo_root, upstream_context=None):
        seen_questions.append((role_config.role, question, upstream_context))
        return {"headline": "", "opinions": [], "raw": "SIN OBJECIÓN: ok."}

    monkeypatch.setattr(team_module, "consult_role", fake_consult_role)
    session = TeamSession(draft_llm_factory=lambda: FakeLLM(), role_llm_factory_for_role=lambda role: FakeLLM())
    session.run("objetivo real", roles=["cmo", "creative"], max_rounds=1)

    assert len(seen_questions) == 2
    roles_seen = {q[0] for q in seen_questions}
    assert roles_seen == {"cmo", "creative"}
    # Ninguna pregunta de un rol menciona la crítica del otro.
    for role, question, _ in seen_questions:
        assert "creative" not in question if role == "cmo" else True


def test_parse_objections_extracts_severity_and_text():
    raw = (
        "BLOQUEANTE: falta el presupuesto.\n"
        "sin texto random que no matchea\n"
        "SUGERENCIA: podría acortarse.\n"
        "sin objeción: está OK en general.\n"
    )
    objections = _parse_objections(raw)
    severities = [o["severity"] for o in objections]
    assert severities == ["BLOQUEANTE", "SUGERENCIA", "SIN OBJECIÓN"]
    assert objections[0]["text"] == "falta el presupuesto."


def test_parse_objections_returns_empty_list_for_empty_text():
    assert _parse_objections("") == []
    assert _parse_objections(None) == []
