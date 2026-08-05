"""Research (Fase I, ver plan de expansión "Inteligencia Ejecutiva") — una
sola clase real, tres configs (mismo patrón que ExecutiveRoleConfig, ADR
0098): deep_research/trend_scan/competitor_watch comparten exactamente el
mismo mecanismo (buscar fuentes reales, sintetizar con honestidad, publicar
e indexar), solo cambia el system prompt y el rol de ruteo de LLM.

LightRAG Query del video de referencia ya es knowledge_search con otro
nombre (ver KNOWLEDGE.md) — no se adopta LightRAG como framework, mismo
criterio "cero framework" que ya aplica a Inteligencia Ejecutiva (ADR 0094).
NotebookLM Bridge queda fuera de alcance: Google no publica ninguna API real
para eso."""

import re

from snarf.specialists.base import Specialist
from snarf.specialists.research.mode import ResearchModeConfig

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "topic": {"type": "string"},
        "video_urls": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["topic"],
}
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "topic": {"type": "string"},
        "report_text": {"type": "string"},
        "sources": {"type": "array"},
        "document": {"type": "object"},
    },
}

_VIDEO_ID_RE = re.compile(r"(?:v=|youtu\.be/|/embed/)([A-Za-z0-9_-]{11})")


def _extract_video_id(url: str) -> str | None:
    match = _VIDEO_ID_RE.search(url)
    return match.group(1) if match else None


class ResearchSpecialist(Specialist):
    """Investiga un tema real (búsqueda web +, opcional, transcripciones de
    YouTube) y publica el resultado como documento indexado — nunca solo
    texto perdido en el chat (ver KNOWLEDGE.md, "Reportes como insumo")."""

    domain = "research"

    def __init__(self, config: ResearchModeConfig, web_search, youtube, document_publisher, llm_factory, user_id: str):
        self.name = config.mode
        self._config = config
        self._web_search = web_search
        self._youtube = youtube
        self._document_publisher = document_publisher
        self._llm_factory = llm_factory
        self._user_id = user_id

    def _gather_sources(self, topic: str, video_urls: list[str]) -> list[dict]:
        sources: list[dict] = []
        if self._web_search.available:
            try:
                web_result = self._web_search.search(topic)
                for r in web_result["results"]:
                    sources.append({"type": "web", "title": r["title"], "url": r["url"], "content": r["content"]})
                if web_result.get("answer"):
                    sources.append({"type": "web_answer", "title": "Tavily", "url": "", "content": web_result["answer"]})
            except Exception as exc:
                sources.append({"type": "error", "title": "búsqueda web", "url": "", "content": f"falló: {exc}"})

        for url in video_urls:
            video_id = _extract_video_id(url)
            captions = self._youtube.get_video_captions(video_id) if video_id else None
            if captions:
                sources.append({"type": "youtube_captions", "title": url, "url": url, "content": captions[:8000]})

        return sources

    def research(self, topic: str, video_urls: list[str] | None = None) -> dict:
        video_urls = video_urls or []
        llm = self._llm_factory()
        if not llm.available:
            return {
                "topic": topic,
                "report_text": "No se pudo investigar: falta configurar el modelo de lenguaje (ANTHROPIC_API_KEY).",
                "sources": [],
                "document": None,
            }

        sources = self._gather_sources(topic, video_urls)
        real_sources = [s for s in sources if s["type"] != "error"]
        if not real_sources:
            return {
                "topic": topic,
                "report_text": (
                    "No se pudo investigar: ninguna fuente real disponible (TAVILY_API_KEY sin "
                    "configurar, y ningún video con transcripción accesible)."
                ),
                "sources": sources,
                "document": None,
            }

        listing = "\n\n".join(
            f"FUENTE ({s['type']}) — {s['title']} ({s['url']}):\n{s['content']}" for s in real_sources
        )
        response = llm.generate(
            system=self._config.system_prompt,
            messages=[{"role": "user", "content": f"Tema: {topic}\n\n{listing}"}],
        )
        report_text = response.text

        document = self._document_publisher.create_document(
            title=f"{self._config.display_name}: {topic}", content=report_text, format="markdown", destination="drive"
        )

        return {"topic": topic, "report_text": report_text, "sources": sources, "document": document}

    def handle(self, task: str, context: dict) -> str:
        return self.research(task, context.get("video_urls"))["report_text"]
