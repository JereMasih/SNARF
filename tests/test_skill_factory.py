from snarf.capabilities.claude_code import ClaudeCodeResult
from snarf.specialists.skill_factory import SkillFactorySpecialist


class _FakeClaudeCode:
    available = True

    def __init__(self, result: ClaudeCodeResult):
        self._result = result
        self.calls = []

    def run(self, prompt: str) -> ClaudeCodeResult:
        self.calls.append(prompt)
        return self._result


def _ok_result(**overrides) -> ClaudeCodeResult:
    base = dict(ok=True, result_text="listo", session_id="s1", cost_usd=0.05, num_turns=4, raw={})
    base.update(overrides)
    return ClaudeCodeResult(**base)


def _factory(
    tmp_path,
    claude_code=None,
    dirty_files_sequence=None,
    tests_pass=True,
    restart_calls=None,
):
    dirty_files_sequence = list(dirty_files_sequence or [set(), set()])

    def dirty_files_fn():
        return dirty_files_sequence.pop(0)

    def run_tests_fn():
        return {"passed": tests_pass, "output": "output real de pytest"}

    def restart_fn():
        if restart_calls is not None:
            restart_calls.append(True)

    return SkillFactorySpecialist(
        claude_code=claude_code or _FakeClaudeCode(_ok_result()),
        repo_root=tmp_path,
        git_dirty_files_fn=dirty_files_fn,
        run_tests_fn=run_tests_fn,
        restart_fn=restart_fn,
        proposals_dir=tmp_path / "skill_proposals",
    )


def test_build_skill_within_scope_succeeds(tmp_path):
    before = set()
    after = {
        "snarf/specialists/research/deep_research.py",
        "tests/test_deep_research.py",
        "snarf/core/orchestrator.py",
        "snarf/telemetry/brain.py",
        "snarf/telemetry/verbs.py",
        "snarf/telemetry/detail.py",
    }
    factory = _factory(tmp_path, dirty_files_sequence=[before, after])

    result = factory.build_skill("research", "deep_research", "investiga temas a fondo")

    assert result["status"] == "built"
    assert sorted(result["diff_files"]) == sorted(after)
    manifest = factory.load_manifest(result["proposal_id"])
    assert manifest["status"] == "built"


def test_build_skill_tolerates_preexisting_dirty_files_from_another_session(tmp_path):
    # El working tree YA tenía cambios reales sin commitear de otra sesión
    # antes de esta construcción — no deben contarse como "tocados" por
    # Claude Code, ni disparar un abort falso.
    before = {"snarf/runtime/llm_routing.py", "app.py"}
    after = before | {
        "snarf/specialists/finance/receipts_tracker.py",
        "tests/test_receipts_tracker.py",
        "snarf/core/orchestrator.py",
        "snarf/telemetry/brain.py",
        "snarf/telemetry/verbs.py",
        "snarf/telemetry/detail.py",
    }
    factory = _factory(tmp_path, dirty_files_sequence=[before, after])

    result = factory.build_skill("finance", "receipts_tracker", "trackea recibos reales")

    assert result["status"] == "built"
    assert "snarf/runtime/llm_routing.py" not in result["diff_files"]
    assert "app.py" not in result["diff_files"]


def test_build_skill_aborts_when_a_foundational_doc_is_touched(tmp_path):
    before = set()
    after = {
        "snarf/specialists/research/x.py",
        "tests/test_x.py",
        "snarf/core/orchestrator.py",
        "snarf/telemetry/brain.py",
        "snarf/telemetry/verbs.py",
        "snarf/telemetry/detail.py",
        "CONSTITUTION.md",
    }
    factory = _factory(tmp_path, dirty_files_sequence=[before, after])

    result = factory.build_skill("research", "x", "algo")

    assert result["status"] == "aborted"
    assert "CONSTITUTION.md" in result["reason"]
    manifest = factory.load_manifest(result["proposal_id"])
    assert manifest["status"] == "aborted"


def test_build_skill_aborts_when_an_unexpected_file_outside_scope_is_touched(tmp_path):
    before = set()
    after = {
        "snarf/specialists/research/x.py",
        "tests/test_x.py",
        "snarf/core/orchestrator.py",
        "snarf/telemetry/brain.py",
        "snarf/telemetry/verbs.py",
        "snarf/telemetry/detail.py",
        "snarf/capabilities/google_drive.py",  # nunca autorizado a tocar una Capacidad existente
    }
    factory = _factory(tmp_path, dirty_files_sequence=[before, after])

    result = factory.build_skill("research", "x", "algo")

    assert result["status"] == "aborted"
    assert "google_drive.py" in result["reason"]


def test_build_skill_fails_when_the_real_test_suite_does_not_pass(tmp_path):
    before = set()
    after = {
        "snarf/specialists/research/x.py",
        "tests/test_x.py",
        "snarf/core/orchestrator.py",
        "snarf/telemetry/brain.py",
        "snarf/telemetry/verbs.py",
        "snarf/telemetry/detail.py",
    }
    factory = _factory(tmp_path, dirty_files_sequence=[before, after], tests_pass=False)

    result = factory.build_skill("research", "x", "algo")

    assert result["status"] == "failed"
    assert "test_output" in result


def test_build_skill_fails_honestly_when_claude_code_itself_fails(tmp_path):
    broken = _FakeClaudeCode(ClaudeCodeResult(ok=False, result_text="crédito agotado", session_id=None, cost_usd=None, num_turns=None, raw={}))
    factory = _factory(tmp_path, claude_code=broken, dirty_files_sequence=[set(), set()])

    result = factory.build_skill("research", "x", "algo")

    assert result["status"] == "failed"
    assert "crédito agotado" in result["reason"]


def test_build_skill_fails_when_claude_code_is_not_available(tmp_path):
    class _Unavailable:
        available = False

    factory = SkillFactorySpecialist(
        claude_code=_Unavailable(), repo_root=tmp_path, proposals_dir=tmp_path / "skill_proposals"
    )

    result = factory.build_skill("research", "x", "algo")

    assert result["status"] == "failed"
    assert "no está instalado" in result["reason"]


def test_activate_requires_a_built_proposal(tmp_path):
    restart_calls = []
    factory = _factory(tmp_path, dirty_files_sequence=[set(), set()], restart_calls=restart_calls)
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
    before = set()
    after = {
        "snarf/specialists/research/x.py",
        "tests/test_x.py",
        "snarf/core/orchestrator.py",
        "snarf/telemetry/brain.py",
        "snarf/telemetry/verbs.py",
        "snarf/telemetry/detail.py",
        "CONSTITUTION.md",
    }
    restart_calls = []
    factory = _factory(tmp_path, dirty_files_sequence=[before, after], restart_calls=restart_calls)
    aborted = factory.build_skill("research", "x", "algo")

    result = factory.activate(aborted["proposal_id"])

    assert "error" in result
    assert restart_calls == []


def test_status_returns_the_persisted_manifest(tmp_path):
    factory = _factory(tmp_path, dirty_files_sequence=[set(), set()])
    built = factory.build_skill("research", "x", "algo")

    status = factory.status(built["proposal_id"])

    assert status["branch"] == "research"
    assert status["skill_name"] == "x"


def test_list_proposals_reflects_the_index(tmp_path):
    factory = _factory(tmp_path, dirty_files_sequence=[set(), set()])
    factory.build_skill("research", "x", "algo")

    proposals = factory.list_proposals()

    assert len(proposals) == 1
    assert proposals[0]["skill_name"] == "x"
