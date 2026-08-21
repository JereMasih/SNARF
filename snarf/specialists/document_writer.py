import json
import time
import uuid
from pathlib import Path

# Namespaced por user_id desde el día uno (mismo criterio que
# SecondBrainManager/FinanceSupervisor/FounderMood, ADR 0182/0183/0197).
DOCUMENT_WRITES_DIR = Path("data/document_writes")

# Nunca infinito (ADR 0199, mismo criterio que _max_continuations de
# AnthropicLLM, ADR 0113, y max_rounds de TeamSession, ADR 0198) — tope real
# de reintentos por sección, tanto para generar+escribir como para verificar
# la escritura ya hecha.
MAX_SECTION_ATTEMPTS = 3

DOCUMENT_SECTION_SYSTEM_PROMPT = (
    "Redactás el contenido real de UNA sección de un documento más grande, en español, texto plano "
    "(párrafos separados por línea en blanco, sin encabezados propios ni markdown — eso lo maneja el "
    "destino final). Escribís solo esa sección, nunca repitas ni resumas las secciones anteriores. "
    "Nunca inventes datos, cifras o afirmaciones que no te hayan dado en el objetivo o el brief."
)

# Estados terminales de una sección: no se vuelve a tocar en _advance() salvo
# que alguien arranque una escritura nueva. "failed": nunca se llegó a
# escribir (falló generar o falló el append) tras agotar los reintentos.
# "unverified": SÍ se escribió (el append real ya sucedió) pero releer la
# página nunca lo confirmó tras agotar los reintentos — nunca se reintenta el
# append en ese caso, para no duplicar contenido real en la página del
# usuario; queda para revisión manual.
TERMINAL_STATUSES = {"verified", "failed", "unverified"}


def _normalize(text: str) -> str:
    """Misma normalización que `_paragraph_blocks` de la Capacidad Notion
    (párrafos separados por línea en blanco, cada uno recortado) — para que
    comparar contra `read_page_text()` después de escribir sea un chequeo
    real, no aproximado."""
    return "\n\n".join(p.strip() for p in text.split("\n\n") if p.strip())


