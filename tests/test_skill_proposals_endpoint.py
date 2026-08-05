from test_app import client  # noqa: F401 (fixture real de la app, ver test_app.py)


def test_skill_proposals_empty_before_any_build(client):
    res = client.get("/skill_proposals")
    assert res.status_code == 200
    assert res.json() == {"proposals": []}


def test_skill_proposals_reflects_a_real_build(client, monkeypatch, tmp_path):
    import app as app_module

    monkeypatch.setattr(app_module.orchestrator.skill_factory, "_proposals_dir", tmp_path / "skill_proposals")
    monkeypatch.setattr(app_module.orchestrator.skill_factory, "_claude_code", _FakeAvailableClaudeCode())
    monkeypatch.setattr(app_module.orchestrator.skill_factory, "_git_dirty_files_fn", lambda: set())
    monkeypatch.setattr(app_module.orchestrator.skill_factory, "_run_tests_fn", lambda: {"passed": True, "output": "ok"})

    app_module.orchestrator.skill_factory.build_skill("research", "x", "algo")

    res = client.get("/skill_proposals")
    proposals = res.json()["proposals"]
    assert len(proposals) == 1
    assert proposals[0]["skill_name"] == "x"


def test_skill_proposal_detail_for_an_unknown_id(client):
    res = client.get("/skill_proposals/no-existe")
    assert res.status_code == 200
    assert "error" in res.json()


class _FakeAvailableClaudeCode:
    available = True

    def run(self, prompt):
        from snarf.capabilities.claude_code import ClaudeCodeResult

        return ClaudeCodeResult(ok=True, result_text="listo", session_id="s1", cost_usd=0.01, num_turns=1, raw={})
