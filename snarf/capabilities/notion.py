import os

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
