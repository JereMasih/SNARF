from snarf.capabilities.local_code_writer import LocalCodeWriterResult
from snarf.specialists.skill_factory import SkillFactorySpecialist


class _FakeCodeWriter:
    available = True

    def __init__(self, result: LocalCodeWriterResult):
        self._result = result
        self.calls = []

    def run(self, prompt: str, allowed_write_paths: set, allowed_edit_paths: set) -> LocalCodeWriterResult:
        self.calls.append((prompt, allowed_write_paths, allowed_edit_paths))
        return self._result


def _ok_result(files_written=frozenset(), **overrides) -> LocalCodeWriterResult:
    base = dict(
        ok=True, result_text="LISTO", session_id=None, cost_usd=None, num_turns=6, raw={}, files_written=files_written
    )
    base.update(overrides)
    return LocalCodeWriterResult(**base)


def _factory(
    tmp_path,
    code_writer=None,
    tests_pass=True,
    restart_calls=None,
):
    def run_tests_fn():
        return {"passed": tests_pass, "output": "output real de pytest"}

    def restart_fn():
        if restart_calls is not None:
            restart_calls.append(True)

    return SkillFactorySpecialist(
        code_writer=code_writer or _FakeCodeWriter(_ok_result()),
        repo_root=tmp_path,
        run_tests_fn=run_tests_fn,
        restart_fn=restart_fn,
        proposals_dir=tmp_path / "skill_proposals",
    )


def test_build_skill_within_scope_succeeds(tmp_path):
    written = {
        "snarf/specialists/research/deep_research.py",
        "snarf/specialists/research/__init__.py",
        "tests/test_deep_research.py",
        "snarf/core/orchestrator.py",
        "snarf/telemetry/brain.py",
        "snarf/telemetry/verbs.py",
        "snarf/telemetry/detail.py",
    }
    factory = _factory(tmp_path, code_writer=_FakeCodeWriter(_ok_result(files_written=frozenset(written))))

    result = factory.build_skill("research", "deep_research", "investiga temas a fondo")

    assert result["status"] == "built"
    assert sorted(result["diff_files"]) == sorted(written)
    manifest = factory.load_manifest(result["proposal_id"])
    assert manifest["status"] == "built"


def test_build_skill_passes_the_scoped_allowed_paths_to_the_code_writer(tmp_path):
    writer = _FakeCodeWriter(_ok_result())
    factory = _factory(tmp_path, code_writer=writer)

    factory.build_skill("research", "x", "algo")

    _, allowed_write_paths, allowed_edit_paths = writer.calls[0]
    assert allowed_write_paths == {
        "snarf/specialists/research/x.py",
        "snarf/specialists/research/__init__.py",
        "tests/test_x.py",
    }
    assert allowed_edit_paths == {
        "snarf/core/orchestrator.py",
        "snarf/telemetry/brain.py",
        "snarf/telemetry/verbs.py",
        "snarf/telemetry/detail.py",
    }


def test_build_skill_never_consults_git_or_the_working_tree_for_the_scope_decision(tmp_path, monkeypatch):
    # Bug real corregido 2026-08-12: la decisión de alcance solía compararse
    # contra dos fotos de `git status` del repo entero, que se rompía con
    # cualquier trabajo concurrente en el mismo working tree (otra sesión de
    # Claude Code, un `git` manual). Ahora se basa exclusivamente en
    # result.files_written — build_skill() ni siquiera necesita que
    # repo_root sea un repo git real para decidir el alcance correctamente.
    import subprocess

    def _no_git_allowed(*a, **kw):
        raise AssertionError("build_skill() no debería invocar git para la decisión de alcance")

    monkeypatch.setattr(subprocess, "run", _no_git_allowed)
    written = {
        "snarf/specialists/research/x.py",
        "snarf/specialists/research/__init__.py",
        "tests/test_x.py",
    }
    factory = _factory(tmp_path, code_writer=_FakeCodeWriter(_ok_result(files_written=frozenset(written))))

    result = factory.build_skill("research", "x", "algo")

    assert result["status"] == "built"


