"""Control real de los procesos/LaunchAgents propios de Snarf en esta Mac —
primera pieza real del cockpit del fundador (Fase 9.1 del plan de
multi-usuario/observabilidad, adelantada por pedido explícito: "necesito
poder distinguir con nombre correcto esos procesos... y tener una interfaz
para abrirlos y cerrarlos"). Allowlist positivo explícito de labels reales
de LaunchAgent — nunca un label arbitrario, mismo criterio de seguridad que
`snarf/mcp/tools.py::MCP_EXPOSED_TOOLS`."""

import os
import subprocess
from typing import Callable

LAUNCH_AGENT_LABELS: dict[str, str] = {
    "com.snarf.server": "Servidor principal de Snarf (puerto 8002)",
    "com.snarf.mlx-fast": "Modelo local rápido (MLX, puerto 8991)",
    "com.snarf.mlx-heavy": "Modelo local pesado (MLX, puerto 8990)",
    "com.snarf.mlx-mid": "Modelo local intermedio (MLX, puerto 8992)",
    "com.snarf.mlx-watchdog": "Vigilante de memoria de los servers MLX (corre cada 90s, no queda 'running' entre ciclos)",
    "com.snarf.kokoro-tts": "Síntesis de voz nativa (Kokoro, puerto 8880)",
}

# Reiniciarse a sí mismo mataría el propio proceso que está respondiendo
# este mismo tool call a mitad de camino — a diferencia de los demás, nunca
# se ejecuta desde el chat. Reiniciarlo sigue siendo manual por terminal
# (ver CLAUDE.md: "confirmar con el fundador primero").
_NOT_RESTARTABLE_VIA_TOOL = {"com.snarf.server"}

CommandRunner = Callable[[list[str]], subprocess.CompletedProcess]


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=15)


def _pid_for_label(label: str, run: CommandRunner) -> int | None:
    result = run(["launchctl", "list"])
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[2] == label and parts[0] != "-":
            try:
                return int(parts[0])
            except ValueError:
                return None
    return None


def _rss_mb(pid: int, run: CommandRunner) -> float | None:
    result = run(["ps", "-o", "rss=", "-p", str(pid)])
    text = result.stdout.strip()
    if not text:
        return None
    try:
        return round(int(text) / 1024, 1)
    except ValueError:
        return None


def status(run: CommandRunner = _run) -> list[dict]:
    """Estado real de cada LaunchAgent conocido — nunca inventa un pid o un
    uso de memoria: `running=False`/`pid=None`/`rss_mb=None` cuando de
    verdad no está corriendo (ej. com.snarf.mlx-watchdog entre sus ciclos de
    90s, o com.snarf.mlx-heavy/-mid si no están cargados)."""
    entries = []
    for label, friendly_name in LAUNCH_AGENT_LABELS.items():
        pid = _pid_for_label(label, run)
        entries.append(
            {
                "label": label,
                "friendly_name": friendly_name,
                "running": pid is not None,
                "pid": pid,
                "rss_mb": _rss_mb(pid, run) if pid is not None else None,
                "restartable_via_tool": label not in _NOT_RESTARTABLE_VIA_TOOL,
            }
        )
    return entries


def restart(label: str, run: CommandRunner = _run) -> dict:
    if label not in LAUNCH_AGENT_LABELS:
        raise ValueError(f"'{label}' no es un proceso real de Snarf conocido.")
    if label in _NOT_RESTARTABLE_VIA_TOOL:
        raise ValueError(
            f"'{label}' no se reinicia desde acá — reiniciaría el propio proceso que está "
            "respondiendo este pedido. Hacelo por terminal (ver CLAUDE.md)."
        )
    run(["launchctl", "kickstart", "-k", f"gui/{os.getuid()}/{label}"])
    return {"label": label, "restarted": True}
