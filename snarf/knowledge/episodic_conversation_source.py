from typing import Iterator

from snarf.knowledge.source import KnowledgeItem, KnowledgeSource
from snarf.memory.episodic import EpisodicMemory


class EpisodicConversationSource(KnowledgeSource):
    """Fuente de conocimiento sobre el propio historial de conversaciones de
    Snarf (EpisodicMemory) — dominio 'conversations' de la Knowledge Layer
    (ver KNOWLEDGE.md), mismo precedente que 'code' (ADR 0096): costo cero
    más allá de embeddings, ya vive en disco, sin llamada de red para leer
    contenido.

    Una conversación ENTERA es el ítem indexable (no un chunk por mensaje) —
    `modified_marker` es su `last_activity` real, así que una conversación
    que sigue creciendo se reindexa sola en el próximo ciclo (KnowledgeIndexer
    ya compara el marker contra lo guardado en el manifiesto, sin código
    nuevo acá). `project_id` viaja como metadata real (nunca inventado) para
    poder filtrar la búsqueda por proyecto — ver
    Orchestrator._tool_conversations_search. Se omite la clave por completo
    cuando la conversación no está asignada a ningún proyecto, en vez de
    guardar `None`: chromadb (el backend real de VectorStore) no acepta
    `None` como valor de metadata y lo rechaza con un TypeError al indexar."""

    domain = "conversations"

    def __init__(self, memory: EpisodicMemory):
        self._memory = memory

    def iter_items(self) -> Iterator[KnowledgeItem]:
        for conv in self._memory.list_conversations():
            conversation_id = conv["conversation_id"]
            extra_metadata = {"started_at": conv["started_at"]}
            project_id = self._memory.get_conversation_project(conversation_id)
            if project_id:
                extra_metadata["project_id"] = project_id
            yield KnowledgeItem(
                id=conversation_id,
                name=conv.get("title") or conversation_id,
                mime_type="text/plain",
                modified_marker=str(conv["last_activity"]),
                extra_metadata=extra_metadata,
            )

    def read_item(self, item: KnowledgeItem) -> str:
        entries = self._memory.get_conversation(item.id)
        lines = [f"Conversación: {item.name}"]
        project_id = item.extra_metadata.get("project_id")
        if project_id:
            lines.append(f"Proyecto: {project_id}")
        for entry in entries:
            lines.append(f"Usuario: {entry['input']}")
            lines.append(f"Snarf: {entry['response']}")
        return "\n".join(lines)
