import concurrent.futures
import contextvars
import json
import time
from pathlib import Path
from typing import Callable

from snarf.executive.process import REPO_ROOT, consult_role
from snarf.executive.roles import ROLE_CONFIGS
from snarf.runtime import agent_graph_registry
from snarf.specialists.base import Specialist
from snarf.telemetry import detail, spans

CACHE_DIR = Path("data/executive_board")

# Convención de Skill Framework (ver snarf/specialists/base.py, Fase G).
INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "question": {"type": "string"},
        "roles": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": ["cto", "coo", "research", "ceo", "cfo", "cmo", "creative"],
            },
        },
    },
    "required": ["question"],
}
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "question": {"type": "string"},
        "roles": {"type": "object"},
        "generated_at": {"type": "number"},
        "error": {"type": "string"},
    },
}


def _format_upstream_context(upstream: dict[str, dict] | None) -> str | None:
    """Texto real a anteponer al system prompt de un rol cuando corre en una
    stage posterior a otras (Fase 17, ADR 0158) — None si `upstream` está
    vacío (comportamiento sin cambios: consult_role no toca el system
    prompt). Deja explícito en el propio texto que esto es información, no
    autoridad (ADR 0094 sigue vigente: ningún rol decide por otro)."""
    if not upstream:
        return None
    lines = [f"Postura previa de {role}: {data.get('headline', '')}" for role, data in upstream.items()]
    return (
        "Contexto de una stage anterior de esta misma consulta al board — información adicional, "
        "nunca autoridad sobre tu propia postura, opiná con tu propio criterio:\n" + "\n".join(lines)
    )


