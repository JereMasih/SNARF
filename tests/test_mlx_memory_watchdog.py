from snarf.runtime import mlx_memory_watchdog as watchdog


def test_is_over_budget_true_when_rss_exceeds_the_fraction():
    total_memory = 32 * (1024**3)
    over_budget_rss = int(total_memory * 0.26)
    assert watchdog.is_over_budget(over_budget_rss, total_memory) is True


def test_is_over_budget_false_when_rss_is_within_the_fraction():
    total_memory = 32 * (1024**3)
    within_budget_rss = int(total_memory * 0.10)
    assert watchdog.is_over_budget(within_budget_rss, total_memory) is False


def test_pid_for_label_parses_a_real_launchctl_list_line():
    fake_output = "12345\t0\tcom.snarf.mlx-fast\n54634\t0\tcom.snarf.server\n"
    assert watchdog.pid_for_label("com.snarf.mlx-fast", run=lambda args: fake_output) == 12345


def test_pid_for_label_returns_none_when_the_agent_is_not_loaded():
    fake_output = "54634\t0\tcom.snarf.server\n"
    assert watchdog.pid_for_label("com.snarf.mlx-fast", run=lambda args: fake_output) is None


def test_pid_for_label_returns_none_when_loaded_without_a_live_pid():
    # launchctl list muestra "-" en vez de un PID para un agente registrado
    # pero no corriendo ahora mismo (recién bootout, o crasheó y no reinició
    # todavía) — no hay proceso real al que pedirle memoria.
    fake_output = "-\t78\tcom.snarf.mlx-fast\n"
    assert watchdog.pid_for_label("com.snarf.mlx-fast", run=lambda args: fake_output) is None


def test_rss_bytes_converts_the_kilobyte_output_of_ps_to_bytes():
    assert watchdog.rss_bytes(22771, run=lambda args: "12176\n") == 12176 * 1024


class _FakeRun:
    """Simula sysctl/launchctl/ps reales — cada comando real que el módulo
    ejecuta llega acá por su primer argumento distintivo, sin tocar el
    sistema real (nunca correr launchctl kickstart de verdad en un test)."""

    def __init__(self, total_memory: int, pids_by_label: dict, rss_by_pid: dict):
        self.total_memory = total_memory
        self.pids_by_label = pids_by_label
        self.rss_by_pid = rss_by_pid
        self.kickstarted = []

    def __call__(self, args: list[str]) -> str:
        if args[:2] == ["sysctl", "-n"]:
            return str(self.total_memory)
        if args[0] == "launchctl" and args[1] == "list":
            lines = [f"{pid}\t0\t{label}" for label, pid in self.pids_by_label.items() if pid is not None]
            return "\n".join(lines)
        if args[0] == "ps":
            pid = int(args[-1])
            return str(self.rss_by_pid.get(pid, 0))
        if args[0] == "launchctl" and args[1] == "kickstart":
            self.kickstarted.append(args[-1])
            return ""
        raise AssertionError(f"comando inesperado en el test: {args}")


def test_check_and_restart_restarts_only_the_agent_over_budget():
    total_memory = 32 * (1024**3)
    over_budget_rss_kb = int(total_memory * 0.30 / 1024)
    within_budget_rss_kb = int(total_memory * 0.05 / 1024)
    fake_run = _FakeRun(
        total_memory=total_memory,
        pids_by_label={"com.snarf.mlx-fast": 111, "com.snarf.mlx-heavy": None, "com.snarf.mlx-mid": 222},
        rss_by_pid={111: over_budget_rss_kb, 222: within_budget_rss_kb},
    )

    restarted = watchdog.check_and_restart_over_budget_agents(run=fake_run)

    assert restarted == ["com.snarf.mlx-fast"]
    assert fake_run.kickstarted == [f"gui/{__import__('os').getuid()}/com.snarf.mlx-fast"]


def test_check_and_restart_does_nothing_when_every_agent_is_within_budget():
    total_memory = 32 * (1024**3)
    within_budget_rss_kb = int(total_memory * 0.05 / 1024)
    fake_run = _FakeRun(
        total_memory=total_memory,
        pids_by_label={"com.snarf.mlx-fast": 111},
        rss_by_pid={111: within_budget_rss_kb},
    )

    restarted = watchdog.check_and_restart_over_budget_agents(labels=["com.snarf.mlx-fast"], run=fake_run)

    assert restarted == []
    assert fake_run.kickstarted == []
