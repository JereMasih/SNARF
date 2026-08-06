import json
import os
import time
from types import SimpleNamespace
from typing import Callable

from snarf.capabilities.anthropic_llm import MAX_CONTINUATIONS, MAX_OUTPUT_TOKENS, LLMResponse, split_speech
from snarf.capabilities.base import Capability
from snarf.telemetry import detail, usage_tracker

MAX_TOOL_ROUNDS = 5
# Default correcto para el chat interactivo (latencia real importa ahí) —
# generate() acepta max_tool_rounds como parámetro (mismo default acá) para
# que un uso de background sin restricción de latencia (ej.
# snarf/capabilities/local_code_writer.py, que corre una construcción real
# de la Skill Factory tras una confirmación explícita) pueda pedir un
# presupuesto de rondas mayor sin tocar este default global.
#
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
# 240s, no 150s: el rol orchestrator (con tool-calling real de punta a
# punta, varias rondas de herramientas en un turno complejo) seguía cayendo
# a fallback en vivo con 150s incluso con el server ya caliente — no por
# estar colgado, sino por estar genuinamente ocupado generando. Ver también
# streaming abajo: con `stream=True` este timeout pasa a ser de INACTIVIDAD
# entre chunks (httpx corta si no llega NINGÚN byte en ese lapso), no de
# duración total — una generación lenta pero que sigue progresando ya no
# choca contra este número, solo un cuelgue real lo hace. 240s queda como
# red de seguridad adicional sobre ese mecanismo, no como el límite
# principal.
LOCAL_TIMEOUT_SECONDS = 240.0

# Tope real de tamaño de prompt antes de mandarlo a un proveedor LOCAL (ver
# LocalPromptTooLargeError más abajo) — nunca se aplica a un proveedor cloud
# (esos no comparten la memoria de Metal de esta Mac con el resto del
# sistema). Basado en números reales medidos en esta misma sesión, no
# estimados: el system+tools del rol orchestrator solo ya son ~16.000
# caracteres/~15.630 tokens (medido en vivo, ver comentario de
# MLX_LOCAL_BASE_URL en llm_routing.py) — eso funciona sin problema en cada
# request normal. Lo que SÍ tumbó el server MLX local con un crash real de
# Metal (out-of-memory) fue un prompt de 20.804 tokens combinado con otros
# requests concurrentes (ADR 0128, incidente original) y, de nuevo el mismo
# día de esta ronda, un prompt de 82.284 tokens en un único request (mismo
# error real de Metal, misma falla de limpieza — ver ADR de esta ronda).
# 60.000 caracteres da margen real para el uso normal (system+tools más un
# historial de conversación cargado) sin acercarse a ninguna de las dos
# zonas ya confirmadas como peligrosas.
MAX_LOCAL_PROMPT_CHARS = 60000


class LocalPromptTooLargeError(RuntimeError):
    """El prompt total (system + mensajes, en cualquier ronda del loop de
    herramientas) supera MAX_LOCAL_PROMPT_CHARS para un proveedor local —
    nunca se intenta la llamada real. Un prompt de este tamaño es la causa
    confirmada de un crash real de Metal (out-of-memory) en el server MLX
    local, con fuga de memoria real en la limpieza posterior (ver ADR de
    esta ronda) — más vale un error claro acá que arriesgar tumbar el
    server que atiende a TODOS los roles locales. Reconocida como
    fallback-worthy en llm_routing.is_provider_level_error(): un prompt
    demasiado grande para el hardware local puede seguir siendo viable en
    un proveedor cloud con más memoria real disponible."""

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


class _StreamedToolCall:
    """Mismo shape que un tool_call real no-streaming (`.id`,
    `.function.name`, `.function.arguments`, `.model_dump()`) — reconstruido
    acumulando los deltas de `_consume_stream`, para que el resto de
    `generate()` no tenga que distinguir de dónde vino."""

    def __init__(self, id: str, name: str, arguments: str):
        self.id = id
        self.function = SimpleNamespace(name=name, arguments=arguments)

    def model_dump(self) -> dict:
        return {"id": self.id, "type": "function", "function": {"name": self.function.name, "arguments": self.function.arguments}}