class ExecutiveBoardSpecialist(Specialist):
    """Board asesor de Inteligencia Ejecutiva (ver COGNITION.md, ADR 0094):
    hasta 7 roles opinan en paralelo, cada uno en su propio proceso MCP
    (snarf/executive/process.py) — ninguno ve la opinión de los otros
    (Art. IV, ningún rol se ancla al framing de otro). Cero autoridad de
    ejecución: cada rol solo puede leer, nunca mutar nada. Snarf es el único
    que sintetiza estas posturas en su propia voz. Cada consulta real
    persiste (mismo patrón cache-first que GmailDigestSpecialist/
    DashboardCuratorSpecialist) para que el widget del dashboard pueda
    mostrar las posturas crudas por rol sin disparar una consulta nueva en
    cada request."""

    name = "executive_board"
    domain = "advisory"

    def __init__(self, llm_factory_for_role: Callable[[str], object], user_id: str = "default", repo_root: Path = REPO_ROOT):
        self._llm_factory_for_role = llm_factory_for_role
        self._user_id = user_id
        self._repo_root = repo_root

    def _cache_path(self) -> Path:
        return CACHE_DIR / f"{self._user_id}.json"

    def cached_consult(self) -> dict | None:
        path = self._cache_path()
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _persist(self, result: dict) -> None:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._cache_path().write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    def consult(self, question: str, roles: list[str] | None = None) -> dict:
        selected = roles or list(ROLE_CONFIGS.keys())
        unknown = [r for r in selected if r not in ROLE_CONFIGS]
        if unknown:
            return {
                "error": (
                    f"Rol(es) desconocido(s): {', '.join(unknown)}. "
                    f"Roles válidos: {', '.join(ROLE_CONFIGS)}."
                )
            }

        stages = self._stages_for(selected)
        results: dict[str, dict] = {}
        # spans.start_workflow (Fase 1 del plan de observabilidad): traza
        # propia para esta consulta al board — cada rol cuelga de acá como
        # agent.started/agent.finished (ver _consult_one), compartiendo el
        # mismo trace_id.
        board = spans.start_workflow("executive_board", detalle=detail.truncate_detalle(question))
        failed_roles: list[str] = []
        upstream: dict[str, dict] = {}
        with spans.active(board):
            # Fase 17 (ADR 0158): sin stages configuradas (default,
            # agent_graph_registry.get_active_stages() devuelve una sola
            # stage con los 7 roles), esto es exactamente el fan-out 100%
            # paralelo de siempre — cero cambio de comportamiento. Con
            # stages reales, cada una corre en paralelo puertas adentro y en
            # secuencia entre sí, pasando el resultado de la anterior como
            # CONTEXTO (nunca autoridad, ver _consult_one/consult_role) a la
            # siguiente.
            for stage in stages:
                # contextvars.copy_context() (Fase 1): ThreadPoolExecutor NO
                # propaga contextvars por sí solo (a diferencia de anyio,
                # que sí copia el context al pasar de un request async a un
                # worker de threadpool) — sin esto, cada rol perdería tanto
                # el trace_id/parent del board como conversation_id/user_id
                # del turno que disparó la consulta. Un `Context` copiado
                # solo puede correr en UN thread a la vez (`.run()` no es
                # reentrante) — cada rol necesita su PROPIA copia, nunca una
                # compartida entre los N submits (si no, el segundo rol en
                # arrancar revienta con "cannot enter context: already
                # entered").
                with concurrent.futures.ThreadPoolExecutor(max_workers=len(stage)) as pool:
                    futures = {
                        pool.submit(contextvars.copy_context().run, self._consult_one, role, question, upstream): role
                        for role in stage
                    }
                    for future in concurrent.futures.as_completed(futures):
                        role = futures[future]
                        try:
                            results[role] = future.result()
                        except Exception as exc:
                            failed_roles.append(role)
                            results[role] = {"headline": f"No se pudo consultar a {role}: {exc}", "opinions": [], "raw": ""}
                # Solo roles que sí respondieron pasan como contexto a la
                # stage siguiente — un rol fallido no debe propagar un
                # mensaje de error como si fuera una postura real.
                upstream = {**upstream, **{r: results[r] for r in stage if r not in failed_roles}}
        spans.finish(board, estado="completo" if not failed_roles else "error")
        outcome = {"question": question, "roles": results, "generated_at": time.time()}
        self._persist(outcome)
        return outcome

    def _stages_for(self, selected: list[str]) -> list[list[str]]:
        """Las stages guardadas (agent_graph_registry), recortadas a los
        roles pedidos en esta consulta puntual (`roles=` de consult()).
        Cualquier rol pedido que la configuración guardada no menciona en
        ninguna stage corre igual, en una stage extra al final — nunca se
        pierde un rol seleccionado solo porque el grafo guardado no lo
        cubre explícitamente."""
        stored = agent_graph_registry.get_active_stages()
        selected_set = set(selected)
        filtered = [[role for role in stage if role in selected_set] for stage in stored]
        filtered = [stage for stage in filtered if stage]
        covered = {role for stage in filtered for role in stage}
        leftover = [role for role in selected if role not in covered]
        if leftover:
            filtered.append(leftover)
        return filtered or [selected]

    def _consult_one(self, role: str, question: str, upstream: dict[str, dict] | None = None) -> dict:
        # spans.start_agent (Fase 1): el mejor precedente real de "agente"
        # en el sentido multi-agente — cada rol es un subproceso MCP propio
        # (ver executive/process.py), fan-out en paralelo dentro de cada
        # stage (ver consult()).
        span = spans.start_agent(role)
        try:
            with spans.active(span):
                result = consult_role(
                    ROLE_CONFIGS[role],
                    question,
                    self._llm_factory_for_role(role),
                    self._repo_root,
                    upstream_context=_format_upstream_context(upstream),
                )
            spans.finish(span, estado="completo")
            return result
        except Exception as exc:
            spans.fail(span, reason=type(exc).__name__)
            raise

    def handle(self, task: str, context: dict) -> str:
        result = self.consult(task, context.get("roles"))
        if "error" in result:
            return result["error"]
        lines = [f"{role}: {r.get('headline', '')}" for role, r in result["roles"].items()]
        return "\n".join(lines)
