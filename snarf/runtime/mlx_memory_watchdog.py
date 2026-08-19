import os
import re
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
#
# 2026-08-18: el mismo escenario (31GB) volvió a pasar con esta red de
# seguridad ya desplegada, porque medía con `ps -o rss=` — que en procesos
# MLX no ve la memoria unificada de Metal (GPU): `ps` reportaba 2.2GB
# mientras `top`/Activity Monitor (phys_footprint real) marcaban 31GB, así
# que el watchdog nunca detectó el problema. Ahora mide con
# `top -l 1 -pid <pid> -stats pid,mem` (la misma cifra que Activity Monitor)
# y avisa por notificación de macOS cuando reinicia algo.
MAX_MEMORY_FRACTION = 0.25

MLX_LAUNCH_AGENT_LABELS = ["com.snarf.mlx-fast", "com.snarf.mlx-heavy", "com.snarf.mlx-mid"]

CommandRunner = Callable[[list[str]], str]

_MEMORY_SIZE_RE = re.compile(r"^([\d.]+)([BKMGT]?)$", re.IGNORECASE)
_MEMORY_UNIT_MULTIPLIER = {"": 1, "B": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}


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


def _parse_memory_size(text: str) -> int:
    match = _MEMORY_SIZE_RE.match(text.strip())
    if not match:
        return 0
    value, unit = match.groups()
    return int(float(value) * _MEMORY_UNIT_MULTIPLIER[unit.upper()])


def footprint_bytes(pid: int, run: CommandRunner = _run) -> int:
    """Memoria física real del proceso (phys_footprint) — la misma cifra que
    Activity Monitor, incluye la memoria unificada de Metal que
    `ps -o rss=` no ve en procesos MLX."""
    output = run(["top", "-l", "1", "-pid", str(pid), "-stats", "pid,mem"])
    for line in reversed(output.splitlines()):
        parts = line.split()
        if len(parts) >= 2 and parts[0] == str(pid):
            return _parse_memory_size(parts[-1])
    return 0


def is_over_budget(footprint: int, total_memory: int, max_fraction: float = MAX_MEMORY_FRACTION) -> bool:
    return footprint > total_memory * max_fraction


def restart_label(label: str, run: CommandRunner = _run) -> None:
    run(["launchctl", "kickstart", "-k", f"gui/{os.getuid()}/{label}"])


def _notify_restart(label: str, footprint: int, run: CommandRunner) -> None:
    gb = footprint / (1024**3)
    message = f"{label} superó la cuota de memoria ({gb:.1f} GB) y se reinició solo."
    run(["osascript", "-e", f'display notification "{message}" with title "Snarf"'])


def check_and_restart_over_budget_agents(
    labels: list[str] = MLX_LAUNCH_AGENT_LABELS, run: CommandRunner = _run
) -> list[str]:
    """Revisa cada LaunchAgent MLX real por su memoria física (no RSS) y
    reinicia (`launchctl kickstart -k`) el que supere la cuota, avisando por
    notificación de macOS — devuelve los labels reiniciados en esta pasada
    (lista vacía si ninguno la superó, incluidos los que ni siquiera están
    cargados)."""
    total_memory = total_memory_bytes(run)
    restarted = []
    for label in labels:
        pid = pid_for_label(label, run)
        if pid is None:
            continue
        footprint = footprint_bytes(pid, run)
        if is_over_budget(footprint, total_memory):
            restart_label(label, run)
            _notify_restart(label, footprint, run)
            restarted.append(label)
    return restarted


if __name__ == "__main__":
    check_and_restart_over_budget_agents()