def test_build_skill_ignores_files_touched_by_a_concurrent_session(tmp_path):
    # Otra sesión (real: otra ventana de Claude Code) puede estar escribiendo
    # archivos sin relación en el mismo repo mientras esta build corre — como
    # el alcance ahora se basa en files_written (lo que el propio motor
    # reportó haber escrito, nunca inferido del working tree), esos archivos
    # ajenos ni siquiera entran en la decisión.
    written = {
        "snarf/specialists/finance/receipts_tracker.py",
        "snarf/specialists/finance/__init__.py",
        "tests/test_receipts_tracker.py",
        "snarf/core/orchestrator.py",
        "snarf/telemetry/brain.py",
        "snarf/telemetry/verbs.py",
        "snarf/telemetry/detail.py",
    }
    factory = _factory(tmp_path, code_writer=_FakeCodeWriter(_ok_result(files_written=frozenset(written))))

    result = factory.build_skill("finance", "receipts_tracker", "trackea recibos reales")

    assert result["status"] == "built"
    assert "snarf/runtime/llm_routing.py" not in result["diff_files"]
    assert "app.py" not in result["diff_files"]


def test_build_skill_aborts_when_a_foundational_doc_is_touched(tmp_path):
    written = {
        "snarf/specialists/research/x.py",
        "snarf/specialists/research/__init__.py",
        "tests/test_x.py",
        "CONSTITUTION.md",
    }
    factory = _factory(tmp_path, code_writer=_FakeCodeWriter(_ok_result(files_written=frozenset(written))))

    result = factory.build_skill("research", "x", "algo")

    assert result["status"] == "aborted"
    assert "CONSTITUTION.md" in result["reason"]
    manifest = factory.load_manifest(result["proposal_id"])
    assert manifest["status"] == "aborted"


def test_build_skill_aborts_when_an_unexpected_file_outside_scope_is_touched(tmp_path):
    # No debería poder pasar de verdad (LocalCodeWriter._write_file/_edit_file
    # ya rechazan cualquier path fuera de allowed_write_paths/allowed_edit_paths
    # antes de tocar disco) — esto verifica que si ese invariante alguna vez
    # se rompe, build_skill() lo sigue detectando, no confía ciegamente.
    written = {
        "snarf/specialists/research/x.py",
        "snarf/specialists/research/__init__.py",
        "tests/test_x.py",
        "snarf/capabilities/google_drive.py",  # nunca autorizado a tocar una Capacidad existente
    }
    factory = _factory(tmp_path, code_writer=_FakeCodeWriter(_ok_result(files_written=frozenset(written))))

    result = factory.build_skill("research", "x", "algo")

    assert result["status"] == "aborted"
    assert "google_drive.py" in result["reason"]


def test_build_skill_fails_when_the_real_test_suite_does_not_pass(tmp_path):
    written = {
        "snarf/specialists/research/x.py",
        "snarf/specialists/research/__init__.py",
        "tests/test_x.py",
    }
    factory = _factory(
        tmp_path, code_writer=_FakeCodeWriter(_ok_result(files_written=frozenset(written))), tests_pass=False
    )

    result = factory.build_skill("research", "x", "algo")

    assert result["status"] == "failed"
    assert "test_output" in result


def test_build_skill_fails_honestly_when_the_code_writer_itself_fails(tmp_path):
    # Mismo criterio que antes con Claude Code: si el motor no termina con
    # éxito (acá, típico de un modelo local: se quedó sin rondas de
    # herramientas sin terminar, ver LocalCodeWriter.MAX_BUILD_TOOL_ROUNDS),
    # el fracaso se muestra tal cual, nunca se disimula.
    broken = _FakeCodeWriter(
        LocalCodeWriterResult(
            ok=False,
            result_text="[demasiadas consultas a herramientas, no llegué a una respuesta final]",
            session_id=None,
            cost_usd=None,
            num_turns=40,
            raw={},
        )
    )
    factory = _factory(tmp_path, code_writer=broken)

    result = factory.build_skill("research", "x", "algo")

    assert result["status"] == "failed"
    assert "demasiadas consultas" in result["reason"]


