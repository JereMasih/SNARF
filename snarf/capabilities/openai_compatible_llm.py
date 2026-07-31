import json
import os
from typing import Callable

from snarf.capabilities.anthropic_llm import MAX_OUTPUT_TOKENS, LLMResponse, split_speech
from snarf.capabilities.base import Capability
from snarf.telemetry import usage_tracker

MAX_TOOL_ROUNDS = 5

# xAI (Grok) y Llama vía Groq exponen la API clásica de Chat Completions de
# OpenAI (no la Responses API, que es propietaria de OpenAI) — la misma
# clase cubre los tres, solo cambia base_url/api_key_env/model. Investigado
# con búsqueda web real el 2026-07-30 (ver ADR de esta ronda), no asumido.
_VENDOR_BY_API_KEY_ENV = {
    "OPENAI_API_KEY": "openai",
    "XAI_API_KEY": "xai",
    "GROQ_API_KEY": "groq_llama",
}


def _translate_content(content) -> str | list[dict]:
    """Los mensajes que arma Orchestrator.handle() son siempre texto plano;
    el único caso con bloques es la extracción por visión de Drive (imagen +
    texto, formato nativo de Anthropic) — se traduce al formato de OpenAI.
    Nunca llegan bloques tool_result desde afuera: esos los arma el propio
    loop de esta clase, no Orchestrator."""
    if isinstance(content, str):
        return content
    parts = []
    for block in content:
        if block.get("type") == "text":
            parts.append({"type": "text", "text": block["text"]})
        elif block.get("type") == "image":
            source = block["source"]
            parts.append(
                {"type": "image_url", "image_url": {"url": f"data:{source['media_type']};base64,{source['data']}"}}
            )
    return parts


def _translate_tools(tools: list[dict]) -> list[dict]:
    return [
        {"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}}
        for t in tools
    ]


class OpenAICompatibleLLM(Capability):
    """Capacidad genérica para cualquier proveedor con API compatible con el
    formato clásico de OpenAI (Chat Completions): OpenAI real, xAI/Grok, y
    Llama vía Groq/Together/Fireworks. Misma interfaz pública que
    AnthropicLLM (generate/available/model) — Orchestrator no necesita saber
    con qué proveedor está hablando."""

    name = "openai_compatible_llm"

    def __init__(self, model: str, base_url: str | None = None, api_key_env: str = "OPENAI_API_KEY"):
        self.model = model
        self._api_key_env = api_key_env
        self._vendor = _VENDOR_BY_API_KEY_ENV.get(api_key_env, "openai")
        self._api_key = os.environ.get(api_key_env)
        self._client = None
        if self._api_key:
            import openai

            kwargs = {"api_key": self._api_key}
            if base_url:
                kwargs["base_url"] = base_url
            self._client = openai.OpenAI(**kwargs)

    @property
    def available(self) -> bool:
        return self._client is not None

    def generate(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        tool_handler: Callable[[str, dict], object] | None = None,
    ) -> LLMResponse:
        if not self._client:
            raise RuntimeError(f"{self._api_key_env} no configurada. Definila en .env (ver .env.example).")

        chat_messages = [{"role": "system", "content": system}]
        for m in messages:
            chat_messages.append({"role": m["role"], "content": _translate_content(m["content"])})
        chat_tools = _translate_tools(tools) if tools else None

        for _ in range(MAX_TOOL_ROUNDS):
            kwargs = dict(model=self.model, max_tokens=MAX_OUTPUT_TOKENS, messages=chat_messages)
            if chat_tools:
                kwargs["tools"] = chat_tools
            response = self._client.chat.completions.create(**kwargs)
            self._record_usage(response)
            choice = response.choices[0]

            if choice.finish_reason == "tool_calls" and tool_handler and choice.message.tool_calls:
                message = choice.message
                chat_messages.append(
                    {
                        "role": "assistant",
                        "content": message.content,
                        "tool_calls": [tc.model_dump() for tc in message.tool_calls],
                    }
                )
                for tc in message.tool_calls:
                    args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                    result = tool_handler(tc.function.name, args)
                    chat_messages.append(
                        {"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result, ensure_ascii=False, default=str)}
                    )
                continue

            text = choice.message.content or ""
            if choice.finish_reason == "length":
                text += "\n\n*(respuesta truncada: llegó al límite de longitud de una respuesta)*"
            return split_speech(text)

        timeout_text = "[demasiadas consultas a herramientas, no llegué a una respuesta final]"
        return LLMResponse(text=timeout_text, speech=timeout_text)

    def _record_usage(self, response) -> None:
        usage = getattr(response, "usage", None)
        if usage is None:
            return
        usage_tracker.record_generic_llm_call(
            self._vendor, self.model, getattr(usage, "prompt_tokens", 0) or 0, getattr(usage, "completion_tokens", 0) or 0
        )
