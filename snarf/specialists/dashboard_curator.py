import json
import re
import time
from pathlib import Path

from snarf.specialists.base import Specialist
from snarf.telemetry import widget_templates

CACHE_DIR = Path("data/dashboard_curation")
# Cola de propuestas de plantilla nueva (Track A del plan v2 — el curador
# puede PROPONER, nunca aplicar: ver CONSTITUTION.md Art. III/V/línea 109,
# ninguna delegación general cubre crear/modificar algo que después se
# ejecuta solo). Archivo único, no por usuario: es una cola de revisión para
# el fundador, no un dato operativo por sesión.
TEMPLATE_PROPOSALS_PATH = Path("data/dashboard_template_proposals.json")
MAX_STORED_TEMPLATE_PROPOSALS = 20

DASHBOARD_CURATOR_SYSTEM_PROMPT = (
    "Curás el dashboard del fundador de Snarf, a partir ÚNICAMENTE de los datos reales que "
    "se te dan a continuación — nunca inventes actividad, cifras, tendencias ni urgencia que "
    "no esté en esa información. Si no hay nada realmente urgente, decilo honestamente en vez "
    "de forzar encontrar algo.\n\n"
    "Cada nodo de la lista ya trae un TAMAÑO de plantilla asignado (grande o mediano) — vos "
    "elegís SOLO la variante dentro de ese tamaño, nunca el tamaño en sí (eso ya lo decidió el "
    "ranking real, no es tu criterio). Cuanto más grande el tamaño, más se espera que tu frase "
    "analice el dato real: grande, hasta 2-3 oraciones sobre por qué importa ahora mismo; "
    "mediano, 1-2 oraciones. Siempre atado a lo que ya te dieron (detalle real, conteos, si hay "
    "actividad reciente) — nunca agregues un dato, tendencia o cifra que no esté ahí.\n\n"
    "Si ninguna de las variantes válidas de un nodo describe bien lo que hace falta mostrar, "
    "podés proponer una nueva — no se aplica sola, alguien la revisa después.\n\n"
    "Respondé en español, en EXACTAMENTE este formato, sin nada alrededor:\n\n"
    "TITULAR: <una o dos oraciones breves sobre lo más relevante ahora mismo, o que no hay "
    "nada urgente si es el caso>\n"
    "---\n"
    "<node_id de la lista, tal cual>: <template_id de las variantes válidas para su tamaño> | "
    "<tu frase real sobre ese nodo>\n"
    "(una línea por cada nodo de la lista de abajo, en el mismo orden, mismo node_id exacto)\n"
    "PROPUESTA: <nombre corto>: <por qué falta esa plantilla>\n"
    "(0 o más líneas PROPUESTA, solo si de verdad hace falta)"
)

# Convención de Skill Framework (ver snarf/specialists/base.py, Fase G).
# refresh() no toma parámetros reales — snapshot_provider ya está inyectado
# por constructor, no por llamada.
INPUT_SCHEMA = {"type": "object", "properties": {}}
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "generated_at": {"type": "number"},
        "headline": {"type": "string"},
        "node_captions": {"type": "object"},
        "node_templates": {"type": "object"},
    },
}


def _template_menu_line(tier: str) -> str:
    templates = widget_templates.templates_for_tier(tier)
    options = ", ".join(f"{template_id} ({t['description']})" for template_id, t in templates.items())
    return f"{tier.upper()}: {options}"


def _curated_nodes(summaries: list[dict], cost_alert: dict | None) -> list[dict]:
    # El nodo sintético "cost" se cura igual que cualquier otro nodo real —
    # su detalle/serie ya son 100% reales (ver widget_summary.py). En v1
    # solo aparecía como una línea de contexto aparte, sin plantilla propia;
    # ahora una alerta de costo real también puede mostrarse con
    # critical_alert/deep_chart en vez de quedar fija en texto plano.
    return list(summaries) + ([cost_alert] if cost_alert else [])


