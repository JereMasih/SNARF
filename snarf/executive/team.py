import re
import time

from snarf.executive.process import REPO_ROOT, consult_role
from snarf.executive.roles import ROLE_CONFIGS

# Nunca infinito (ADR 0198) — mismo criterio que _max_continuations de
# AnthropicLLM (ADR 0113): un tope real, con degradación honesta si se
# agota sin consenso real.
DEFAULT_MAX_ROUNDS = 3

TEAM_DRAFT_SYSTEM_PROMPT = (
    "Redactás un borrador real y concreto para el objetivo que te dan, en español — el borrador en sí, "
    "sin relleno, sin explicar lo que vas a hacer antes de hacerlo. Si te dan objeciones reales de una "
    "ronda de crítica anterior, incorporalas de verdad al reescribir — nunca las ignores ni las repitas "
    "sin cambiar nada. Nunca inventes datos, cifras o afirmaciones que no te hayan dado."
)

_OBJECTION_RE = re.compile(r"^\s*(BLOQUEANTE|SUGERENCIA|SIN OBJECI[OÓ]N)\s*:\s*(.+)$", re.IGNORECASE | re.MULTILINE)


def _normalize_severity(raw: str) -> str:
    upper = raw.strip().upper()
    if upper.startswith("BLOQUEANTE"):
        return "BLOQUEANTE"
    if upper.startswith("SUGERENCIA"):
        return "SUGERENCIA"
    return "SIN OBJECIÓN"


def _parse_objections(raw_text: str) -> list[dict]:
    return [
        {"severity": _normalize_severity(match.group(1)), "text": match.group(2).strip()}
        for match in _OBJECTION_RE.finditer(raw_text or "")
    ]


def _critique_question(objective: str, draft: str, role: str) -> str:
    return (
        f"Objetivo real de este equipo: {objective}\n\n"
        f"Borrador actual a criticar:\n{draft}\n\n"
        f"Dame tu crítica real con tu propio criterio de {role} — nunca te ancles al framing de otro "
        "rol, no lo ves. Para cada objeción real que tengas, una línea empezando con 'BLOQUEANTE:' (si "
        "te parece que no se debería avanzar sin resolverla), 'SUGERENCIA:' (mejora real pero no "
        "bloqueante), o 'SIN OBJECIÓN:' si no tenés nada que objetar sobre ese punto."
    )


class TeamSession:
    """Mecanismo de "equipo" multi-agente (ver COGNITION.md, sección
    "Equipos de agentes", y ADR 0179/0198) — extensión real de la
    Inteligencia Ejecutiva (ADR 0093/0094/0098). A diferencia del board
    asesor (`ExecutiveBoardSpecialist.consult()`: una sola ronda, en
    paralelo, sin visibilidad entre roles, nunca decide nada), un equipo:
    itera con crítica cruzada real sobre un borrador, converge a una
    aprobación interna, y puede producir un artefacto real (no solo
    opiniones etiquetadas). Reusa `consult_role` (mismo primitivo de
    proceso separado vía MCP que ya usa el board, ver snarf/executive/
    process.py) para la crítica de cada rol — nunca duplica esa
    infraestructura. Nunca ejecuta ninguna tool mutante por su cuenta: el
    artefacto final vuelve a quien llamó, igual que cualquier Especialista;
    si se usa para escribir algo real (ej. a Notion), pasa por las tools
    mutantes normales con su propio gate de alto impacto."""

    def __init__(self, draft_llm_factory, role_llm_factory_for_role, repo_root=REPO_ROOT, draft_system_prompt_provider=None):
        # draft_llm_factory: callable sin argumentos para el rol de
        # redacción/revisión del borrador (rol de ruteo nuevo
        # "executive_team_writer", ADR 0198). role_llm_factory_for_role:
        # callable(role) -> LLM, mismo factory que ya usa
        # ExecutiveBoardSpecialist para las críticas de cada rol
        # convocado — nunca una instancia fija (ADR 0026).
        self._draft_llm_factory = draft_llm_factory
        self._role_llm_factory_for_role = role_llm_factory_for_role
        self._repo_root = repo_root
        self._draft_system_prompt_provider = draft_system_prompt_provider or (lambda: TEAM_DRAFT_SYSTEM_PROMPT)

    def run(self, objective: str, roles: list[str], max_rounds: int = DEFAULT_MAX_ROUNDS) -> dict:
        unknown = [r for r in roles if r not in ROLE_CONFIGS]
        if unknown:
            return {
                "error": (
                    f"Rol(es) desconocido(s): {', '.join(unknown)}. Roles válidos: {', '.join(ROLE_CONFIGS)}."
                )
            }
        if not roles:
            return {"error": "Un equipo necesita al menos un rol convocado."}
        if max_rounds < 1:
            return {"error": "max_rounds tiene que ser al menos 1."}

        draft = self._generate_draft(objective, previous_objections=None)
        rounds_log = []
        approved = False
        approved_by_exhaustion = False

        for round_number in range(1, max_rounds + 1):
            critiques = {role: self._critique(role, objective, draft) for role in roles}
            blocking = {
                role: [o for o in result["objections"] if o["severity"] == "BLOQUEANTE"]
                for role, result in critiques.items()
            }
            blocking = {role: objs for role, objs in blocking.items() if objs}
            rounds_log.append({"round": round_number, "draft": draft, "critiques": critiques})

            if not blocking:
                approved = True
                break
            if round_number == max_rounds:
                # Agotamiento de rondas, no consenso real — declarado
                # explícito (Principio VI, Foundation): nunca presentar
                # "aprobado" como si el equipo hubiera coincidido de verdad
                # cuando en realidad se acabaron los intentos.
                approved = True
                approved_by_exhaustion = True
                break
            draft = self._generate_draft(objective, previous_objections=blocking)

        return {
            "objective": objective,
            "roles": roles,
            "draft": draft,
            "approved": approved,
            "approved_by_exhaustion": approved_by_exhaustion,
            "rounds": rounds_log,
            "generated_at": time.time(),
        }

    def _generate_draft(self, objective: str, previous_objections: dict[str, list] | None) -> str:
        llm = self._draft_llm_factory()
        if not llm.available:
            return "No se pudo generar el borrador: falta configurar el modelo de lenguaje."
        content = f"Objetivo real: {objective}"
        if previous_objections:
            lines = [
                f"- ({role}) {objection['text']}"
                for role, objections in previous_objections.items()
                for objection in objections
            ]
            content += "\n\nObjeciones bloqueantes reales de la ronda anterior, a incorporar de verdad:\n" + "\n".join(
                lines
            )
        try:
            return llm.generate(
                system=self._draft_system_prompt_provider(), messages=[{"role": "user", "content": content}]
            ).text
        except Exception as exc:
            return f"No se pudo generar el borrador: {exc}"

    def _critique(self, role: str, objective: str, draft: str) -> dict:
        result = consult_role(
            ROLE_CONFIGS[role],
            _critique_question(objective, draft, role),
            self._role_llm_factory_for_role(role),
            self._repo_root,
        )
        return {
            "headline": result.get("headline", ""),
            "objections": _parse_objections(result.get("raw", "")),
            "raw": result.get("raw", ""),
        }
