import os
from typing import Iterator

import requests

from snarf.capabilities.base import Capability

API_BASE = "https://api.notion.com/v1"
# Versión fija de la API de Notion (no "latest") — evita que un cambio de
# versión por parte de Notion rompa el shape de estas respuestas en
# silencio. Actualizar a propósito, no por accidente.
NOTION_VERSION = "2022-06-28"


def _extract_title(result: dict) -> str:
    for prop in result.get("properties", {}).values():
        if prop.get("type") == "title":
            return "".join(t.get("plain_text", "") for t in prop.get("title", []))
    return result.get("id", "")


def _property_value_text(prop: dict) -> str:
    """Extrae el valor legible de una property tipada de Notion — cada tipo
    guarda su valor bajo una key distinta (`prop["select"]`, `prop["date"]`,
    etc.), sin esto una fila de database no tiene ningún texto plano posible
    de indexar."""
    prop_type = prop.get("type")
    value = prop.get(prop_type)
    if value in (None, [], {}):
        return ""
    if prop_type in ("title", "rich_text"):
        return "".join(t.get("plain_text", "") for t in value)
    if prop_type in ("select", "status"):
        return value.get("name", "")
    if prop_type == "multi_select":
        return ", ".join(v.get("name", "") for v in value)
    if prop_type == "date":
        start = value.get("start", "")
        end = value.get("end")
        return f"{start} - {end}" if end else start
    if prop_type == "number":
        return str(value)
    if prop_type == "checkbox":
        return "sí" if value else "no"
    if prop_type in ("url", "email", "phone_number", "created_time", "last_edited_time"):
        return str(value)
    if prop_type == "people":
        return ", ".join(p.get("name", "") for p in value if p.get("name"))
    if prop_type == "relation":
        return ", ".join(r.get("id", "") for r in value)
    if prop_type == "formula":
        inner_type = value.get("type")
        inner = value.get(inner_type)
        return str(inner) if inner is not None else ""
    return ""


def format_properties_text(properties: dict) -> str:
    """Convierte el dict tipado de properties de una fila de database a texto
    plano legible ('Título: X. Estado: Y...') — es donde vive el contenido
    real de una fila (una nota, una tarea), no en el cuerpo de la página."""
    parts = []
    for name, prop in properties.items():
        value = _property_value_text(prop)
        if value:
            parts.append(f"{name}: {value}")
    return ". ".join(parts)


