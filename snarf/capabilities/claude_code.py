"""Invoca al CLI real de Claude Code de forma headless (ver ADR 0095/0102) —
único consumidor real de esta Capacidad: `SkillFactorySpecialist`. Nunca se
asume la forma del CLI real: verificado campo por campo antes de escribir
este módulo (`claude -p "..." --output-format json`, versión 2.1.220 real
instalada en la máquina del fundador), mismo criterio que ya se usó con el
SDK `mcp` en ADR 0097.

Alcance de herramientas deliberadamente acotado (`--allowedTools`): solo
Edit/Write/Read/Glob/Grep y correr la suite real de tests — nunca acceso a
red, nunca `git push`/`git commit` (el commit real lo hace el fundador o una
sesión de Claude Code interactiva, nunca este flujo automático), nunca un
Bash sin restricción. `--permission-mode acceptEdits` como resguardo para
cualquier tool no cubierto explícito por el allowlist, más un timeout real
como último resguardo — sin esto, una invocación headless sin TTY que
necesite un permiso no cubierto se cuelga esperando una respuesta que nunca
llega."""

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from snarf.capabilities.base import Capability

CLAUDE_BINARY = "claude"

# Alcance real y acotado — ver POLICY_HIGH_IMPACT_ACTIONS.md / ADR 0095: la
# Skill Factory puede escribir/leer código y correr tests, nunca más que eso.
DEFAULT_ALLOWED_TOOLS = ("Edit", "Write", "Read", "Glob", "Grep", "Bash(.venv/bin/python -m pytest*)")
DEFAULT_DISALLOWED_TOOLS = ("Bash(git push*)", "Bash(git commit*)", "Bash(rm -rf*)", "WebFetch", "WebSearch")
DEFAULT_TIMEOUT_SECONDS = 900


@dataclass(frozen=True)
class ClaudeCodeResult:
    ok: bool
    result_text: str
    session_id: str | None
    cost_usd: float | None
    num_turns: int | None
    raw: dict


class ClaudeCode(Capability):
    name = "claude_code"

    def __init__(
        self,
        cwd: Path,
        allowed_tools: tuple[str, ...] = DEFAULT_ALLOWED_TOOLS,
        disallowed_tools: tuple[str, ...] = DEFAULT_DISALLOWED_TOOLS,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ):
        self._cwd = cwd
        self._allowed_tools = allowed_tools
        self._disallowed_tools = disallowed_tools
        self._timeout_seconds = timeout_seconds

    @property
    def available(self) -> bool:
        return shutil.which(CLAUDE_BINARY) is not None

    def run(self, prompt: str) -> ClaudeCodeResult:
        if not self.available:
            raise RuntimeError(f"'{CLAUDE_BINARY}' no está instalado en esta máquina.")
        command = [
            CLAUDE_BINARY,
            "-p",
            prompt,
            "--output-format",
            "json",
            "--permission-mode",
            "acceptEdits",
            "--allowedTools",
            *self._allowed_tools,
            "--disallowedTools",
            *self._disallowed_tools,
        ]
        try:
            result = subprocess.run(
                command, cwd=str(self._cwd), capture_output=True, text=True, timeout=self._timeout_seconds
            )
        except subprocess.TimeoutExpired as exc:
            return ClaudeCodeResult(
                ok=False,
                result_text=f"Timeout real tras {self._timeout_seconds}s sin terminar.",
                session_id=None,
                cost_usd=None,
                num_turns=None,
                raw={"timeout": True, "stdout": (exc.stdout or "")[:2000]},
            )
        try:
            raw = json.loads(result.stdout)
        except (json.JSONDecodeError, ValueError):
            return ClaudeCodeResult(
                ok=False,
                result_text=f"Salida no-JSON real del CLI (returncode={result.returncode}): {result.stderr[:500]}",
                session_id=None,
                cost_usd=None,
                num_turns=None,
                raw={"returncode": result.returncode, "stdout": result.stdout[:2000], "stderr": result.stderr[:2000]},
            )
        ok = raw.get("subtype") == "success" and not raw.get("is_error", True)
        return ClaudeCodeResult(
            ok=ok,
            result_text=raw.get("result", ""),
            session_id=raw.get("session_id"),
            cost_usd=raw.get("total_cost_usd"),
            num_turns=raw.get("num_turns"),
            raw=raw,
        )
