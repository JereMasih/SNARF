import pytest

from snarf.capabilities.anthropic_llm import LLMResponse
from snarf.capabilities.local_code_writer import MAX_BUILD_TOOL_ROUNDS, LocalCodeWriter


class FakeToolLoopLLM:
    """Simula el NETO de un loop real de tool-calling (el loop en sí ya está
    testeado en tests/test_openai_compatible_llm.py) — ejecuta una
    secuencia scripteada de llamadas a tool_handler en orden y devuelve un
    texto final, para poder testear acá solo la lógica propia de
    LocalCodeWriter: gateo de paths, semántica de edit_file, y
    determinación de ok."""

    def __init__(self, available=True, tool_calls=None, final_text="LISTO"):
        self.available = available
        self._tool_calls = tool_calls or []
        self._final_text = final_text
        self.captured_max_tool_rounds = None
        self.tool_results = []

    def generate(self, system, messages, tools=None, tool_handler=None, max_tool_rounds=5):
        self.captured_max_tool_rounds = max_tool_rounds
        for name, tool_input in self._tool_calls:
            self.tool_results.append(tool_handler(name, tool_input))
        return LLMResponse(text=self._final_text, speech=self._final_text)


def make_writer(tmp_path, available=True, tool_calls=None, final_text="LISTO", run_tests_fn=None):
    llm = FakeToolLoopLLM(available=available, tool_calls=tool_calls, final_text=final_text)
    # Nunca corre pytest real por defecto (tmp_path no tiene .venv real) —
    # solo el test dedicado a run_tests_fn pasa el suyo propio.
    run_tests_fn = run_tests_fn or (lambda: {"passed": True, "output": "ok"})
    writer = LocalCodeWriter(llm_factory=lambda: llm, repo_root=tmp_path, run_tests_fn=run_tests_fn)
    return writer, llm


def test_available_reflects_the_llm_factory(tmp_path):
    writer, _ = make_writer(tmp_path, available=False)
    assert writer.available is False
    writer2, _ = make_writer(tmp_path, available=True)
    assert writer2.available is True


def test_run_raises_when_the_llm_is_not_available(tmp_path):
    writer, _ = make_writer(tmp_path, available=False)
    with pytest.raises(RuntimeError):
        writer.run("hacé algo", allowed_write_paths=set(), allowed_edit_paths=set())


def test_write_file_within_scope_writes_the_real_file_and_succeeds(tmp_path):
    writer, _ = make_writer(
        tmp_path,
        tool_calls=[
            ("write_file", {"path": "snarf/specialists/research/x.py", "content": "contenido real"}),
            ("run_tests", {}),
        ],
    )
    result = writer.run(
        "prompt", allowed_write_paths={"snarf/specialists/research/x.py"}, allowed_edit_paths=set()
    )
    assert result.ok is True
    assert (tmp_path / "snarf/specialists/research/x.py").read_text(encoding="utf-8") == "contenido real"


def test_files_written_reports_every_successful_write(tmp_path):
    # files_written (ver docstring del módulo) es la única fuente de verdad
    # que SkillFactorySpecialist usa ahora para decidir alcance — nunca un
    # diff de git contra el working tree completo (bug real corregido
    # 2026-08-12: se rompía con cualquier trabajo concurrente en el mismo
    # repo).
    writer, _ = make_writer(
        tmp_path,
        tool_calls=[
            ("write_file", {"path": "snarf/specialists/research/x.py", "content": "contenido"}),
            ("run_tests", {}),
        ],
    )
    result = writer.run(
        "prompt", allowed_write_paths={"snarf/specialists/research/x.py"}, allowed_edit_paths=set()
    )
    assert result.files_written == frozenset({"snarf/specialists/research/x.py"})


def test_files_written_never_includes_a_write_rejected_for_being_out_of_scope(tmp_path):
    writer, _ = make_writer(
        tmp_path,
        tool_calls=[
            ("write_file", {"path": "snarf/core/orchestrator.py", "content": "malicioso"}),
            ("run_tests", {}),
        ],
    )
    result = writer.run("prompt", allowed_write_paths={"snarf/specialists/research/x.py"}, allowed_edit_paths=set())
    assert result.files_written == frozenset()


