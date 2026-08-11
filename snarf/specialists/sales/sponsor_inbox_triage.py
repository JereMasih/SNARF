import json
import time
from pathlib import Path

from snarf.specialists.base import Specialist

CACHE_DIR = Path("data/sponsor_inbox_triage")

# Query real de Gmail (mismo lenguaje de búsqueda que ya usa
# gmail_list_messages) — acotada a lo que suele indicar una oportunidad de
# sponsor/partnership real, ajustable sin tocar el resto del mecanismo.
DEFAULT_QUERY = "sponsor OR sponsorship OR partnership OR collab OR propuesta OR presupuesto OR budget"

SYSTEM_PROMPT = (
    "Interpretás correos de Gmail que podrían ser oportunidades reales de sponsor/partnership para "
    "el fundador de Snarf. Dado un listado de correos reales (remitente, asunto, fragmento), "
    "respondé en español, en Markdown: separá los que son oportunidades reales de negocio de los "
    "que solo mencionan una palabra clave sin serlo realmente (spam, newsletter, uso casual del "
    "término), y para cada oportunidad real señalá qué conviene responder primero y por qué. Sé "
    "breve y accionable, nunca inventes que un correo es una oportunidad si el contenido real no lo "
    "sugiere."
)

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "max_results": {"type": "integer", "description": "Default 20."},
        "query": {"type": "string", "description": f"Default: '{DEFAULT_QUERY}'."},
    },
}
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "generated_at": {"type": "number"},
        "message_count": {"type": "integer"},
        "triage_text": {"type": "string"},
        "messages": {"type": "array"},
    },
}


class SponsorInboxTriageSpecialist(Specialist):
    """Triage real de correos de sponsor/partnership — mismo patrón
    cache-first que GmailDigestSpecialist, acotado a una búsqueda real
    distinta (oportunidades de negocio, no la bandeja entera)."""

    name = "sponsor_inbox_triage"
    domain = "sales"

    def __init__(self, gmail, llm_factory, user_id: str, system_prompt_provider=None):
        self._gmail = gmail
        self._llm_factory = llm_factory
        self._user_id = user_id
        # system_prompt_provider: ver el criterio documentado en
        # GmailDigestSpecialist.__init__ (Prompt Registry, ADR 0141).
        self._system_prompt_provider = system_prompt_provider or (lambda: SYSTEM_PROMPT)

    def _cache_path(self) -> Path:
        return CACHE_DIR / f"{self._user_id}.json"

    def cached_triage(self) -> dict | None:
        path = self._cache_path()
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def refresh(self, max_results: int = 20, query: str = DEFAULT_QUERY) -> dict:
        messages = self._gmail.list_messages(max_results=max_results, query=query)
        if not messages:
            triage_text = "No hay correos recientes que coincidan con oportunidades de sponsor/partnership."
        else:
            llm = self._llm_factory()
            if not llm.available:
                triage_text = "No se pudo interpretar: falta configurar el modelo de lenguaje (ANTHROPIC_API_KEY)."
            else:
                listing = "\n".join(
                    f"- De: {m.get('from', '')} | Asunto: {m.get('subject', '')} | {m.get('snippet', '')[:160]}"
                    for m in messages
                )
                response = llm.generate(system=self._system_prompt_provider(), messages=[{"role": "user", "content": listing}])
                triage_text = response.text

        triage = {
            "generated_at": time.time(),
            "message_count": len(messages),
            "triage_text": triage_text,
            "messages": [
                {"id": m.get("id"), "subject": m.get("subject", ""), "from": m.get("from", "")} for m in messages
            ],
        }
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._cache_path().write_text(json.dumps(triage, ensure_ascii=False, indent=2), encoding="utf-8")
        return triage

    def handle(self, task: str, context: dict) -> str:
        return self.refresh(max_results=context.get("max_results", 20))["triage_text"]
