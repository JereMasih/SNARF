import json
import re
import time
from pathlib import Path

from snarf.specialists.base import Specialist

CACHE_DIR = Path("data/morning_routine")

# Cuántos correos "prioritarios" se leen de verdad (cuerpo completo) por
# rutina — un tope duro, no lo que el modelo de clasificación pida: sin esto,
# una clasificación generosa (o un modelo local de baja calidad marcando
# demasiados) dispara N llamadas reales a la API de Gmail más una síntesis
# final cada vez más pesada. 5 alcanza para "lo urgente de hoy" sin volverse
# un costo real por turno.
MAX_PRIORITY_READS = 5

# Cuerpo real de un correo puede ser enorme (un hilo largo, un adjunto en
# base64 que se coló en el texto plano) — tope defensivo antes de mandarlo al
# LLM de síntesis, mismo criterio que el resto del repo (nunca un prompt sin
# límite hacia el modelo local, ver el fix real de la fuga de memoria del
# server MLX, ADR 0128).
MAX_BODY_CHARS_PER_MESSAGE = 6000

_PRIORITY_LINE_RE = re.compile(r"^PRIORITY_IDS:\s*(.*)$", re.MULTILINE)

CLASSIFY_SYSTEM_PROMPT = (
    "Armás la primera pasada de la rutina matutina del fundador de Snarf, a partir de un listado "
    "real de correos recientes de Gmail y de próximos eventos reales de Google Calendar — nunca "
    "inventes un correo, evento, remitente o fecha que no esté en esos listados. Agrupá los correos "
    "por categoría (trabajo, personal, financiero, notificaciones, promociones, u otra que "
    "corresponda) señalando cuáles conviene revisar y por qué, y resumí la agenda agrupando por día "
    "si hay más de un evento, señalando conflictos de horario reales. Sé breve y accionable, en "
    "español, en Markdown.\n\n"
    "Después de esa interpretación, en una línea NUEVA y aparte, exactamente en este formato, "
    "listá los ids reales (tal cual aparecen en el listado de correos, nunca inventados ni "
    "derivados del asunto) de los correos cuyo cuerpo completo conviene leer antes de dar la "
    "versión final — porque son urgentes, piden una acción concreta, o el fragmento no alcanza "
    "para entender de qué tratan de verdad:\n"
    "PRIORITY_IDS: id1, id2\n"
    "o, si ninguno lo amerita:\n"
    "PRIORITY_IDS: ninguno"
)

SYNTHESIZE_SYSTEM_PROMPT = (
    "Cerrás la rutina matutina del fundador de Snarf con la versión final. Ya tenés la "
    "interpretación inicial (agenda + correos agrupados por categoría) y, para cada correo que se "
    "marcó como prioritario en esa primera pasada, su contenido real completo. Reescribí una única "
    "respuesta cohesiva en español, en Markdown: mantené la estructura de la interpretación "
    "inicial, pero para cada correo prioritario reemplazá la referencia genérica por el detalle "
    "real que ahora tenés — de qué se trata concretamente, qué acción puntual requiere, cualquier "
    "fecha límite mencionada en el cuerpo. Nunca inventes un dato que no esté en el contenido real "
    "que se te da. Si no hubo ningún correo prioritario, dejá la interpretación inicial "
    "prácticamente tal cual, sin inventar detalle donde no lo hay."
)

# Convención de Skill Framework (ver snarf/specialists/base.py, ADR 0101).
INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "force_refresh": {"type": "boolean"},
        "max_messages": {"type": "integer", "description": "Default 20."},
        "max_events": {"type": "integer", "description": "Default 10."},
    },
}
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "generated_at": {"type": "number"},
        "message_count": {"type": "integer"},
        "event_count": {"type": "integer"},
        "priority_message_ids": {"type": "array"},
        "routine_text": {"type": "string"},
        "messages": {"type": "array"},
        "events": {"type": "array"},
        "priority_messages": {"type": "array"},
    },
}


def _extract_priority_ids(text: str, known_ids: set[str]) -> tuple[str, list[str]]:
    """Separa la línea 'PRIORITY_IDS: ...' del texto visible y devuelve los
    ids reales que contiene — cualquier id que el modelo haya escrito pero
    que NO esté en `known_ids` (el listado real que se le pasó) se descarta
    en silencio acá, nunca llega a gmail_read_message. Esta validación es la
    que reemplaza confiar en que un modelo de 4B nunca invente un id (ver
    ADR de esta ronda: exactamente ese tipo de invención rompió la rutina
    real de un fundador antes de este fix)."""
    match = _PRIORITY_LINE_RE.search(text)
    if not match:
        return text, []
    raw = match.group(1).strip()
    ids = []
    if raw and raw.lower() != "ninguno":
        for candidate in raw.split(","):
            candidate = candidate.strip()
            if candidate in known_ids and candidate not in ids:
                ids.append(candidate)
    cleaned_text = _PRIORITY_LINE_RE.sub("", text).rstrip()
    return cleaned_text, ids[:MAX_PRIORITY_READS]


