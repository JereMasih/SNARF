import os
import time
from typing import Iterator

import requests

from snarf.capabilities.base import Capability

API_BASE = "https://api.notion.com/v1"
# Versión fija de la API de Notion (no "latest") — evita que un cambio de
# versión por parte de Notion rompa el shape de estas respuestas en
# silencio. Actualizar a propósito, no por accidente.
NOTION_VERSION = "2022-06-28"

# Límite real de la API de Notion: como mucho 100 bloques `children` por
# request de creación/append — sin trocear, un documento largo generado de
# una sola vez falla a mitad de camino (ver ADR 0180, prerrequisito de la
# escritura confiable de documentos del roadmap Second Brain).
MAX_CHILDREN_PER_REQUEST = 100

# Mismo criterio de 3 intentos con pausa corta que
# `google_retry.retry_with_fresh_client` (ADR 0041), adaptado acá a un
# cliente HTTP sin estado: no hay ningún "service" cacheado que resetear,
# solo reintentar la misma llamada ante un 429 (rate limit) o 5xx
# transitorio de Notion.
NOTION_MAX_ATTEMPTS = 3
NOTION_RETRY_DELAY_SECONDS = 0.4


def _is_transient_error(response) -> bool:
    return response.status_code == 429 or response.status_code >= 500


def _chunked(items: list, size: int) -> Iterator[list]:
    for i in range(0, len(items), size):
        yield items[i:i + size]


def extract_title(result: dict) -> str:
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