def _consume_stream(stream):
    """Recorre un stream real de chunks (`stream=True`) y devuelve
    `(content, reasoning, tool_calls, finish_reason, usage)` con la misma
    forma que leer `choice.message`/`choice.finish_reason` de una respuesta
    no-streaming — mlx_lm.server (confirmado en vivo, 2026-08-05) manda los
    argumentos de cada tool_call completos en un solo delta por índice, pero
    esto igual los acumula fragmento a fragmento por si algún proveedor los
    parte de verdad (así es como streaming de tool-calls funciona en la API
    real de OpenAI). El punto real de esto no es la acumulación en sí — es
    que iterar el stream hace que el timeout de httpx (LOCAL_TIMEOUT_SECONDS)
    pase a medir inactividad ENTRE chunks en vez de la duración total de la
    generación (ver comentario ahí)."""
    content = ""
    reasoning = ""
    tool_calls_by_index: dict[int, dict] = {}
    finish_reason = None
    usage = None
    for chunk in stream:
        if getattr(chunk, "usage", None) is not None:
            usage = chunk.usage
        if not chunk.choices:
            continue
        choice = chunk.choices[0]
        if choice.finish_reason:
            finish_reason = choice.finish_reason
        delta = choice.delta
        if delta.content:
            content += delta.content
        reasoning_piece = getattr(delta, "reasoning", None)
        if reasoning_piece:
            reasoning += reasoning_piece
        if delta.tool_calls:
            for tc_delta in delta.tool_calls:
                entry = tool_calls_by_index.setdefault(tc_delta.index, {"id": None, "name": None, "arguments": ""})
                if tc_delta.id:
                    entry["id"] = tc_delta.id
                if tc_delta.function:
                    if tc_delta.function.name:
                        entry["name"] = tc_delta.function.name
                    if tc_delta.function.arguments:
                        entry["arguments"] += tc_delta.function.arguments
    tool_calls = [
        _StreamedToolCall(entry["id"], entry["name"], entry["arguments"])
        for _, entry in sorted(tool_calls_by_index.items())
    ] or None
    return content, reasoning, tool_calls, finish_reason, usage


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

    def _complete_once(self, kwargs: dict):
        """Una sola llamada real al proveedor. Local usa streaming — el
        timeout de httpx (LOCAL_TIMEOUT_SECONDS) pasa a medir inactividad
        ENTRE chunks en vez de la duración total de la generación (un modelo
        lento pero que sigue progresando ya no choca contra el límite, solo
        un cuelgue real lo hace); cloud sigue sin streaming, sin motivo real
        para tocar un camino ya probado en producción. Devuelve
        `(content, reasoning, tool_calls, finish_reason)` — mismo shape para
        los dos casos, el resto de generate() no necesita saber cuál fue."""
        start = time.monotonic()
        if self._local:
            stream = self._client.chat.completions.create(**kwargs, stream=True, stream_options={"include_usage": True})
            content, reasoning, tool_calls, finish_reason, usage = _consume_stream(stream)
            self._record_usage_from_parts(usage, content, (time.monotonic() - start) * 1000)
            return content, reasoning, tool_calls, finish_reason
        response = self._client.chat.completions.create(**kwargs)
        self._record_usage(response, (time.monotonic() - start) * 1000)
        choice = response.choices[0]
        # Algunos modelos locales "thinking" (ej. Qwen3.5, vía mlx_lm.server)
        # devuelven el razonamiento en un campo separado `reasoning`, fuera
        # del schema estándar de OpenAI — se lee con getattr (ausente para
        # cualquier proveedor/modelo que no lo exponga, incluida la mayoría).
        reasoning = getattr(choice.message, "reasoning", None) or ""
        return choice.message.content, reasoning, choice.message.tool_calls, choice.finish_reason

    def generate(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        tool_handler: Callable[[str, dict], object] | None = None,
        max_tool_rounds: int = MAX_TOOL_ROUNDS,
    ) -> LLMResponse:
        if not self._client:
            raise RuntimeError(f"{self._api_key_env} no configurada. Definila en .env (ver .env.example).")

        chat_messages = [{"role": "system", "content": system}]
        for m in messages:
            chat_messages.append({"role": m["role"], "content": _translate_content(m["content"])})
        chat_tools = _translate_tools(tools) if tools else None

        for _ in range(max_tool_rounds):
            if self._local:
                # Recalculado en CADA ronda, no solo antes del loop: un
                # resultado de herramienta grande puede hacer crecer
                # chat_messages a mitad de un turno (ver docstring de
                # LocalPromptTooLargeError) — el mismo riesgo real que un
                # prompt inicial gigante.
                total_chars = sum(len(str(m.get("content", ""))) for m in chat_messages)
                if total_chars > MAX_LOCAL_PROMPT_CHARS:
                    raise LocalPromptTooLargeError(
                        f"El prompt total ({total_chars} caracteres) supera el tope seguro para un "
                        f"proveedor local ({MAX_LOCAL_PROMPT_CHARS}) — ver ADR de esta ronda."
                    )
            kwargs = dict(model=self.model, max_tokens=MAX_OUTPUT_TOKENS, messages=chat_messages)
            if chat_tools:
                kwargs["tools"] = chat_tools
            content, reasoning, tool_calls, finish_reason = self._complete_once(kwargs)

            if finish_reason == "tool_calls" and tool_handler and tool_calls:
                chat_messages.append(
                    {
                        "role": "assistant",
                        "content": content,
                        "tool_calls": [tc.model_dump() for tc in tool_calls],
                    }
                )
                for tc in tool_calls:
                    args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                    result = tool_handler(tc.function.name, args)
                    chat_messages.append(
                        {"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result, ensure_ascii=False, default=str)}
                    )
                continue

            text = content or ""
            thinking = reasoning or ""
            continuations = 0
            while finish_reason == "length" and continuations < MAX_CONTINUATIONS:
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
                cont_content, cont_reasoning, _, finish_reason = self._complete_once(kwargs)
                text += cont_content or ""
                thinking += cont_reasoning or ""

            if finish_reason == "length":
                text += "\n\n*(respuesta truncada: llegó al límite de longitud incluso después de continuar)*"
            return split_speech(text, thinking=thinking or None)

        timeout_text = "[demasiadas consultas a herramientas, no llegué a una respuesta final]"
        return LLMResponse(text=timeout_text, speech=timeout_text)

    def _record_usage(self, response, duration_ms: float | None = None) -> None:
        usage = getattr(response, "usage", None)
        text = ""
        choices = getattr(response, "choices", None) or []
        if choices and getattr(choices[0], "message", None):
            text = choices[0].message.content or ""
        self._record_usage_from_parts(usage, text, duration_ms)

    def _record_usage_from_parts(self, usage, text: str, duration_ms: float | None = None) -> None:
        if usage is None:
            return
        usage_tracker.record_generic_llm_call(
            self._vendor,
            self.model,
            getattr(usage, "prompt_tokens", 0) or 0,
            getattr(usage, "completion_tokens", 0) or 0,
            detalle=detail.truncate_detalle(text or ""),
            duration_ms=duration_ms,
        )
