import json
import os
import re
from dataclasses import dataclass
from typing import Callable

from snarf.capabilities.base import Capability
from snarf.telemetry import usage_tracker

DEFAULT_MODEL = "claude-sonnet-5"
MAX_TOOL_ROUNDS = 5
MAX_OUTPUT_TOKENS = 4096
CACHE_TTL = "1h"

# Marcadores que separan, dentro de un mismo texto generado, la respuesta
# completa (a pantalla) de su narración hablada (a voz) y — cuando corresponde
# — del entregable puntual que la respuesta contiene (un plan, un documento,
# una copia pedida). Ver ADR de la capa de voz + ADR de esta ronda (escuchar
# vs escuchar entregable). El system prompt (orchestrator.SYSTEM_PREFIX)
# instruye al modelo a usar exactamente estos delimitadores; se definen acá
# porque este módulo es el único que los parsea, una sola fuente de verdad.
SPEECH_START = "---HABLA---"
SPEECH_END = "---FIN-HABLA---"
DELIVERABLE_START = "---ENTREGABLE---"
DELIVERABLE_END = "---FIN-ENTREGABLE---"
FALLBACK_SPEECH_MAX_CHARS = 400


@dataclass(frozen=True)
class LLMResponse:
    """Una respuesta generada, separada en pantalla / narración hablada / entregable.

    text: la respuesta íntegra, con estructura/markdown, para mostrar en pantalla.
    speech: narración hablada de ESA MISMA respuesta completa — no es un resumen
    acortado, cubre todo lo sustancial que está en pantalla, fraseado para voz
    (sin markdown, sin URLs deletreadas). Nunca oculta un riesgo o dato faltante.
    deliverable: cuando la respuesta contiene un entregable puntual y pedido
    explícitamente (un plan, un documento, una copia) distinto de la charla
    alrededor, es SOLO ese contenido, fraseado para voz — None si esta
    respuesta es puramente conversacional y no hay nada que aislar.
    """

    text: str
    speech: str
    deliverable: str | None = None


def fallback_speech(text: str) -> str:
    """Versión hablada aproximada cuando el modelo no incluyó el marcador de habla.

    Puramente mecánico (sin otra llamada al modelo): saca marcado Markdown básico
    y corta en un límite de caracteres razonable, preferentemente en un borde de
    oración. No es tan bueno como una versión pensada por el modelo, pero evita
    leer en voz alta encabezados/asteriscos/backticks crudos.
    """
    stripped = re.sub(r"[#*`_>]|^-\s+", "", text, flags=re.MULTILINE).strip()
    stripped = re.sub(r"\s+", " ", stripped)
    if len(stripped) <= FALLBACK_SPEECH_MAX_CHARS:
        return stripped
    truncated = stripped[:FALLBACK_SPEECH_MAX_CHARS]
    cut = max(truncated.rfind(". "), truncated.rfind("? "), truncated.rfind("! "))
    return (truncated[: cut + 1] if cut > 0 else truncated).strip()


def _extract_deliverable(remainder: str) -> str | None:
    """Busca el bloque de entregable en lo que queda después del cierre de habla.

    Ausente en la mayoría de las respuestas (puramente conversacionales) — solo
    aparece cuando el modelo decidió que hay algo puntual para aislar."""
    start = remainder.find(DELIVERABLE_START)
    if start == -1:
        return None
    end = remainder.find(DELIVERABLE_END, start)
    block = remainder[start + len(DELIVERABLE_START) : end if end != -1 else None].strip()
    return block or None


def split_speech(raw_text: str) -> LLMResponse:
    """Separa el texto crudo del modelo en (text, speech, deliverable) según los delimitadores."""
    start = raw_text.find(SPEECH_START)
    if start == -1:
        text = raw_text.strip()
        return LLMResponse(text=text, speech=fallback_speech(text))
    text = raw_text[:start].rstrip()
    tail = raw_text[start + len(SPEECH_START) :]

    deliverable_pos = tail.find(DELIVERABLE_START)
    # El marcador de entregable, si aparece, siempre marca el final real del
    # contenido hablado — incluso cuando el modelo se olvidó de cerrar
    # FIN-HABLA antes de abrirlo (visto en un caso real: el modelo encadenó
    # ---ENTREGABLE--- directo después de la narración, sin cerrar el
    # marcador anterior). Sin este chequeo, esos marcadores quedaban crudos
    # dentro del audio de "escuchar" y el entregable nunca se extraía.
    speech_region = tail[:deliverable_pos] if deliverable_pos != -1 else tail
    deliverable = _extract_deliverable(tail[deliverable_pos:]) if deliverable_pos != -1 else None

    end = speech_region.find(SPEECH_END)
    speech_block = (speech_region[:end] if end != -1 else speech_region).strip()

    return LLMResponse(text=text, speech=speech_block or fallback_speech(text), deliverable=deliverable)


