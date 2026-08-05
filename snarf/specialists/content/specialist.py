"""Content (Fase I, ver plan de expansión "Inteligencia Ejecutiva") — una
sola clase real, tres configs (mismo patrón que ResearchSpecialist/
ExecutiveRoleConfig): blog_post/social_post/newsletter comparten el mismo
mecanismo (redactar con AnthropicLLM, publicar con DocumentPublisher), solo
cambia el system prompt y el rol de ruteo de LLM.

Generación de imágenes queda deliberadamente fuera de esta rama — ver
IMAGE_GENERATION_RESEARCH.md, investigado pero sin decisión de vendor
todavía; reusar esa decisión cuando el fundador la tome, no revisitarla acá."""

from snarf.specialists.base import Specialist
from snarf.specialists.content.mode import ContentModeConfig

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "brief": {"type": "string"},
        "reference_material": {"type": "string"},
    },
    "required": ["brief"],
}
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "draft_text": {"type": "string"},
        "document": {"type": "object"},
    },
}


class ContentSpecialist(Specialist):
    """Redacta un borrador de contenido real y lo publica como documento
    indexado — nunca solo texto perdido en el chat, mismo criterio que
    ResearchSpecialist."""

    domain = "content"

    def __init__(self, config: ContentModeConfig, document_publisher, llm_factory, user_id: str):
        self.name = config.mode
        self._config = config
        self._document_publisher = document_publisher
        self._llm_factory = llm_factory
        self._user_id = user_id

    def draft(self, brief: str, reference_material: str = "") -> dict:
        llm = self._llm_factory()
        if not llm.available:
            return {
                "draft_text": "No se pudo redactar: falta configurar el modelo de lenguaje (ANTHROPIC_API_KEY).",
                "document": None,
            }

        user_content = f"Brief: {brief}"
        if reference_material:
            user_content += f"\n\nMaterial de referencia real:\n{reference_material}"

        response = llm.generate(system=self._config.system_prompt, messages=[{"role": "user", "content": user_content}])
        draft_text = response.text

        document = self._document_publisher.create_document(
            title=f"{self._config.display_name}: {brief[:80]}", content=draft_text, format="markdown", destination="drive"
        )
        return {"draft_text": draft_text, "document": document}

    def handle(self, task: str, context: dict) -> str:
        return self.draft(task, context.get("reference_material", ""))["draft_text"]