def test_files_written_includes_successful_edits_and_deduplicates_repeated_writes(tmp_path):
    target = tmp_path / "snarf/core/orchestrator.py"
    target.parent.mkdir(parents=True)
    target.write_text("ANCLA\n", encoding="utf-8")

    writer, _ = make_writer(
        tmp_path,
        tool_calls=[
            ("write_file", {"path": "snarf/specialists/research/x.py", "content": "v1"}),
            ("write_file", {"path": "snarf/specialists/research/x.py", "content": "v2"}),  # autocorrección, mismo path
            ("edit_file", {"path": "snarf/core/orchestrator.py", "old_string": "ANCLA", "new_string": "ANCLA\nnueva"}),
            ("run_tests", {}),
        ],
    )
    result = writer.run(
        "prompt",
        allowed_write_paths={"snarf/specialists/research/x.py"},
        allowed_edit_paths={"snarf/core/orchestrator.py"},
    )
    assert result.files_written == frozenset({"snarf/specialists/research/x.py", "snarf/core/orchestrator.py"})


def test_write_file_can_be_called_again_on_the_same_path_to_self_correct(tmp_path):
    # El motor descubre un error de sintaxis en el propio Specialist que
    # escribió y lo corrige volviendo a llamar write_file sobre el mismo
    # path — nunca necesita (ni tiene) edit_file para sus propios archivos
    # nuevos. Antes de este fix, la descripción de write_file decía "nunca
    # para un archivo que ya existe", lo que hacía que el motor se
    # autobloqueara y abandonara con NO PUDE en vez de corregirse.
    writer, _ = make_writer(
        tmp_path,
        tool_calls=[
            ("write_file", {"path": "snarf/specialists/research/x.py", "content": "contenido con bug"}),
            ("write_file", {"path": "snarf/specialists/research/x.py", "content": "contenido corregido"}),
            ("run_tests", {}),
        ],
    )
    result = writer.run(
        "prompt", allowed_write_paths={"snarf/specialists/research/x.py"}, allowed_edit_paths=set()
    )
    assert result.ok is True
    assert (tmp_path / "snarf/specialists/research/x.py").read_text(encoding="utf-8") == "contenido corregido"


def test_write_file_outside_scope_never_touches_disk(tmp_path):
    writer, llm = make_writer(
        tmp_path,
        tool_calls=[
            ("write_file", {"path": "snarf/core/orchestrator.py", "content": "malicioso"}),
            ("run_tests", {}),
        ],
    )
    writer.run("prompt", allowed_write_paths={"snarf/specialists/research/x.py"}, allowed_edit_paths=set())

    assert not (tmp_path / "snarf/core/orchestrator.py").exists()
    assert "error" in llm.tool_results[0]


def test_edit_file_replaces_a_unique_old_string(tmp_path):
    target = tmp_path / "snarf/core/orchestrator.py"
    target.parent.mkdir(parents=True)
    target.write_text("linea a\nANCLA_UNICA\nlinea c\n", encoding="utf-8")

    writer, _ = make_writer(
        tmp_path,
        tool_calls=[
            (
                "edit_file",
                {"path": "snarf/core/orchestrator.py", "old_string": "ANCLA_UNICA", "new_string": "ANCLA_UNICA\nnueva_linea"},
            ),
            ("run_tests", {}),
        ],
    )
    result = writer.run("prompt", allowed_write_paths=set(), allowed_edit_paths={"snarf/core/orchestrator.py"})

    assert result.ok is True
    assert target.read_text(encoding="utf-8") == "linea a\nANCLA_UNICA\nnueva_linea\nlinea c\n"


def test_edit_file_fails_when_old_string_is_not_found(tmp_path):
    target = tmp_path / "snarf/core/orchestrator.py"
    target.parent.mkdir(parents=True)
    target.write_text("contenido original\n", encoding="utf-8")

    writer, llm = make_writer(
        tmp_path,
        tool_calls=[
            ("edit_file", {"path": "snarf/core/orchestrator.py", "old_string": "no existe", "new_string": "x"}),
            ("run_tests", {}),
        ],
    )
    writer.run("prompt", allowed_write_paths=set(), allowed_edit_paths={"snarf/core/orchestrator.py"})

    assert "error" in llm.tool_results[0]
    assert target.read_text(encoding="utf-8") == "contenido original\n"


def test_edit_file_fails_when_old_string_is_not_unique(tmp_path):
    target = tmp_path / "snarf/core/orchestrator.py"
    target.parent.mkdir(parents=True)
    target.write_text("repetido\nrepetido\n", encoding="utf-8")

    writer, llm = make_writer(
        tmp_path,
        tool_calls=[
            ("edit_file", {"path": "snarf/core/orchestrator.py", "old_string": "repetido", "new_string": "x"}),
            ("run_tests", {}),
        ],
    )
    writer.run("prompt", allowed_write_paths=set(), allowed_edit_paths={"snarf/core/orchestrator.py"})

    assert "error" in llm.tool_results[0]
    assert "no es único" in llm.tool_results[0]["error"]
    assert target.read_text(encoding="utf-8") == "repetido\nrepetido\n"


