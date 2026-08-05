"""Único mecanismo genuinamente nuevo de la Fase F (ver HARNESS.md — casi
todo lo demás pedido ya existía, repartido sin nombre común, y este
documento se limita a nombrarlo).

compare() corre el mismo prompt contra N proveedores reales de
snarf/runtime/llm_routing.py y devuelve las N respuestas reales para
inspección manual del fundador — sin juez-LLM automático, sin selección de
ganador automática (ver HARNESS.md, "Qué NO se construye en esta ronda")."""

from dataclasses import dataclass

from snarf.capabilities.anthropic_llm import AnthropicLLM, LLMResponse
from snarf.capabilities.gemini_llm import GeminiLLM
from snarf.capabilities.openai_compatible_llm import OpenAICompatibleLLM
from snarf.runtime.llm_routing import PROVIDER_PRESETS


@dataclass(frozen=True)
class ComparisonResult:
    provider: str
    model: str
    response: LLMResponse | None
    error: str | None = None


def _build_provider(provider: str, model: str):
    preset = PROVIDER_PRESETS[provider]
    if preset["capability"] == "anthropic":
        return AnthropicLLM(model=model)
    if preset["capability"] == "gemini":
        return GeminiLLM(model=model)
    return OpenAICompatibleLLM(model=model, base_url=preset["base_url"], api_key_env=preset["api_key_env"])


def compare(system: str, messages: list[dict], providers: dict[str, str]) -> list[ComparisonResult]:
    """`providers`: {provider: model} — el fundador (o Snarf, a pedido
    explícito) elige a propósito qué proveedores/modelos concretos quiere
    comparar, nunca un default adivinado; ver PROVIDER_PRESETS para los
    proveedores reales disponibles. Un proveedor sin credencial real o que
    falla queda reflejado en su propia entrada (`error`), nunca oculta el
    resultado de los demás."""
    results = []
    for provider, model in providers.items():
        llm = _build_provider(provider, model)
        if not llm.available:
            results.append(
                ComparisonResult(provider=provider, model=model, response=None, error="sin credencial real configurada")
            )
            continue
        try:
            response = llm.generate(system=system, messages=messages)
            results.append(ComparisonResult(provider=provider, model=model, response=response))
        except Exception as exc:
            results.append(ComparisonResult(provider=provider, model=model, response=None, error=str(exc)))
    return results
