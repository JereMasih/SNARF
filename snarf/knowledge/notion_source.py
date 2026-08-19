from typing import Iterator

from snarf.capabilities.notion import format_properties_text
from snarf.knowledge.source import KnowledgeItem, KnowledgeSource


def _row_title(properties: dict, fallback: str) -> str:
    for prop in properties.values():
        if prop.get("type") == "title":
            text = "".join(t.get("plain_text", "") for t in prop.get("title", []))
            if text:
                return text
    return fallback


class NotionSource(KnowledgeSource):
    """Fuente de conocimiento sobre el Notion del fundador — mismo dominio
    'personal' que Drive (ver KNOWLEDGE.md), para que knowledge_search los
    encuentre juntos sin tocar esa función, distinguibles solo por metadata
    (`source: "notion"`). Cada página es un ítem; cada fila de una database
    también, porque ahí vive el contenido real de una nota o tarea (sus
    properties tipadas), no en el cuerpo de la página."""

    domain = "personal"

    def __init__(self, notion):
        self._notion = notion
        # Poblado durante iter_items, consumido en read_item — evita meter
        # dicts anidados de properties en extra_metadata (ChromaDB exige
        # metadata plana). Ambos corren en la misma corrida del indexer.
        self._row_properties: dict[str, dict] = {}

    def iter_items(self) -> Iterator[KnowledgeItem]:
        self._row_properties = {}
        for page in self._notion.iter_all_pages():
            yield KnowledgeItem(
                id=page["id"],
                name=page.get("title") or page["id"],
                mime_type="notion/page",
                modified_marker=page.get("last_edited_time") or "",
                # 'location' (no 'source'): misma key real que ya usa
                # DriveIndexer (location='drive'/'local') — KNOWLEDGE.md
                # mencionaba 'source' antes de que hubiera código real detrás;
                # se corrige acá para que ambas fuentes sean filtrables con el
                # mismo mecanismo real (ver knowledge_search(source=...)).
                extra_metadata={"location": "notion", "notion_url": page.get("url") or ""},
            )
        for database in self._notion.iter_all_databases():
            for row in self._notion.iter_database_rows(database["id"]):
                self._row_properties[row["id"]] = row["properties"]
                yield KnowledgeItem(
                    id=row["id"],
                    name=_row_title(row["properties"], row["id"]),
                    mime_type="notion/database_row",
                    modified_marker=row.get("last_edited_time") or "",
                    extra_metadata={
                        "location": "notion",
                        "notion_url": row.get("url") or "",
                        "notion_database_id": database["id"],
                    },
                )

    def read_item(self, item: KnowledgeItem) -> str:
        body = self._notion.read_page_text(item.id)
        properties = self._row_properties.get(item.id)
        if properties is None:
            return body
        properties_text = format_properties_text(properties)
        return f"{properties_text}\n\n{body}".strip()
