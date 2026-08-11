import sys

from snarf.runtime import proctitle_exec


def test_main_sets_the_real_process_title(monkeypatch):
    calls = []
    monkeypatch.setattr("setproctitle.setproctitle", lambda title: calls.append(title))
    monkeypatch.setattr(sys, "argv", ["proctitle_exec", "snarf-mlx-fast", "json", "--help"])
    monkeypatch.setattr("runpy.run_module", lambda module, run_name=None: calls.append((module, run_name)))

    proctitle_exec.main()

    assert calls[0] == "snarf-mlx-fast"
    assert calls[1] == ("json", "__main__")


def test_main_rewrites_argv_for_the_wrapped_module(monkeypatch):
    monkeypatch.setattr("setproctitle.setproctitle", lambda title: None)
    monkeypatch.setattr(sys, "argv", ["proctitle_exec", "snarf-kokoro-tts", "uvicorn", "api.src.main:app", "--port", "8880"])

    captured_argv = {}

    def fake_run_module(module, run_name=None):
        captured_argv["argv"] = list(sys.argv)
        captured_argv["module"] = module

    monkeypatch.setattr("runpy.run_module", fake_run_module)

    proctitle_exec.main()

    assert captured_argv["module"] == "uvicorn"
    assert captured_argv["argv"] == ["uvicorn", "api.src.main:app", "--port", "8880"]


def test_main_requires_at_least_a_title_and_a_module(monkeypatch):
    import pytest

    monkeypatch.setattr(sys, "argv", ["proctitle_exec", "solo-un-nombre"])
    with pytest.raises(SystemExit):
        proctitle_exec.main()