def _paragraph_blocks(text: str) -> list[dict]:
    """Convierte texto plano (párrafos separados por línea en blanco) en
    bloques 'paragraph' de Notion. A propósito NO es un parser de Markdown
    completo (sin negrita/listas/encabezados) — alcanza para que texto real
    llegue legible a una página; una conversión más rica es una extensión
    futura, no algo que este alcance prometa."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    return [
        {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": p}}]}}
        for p in paragraphs
    ]


class Notion(Capability):
    name = "notion"

    def __init__(self):
        self._api_key = os.environ.get("NOTION_API_KEY")

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }

    def _require_available(self) -> None:
        if not self.available:
            raise RuntimeError("NOTION_API_KEY no configurada (ver .env.example).")

    def search(self, query: str, page_size: int = 20) -> list[dict]:
        self._require_available()
        response = requests.post(
            f"{API_BASE}/search", headers=self._headers(), json={"query": query, "page_size": page_size}, timeout=15
        )
        response.raise_for_status()
        return [
            {"id": r.get("id"), "object": r.get("object"), "title": _extract_title(r), "url": r.get("url")}
            for r in response.json().get("results", [])
        ]

    def create_page(self, parent_page_id: str, title: str, content: str = "") -> dict:
        self._require_available()
        body: dict = {
            "parent": {"page_id": parent_page_id},
            "properties": {"title": {"title": [{"type": "text", "text": {"content": title}}]}},
        }
        blocks = _paragraph_blocks(content)
        if blocks:
            body["children"] = blocks
        response = requests.post(f"{API_BASE}/pages", headers=self._headers(), json=body, timeout=15)
        response.raise_for_status()
        data = response.json()
        return {"id": data.get("id"), "url": data.get("url")}

    def append_to_page(self, page_id: str, content: str) -> dict:
        self._require_available()
        response = requests.patch(
            f"{API_BASE}/blocks/{page_id}/children",
            headers=self._headers(),
            json={"children": _paragraph_blocks(content)},
            timeout=15,
        )
        response.raise_for_status()
        return {"status": "appended", "page_id": page_id}

    def read_page_text(self, page_id: str) -> str:
        self._require_available()
        response = requests.get(f"{API_BASE}/blocks/{page_id}/children", headers=self._headers(), timeout=15)
        response.raise_for_status()
        lines = []
        for block in response.json().get("results", []):
            block_type = block.get("type")
            rich_text = block.get(block_type, {}).get("rich_text", [])
            text = "".join(rt.get("plain_text", "") for rt in rich_text)
            if text:
                lines.append(text)
        return "\n\n".join(lines)

    def get_database(self, database_id: str) -> dict:
        """Schema real de una database (nombre + properties tipadas: select,
        multi-select, date, number, checkbox, relation, etc.) — necesario
        ANTES de poder llenarla o cambiarle propiedades, para saber qué
        properties existen y de qué tipo es cada una."""
        self._require_available()
        response = requests.get(f"{API_BASE}/databases/{database_id}", headers=self._headers(), timeout=15)
        response.raise_for_status()
        data = response.json()
        return {
            "id": data.get("id"),
            "title": "".join(t.get("plain_text", "") for t in data.get("title", [])),
            "url": data.get("url"),
            "properties": {
                name: prop.get("type") for name, prop in data.get("properties", {}).items()
            },
        }

    def query_database(self, database_id: str, filter: dict | None = None, sorts: list[dict] | None = None, page_size: int = 100) -> list[dict]:
        """Registros (páginas) de una database, con las properties tipadas
        de cada una tal cual las devuelve Notion — sin reinterpretarlas, para
        no perder información de tipo (select/date/number/etc)."""
        self._require_available()
        body: dict = {"page_size": page_size}
        if filter:
            body["filter"] = filter
        if sorts:
            body["sorts"] = sorts
        response = requests.post(f"{API_BASE}/databases/{database_id}/query", headers=self._headers(), json=body, timeout=15)
        response.raise_for_status()
        return [
            {"id": r.get("id"), "url": r.get("url"), "properties": r.get("properties", {})}
            for r in response.json().get("results", [])
        ]

    def create_database_item(self, database_id: str, properties: dict) -> dict:
        """Crea un registro (página) dentro de una database. `properties` va
        tal cual llega — ya en la forma tipada que exige la API de Notion
        para cada tipo (ver get_database para el schema real de esta
        database antes de armar el dict)."""
        self._require_available()
        body = {"parent": {"database_id": database_id}, "properties": properties}
        response = requests.post(f"{API_BASE}/pages", headers=self._headers(), json=body, timeout=15)
        response.raise_for_status()
        data = response.json()
        return {"id": data.get("id"), "url": data.get("url")}

    def _iter_search_results(self, object_type: str, page_size: int = 100) -> Iterator[dict]:
        self._require_available()
        cursor: str | None = None
        while True:
            body: dict = {"filter": {"property": "object", "value": object_type}, "page_size": page_size}
            if cursor:
                body["start_cursor"] = cursor
            response = requests.post(f"{API_BASE}/search", headers=self._headers(), json=body, timeout=15)
            response.raise_for_status()
            data = response.json()
            yield from data.get("results", [])
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")

    def iter_all_pages(self) -> Iterator[dict]:
        """Enumera TODAS las páginas compartidas con la integración, paginando
        hasta agotarlas — a diferencia de `search` (pensada para un pedido
        puntual del LLM, tope de 20), esto es para indexado semántico
        completo (ver NotionSource en snarf/knowledge/)."""
        for result in self._iter_search_results("page"):
            yield {
                "id": result.get("id"),
                "title": _extract_title(result),
                "url": result.get("url"),
                "last_edited_time": result.get("last_edited_time"),
            }

    def iter_all_databases(self) -> Iterator[dict]:
        """Igual que iter_all_pages pero para databases reales."""
        for result in self._iter_search_results("database"):
            yield {
                "id": result.get("id"),
                "title": "".join(t.get("plain_text", "") for t in result.get("title", [])),
                "url": result.get("url"),
                "last_edited_time": result.get("last_edited_time"),
            }

    def iter_database_rows(self, database_id: str, page_size: int = 100) -> Iterator[dict]:
        """Todas las filas reales de una database, paginando hasta agotarlas
        — a diferencia de query_database (pensada para un pedido puntual del
        LLM, tope fijo sin cursor), esto es para indexado semántico
        completo."""
        self._require_available()
        cursor: str | None = None
        while True:
            body: dict = {"page_size": page_size}
            if cursor:
                body["start_cursor"] = cursor
            response = requests.post(
                f"{API_BASE}/databases/{database_id}/query", headers=self._headers(), json=body, timeout=15
            )
            response.raise_for_status()
            data = response.json()
            for result in data.get("results", []):
                yield {
                    "id": result.get("id"),
                    "url": result.get("url"),
                    "last_edited_time": result.get("last_edited_time"),
                    "properties": result.get("properties", {}),
                }
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")

    def update_page_properties(self, page_id: str, properties: dict) -> dict:
        """Cambia properties tipadas de una página existente (típicamente un
        registro dentro de una database) — mismo formato tipado que
        create_database_item."""
        self._require_available()
        response = requests.patch(
            f"{API_BASE}/pages/{page_id}", headers=self._headers(), json={"properties": properties}, timeout=15
        )
        response.raise_for_status()
        return {"id": page_id, "status": "updated"}