def _block_plain_text(block: dict) -> str:
    """Extrae el texto plano real de un bloque de Notion — la mayoría lo
    guarda bajo `block[type]["rich_text"]`, pero una fila de tabla
    (`table_row`) lo guarda como una lista de celdas (`["cells"]`), cada una
    su propia lista de rich_text; sin este caso especial una tabla se
    recorre pero no aporta ningún texto legible."""
    btype = block.get("type")
    inner = block.get(btype)
    if not isinstance(inner, dict):
        return ""
    if btype == "table_row":
        return " | ".join(
            "".join(t.get("plain_text", "") for t in cell) for cell in inner.get("cells", [])
        )
    rich_text = inner.get("rich_text")
    if rich_text:
        return "".join(t.get("plain_text", "") for t in rich_text)
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

    def __init__(self, notion_auth=None):
        self._api_key = os.environ.get("NOTION_API_KEY")
        # notion_auth: NotionAuth opcional (ADR 0186) — mismo patrón de
        # inyección que GoogleDrive(google_auth). Si el usuario ya conectó
        # su propio Notion vía OAuth, su token real tiene prioridad; si no
        # (o no se inyectó ningún NotionAuth, ej. tests viejos), cae de
        # vuelta al NOTION_API_KEY global — DEFAULT_USER_ID sigue
        # funcionando exactamente igual que antes de este ADR.
        self._notion_auth = notion_auth

    def _resolve_token(self) -> str | None:
        if self._notion_auth is not None:
            token = self._notion_auth.access_token()
            if token:
                return token
        return self._api_key

    @property
    def available(self) -> bool:
        return bool(self._resolve_token())

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._resolve_token()}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }

    def _require_available(self) -> None:
        if not self.available:
            raise RuntimeError("NOTION_API_KEY no configurada (ver .env.example).")

    def _request_with_retry(self, verb: str, url: str, json_body: dict) -> requests.Response:
        """`verb` es 'post' o 'patch' (los dos únicos usados en escritura por
        tandas hoy — create_page/append_to_page). Reintenta hasta
        NOTION_MAX_ATTEMPTS veces ante un 429/5xx transitorio; un error real
        (4xx que no sea rate limit) se devuelve tal cual en el primer
        intento, sin reintentar en vano."""
        request_fn = getattr(requests, verb)
        response = None
        for attempt in range(NOTION_MAX_ATTEMPTS):
            response = request_fn(url, headers=self._headers(), json=json_body, timeout=15)
            if not _is_transient_error(response):
                return response
            if attempt < NOTION_MAX_ATTEMPTS - 1:
                time.sleep(NOTION_RETRY_DELAY_SECONDS)
        return response

    def _append_blocks(self, page_id: str, blocks: list[dict]) -> None:
        response = self._request_with_retry(
            "patch", f"{API_BASE}/blocks/{page_id}/children", {"children": blocks}
        )
        response.raise_for_status()

    def search(self, query: str, page_size: int = 20) -> list[dict]:
        self._require_available()
        response = requests.post(
            f"{API_BASE}/search", headers=self._headers(), json={"query": query, "page_size": page_size}, timeout=15
        )
        response.raise_for_status()
        return [
            {"id": r.get("id"), "object": r.get("object"), "title": extract_title(r), "url": r.get("url")}
            for r in response.json().get("results", [])
        ]

    def create_page(self, parent_page_id: str, title: str, content: str = "") -> dict:
        """Si `content` genera más de MAX_CHILDREN_PER_REQUEST bloques, la
        creación en sí solo manda la primera tanda (límite real de la API) y
        el resto se agrega con `_append_blocks` en tandas siguientes — un
        documento largo nunca falla a mitad de camino solo por exceder el
        límite de children por request (ver ADR 0180)."""
        self._require_available()
        blocks = _paragraph_blocks(content)
        first_batch, rest = blocks[:MAX_CHILDREN_PER_REQUEST], blocks[MAX_CHILDREN_PER_REQUEST:]
        body: dict = {
            "parent": {"page_id": parent_page_id},
            "properties": {"title": {"title": [{"type": "text", "text": {"content": title}}]}},
        }
        if first_batch:
            body["children"] = first_batch
        response = self._request_with_retry("post", f"{API_BASE}/pages", body)
        response.raise_for_status()
        data = response.json()
        page_id = data.get("id")
        for batch in _chunked(rest, MAX_CHILDREN_PER_REQUEST):
            self._append_blocks(page_id, batch)
        return {"id": page_id, "url": data.get("url")}

    def append_to_page(self, page_id: str, content: str) -> dict:
        """Trocea en tandas de MAX_CHILDREN_PER_REQUEST bloques, cada una con
        reintento propio ante un 429/5xx transitorio — mismo motivo que
        `create_page`."""
        self._require_available()
        blocks = _paragraph_blocks(content)
        for batch in (list(_chunked(blocks, MAX_CHILDREN_PER_REQUEST)) or [[]]):
            self._append_blocks(page_id, batch)
        return {"status": "appended", "page_id": page_id}

    def _iter_page_blocks(self, block_id: str, _seen: set[str] | None = None) -> Iterator[dict]:
        """Recorre TODO el contenido real de una página, no solo el nivel
        superior — sin esto, una nota armada con toggles (acordeones) o con
        el bloque especial `transcription` que arma el transcriptor de
        reuniones de Notion (pestañas Resumen/Notas/Transcripción) se ve
        vacía, aunque tenga contenido real adentro (ver ADR 0175). Devuelve
        un dict por cada fragmento de texto real: `{id, type, text}` — id
        es `None` para las etiquetas sintéticas que marcan cada pestaña de
        una transcripción, nunca bloques editables de verdad."""
        self._require_available()
        if _seen is None:
            _seen = set()
        if block_id in _seen:
            return
        _seen.add(block_id)
        response = requests.get(
            f"{API_BASE}/blocks/{block_id}/children", headers=self._headers(), params={"page_size": 100}, timeout=15
        )
        response.raise_for_status()
        for block in response.json().get("results", []):
            block_type = block.get("type")
            if block_type == "transcription":
                title = "".join(t.get("plain_text", "") for t in block["transcription"].get("title", []))
                yield {
                    "id": None,
                    "type": "transcription_title",
                    "text": f"Transcripción de reunión: {title}" if title else "Transcripción de reunión",
                }
                children_map = block["transcription"].get("children", {})
                for label, key in (
                    ("Resumen", "summary_block_id"),
                    ("Notas", "notes_block_id"),
                    ("Transcripción", "transcript_block_id"),
                ):
                    child_id = children_map.get(key)
                    if not child_id:
                        continue
                    section_items = list(self._iter_page_blocks(child_id, _seen))
                    if not section_items:
                        continue
                    yield {"id": None, "type": "transcription_section", "text": f"[{label}]"}
                    yield from section_items
                continue
            text = _block_plain_text(block)
            if text:
                yield {"id": block["id"], "type": block_type, "text": text}
            if block.get("has_children"):
                yield from self._iter_page_blocks(block["id"], _seen)

    def read_page_text(self, page_id: str) -> str:
        """Texto plano completo de una página, recorriendo toggles, tablas y
        transcripciones de reunión (ver `_iter_page_blocks`) — no solo el
        primer nivel de bloques."""
        return "\n\n".join(item["text"] for item in self._iter_page_blocks(page_id) if item["text"])

    def list_blocks(self, page_id: str) -> list[dict]:
        """Igual que `read_page_text`, pero sin aplanar a un solo string —
        cada fragmento real conserva su `id` de bloque y su `type`, para
        poder pasarle un `block_id` concreto a `update_block`/`delete_block`
        en vez de tener que adivinarlo."""
        return list(self._iter_page_blocks(page_id))

    def get_block(self, block_id: str) -> dict:
        """Un solo bloque real, tal cual está hoy — pensado para mostrar una
        vista previa de 'esto es lo que hay ahora' antes de update_block o
        delete_block."""
        self._require_available()
        response = requests.get(f"{API_BASE}/blocks/{block_id}", headers=self._headers(), timeout=15)
        response.raise_for_status()
        block = response.json()
        return {"id": block.get("id"), "type": block.get("type"), "text": _block_plain_text(block)}

    def update_block(self, block_id: str, block_type: str, content: str) -> dict:
        """Reemplaza el texto real de un bloque existente (paragraph,
        heading_1/2/3, quote, callout, bulleted_list_item,
        numbered_list_item, to_do, toggle — cualquier tipo con `rich_text`
        propio). `block_type` tiene que coincidir con el tipo real del
        bloque (ver `list_blocks`) — la API de Notion lo exige como key del
        body, no lo adivina."""
        self._require_available()
        response = requests.patch(
            f"{API_BASE}/blocks/{block_id}",
            headers=self._headers(),
            json={block_type: {"rich_text": [{"type": "text", "text": {"content": content}}]}},
            timeout=15,
        )
        response.raise_for_status()
        return {"id": block_id, "status": "updated"}

    def get_table_row(self, block_id: str) -> dict:
        """Una fila de tabla (`table_row`) completa, con el texto real de
        CADA columna por separado — a diferencia de `get_block`/`list_blocks`
        (que la aplanan a un solo string 'Col A | Col B'), esto conserva el
        índice de columna real, necesario para no perder las demás celdas al
        editar una sola con `update_table_cell`."""
        self._require_available()
        response = requests.get(f"{API_BASE}/blocks/{block_id}", headers=self._headers(), timeout=15)
        response.raise_for_status()
        block = response.json()
        cells = block.get("table_row", {}).get("cells", [])
        return {
            "id": block.get("id"),
            "cells": ["".join(t.get("plain_text", "") for t in cell) for cell in cells],
        }

    def update_table_cell(self, block_id: str, column_index: int, content: str) -> dict:
        """Reemplaza el texto de UNA celda de una fila de tabla ya
        existente, dado el índice de columna (0-based, mismo orden que
        muestra 'Col A | Col B | ...' en read_page_text/list_blocks). La API
        de Notion exige mandar TODAS las celdas de la fila en cada PATCH —
        por eso primero trae la fila real completa y solo reemplaza la
        celda pedida, para no borrar el resto de las columnas."""
        self._require_available()
        response = requests.get(f"{API_BASE}/blocks/{block_id}", headers=self._headers(), timeout=15)
        response.raise_for_status()
        row = response.json()
        cells = row.get("table_row", {}).get("cells", [])
        if column_index < 0 or column_index >= len(cells):
            raise ValueError(f"column_index {column_index} fuera de rango — la fila tiene {len(cells)} columnas")
        new_cells = list(cells)
        new_cells[column_index] = [{"type": "text", "text": {"content": content}}]
        response = requests.patch(
            f"{API_BASE}/blocks/{block_id}",
            headers=self._headers(),
            json={"table_row": {"cells": new_cells}},
            timeout=15,
        )
        response.raise_for_status()
        return {"id": block_id, "status": "updated", "column_index": column_index}

    def delete_block(self, block_id: str) -> dict:
        """Borra (envía a la papelera de Notion, recuperable ahí — mismo
        criterio de reversibilidad que drive_delete_file) un bloque real."""
        self._require_available()
        response = requests.delete(f"{API_BASE}/blocks/{block_id}", headers=self._headers(), timeout=15)
        response.raise_for_status()
        return {"id": block_id, "status": "deleted"}

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

    def find_child_databases(self, page_id: str, _seen: set[str] | None = None) -> list[dict]:
        """Recorre recursivamente los bloques reales de una página buscando
        databases incrustadas (`child_database`) — `/search` de Notion no
        las lista (gap real, ver ADR 0193), así que sin esto quedan
        invisibles para `iter_all_databases`/el indexado semántico. Mismo
        mecanismo de recorrido que `_iter_page_blocks` (recursión sobre
        `has_children`), pero acá interesa el bloque `child_database` en sí
        (id + título), no su texto — a diferencia de una database real
        consultable con `query_database`, no tiene sentido "recursar
        adentro" de una database incrustada como si fuera un bloque más."""
        self._require_available()
        if _seen is None:
            _seen = set()
        if page_id in _seen:
            return []
        _seen.add(page_id)
        found: list[dict] = []
        response = requests.get(
            f"{API_BASE}/blocks/{page_id}/children", headers=self._headers(), params={"page_size": 100}, timeout=15
        )
        response.raise_for_status()
        for block in response.json().get("results", []):
            if block.get("type") == "child_database":
                found.append({"id": block["id"], "title": block.get("child_database", {}).get("title", "")})
            elif block.get("has_children"):
                found.extend(self.find_child_databases(block["id"], _seen))
        return found

    def get_page(self, page_id: str) -> dict:
        """Página real completa a nivel de metadata — properties tipadas tal
        cual las devuelve Notion, más el estado de archivado — no de
        contenido/bloques (ver read_page_text/list_blocks para eso). Trae
        UN registro puntual (ej. una fila de Área o de Proyecto del Second
        Brain) sin tener que recorrer toda la database con query_database."""
        self._require_available()
        response = requests.get(f"{API_BASE}/pages/{page_id}", headers=self._headers(), timeout=15)
        response.raise_for_status()
        data = response.json()
        return {
            "id": data.get("id"),
            "url": data.get("url"),
            "archived": data.get("archived", False),
            "properties": data.get("properties", {}),
        }

    def create_database(self, parent_page_id: str, title: str, properties: dict) -> dict:
        """Crea una database NUEVA (no una fila) bajo una página padre — a
        diferencia de `create_database_item` (crea un registro dentro de una
        database YA existente). `properties` va tal cual llega, ya en la
        forma tipada que exige la API de Notion para el schema
        (ej. {'Nombre': {'title': {}}, 'Estado': {'select': {'options': [...]}}}).
        Necesario para que el onboarding del Second Brain (ver
        ROADMAP_SECOND_BRAIN_NOTION.md, Fase A4) pueda construir las
        databases Área/Proyecto/Recursos/Archivo cuando el usuario no las
        tiene todavía."""
        self._require_available()
        body = {
            "parent": {"type": "page_id", "page_id": parent_page_id},
            "title": [{"type": "text", "text": {"content": title}}],
            "properties": properties,
        }
        response = requests.post(f"{API_BASE}/databases", headers=self._headers(), json=body, timeout=15)
        response.raise_for_status()
        data = response.json()
        return {"id": data.get("id"), "url": data.get("url")}

    def move_page(self, page_id: str, new_parent_database_id: str) -> dict:
        """Mueve una página existente a otra database, cambiando su
        `parent`. Notion descarta en silencio cualquier property que no
        exista (por nombre y tipo) en la database destino — el fundador
        pierde esos valores sin ningún aviso de la API; quien llame a esto
        debe advertirlo antes de pedir confirmación (ver ADR 0180)."""
        self._require_available()
        response = requests.patch(
            f"{API_BASE}/pages/{page_id}",
            headers=self._headers(),
            json={"parent": {"database_id": new_parent_database_id}},
            timeout=15,
        )
        response.raise_for_status()
        return {"id": page_id, "status": "moved", "database_id": new_parent_database_id}

    def update_page_cover(self, page_id: str, cover_url: str | None) -> dict:
        """Cambia (o quita, con `cover_url=None`) la portada de una página —
        la API de Notion solo acepta covers externos (una URL), nunca subir
        un archivo directo por esta vía."""
        self._require_available()
        cover = {"type": "external", "external": {"url": cover_url}} if cover_url else None
        response = requests.patch(
            f"{API_BASE}/pages/{page_id}", headers=self._headers(), json={"cover": cover}, timeout=15
        )
        response.raise_for_status()
        return {"id": page_id, "status": "updated"}

    def update_page_icon(self, page_id: str, icon: dict | None) -> dict:
        """Cambia (o quita, con `icon=None`) el ícono de una página. `icon`
        va tal cual en la forma tipada real de Notion — emoji
        (`{'type': 'emoji', 'emoji': '🎯'}`) o externo
        (`{'type': 'external', 'external': {'url': ...}}`)."""
        self._require_available()
        response = requests.patch(
            f"{API_BASE}/pages/{page_id}", headers=self._headers(), json={"icon": icon}, timeout=15
        )
        response.raise_for_status()
        return {"id": page_id, "status": "updated"}

    def update_database_cover(self, database_id: str, cover_url: str | None) -> dict:
        """Igual que `update_page_cover` pero para una database entera."""
        self._require_available()
        cover = {"type": "external", "external": {"url": cover_url}} if cover_url else None
        response = requests.patch(
            f"{API_BASE}/databases/{database_id}", headers=self._headers(), json={"cover": cover}, timeout=15
        )
        response.raise_for_status()
        return {"id": database_id, "status": "updated"}

    def update_database_icon(self, database_id: str, icon: dict | None) -> dict:
        """Igual que `update_page_icon` pero para una database entera."""
        self._require_available()
        response = requests.patch(
            f"{API_BASE}/databases/{database_id}", headers=self._headers(), json={"icon": icon}, timeout=15
        )
        response.raise_for_status()
        return {"id": database_id, "status": "updated"}

    def archive_page(self, page_id: str) -> dict:
        """Envía una página a la papelera de Notion — recuperable ahí,
        mismo criterio de reversibilidad que `delete_block`/
        `drive_delete_file`."""
        return self._set_page_archived(page_id, True)

    def restore_page(self, page_id: str) -> dict:
        """Restaura una página archivada previamente con `archive_page`."""
        return self._set_page_archived(page_id, False)

    def _set_page_archived(self, page_id: str, archived: bool) -> dict:
        self._require_available()
        response = requests.patch(
            f"{API_BASE}/pages/{page_id}", headers=self._headers(), json={"archived": archived}, timeout=15
        )
        response.raise_for_status()
        return {"id": page_id, "status": "archived" if archived else "restored"}

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
                "title": extract_title(result),
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