class MorningRoutineSpecialist(Specialist):
    """Rutina matutina real: agenda + correos, con el cuerpo completo ya
    leído para los correos que ameritan detalle — no depende de que el
    Orchestrator (modelo local chico) encadene bien varias llamadas a
    herramientas en el mismo turno para llegar a ese detalle (ver ADR de
    esta ronda, causa real de una rutina rota en producción)."""

    name = "morning_routine"
    domain = "productivity"

    def __init__(self, gmail, calendar, llm_factory, user_id: str):
        self._gmail = gmail
        self._calendar = calendar
        self._llm_factory = llm_factory
        self._user_id = user_id

    def _cache_path(self) -> Path:
        return CACHE_DIR / f"{self._user_id}.json"

    def cached_routine(self) -> dict | None:
        path = self._cache_path()
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def refresh(self, max_messages: int = 20, max_events: int = 10) -> dict:
        messages = self._gmail.list_messages(max_results=max_messages)
        events = self._calendar.list_upcoming_events(max_results=max_events)
        llm = self._llm_factory()

        priority_ids: list[str] = []
        priority_messages: list[dict] = []

        if not messages and not events:
            routine_text = "No hay correos ni eventos próximos para armar la rutina de hoy."
        elif not llm.available:
            routine_text = "No se pudo interpretar: falta configurar el modelo de lenguaje (ANTHROPIC_API_KEY)."
        else:
            message_listing = "\n".join(
                f"- id={m.get('id', '')} | De: {m.get('from', '')} | Asunto: {m.get('subject', '')} | "
                f"{m.get('snippet', '')[:160]}"
                for m in messages
            ) or "(sin correos recientes)"
            event_listing = "\n".join(
                f"- {e.get('summary', '(sin título)')} | {e.get('start', '')}"
                + (f" | {e['location']}" if e.get("location") else "")
                for e in events
            ) or "(sin eventos próximos)"
            classify_input = f"CORREOS:\n{message_listing}\n\nAGENDA:\n{event_listing}"
            classify_response = llm.generate(
                system=CLASSIFY_SYSTEM_PROMPT, messages=[{"role": "user", "content": classify_input}]
            )
            known_ids = {m["id"] for m in messages if m.get("id")}
            routine_text, priority_ids = _extract_priority_ids(classify_response.text, known_ids)

            if priority_ids:
                for message_id in priority_ids:
                    full = self._gmail.read_message(message_id)
                    priority_messages.append({"id": message_id, **full})

                priority_bodies = "\n\n".join(
                    f"id={pm['id']} | De: {pm.get('from', '')} | Asunto: {pm.get('subject', '')}\n"
                    f"{pm.get('body', '')[:MAX_BODY_CHARS_PER_MESSAGE]}"
                    for pm in priority_messages
                )
                synthesize_input = (
                    f"INTERPRETACIÓN INICIAL:\n{routine_text}\n\n"
                    f"CORREOS PRIORITARIOS (contenido real completo):\n\n{priority_bodies}"
                )
                synthesize_response = llm.generate(
                    system=SYNTHESIZE_SYSTEM_PROMPT, messages=[{"role": "user", "content": synthesize_input}]
                )
                routine_text = synthesize_response.text

        routine = {
            "generated_at": time.time(),
            "message_count": len(messages),
            "event_count": len(events),
            "priority_message_ids": priority_ids,
            "routine_text": routine_text,
            "messages": [
                {"id": m.get("id"), "subject": m.get("subject", ""), "from": m.get("from", ""), "date": m.get("date", "")}
                for m in messages
            ],
            "events": [
                {"id": e.get("id"), "summary": e.get("summary", ""), "start": e.get("start", "")} for e in events
            ],
            "priority_messages": priority_messages,
        }
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._cache_path().write_text(json.dumps(routine, ensure_ascii=False, indent=2), encoding="utf-8")
        return routine

    def handle(self, task: str, context: dict) -> str:
        return self.refresh(
            max_messages=context.get("max_messages", 20), max_events=context.get("max_events", 10)
        )["routine_text"]