class DocumentWriter:
    """Escritura confiable de documentos largos hacia Notion (ver
    ROADMAP_SECOND_BRAIN_NOTION.md, Fase D4, ADR 0199) — resuelve los 3
    tipos de corte que motivaron todo Track D:
    - Límite de tokens del modelo: cada sección es una llamada de LLM
      independiente con su propio contexto acotado (título+brief+objetivo,
      nunca el documento entero acumulado) — nunca un prompt gigante que
      dependa de continuaciones automáticas para el documento completo.
    - Caída de proceso/RAM: el estado se persiste en disco después de cada
      paso (`data/document_writes/<user_id>/<write_id>.json`) — una sesión o
      proceso nuevo puede seguir exactamente donde quedó vía
      `continue_write(write_id)`, sin nada en memoria.
    - Fallas de API: cada sección se verifica releyendo la página real antes
      de avanzar a la siguiente, con reintento acotado — y si el append ya
      sucedió pero la verificación falla, nunca se reintenta el append (eso
      duplicaría contenido real), queda "unverified" para revisión manual.

    Compone la Capacidad Notion (ya con batching/retry real, ADR 0180) sin
    importar snarf.core/snarf.runtime (ADR 0026). A propósito NO es genérico
    por destino todavía, aunque el diseño original lo pedía: hoy solo sabe
    escribir a una página de Notion — generalizar a otro backend queda para
    cuando haya un segundo destino real que lo justifique (Principio VI:
    mejor una desviación honesta que una abstracción sin uso real)."""

    def __init__(
        self,
        notion,
        llm_factory,
        user_id: str,
        writes_dir: Path = DOCUMENT_WRITES_DIR,
        section_system_prompt_provider=None,
    ):
        self._notion = notion
        # llm_factory: callable sin argumentos, None si no se inyecta —
        # mismo criterio de ProjectManager/SecondBrainManager/
        # FinanceSupervisor (ADR 0026).
        self._llm_factory = llm_factory
        self._user_id = user_id
        self._writes_dir = writes_dir
        self._section_system_prompt_provider = section_system_prompt_provider or (
            lambda: DOCUMENT_SECTION_SYSTEM_PROMPT
        )

    def _user_dir(self) -> Path:
        return self._writes_dir / self._user_id

    def _write_path(self, write_id: str) -> Path:
        return self._user_dir() / f"{write_id}.json"

    def _save(self, state: dict) -> None:
        state["updated_at"] = time.time()
        path = self._write_path(state["write_id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load(self, write_id: str) -> dict | None:
        path = self._write_path(write_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def start(self, page_id: str, title: str, sections: list, objective: str = "") -> dict:
        if not sections:
            return {"error": "un documento necesita al menos una sección."}
        write_id = uuid.uuid4().hex
        state = {
            "write_id": write_id,
            "user_id": self._user_id,
            "page_id": page_id,
            "title": title,
            "objective": objective,
            "created_at": time.time(),
            "sections": [
                {
                    "title": section["title"] if isinstance(section, dict) else section,
                    "brief": section.get("brief", "") if isinstance(section, dict) else "",
                    "status": "pending",
                    "content": None,
                    "attempts": 0,
                    "verify_attempts": 0,
                    "error": None,
                }
                for section in sections
            ],
        }
        self._advance(state)
        self._save(state)
        return self._progress(state)

    def continue_write(self, write_id: str) -> dict:
        state = self._load(write_id)
        if state is None:
            return {"error": f"no existe ninguna escritura con id {write_id}."}
        self._advance(state)
        self._save(state)
        return self._progress(state)

    def status(self, write_id: str) -> dict:
        state = self._load(write_id)
        if state is None:
            return {"error": f"no existe ninguna escritura con id {write_id}."}
        return self._progress(state)

    def _progress(self, state: dict) -> dict:
        sections = state["sections"]
        verified = sum(1 for s in sections if s["status"] == "verified")
        stuck = [s["title"] for s in sections if s["status"] in ("failed", "unverified")]
        return {
            "write_id": state["write_id"],
            "page_id": state["page_id"],
            "title": state["title"],
            "sections_total": len(sections),
            "sections_verified": verified,
            "sections_stuck": stuck,
            "completed": verified == len(sections),
            "sections": sections,
        }

    def _generate_section_content(self, state: dict, section: dict) -> str | None:
        llm = self._llm_factory() if self._llm_factory else None
        if llm is None or not llm.available:
            section["error"] = "falta configurar el modelo de lenguaje"
            return None
        prior_titles = [s["title"] for s in state["sections"] if s["status"] == "verified"]
        context = (
            f"Documento: {state['title']}\n"
            f"Objetivo real: {state['objective']}\n"
            f"Sección a escribir ahora: {section['title']}\n"
            f"Brief de la sección: {section['brief']}"
        )
        if prior_titles:
            context += (
                f"\nSecciones ya escritas antes de esta (para coherencia, no las repitas): "
                f"{', '.join(prior_titles)}"
            )
        try:
            return llm.generate(
                system=self._section_system_prompt_provider(), messages=[{"role": "user", "content": context}]
            ).text
        except Exception as exc:
            section["error"] = str(exc)
            return None

    def _advance(self, state: dict) -> None:
        """Avanza UN paso real (generar+escribir, o verificar) sobre la
        primera sección no terminal — nunca procesa más de una sección por
        llamada, a propósito: cada llamada queda acotada y rápida, el
        avance completo de un documento largo es responsabilidad de quien
        llama repitiendo `continue_write` (mismo patrón que el propio loop
        de herramientas del Orchestrator ya usa para tareas largas, ADR
        0113 — nunca un loop interno sin tope acá tampoco)."""
        section = next((s for s in state["sections"] if s["status"] not in TERMINAL_STATUSES), None)
        if section is None:
            return

        if section["status"] == "pending":
            section["attempts"] += 1
            content = self._generate_section_content(state, section)
            if content is None:
                if section["attempts"] >= MAX_SECTION_ATTEMPTS:
                    section["status"] = "failed"
                return
            try:
                self._notion.append_to_page(state["page_id"], content)
            except Exception as exc:
                section["error"] = f"fallo al escribir: {exc}"
                if section["attempts"] >= MAX_SECTION_ATTEMPTS:
                    section["status"] = "failed"
                return
            section["content"] = content
            section["status"] = "written"
            section["error"] = None

        section["verify_attempts"] += 1
        try:
            page_text = self._notion.read_page_text(state["page_id"])
        except Exception as exc:
            section["error"] = f"fallo al verificar: {exc}"
            if section["verify_attempts"] >= MAX_SECTION_ATTEMPTS:
                section["status"] = "unverified"
            return
        if _normalize(section["content"]) in page_text:
            section["status"] = "verified"
            section["error"] = None
        else:
            section["error"] = "el contenido escrito no aparece al releer la página"
            if section["verify_attempts"] >= MAX_SECTION_ATTEMPTS:
                section["status"] = "unverified"