def _mark_cache_breakpoint(message: dict) -> dict:
    """Devuelve una copia del mensaje con cache_control en su último bloque.

    No muta el mensaje original: los mensajes de entrada pueden ser
    reutilizados por quien llama (ver EpisodicMemory.recent en el
    orchestrator), y este marcado es efímero por-llamada.
    """
    content = message.get("content")
    blocks = [{"type": "text", "text": content}] if isinstance(content, str) else [
        dict(block) if isinstance(block, dict) else block for block in content
    ]
    if blocks and isinstance(blocks[-1], dict):
        blocks[-1] = {**blocks[-1], "cache_control": {"type": "ephemeral", "ttl": CACHE_TTL}}
    return {**message, "content": blocks}


class AnthropicLLM(Capability):
    name = "anthropic_llm"

    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model
        self._api_key = os.environ.get("ANTHROPIC_API_KEY")
        self._client = None
        if self._api_key:
            import anthropic

            self._client = anthropic.Anthropic(api_key=self._api_key)

    @property
    def available(self) -> bool:
        return self._client is not None

    def warmup(self) -> None:
        if not self._client:
            return
        try:
            self._client.messages.create(
                model=self.model, max_tokens=1, messages=[{"role": "user", "content": "hola"}]
            )
        except Exception:
            pass

    def generate(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        tool_handler: Callable[[str, dict], object] | None = None,
    ) -> LLMResponse:
        if not self._client:
            raise RuntimeError(
                "ANTHROPIC_API_KEY no configurada. Definila en .env (ver .env.example)."
            )

        # El system prompt de Snarf (FOUNDATION+CONSTITUTION+CHARACTER) es
        # idéntico en cada llamada, en todas las conversaciones — un caso de
        # cacheo casi perfecto. cache_control en el bloque de system cachea
        # también las tools que lo preceden (mismo orden de renderizado:
        # tools -> system -> messages), y no cuesta nada si el prompt es
        # demasiado corto para cachear (simplemente no cachea, sin error).
        # TTL extendido (1h en vez del default de 5 min): Snarf llama a la
        # API directa, no la suscripción de Claude, así que sin esto el
        # cache expira rápido entre usos espaciados del fundador.
        cached_system = [
            {"type": "text", "text": system, "cache_control": {"type": "ephemeral", "ttl": CACHE_TTL}}
        ]

        conversation = list(messages)
        for _ in range(MAX_TOOL_ROUNDS):
            call_messages = list(conversation)
            if call_messages:
                # Segundo punto de cacheo: el historial de la conversación
                # (reconstruido igual en cada turno desde EpisodicMemory) y,
                # dentro de una misma llamada, cada ronda del loop de
                # herramientas — hoy se reprocesaba entero y sin cachear.
                call_messages[-1] = _mark_cache_breakpoint(call_messages[-1])
            kwargs = dict(model=self.model, max_tokens=MAX_OUTPUT_TOKENS, system=cached_system, messages=call_messages)
            if tools:
                kwargs["tools"] = tools
            response = self._client.messages.create(**kwargs)
            self._record_usage(response)

            if response.stop_reason == "tool_use" and tool_handler:
                conversation.append({"role": "assistant", "content": response.content})
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = tool_handler(block.name, block.input)
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": json.dumps(result, ensure_ascii=False, default=str),
                            }
                        )
                conversation.append({"role": "user", "content": tool_results})
                continue

            text = "".join(block.text for block in response.content if block.type == "text")
            if response.stop_reason == "max_tokens":
                # El corte pudo haber pasado antes de llegar al marcador de habla
                # (---HABLA---) — split_speech simplemente no lo va a encontrar y
                # cae al fallback mecánico sobre el texto ya truncado, que sigue
                # siendo una degradación razonable.
                text += "\n\n*(respuesta truncada: llegó al límite de longitud de una respuesta)*"
            return split_speech(text)

        timeout_text = "[demasiadas consultas a herramientas, no llegué a una respuesta final]"
        return LLMResponse(text=timeout_text, speech=timeout_text)

    def _record_usage(self, response) -> None:
        usage = getattr(response, "usage", None)
        if usage is None:
            return
        usage_tracker.record_anthropic_call(
            self.model,
            getattr(usage, "input_tokens", 0) or 0,
            getattr(usage, "output_tokens", 0) or 0,
            getattr(usage, "cache_creation_input_tokens", 0) or 0,
            getattr(usage, "cache_read_input_tokens", 0) or 0,
        )
