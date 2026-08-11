import json
import time
from pathlib import Path

from snarf.specialists.base import Specialist

CACHE_DIR = Path("data/calendar_brief")

SYSTEM_PROMPT = (
    "Interpretás la agenda de Google Calendar del fundador de Snarf. Dado un listado de eventos "
    "próximos reales (título, hora de inicio, ubicación si tiene), respondé en español, en "
    "Markdown, con un resumen breve y accionable de lo que se viene: agrupá por día si hay más de "
    "uno, señalá conflictos de horario reales (dos eventos que se superponen) si los hay. No "
    "repitas el listado completo tal cual, priorizá lo que conviene tener en cuenta. Nunca inventes "
    "un evento, hora o ubicación que no esté en el listado."
)

# Convención de Skill Framework (ver snarf/specialists/base.py, ADR 0101).
INPUT_SCHEMA = {
    "type": "object",
    "properties": {"max_results": {"type": "integer", "description": "Default 10."}},
}
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "generated_at": {"type": "number"},
        "event_count": {"type": "integer"},
        "brief_text": {"type": "string"},
        "events": {"type": "array"},
    },
}


class CalendarBriefSpecialist(Specialist):
    """Interpreta la agenda real del fundador en un resumen accionable —
    mismo patrón cache-first que GmailDigestSpecialist: cached_brief() nunca
    llama al LLM, solo refresh() explícito lo hace."""

    name = "calendar_brief"
    domain = "calendar"

    def __init__(self, calendar, llm_factory, user_id: str, system_prompt_provider=None):
        self._calendar = calendar
        self._llm_factory = llm_factory
        self._user_id = user_id
        # system_prompt_provider: ver el criterio documentado en
        # GmailDigestSpecialist.__init__ (Prompt Registry, ADR 0141).
        self._system_prompt_provider = system_prompt_provider or (lambda: SYSTEM_PROMPT)

    def _cache_path(self) -> Path:
        return CACHE_DIR / f"{self._user_id}.json"

    def cached_brief(self) -> dict | None:
        path = self._cache_path()
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def refresh(self, max_results: int = 10) -> dict:
        events = self._calendar.list_upcoming_events(max_results=max_results)
        if not events:
            brief_text = "No hay eventos próximos en la agenda."
        else:
            llm = self._llm_factory()
            if not llm.available:
                brief_text = "No se pudo interpretar: falta configurar el modelo de lenguaje (ANTHROPIC_API_KEY)."
            else:
                listing = "\n".join(
                    f"- {e.get('summary', '(sin título)')} | {e.get('start', '')}"
                    + (f" | {e['location']}" if e.get("location") else "")
                    for e in events
                )
                response = llm.generate(system=self._system_prompt_provider(), messages=[{"role": "user", "content": listing}])
                brief_text = response.text

        brief = {
            "generated_at": time.time(),
            "event_count": len(events),
            "brief_text": brief_text,
            "events": [
                {"id": e.get("id"), "summary": e.get("summary", ""), "start": e.get("start", "")} for e in events
            ],
        }
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._cache_path().write_text(json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8")
        return brief

    def handle(self, task: str, context: dict) -> str:
        return self.refresh(max_results=context.get("max_results", 10))["brief_text"]
