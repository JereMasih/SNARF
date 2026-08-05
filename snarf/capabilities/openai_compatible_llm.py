import json
import os
from typing import Callable

from snarf.capabilities.anthropic_llm import MAX_CONTINUATIONS, MAX_OUTPUT_TOKENS, LLMResponse, split_speech
from snarf.capabilities.base import Capability
from snarf.telemetry import detail, usage_tracker

MAX_TOOL_ROUNDS = 5
# Runtimes locales (ej. mlx_lm.server, el server OpenAI-compatible de MLX —
# ver llm_routing.PROVIDER_PRESETS) no exigen ninguna key real. El cliente
# openai.OpenAI() sigue necesitando *algo* no-vacío en api_key para
# construirse; este valor nunca viaja a ningún lado fuera de la Mac.
_LOCAL_DUMMY_API_KEY = "not-needed"

# El default de la SDK de OpenAI es 10 minutos — razonable contra un
# proveedor cloud real, pero inaceptable contra un modelo local corriendo en
# esta misma Mac: dejar esperar hasta 10 minutos antes de caer al fallback
# deja el chat "colgado" sin ninguna señal. Un timeout corto hace que falle
# rápido y dispare el fallback a Anthropic/xAI (ver
# llm_routing.is_provider_level_error, que ya trata openai.APITimeoutError
# como error de proveedor — es subclase de APIConnectionError) en vez de
# dejar al fundador esperando en silencio.
#
# 150s, no 90s: bug real encontrado en vivo esta ronda — con 90s, la
# PRIMERA request real contra el prefijo en frío del prompt completo de
# Snarf (system + 88 tools, ~15.630 tokens) tarda ~90-105s incluso con el
# modelo "pesado" liviano (Qwen3-8B) — un pelo MÁS que el timeout. Eso
# disparaba el fallback automático (que sí persiste el cambio en
# data/llm_routing.json, ver attempt_fallback) apenas arrancaba el server
# MLX, revirtiendo `orchestrator` a otro proveedor en silencio antes de que
# el prefijo llegara a cachearse — exactamente la peor combinación posible
# con los LaunchAgents 24/7 (ver ADR de esta ronda), que garantizan que la
# primera request real de cada arranque SIEMPRE sea en frío. 150s da margen
# real sobre el peor caso medido sin dejar de fallar mucho más rápido que
# el default de 10 minutos de la SDK.
LOCAL_TIMEOUT_SECONDS = 150.0

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

    def __init__(self, model: str, base_url: str | None = None, api_key_env: str = "OPENAI_API_KEY", local: bool = False):
        self.model = model
        self._api_key_env = api_key_env
        self._vendor = _VENDOR_BY_API_KEY_ENV.get(api_key_env, "openai")
        self._local = local
        self._api_key = _LOCAL_DUMMY_API_KEY if local else os.environ.get(api_key_env)
        self._client = None
        if self._api_key:
            import openai

            kwargs = {"api_key": self._api_key}
            if base_url:
                kwargs["base_url"] = base_url
            if local:
                kwargs["timeout"] = LOCAL_TIMEOUT_SECONDS
                # El default de la SDK (max_retries=2) reintenta la misma
                # request en silencio ante un timeout — contra un proveedor
                # local eso convierte los 90s de LOCAL_TIMEOUT_SECONDS en
                # hasta 270s reales antes de disparar el fallback (medido en
                # vivo esta ronda: un request que tardó justo más de 90s
                # generó un segundo request idéntico visible en el log del
                # server MLX). El propio fallback a Anthropic ya es el
                # mecanismo de reintento real acá — la SDK no debería
                # duplicarlo por debajo sin que nadie lo pida.
                kwargs["max_retries"] = 0
            self._client = openai.OpenAI(**kwargs)

    @property
    def available(self) -> bool:
        return self._client is not None

    def warmup(self) -> None:
        if not self._client:
            return
        try:
            self._client.chat.completions.create(
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
            # Algunos modelos locales "thinking" (ej. Qwen3.5, vía
            # mlx_lm.server) devuelven el razonamiento en un campo separado
            # `reasoning`, fuera de `content` — no está en el schema estándar
            # de OpenAI, así que se lee con getattr (ausente para cualquier
            # proveedor/modelo que no lo exponga, incluida la mayoría).
            thinking = getattr(choice.message, "reasoning", None) or ""
            continuations = 0
            while choice.finish_reason == "length" and continuations < MAX_CONTINUATIONS:
                # Misma red de seguridad que AnthropicLLM.generate(): en vez
                # de aceptar el corte, pedirle al modelo que continúe exacto
                # donde quedó y concatenar.
                continuations += 1
                chat_messages.append({"role": "assistant", "content": text})
                chat_messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Tu respuesta anterior se cortó por el límite de longitud. "
                            "Continuá exactamente desde donde cortaste — no repitas nada "
                            "de lo ya escrito, no agregues una introducción nueva."
                        ),
                    }
                )
                kwargs = dict(model=self.model, max_tokens=MAX_OUTPUT_TOKENS, messages=chat_messages)
                response = self._client.chat.completions.create(**kwargs)
                self._record_usage(response)
                choice = response.choices[0]
                text += choice.message.content or ""
                thinking += getattr(choice.message, "reasoning", None) or ""

            if choice.finish_reason == "length":
                text += "\n\n*(respuesta truncada: llegó al límite de longitud incluso después de continuar)*"
            return split_speech(text, thinking=thinking or None)

        timeout_text = "[demasiadas consultas a herramientas, no llegué a una respuesta final]"
        return LLMResponse(text=timeout_text, speech=timeout_text)

    def _record_usage(self, response) -> None:
        usage = getattr(response, "usage", None)
        if usage is None:
            return
        text = ""
        choices = getattr(response, "choices", None) or []
        if choices and getattr(choices[0], "message", None):
            text = choices[0].message.content or ""
        usage_tracker.record_generic_llm_call(
            self._vendor,
            self.model,
            getattr(usage, "prompt_tokens", 0) or 0,
            getattr(usage, "completion_tokens", 0) or 0,
            detalle=detail.truncate_detalle(text),
        )
