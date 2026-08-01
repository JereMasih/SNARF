"""Parser del export completo de ChatGPT (Settings -> Data Controls -> Export).

Formato real documentado por OpenAI: un ZIP con `conversations.json` (lista
de conversaciones, cada una con un árbol `mapping` de nodos
{id, message, parent, children}), más `user.json`, `chat.html` y adjuntos
sueltos.

Limitación real, confirmada al escribir esto (ver ADR 0076 y la memoria
`snarf_roadmap_legion_and_notion_deferred_items`): ChatGPT NO expone de
forma documentada a qué Project pertenece cada conversación en este export
— por eso `filter_by_title_keyword` es un heurístico de texto sobre el
título, no la lectura de un campo real. Cuando el fundador tenga el ZIP
real, hay que confirmar contra los datos reales si existe algún campo
adicional (`gizmo_id`, `conversation_template_id` o similar) antes de
confiar en el heurístico para algo importante — este módulo todavía no se
probó contra un export real, solo contra fixtures con la forma documentada.
"""

import json
import zipfile
from dataclasses import dataclass, field


@dataclass
class ChatGPTMessage:
    role: str
    text: str
    create_time: float | None = None


@dataclass
class ChatGPTConversation:
    id: str
    title: str
    create_time: float | None = None
    messages: list[ChatGPTMessage] = field(default_factory=list)


def _message_text(message: dict) -> str:
    content = message.get("content") or {}
    if content.get("content_type") != "text":
        return ""
    parts = content.get("parts") or []
    return "\n".join(p for p in parts if isinstance(p, str)).strip()


def _linearize(mapping: dict, current_node: str | None) -> list[dict]:
    """Camina el árbol `mapping` desde `current_node` hasta la raíz (o desde
    cualquier hoja si no hay current_node) y devuelve los nodos en el orden
    cronológico real en que se mostraron — el orden de inserción del dict
    de Python no está garantizado que coincida con esto."""
    if current_node is None:
        leaves = [node_id for node_id, node in mapping.items() if not node.get("children")]
        current_node = leaves[-1] if leaves else None
    chain = []
    node_id = current_node
    seen: set[str] = set()
    while node_id is not None and node_id not in seen:
        seen.add(node_id)
        node = mapping.get(node_id)
        if node is None:
            break
        chain.append(node)
        node_id = node.get("parent")
    chain.reverse()
    return chain


def parse_conversations(conversations_json: list[dict]) -> list[ChatGPTConversation]:
    """Parsea la lista cruda de conversations.json en objetos tipados, con
    los mensajes de cada conversación en orden cronológico real."""
    result = []
    for raw in conversations_json:
        mapping = raw.get("mapping") or {}
        nodes = _linearize(mapping, raw.get("current_node"))
        messages = []
        for node in nodes:
            message = node.get("message")
            if not message:
                continue
            role = (message.get("author") or {}).get("role", "")
            if role not in ("user", "assistant"):
                continue
            text = _message_text(message)
            if not text:
                continue
            messages.append(ChatGPTMessage(role=role, text=text, create_time=message.get("create_time")))
        result.append(
            ChatGPTConversation(
                id=raw.get("id") or raw.get("conversation_id") or "",
                title=raw.get("title") or "(sin título)",
                create_time=raw.get("create_time"),
                messages=messages,
            )
        )
    return result


def load_export_zip(zip_path: str) -> list[ChatGPTConversation]:
    """Punto de entrada real: abre el ZIP de exportación completa de
    ChatGPT y devuelve las conversaciones parseadas. Falla fuerte si
    conversations.json no está adentro — es la señal de que no es un
    export real de ChatGPT, mejor un error claro que degradar en silencio."""
    with zipfile.ZipFile(zip_path) as zf:
        with zf.open("conversations.json") as f:
            raw = json.load(f)
    return parse_conversations(raw)


def filter_by_title_keyword(conversations: list[ChatGPTConversation], keyword: str) -> list[ChatGPTConversation]:
    """Heurístico de texto para aproximar 'conversaciones de tal Project'
    (ver limitación documentada arriba). Coincidencia simple, sin
    distinguir mayúsculas, del título de la conversación."""
    needle = keyword.strip().lower()
    return [c for c in conversations if needle in c.title.lower()]


def conversation_to_markdown(conversation: ChatGPTConversation) -> str:
    """Texto plano legible de una conversación completa — listo para pasar
    a project_add_note o drive_create_document (Snarf), no reimplementa
    ningún paso de guardado, solo prepara el contenido."""
    lines = [f"# {conversation.title}", ""]
    for message in conversation.messages:
        speaker = "Vos" if message.role == "user" else "ChatGPT"
        lines.append(f"**{speaker}:** {message.text}")
        lines.append("")
    return "\n".join(lines).strip()
