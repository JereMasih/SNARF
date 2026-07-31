import base64
import os
from typing import Callable

from snarf.capabilities.anthropic_llm import MAX_OUTPUT_TOKENS, LLMResponse, split_speech
from snarf.capabilities.base import Capability
from snarf.telemetry import usage_tracker

MAX_TOOL_ROUNDS = 5

# Escrito contra la documentación real del SDK google-genai (investigación
# de esta ronda, ver ADR) para tool-calling manual multi-turno — a
# diferencia de openai_compatible_llm.py (formato clásico, muy estable
# desde hace años), esta es una integración nueva sin GEMINI_API_KEY
# configurada todavía: falta un smoke-test real antes de darla por 100%
# verificada (ver Consecuencias del ADR).


def _translate_content(content):
    from google.genai import types

    if isinstance(content, str):
        return [types.Part.from_text(text=content)]
    parts = []
    for block in content:
        if block.get("type") == "text":
            parts.append(types.Part.from_text(text=block["text"]))
        elif block.get("type") == "image":
            source = block["source"]
            parts.append(types.Part.from_bytes(data=base64.b64decode(source["data"]), mime_type=source["media_type"]))
    return parts


def _translate_tools(tools: list[dict]):
    from google.genai import types

    # parameters_json_schema acepta el dict de JSON schema tal cual — mismo
    # formato que ya usa input_schema del lado de Anthropic, sin traducir
    # nada a la clase Schema propia de Gemini (confirmado contra el SDK real
    # instalado, no asumido).
    declarations = [
        types.FunctionDeclaration(name=t["name"], description=t["description"], parameters_json_schema=t["input_schema"])
        for t in tools
    ]
    return [types.Tool(function_declarations=declarations)]


class GeminiLLM(Capability):
    """Misma interfaz pública que AnthropicLLM (generate/available/model)."""

    name = "gemini_llm"

    def __init__(self, model: str):
        self.model = model
        self._api_key = os.environ.get("GEMINI_API_KEY")
        self._client = None
        if self._api_key:
            from google import genai

            self._client = genai.Client(api_key=self._api_key)

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
            raise RuntimeError("GEMINI_API_KEY no configurada. Definila en .env (ver .env.example).")

        from google.genai import types

        contents = [
            types.Content(role="model" if m["role"] == "assistant" else "user", parts=_translate_content(m["content"]))
            for m in messages
        ]
        config_kwargs = {"system_instruction": system, "max_output_tokens": MAX_OUTPUT_TOKENS}
        if tools:
            config_kwargs["tools"] = _translate_tools(tools)

        for _ in range(MAX_TOOL_ROUNDS):
            response = self._client.models.generate_content(
                model=self.model, contents=contents, config=types.GenerateContentConfig(**config_kwargs)
            )
            self._record_usage(response)
            candidate = response.candidates[0]
            function_calls = [p.function_call for p in candidate.content.parts if p.function_call]

            if function_calls and tool_handler:
                contents.append(candidate.content)
                response_parts = []
                for fc in function_calls:
                    result = tool_handler(fc.name, dict(fc.args))
                    response_parts.append(types.Part.from_function_response(name=fc.name, response={"result": result}))
                contents.append(types.Content(role="user", parts=response_parts))
                continue

            text = "".join(p.text for p in candidate.content.parts if p.text)
            if candidate.finish_reason == "MAX_TOKENS":
                text += "\n\n*(respuesta truncada: llegó al límite de longitud de una respuesta)*"
            return split_speech(text)

        timeout_text = "[demasiadas consultas a herramientas, no llegué a una respuesta final]"
        return LLMResponse(text=timeout_text, speech=timeout_text)

    def _record_usage(self, response) -> None:
        usage = getattr(response, "usage_metadata", None)
        if usage is None:
            return
        usage_tracker.record_generic_llm_call(
            "gemini",
            self.model,
            getattr(usage, "prompt_token_count", 0) or 0,
            getattr(usage, "candidates_token_count", 0) or 0,
        )
