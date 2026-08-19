from snarf.runtime import mlx_memory_watchdog as watchdog


def test_is_over_budget_true_when_footprint_exceeds_the_fraction():
    total_memory = 32 * (1024**3)
    over_budget = int(total_memory * 0.26)
    assert watchdog.is_over_budget(over_budget, total_memory) is True


def test_is_over_budget_false_when_footprint_is_within_the_fraction():
    total_memory = 32 * (1024**3)
    within_budget = int(total_memory * 0.10)
    assert watchdog.is_over_budget(within_budget, total_memory) is False


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


def test_footprint_bytes_parses_the_mem_column_of_top_with_a_gigabyte_suffix():
    # Formato real de `top -l 1 -pid <pid> -stats pid,mem`: líneas de resumen
    # del sistema, después el header y la fila de datos (la que importa).
    fake_output = "Processes: 500 total\nPhysMem: 31G used\n\nPID   COMMAND MEM\n1578  Python  31G\n"
    assert watchdog.footprint_bytes(1578, run=lambda args: fake_output) == 31 * (1024**3)


def test_footprint_bytes_parses_the_mem_column_of_top_with_a_megabyte_suffix():
    fake_output = "PID   COMMAND MEM\n36660  Python  2439M\n"
    assert watchdog.footprint_bytes(36660, run=lambda args: fake_output) == 2439 * (1024**2)


def test_footprint_bytes_is_zero_when_top_has_no_data_row_for_the_pid():
    # `top -pid <pid>` con un pid que ya no existe: exit 0, sin fila de datos.
    fake_output = "Processes: 466 total\nPhysMem: 15G used\n"
    assert watchdog.footprint_bytes(999999, run=lambda args: fake_output) == 0


class _FakeRun:
    """Simula sysctl/launchctl/top/osascript reales — cada comando real que
    el módulo ejecuta llega acá por su primer argumento distintivo, sin
    tocar el sistema real (nunca correr launchctl kickstart de verdad en un
    test)."""

    def __init__(self, total_memory: int, pids_by_label: dict, footprint_by_pid: dict):
        self.total_memory = total_memory
        self.pids_by_label = pids_by_label
        self.footprint_by_pid = footprint_by_pid
        self.kickstarted = []
        self.notified = []

    def __call__(self, args: list[str]) -> str:
        if args[:2] == ["sysctl", "-n"]:
            return str(self.total_memory)
        if args[0] == "launchctl" and args[1] == "list":
            lines = [f"{pid}\t0\t{label}" for label, pid in self.pids_by_label.items() if pid is not None]
            return "\n".join(lines)
        if args[0] == "top":
            pid = int(args[args.index("-pid") + 1])
            footprint = self.footprint_by_pid.get(pid, 0)
            return f"PID   COMMAND MEM\n{pid}  Python  {footprint}B\n"
        if args[0] == "launchctl" and args[1] == "kickstart":
            self.kickstarted.append(args[-1])
            return ""
        if args[0] == "osascript":
            self.notified.append(args[-1])
            return ""
        raise AssertionError(f"comando inesperado en el test: {args}")


def test_check_and_restart_restarts_only_the_agent_over_budget():
    total_memory = 32 * (1024**3)
    over_budget = int(total_memory * 0.30)
    within_budget = int(total_memory * 0.05)
    fake_run = _FakeRun(
        total_memory=total_memory,
        pids_by_label={"com.snarf.mlx-fast": 111, "com.snarf.mlx-heavy": None, "com.snarf.mlx-mid": 222},
        footprint_by_pid={111: over_budget, 222: within_budget},
    )

    restarted = watchdog.check_and_restart_over_budget_agents(run=fake_run)

    assert restarted == ["com.snarf.mlx-fast"]
    assert fake_run.kickstarted == [f"gui/{__import__('os').getuid()}/com.snarf.mlx-fast"]
    assert len(fake_run.notified) == 1
    assert "com.snarf.mlx-fast" in fake_run.notified[0]


def test_check_and_restart_does_nothing_when_every_agent_is_within_budget():
    total_memory = 32 * (1024**3)
    within_budget = int(total_memory * 0.05)
    fake_run = _FakeRun(
        total_memory=total_memory,
        pids_by_label={"com.snarf.mlx-fast": 111},
        footprint_by_pid={111: within_budget},
    )

    restarted = watchdog.check_and_restart_over_budget_agents(labels=["com.snarf.mlx-fast"], run=fake_run)

    assert restarted == []
    assert fake_run.kickstarted == []
    assert fake_run.notified == []
