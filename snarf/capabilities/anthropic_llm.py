import json
import os
from typing import Callable

from snarf.capabilities.base import Capability
from snarf.telemetry import usage_tracker

DEFAULT_MODEL = "claude-sonnet-5"
MAX_TOOL_ROUNDS = 5
MAX_OUTPUT_TOKENS = 4096
CACHE_TTL = "1h"


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
    ) -> str:
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
                text += "\n\n*(respuesta truncada: llegó al límite de longitud de una respuesta)*"
            return text

        return "[demasiadas consultas a herramientas, no llegué a una respuesta final]"

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