def test_build_skill_fails_when_the_code_writer_is_not_available(tmp_path):
    class _Unavailable:
        available = False

    factory = SkillFactorySpecialist(
        code_writer=_Unavailable(), repo_root=tmp_path, proposals_dir=tmp_path / "skill_proposals"
    )

    result = factory.build_skill("research", "x", "algo")

    assert result["status"] == "failed"
    assert "no está disponible" in result["reason"]


def test_activate_requires_a_built_proposal(tmp_path):
    restart_calls = []
    factory = _factory(tmp_path, restart_calls=restart_calls)
    built = factory.build_skill(
        "research",
        "x",
        "algo",
    )

    result = factory.activate(built["proposal_id"])

    assert result["status"] == "activated"
    assert restart_calls == [True]


def test_activate_rejects_an_unknown_proposal(tmp_path):
    factory = _factory(tmp_path)
    result = factory.activate("no-existe-1234")
    assert "error" in result


def test_activate_rejects_a_proposal_that_never_finished_building(tmp_path):
    written = {
        "snarf/specialists/research/x.py",
        "snarf/specialists/research/__init__.py",
        "tests/test_x.py",
        "CONSTITUTION.md",
    }
    restart_calls = []
    factory = _factory(
        tmp_path, code_writer=_FakeCodeWriter(_ok_result(files_written=frozenset(written))), restart_calls=restart_calls
    )
    aborted = factory.build_skill("research", "x", "algo")

    result = factory.activate(aborted["proposal_id"])

    assert "error" in result
    assert restart_calls == []


def test_status_returns_the_persisted_manifest(tmp_path):
    factory = _factory(tmp_path)
    built = factory.build_skill("research", "x", "algo")

    status = factory.status(built["proposal_id"])

    assert status["branch"] == "research"
    assert status["skill_name"] == "x"


def test_build_skill_rejects_a_skill_name_with_path_traversal_before_touching_anything(tmp_path):
    # skill_name adversarial que intenta escapar snarf/specialists/ — tiene
    # que rechazarse ANTES de invocar el motor local, nunca dejar que
    # LocalCodeWriter llegue a evaluarlo.
    writer = _FakeCodeWriter(_ok_result())
    factory = _factory(tmp_path, code_writer=writer)

    result = factory.build_skill("research", "../../../tmp/evil", "algo")

    assert result["status"] == "rejected"
    assert "skill_name" in result["reason"]
    assert writer.calls == []


def test_build_skill_rejects_a_branch_with_a_slash(tmp_path):
    writer = _FakeCodeWriter(_ok_result())
    factory = _factory(tmp_path, code_writer=writer)

    result = factory.build_skill("research/../../etc", "x", "algo")

    assert result["status"] == "rejected"
    assert "branch" in result["reason"]
    assert writer.calls == []


def test_build_skill_rejects_names_outside_snake_case(tmp_path):
    writer = _FakeCodeWriter(_ok_result())
    factory = _factory(tmp_path, code_writer=writer)

    result = factory.build_skill("research", "Skill Con Espacios", "algo")

    assert result["status"] == "rejected"
    assert writer.calls == []


def test_build_skill_accepts_a_valid_snake_case_branch_and_skill_name(tmp_path):
    written = {
        "snarf/specialists/research/deep_research_v2.py",
        "snarf/specialists/research/__init__.py",
        "tests/test_deep_research_v2.py",
    }
    factory = _factory(tmp_path, code_writer=_FakeCodeWriter(_ok_result(files_written=frozenset(written))))

    result = factory.build_skill("research", "deep_research_v2", "algo")

    assert result["status"] == "built"


def test_list_proposals_reflects_the_index(tmp_path):
    factory = _factory(tmp_path)
    factory.build_skill("research", "x", "algo")

    proposals = factory.list_proposals()

    assert len(proposals) == 1
    assert proposals[0]["skill_name"] == "x"
