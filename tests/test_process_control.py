from types import SimpleNamespace

import pytest

from snarf.runtime import process_control


def _fake_runner(launchctl_list_output: str, rss_by_pid: dict[int, str] | None = None):
    rss_by_pid = rss_by_pid or {}

    def run(args: list[str]):
        if args[:2] == ["launchctl", "list"]:
            return SimpleNamespace(stdout=launchctl_list_output)
        if args[0] == "ps":
            pid = int(args[-1])
            return SimpleNamespace(stdout=rss_by_pid.get(pid, ""))
        if args[:2] == ["launchctl", "kickstart"]:
            return SimpleNamespace(stdout="")
        raise AssertionError(f"comando inesperado: {args}")

    return run


def test_status_reports_a_running_process_with_real_pid_and_rss():
    launchctl_output = "39144\t0\tcom.snarf.mlx-fast\n"
    run = _fake_runner(launchctl_output, rss_by_pid={39144: "2528640"})
    entries = process_control.status(run=run)
    fast = next(e for e in entries if e["label"] == "com.snarf.mlx-fast")
    assert fast["running"] is True
    assert fast["pid"] == 39144
    assert fast["rss_mb"] == 2469.4
    assert fast["restartable_via_tool"] is True


def test_status_reports_a_stopped_process_honestly():
    run = _fake_runner("")  # launchctl list vacío -> nada corriendo
    entries = process_control.status(run=run)
    heavy = next(e for e in entries if e["label"] == "com.snarf.mlx-heavy")
    assert heavy["running"] is False
    assert heavy["pid"] is None
    assert heavy["rss_mb"] is None


def test_status_treats_a_dash_pid_as_not_running():
    # launchctl usa "-" cuando el label está registrado pero sin PID activo
    # (ej. com.snarf.mlx-watchdog entre sus ciclos de 90s) — no es lo mismo
    # que "no existe", pero tampoco está "corriendo" de verdad ahora mismo.
    run = _fake_runner("-\t0\tcom.snarf.mlx-watchdog\n")
    entries = process_control.status(run=run)
    watchdog = next(e for e in entries if e["label"] == "com.snarf.mlx-watchdog")
    assert watchdog["running"] is False
    assert watchdog["pid"] is None


def test_com_snarf_server_is_flagged_as_not_restartable_via_tool():
    run = _fake_runner("85796\t0\tcom.snarf.server\n", rss_by_pid={85796: "112640"})
    entries = process_control.status(run=run)
    server = next(e for e in entries if e["label"] == "com.snarf.server")
    assert server["restartable_via_tool"] is False


def test_restart_rejects_an_unknown_label():
    run = _fake_runner("")
    with pytest.raises(ValueError, match="no es un proceso real"):
        process_control.restart("com.algo.inventado", run=run)


def test_restart_refuses_to_restart_its_own_server_process():
    run = _fake_runner("")
    with pytest.raises(ValueError, match="propio proceso"):
        process_control.restart("com.snarf.server", run=run)


def test_restart_calls_launchctl_kickstart_for_a_real_allowed_label():
    calls = []

    def run(args):
        calls.append(args)
        return SimpleNamespace(stdout="")

    result = process_control.restart("com.snarf.mlx-fast", run=run)
    assert result == {"label": "com.snarf.mlx-fast", "restarted": True}
    assert calls[0][0] == "launchctl"
    assert calls[0][1] == "kickstart"
    assert "com.snarf.mlx-fast" in calls[0][3]
