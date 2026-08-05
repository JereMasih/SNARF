import re
from dataclasses import dataclass
from typing import Literal

Basis = Literal["hecho", "inferencia", "hipótesis", "estimación", "opinión"]
BASIS_VALUES: tuple[Basis, ...] = ("hecho", "inferencia", "hipótesis", "estimación", "opinión")


@dataclass(frozen=True)
class ExecutiveOpinion:
    claim: str
    basis: Basis
    source: str | None = None


_CLAIM_LINE_RE = re.compile(r"^CLAIM:\s*(.+?)\s*\|\s*BASIS:\s*(\S+)\s*\|\s*FUENTE:\s*(.*)$", re.IGNORECASE)


def _parse_claim_line(line: str) -> tuple[str, str, str] | None:
    match = _CLAIM_LINE_RE.match(line.strip())
    if not match:
        return None
    claim, basis, source = match.group(1).strip(), match.group(2).strip().lower(), match.group(3).strip()
    return claim, basis, source


def parse_opinions(text: str, tools_actually_called: set[str]) -> tuple[str, list[ExecutiveOpinion]]:
    """Parsea la respuesta en formato fijo de un rol de Inteligencia Ejecutiva
    (ver roles.py, el prompt que pide este formato). Disciplina de honestidad
    verificada en código, no confiada al self-report del modelo (ADR 0094):
    una línea que se autodeclara BASIS='hecho' pero cuya FUENTE no es el
    nombre EXACTO de un tool realmente llamado en este turno se degrada
    mecánicamente a 'inferencia' antes de devolverse — ningún rol puede
    afirmar un hecho sin haber consultado de verdad la herramienta que dice
    haber consultado."""
    parts = text.split("---", 1)
    headline = ""
    for line in parts[0].splitlines():
        line = line.strip()
        if line.upper().startswith("HEADLINE:"):
            headline = line.split(":", 1)[1].strip()

    opinions: list[ExecutiveOpinion] = []
    if len(parts) > 1:
        for line in parts[1].splitlines():
            line = line.strip()
            if not line:
                continue
            parsed = _parse_claim_line(line)
            if not parsed:
                continue
            claim, basis, source = parsed
            if not claim:
                continue
            if basis not in BASIS_VALUES:
                basis = "opinión"
            if basis == "hecho" and source not in tools_actually_called:
                basis = "inferencia"
            opinions.append(ExecutiveOpinion(claim=claim, basis=basis, source=source or None))
    return headline or "Sin postura clara.", opinions
