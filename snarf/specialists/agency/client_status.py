"""Weekly Client Status (Fase I, rama Agency — ver plan de expansión
"Inteligencia Ejecutiva"). Único código genuinamente nuevo de la rama: el
resto (Sponsor Pitch Deck, Scope-of-Work Gen, Deliverable QA, Retainer
Renewal Brief) es un caso más de "redactar un documento a partir de un
brief", ya cubierto por conversación + drive_create_document, mismo
criterio que Proposal Drafts en la rama Sales (ver ADR de esta ronda). Esto
es genuinamente distinto: parte de datos REALES y estructurados de un
Proyecto (ProjectManager), no de un brief conversacional."""

from snarf.specialists.base import Specialist

SYSTEM_PROMPT = (
    "Redactás un status semanal real para el cliente de un proyecto del fundador de Snarf, a "
    "partir de tareas y notas reales. Tono profesional pero directo, en español: qué se completó "
    "esta semana, qué sigue en curso, qué necesita del cliente si algo. Nunca inventes un avance o "
    "resultado que no esté reflejado en las tareas/notas reales que se te dan."
)

INPUT_SCHEMA = {"type": "object", "properties": {"project_id": {"type": "string"}}, "required": ["project_id"]}
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "status_text": {"type": "string"},
        "document": {"type": "object"},
        "error": {"type": "string"},
    },
}


class ClientStatusSpecialist(Specialist):
    name = "client_status"
    domain = "agency"

    def __init__(self, projects, document_publisher, llm_factory, user_id: str):
        self._projects = projects
        self._document_publisher = document_publisher
        self._llm_factory = llm_factory
        self._user_id = user_id

    def generate(self, project_id: str) -> dict:
        project = self._projects.get(project_id)
        if project is None:
            return {"error": f"Proyecto '{project_id}' no existe."}

        llm = self._llm_factory()
        if not llm.available:
            return {"status_text": "No se pudo generar: falta configurar el modelo de lenguaje (ANTHROPIC_API_KEY).", "document": None}

        done = [t["text"] for t in project["tasks"] if t["done"]]
        pending = [t["text"] for t in project["tasks"] if not t["done"]]
        notes = [n["text"] for n in project.get("notes", [])]
        listing = (
            f"Proyecto: {project['name']}\n"
            f"Tareas completadas ({len(done)}): {'; '.join(done) or 'ninguna'}\n"
            f"Tareas pendientes ({len(pending)}): {'; '.join(pending) or 'ninguna'}\n"
            f"Notas recientes: {'; '.join(notes[-5:]) or 'ninguna'}"
        )
        response = llm.generate(system=SYSTEM_PROMPT, messages=[{"role": "user", "content": listing}])
        status_text = response.text

        document = self._document_publisher.create_document(
            title=f"Status semanal: {project['name']}", content=status_text, format="markdown", destination="drive"
        )
        return {"status_text": status_text, "document": document}

    def handle(self, task: str, context: dict) -> str:
        result = self.generate(context.get("project_id", ""))
        return result.get("error") or result["status_text"]