def _build_curation_prompt(summaries: list[dict], cost_alert: dict | None, recent_errors: list[dict]) -> str:
    nodes = _curated_nodes(summaries, cost_alert)
    tiers_present = sorted({n["size_tier"] for n in nodes}, key=widget_templates.TIER_ORDER.index)
    lines = ["Plantillas disponibles por tamaño ya asignado:"]
    for tier in tiers_present:
        lines.append(_template_menu_line(tier))
    lines.append("")
    lines.append("Nodos a curar, por relevancia real (mayor primero), con su tamaño ya asignado:")
    for n in nodes:
        detalle = n["last_detalle"] or "sin contenido registrado"
        lines.append(f"- {n['node_id']} [{n['size_tier']}] (score {n['score']}, {n['count_recent']} eventos recientes): {detalle}")
    if recent_errors:
        nodos_con_error = sorted({e.get("nodo", "?") for e in recent_errors})
        lines.append(f"{len(recent_errors)} error(es) real(es) reciente(s) en: {', '.join(nodos_con_error)}")
    return "\n".join(lines)


# Tolerante a cómo el LLM real termina fraseando cada línea (verificado en v1
# con una llamada real: el modelo tiende a repetir el "(score N.N)" que ya
# aparece en el prompt de entrada, aunque el formato pedido diga
# "node_id: ..." a secas) — se extrae el identificador real al principio de
# la línea y se ignora cualquier cosa entre eso y el primer ":".
_NODE_LINE_RE = re.compile(r"^([a-z][a-z0-9_]*)\b[^:]*:\s*(.+)$")
_PROPOSAL_LINE_RE = re.compile(r"^PROPUESTA:\s*([^:]+):\s*(.+)$", re.IGNORECASE)


def _parse_node_line(line: str) -> tuple[str, str, str] | None:
    match = _NODE_LINE_RE.match(line)
    if not match:
        return None
    node_id, rest = match.group(1), match.group(2).strip()
    if "|" in rest:
        template_part, caption = rest.split("|", 1)
        return node_id, template_part.strip(), caption.strip()
    # El modelo se olvidó del separador "|" — se trata todo como caption; el
    # template_id vacío cae después al default mecánico del tier, nunca
    # rompe el render (ver DashboardCuratorSpecialist.refresh).
    return node_id, "", rest


def _parse_proposal_line(line: str) -> dict | None:
    match = _PROPOSAL_LINE_RE.match(line)
    if not match:
        return None
    name, reason = match.group(1).strip(), match.group(2).strip()
    if not name or not reason:
        return None
    return {"name": name, "reason": reason}


def _parse_curation_response(
    text: str, valid_node_ids: set[str]
) -> tuple[str, dict[str, str], dict[str, str], list[dict]]:
    parts = text.split("---", 1)
    headline = ""
    for line in parts[0].splitlines():
        line = line.strip()
        if line.upper().startswith("TITULAR:"):
            headline = line.split(":", 1)[1].strip()

    node_captions: dict[str, str] = {}
    node_templates: dict[str, str] = {}
    template_proposals: list[dict] = []
    if len(parts) > 1:
        for line in parts[1].splitlines():
            line = line.strip()
            if not line:
                continue
            if line.upper().startswith("PROPUESTA:"):
                proposal = _parse_proposal_line(line)
                if proposal:
                    template_proposals.append(proposal)
                continue
            parsed = _parse_node_line(line)
            if not parsed:
                continue
            node_id, template_id, caption = parsed
            if node_id not in valid_node_ids:
                continue
            node_captions[node_id] = caption
            node_templates[node_id] = template_id
    return headline, node_captions, node_templates, template_proposals


def _load_template_proposals() -> list[dict]:
    if not TEMPLATE_PROPOSALS_PATH.exists():
        return []
    return json.loads(TEMPLATE_PROPOSALS_PATH.read_text(encoding="utf-8"))


def _append_template_proposals(proposals: list[dict], user_id: str) -> None:
    if not proposals:
        return
    existing = _load_template_proposals()
    now = time.time()
    for p in proposals:
        existing.append({**p, "user_id": user_id, "proposed_at": now})
    existing = existing[-MAX_STORED_TEMPLATE_PROPOSALS:]
    TEMPLATE_PROPOSALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    TEMPLATE_PROPOSALS_PATH.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