def test_edit_file_outside_scope_is_rejected(tmp_path):
    target = tmp_path / "FOUNDATION.md"
    target.write_text("texto fundacional", encoding="utf-8")

    writer, llm = make_writer(
        tmp_path,
        tool_calls=[
            ("edit_file", {"path": "FOUNDATION.md", "old_string": "texto fundacional", "new_string": "hackeado"}),
            ("run_tests", {}),
        ],
    )
    writer.run("prompt", allowed_write_paths=set(), allowed_edit_paths={"snarf/core/orchestrator.py"})

    assert "error" in llm.tool_results[0]
    assert target.read_text(encoding="utf-8") == "texto fundacional"


def test_read_file_returns_real_content(tmp_path):
    (tmp_path / "snarf").mkdir()
    (tmp_path / "snarf" / "example.py").write_text("contenido de ejemplo", encoding="utf-8")

    writer, llm = make_writer(tmp_path, tool_calls=[("read_file", {"path": "snarf/example.py"}), ("run_tests", {})])
    writer.run("prompt", allowed_write_paths=set(), allowed_edit_paths=set())

    assert llm.tool_results[0] == {"content": "contenido de ejemplo"}


def test_read_file_reports_a_real_error_when_missing(tmp_path):
    writer, llm = make_writer(tmp_path, tool_calls=[("read_file", {"path": "no/existe.py"}), ("run_tests", {})])
    writer.run("prompt", allowed_write_paths=set(), allowed_edit_paths=set())

    assert "error" in llm.tool_results[0]


def test_unknown_tool_returns_an_error_without_crashing(tmp_path):
    writer, llm = make_writer(tmp_path, tool_calls=[("delete_everything", {}), ("run_tests", {})])
    writer.run("prompt", allowed_write_paths=set(), allowed_edit_paths=set())

    assert llm.tool_results[0] == {"error": "herramienta desconocida: delete_everything"}


def test_ok_requires_listo_in_the_final_text(tmp_path):
    writer, _ = make_writer(tmp_path, tool_calls=[("run_tests", {})], final_text="algo intermedio, sin la palabra clave")
    result = writer.run("prompt", allowed_write_paths=set(), allowed_edit_paths=set())
    assert result.ok is False


def test_ok_requires_at_least_one_real_run_tests_call_even_if_the_model_claims_listo(tmp_path):
    # Un modelo local afirmando éxito sin haber corrido los tests ni una
    # vez nunca cuenta como ok=True acá — mismo motivo que la
    # verificación independiente de SkillFactorySpecialist.build_skill()
    # existe: no confiar en lo que el motor dice de sí mismo.
    writer, _ = make_writer(tmp_path, tool_calls=[], final_text="LISTO")
    result = writer.run("prompt", allowed_write_paths=set(), allowed_edit_paths=set())
    assert result.ok is False


def test_ok_is_false_when_the_model_reports_it_could_not_solve_it(tmp_path):
    writer, _ = make_writer(tmp_path, tool_calls=[("run_tests", {})], final_text="NO PUDE: el test sigue fallando")
    result = writer.run("prompt", allowed_write_paths=set(), allowed_edit_paths=set())
    assert result.ok is False


def test_run_passes_a_generous_tool_round_budget_for_background_builds(tmp_path):
    writer, llm = make_writer(tmp_path, tool_calls=[("run_tests", {})])
    writer.run("prompt", allowed_write_paths=set(), allowed_edit_paths=set())
    assert llm.captured_max_tool_rounds == MAX_BUILD_TOOL_ROUNDS
    assert MAX_BUILD_TOOL_ROUNDS > 5  # notablemente mayor al default del chat interactivo


def test_run_tests_delegates_to_the_real_test_runner(tmp_path):
    calls = []

    def fake_run_tests():
        calls.append(True)
        return {"passed": True, "output": "output real"}

    writer, llm = make_writer(tmp_path, tool_calls=[("run_tests", {})], run_tests_fn=fake_run_tests)
    writer.run("prompt", allowed_write_paths=set(), allowed_edit_paths=set())

    assert calls == [True]
    assert llm.tool_results[0] == {"passed": True, "output": "output real"}


def test_session_id_and_cost_are_always_none_for_a_local_model(tmp_path):
    # A diferencia de Claude Code (session_id/cost_usd reales del CLI), acá
    # no hay ni sesión de cuenta ni costo de API real que trackear —
    # nunca se inventa un valor.
    writer, _ = make_writer(tmp_path, tool_calls=[("run_tests", {})])
    result = writer.run("prompt", allowed_write_paths=set(), allowed_edit_paths=set())
    assert result.session_id is None
    assert result.cost_usd is None
