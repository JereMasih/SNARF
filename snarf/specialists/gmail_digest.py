import json
import time
from pathlib import Path

from snarf.specialists.base import Specialist

CACHE_DIR = Path("data/gmail_digest")

SYSTEM_PROMPT = (
    "Interpretás bandejas de entrada de Gmail para el fundador de Snarf. Dado un "
    "listado de correos recientes (remitente, asunto, fragmento), respondé en "
    "español, en Markdown, agrupando los mensajes por categoría (trabajo, "
    "personal, financiero, notificaciones, promociones, u otra que corresponda) "
    "y señalando cuáles conviene revisar y por qué. Sé breve y accionable: no "
    "repitas el listado completo, priorizá lo que requiere atención."
)


class GmailDigestSpecialist(Specialist):
    name = "gmail_digest"
    domain = "email"

    def __init__(self, gmail, llm, user_id: str):
        self._gmail = gmail
        self._llm = llm
        self._user_id = user_id

    def _cache_path(self) -> Path:
        return CACHE_DIR / f"{self._user_id}.json"

    def cached_digest(self) -> dict | None:
        path = self._cache_path()
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def refresh(self, max_results: int = 20) -> dict:
        messages = self._gmail.list_messages(max_results=max_results)
        if not messages:
            digest_text = "No hay mensajes recientes para interpretar."
        elif not self._llm.available:
            digest_text = "No se pudo interpretar: falta configurar el modelo de lenguaje (ANTHROPIC_API_KEY)."
        else:
            listing = "\n".join(
                f"- De: {m.get('from', '')} | Asunto: {m.get('subject', '')} | {m.get('snippet', '')[:160]}"
                for m in messages
            )
            digest_text = self._llm.generate(system=SYSTEM_PROMPT, messages=[{"role": "user", "content": listing}])

        digest = {
            "generated_at": time.time(),
            "message_count": len(messages),
            "digest_text": digest_text,
            "latest_message_id": messages[0].get("id") if messages else None,
        }
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._cache_path().write_text(json.dumps(digest, ensure_ascii=False, indent=2), encoding="utf-8")
        return digest

    def handle(self, task: str, context: dict) -> str:
        return self.refresh(max_results=context.get("max_results", 20))["digest_text"]