class DashboardCuratorSpecialist(Specialist):
    """Cura el dashboard nuevo (Vista HUD) a partir de datos reales ya
    agregados por snarf/telemetry/widget_summary.py — nunca decide QUÉ
    widgets existen ni su tamaño (eso es relevance.dock_priority +
    widget_templates.assign_tier, ambos determinísticos), solo elige la
    variante de plantilla dentro del tamaño ya asignado y redacta texto de
    acompañamiento sobre datos que ya son reales. Mismo patrón cache-first
    que GmailDigestSpecialist: cached_curation() nunca llama al LLM, solo
    refresh() explícito lo hace."""

    name = "dashboard_curator"
    domain = "dashboard"

    def __init__(self, snapshot_provider, llm_factory, user_id: str, system_prompt_provider=None):
        # snapshot_provider: callable() -> el dict real de
        # widget_summary.curation_snapshot() — inyectado (no llamado acá
        # adentro con imports directos a events.py) para que el Specialist
        # sea testeable con datos de fixture, sin tocar archivos reales.
        self._snapshot_provider = snapshot_provider
        self._llm_factory = llm_factory
        self._user_id = user_id
        # system_prompt_provider: mismo criterio que llm_factory/
        # snapshot_provider — callable inyectado por quien construye este
        # Specialist (conectado al Prompt Registry, ADR 0141), nunca un
        # import directo a snarf.runtime acá (ADR 0026,
        # tests/test_architecture_boundaries.py).
        self._system_prompt_provider = system_prompt_provider or (lambda: DASHBOARD_CURATOR_SYSTEM_PROMPT)

    def _cache_path(self) -> Path:
        return CACHE_DIR / f"{self._user_id}.json"

    def cached_curation(self) -> dict | None:
        path = self._cache_path()
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _persist(self, curation: dict) -> None:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._cache_path().write_text(json.dumps(curation, ensure_ascii=False, indent=2), encoding="utf-8")

    def refresh(self) -> dict:
        snapshot = self._snapshot_provider()
        summaries = snapshot["summaries"]
        cost_alert = snapshot["cost_alert"]
        recent_errors = snapshot["recent_errors"]

        # Nada real que curar — igual que GmailDigestSpecialist con la
        # bandeja vacía, ni siquiera se llama al LLM (costo cero, honesto:
        # no hay novedad que inventar).
        if not summaries and not cost_alert and not recent_errors:
            curation = {
                "generated_at": time.time(),
                "headline": "Sin actividad reciente para destacar.",
                "node_captions": {},
                "node_templates": {},
            }
            self._persist(curation)
            return curation

        llm = self._llm_factory()
        if not llm.available:
            curation = {
                "generated_at": time.time(),
                "headline": "No se pudo curar el dashboard: falta configurar el modelo de lenguaje (ANTHROPIC_API_KEY).",
                "node_captions": {},
                "node_templates": {},
            }
            self._persist(curation)
            return curation

        try:
            # Todo lo que depende de la forma del snapshot (incluida la
            # construcción del prompt) vive DENTRO del try — el loop
            # periódico de app.py no tiene su propio try/except alrededor de
            # refresh(), así que un snapshot con una forma inesperada tiene
            # que degradar acá, nunca tirar abajo el loop entero.
            nodes = _curated_nodes(summaries, cost_alert)
            valid_node_ids = {n["node_id"] for n in nodes}
            tier_by_node = {n["node_id"]: n["size_tier"] for n in nodes}
            prompt = _build_curation_prompt(summaries, cost_alert, recent_errors)
            response = llm.generate(system=self._system_prompt_provider(), messages=[{"role": "user", "content": prompt}])
            headline, node_captions, raw_node_templates, template_proposals = _parse_curation_response(
                response.text, valid_node_ids
            )
            if not headline:
                headline = "Sin novedades destacables."
            node_templates_resolved: dict[str, str] = {}
            for node_id, template_id in raw_node_templates.items():
                tier = tier_by_node.get(node_id, widget_templates.SMALL)
                valid_ids_for_tier = set(widget_templates.templates_for_tier(tier).keys())
                node_templates_resolved[node_id] = (
                    template_id if template_id in valid_ids_for_tier else widget_templates.DEFAULT_TEMPLATE_BY_TIER[tier]
                )
            _append_template_proposals(template_proposals, self._user_id)
        except Exception as exc:
            headline = f"No se pudo curar el dashboard: {exc}"
            node_captions = {}
            node_templates_resolved = {}

        curation = {
            "generated_at": time.time(),
            "headline": headline,
            "node_captions": node_captions,
            "node_templates": node_templates_resolved,
        }
        self._persist(curation)
        return curation

    def handle(self, task: str, context: dict) -> str:
        return (self.cached_curation() or self.refresh())["headline"]
