import os
import subprocess
from typing import Callable

# mlx_lm.server (versión instalada, 0.31.3) tiene un bug real confirmado esta
# ronda: --prompt-cache-bytes nunca llega al constructor real de su caché LRU
# (server.py solo pasa --prompt-cache-size), así que el tope de bytes casi
# nunca se respeta; y si una generación choca con un out-of-memory real de
# Metal, la limpieza (BatchGenerator.close/__del__) puede fallar con el MISMO
# error y dejar esa memoria de GPU ya asignada sin liberar nunca — un caso
# real esta ronda llegó a 31GB de RAM real (casi toda la Mac de 32GB), con el
# proceso vivo pero inservible (0% CPU, cada request real caía a Grok). El
# tope de HISTORY_COMPACTION_INPUT_MAX_CHARS en orchestrator.py y
# --prompt-cache-size más bajo en los 3 plists atacan la causa más común
# (ver ADR de esta ronda) — esto es la última red de seguridad: si CUALQUIER
# server mlx_lm real supera la cuota de memoria, se reinicia solo, sin
# esperar a que alguien lo note.
MAX_MEMORY_FRACTION = 0.25

MLX_LAUNCH_AGENT_LABELS = ["com.snarf.mlx-fast", "com.snarf.mlx-heavy", "com.snarf.mlx-mid"]

CommandRunner = Callable[[list[str]], str]


def _run(args: list[str]) -> str:
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout


def total_memory_bytes(run: CommandRunner = _run) -> int:
    return int(run(["sysctl", "-n", "hw.memsize"]).strip())


def pid_for_label(label: str, run: CommandRunner = _run) -> int | None:
    for line in run(["launchctl", "list"]).splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[2] == label and parts[0] != "-":
            return int(parts[0])
    return None


def rss_bytes(pid: int, run: CommandRunner = _run) -> int:
    output = run(["ps", "-o", "rss=", "-p", str(pid)]).strip()
    return int(output) * 1024 if output else 0


def is_over_budget(rss: int, total_memory: int, max_fraction: float = MAX_MEMORY_FRACTION) -> bool:
    return rss > total_memory * max_fraction


def restart_label(label: str, run: CommandRunner = _run) -> None:
    run(["launchctl", "kickstart", "-k", f"gui/{os.getuid()}/{label}"])


def check_and_restart_over_budget_agents(
    labels: list[str] = MLX_LAUNCH_AGENT_LABELS, run: CommandRunner = _run
) -> list[str]:
    """Revisa cada LaunchAgent MLX real por su uso de memoria y reinicia
    (`launchctl kickstart -k`) el que supere la cuota — devuelve los labels
    reiniciados en esta pasada (lista vacía si ninguno la superó, incluidos
    los que ni siquiera están cargados)."""
    total_memory = total_memory_bytes(run)
    restarted = []
    for label in labels:
        pid = pid_for_label(label, run)
        if pid is None:
            continue
        if is_over_budget(rss_bytes(pid, run), total_memory):
            restart_label(label, run)
            restarted.append(label)
    return restarted


if __name__ == "__main__":
    check_and_restart_over_budget_agents()
