import json
import subprocess

from snarf.capabilities.claude_code import ClaudeCode


def _fake_completed_process(stdout: str, returncode: int = 0):
    return subprocess.CompletedProcess(args=["claude"], returncode=returncode, stdout=stdout, stderr="")


def test_available_reflects_whether_the_real_binary_exists(monkeypatch, tmp_path):
    cc = ClaudeCode(cwd=tmp_path)
    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/claude")
    assert cc.available is True
    monkeypatch.setattr("shutil.which", lambda name: None)
    assert cc.available is False


def test_run_parses_a_real_shaped_success_response(monkeypatch, tmp_path):
    raw = {
        "is_error": False,
        "subtype": "success",
        "result": "listo",
        "session_id": "abc123",
        "total_cost_usd": 0.0624227,
        "num_turns": 3,
    }
    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/claude")
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _fake_completed_process(json.dumps(raw)))

    result = ClaudeCode(cwd=tmp_path).run("hacé algo")

    assert result.ok is True
    assert result.result_text == "listo"
    assert result.session_id == "abc123"
    assert result.cost_usd == 0.0624227
    assert result.num_turns == 3


def test_run_reports_is_error_true_as_not_ok(monkeypatch, tmp_path):
    raw = {"is_error": True, "subtype": "error_during_execution", "result": "algo falló"}
    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/claude")
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _fake_completed_process(json.dumps(raw)))

    result = ClaudeCode(cwd=tmp_path).run("hacé algo")

    assert result.ok is False


def test_run_handles_non_json_output_without_crashing(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/claude")
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _fake_completed_process("no es json", returncode=1))

    result = ClaudeCode(cwd=tmp_path).run("hacé algo")

    assert result.ok is False
    assert "no-JSON" in result.result_text


def test_run_handles_a_real_timeout_without_crashing(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/claude")

    def fake_run(*a, **kw):
        raise subprocess.TimeoutExpired(cmd="claude", timeout=1)

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = ClaudeCode(cwd=tmp_path, timeout_seconds=1).run("hacé algo")

    assert result.ok is False
    assert "Timeout" in result.result_text


def test_run_raises_if_the_binary_is_not_available(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda name: None)
    import pytest

    with pytest.raises(RuntimeError):
        ClaudeCode(cwd=tmp_path).run("hacé algo")


def test_run_passes_the_scoped_allowed_and_disallowed_tools(monkeypatch, tmp_path):
    captured = {}

    def fake_run(command, **kw):
        captured["command"] = command
        return _fake_completed_process(json.dumps({"is_error": False, "subtype": "success", "result": "ok"}))

    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/claude")
    monkeypatch.setattr(subprocess, "run", fake_run)

    ClaudeCode(cwd=tmp_path).run("hacé algo")

    command = captured["command"]
    assert "--allowedTools" in command
    assert "Edit" in command
    assert "--disallowedTools" in command
    assert "Bash(git push*)" in command
    assert str(tmp_path) not in command  # cwd va como kwarg, no como argumento de línea de comando
