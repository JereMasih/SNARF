import json
import os
from pathlib import Path

from snarf.capabilities.anthropic_llm import AnthropicLLM
from snarf.capabilities.gemini_llm import GeminiLLM
from snarf.capabilities.openai_compatible_llm import OpenAICompatibleLLM

ROUTING_PATH = Path("data/llm_routing.json")

# Roles reales del sistema (ver Orchestrator.__init__) — cada uno pedía su
# propia AnthropicLLM(model=...) instanciada a mano. Ahora piden su Capacidad
# vía build_llm(role), que resuelve a qué proveedor/modelo corresponde según
# esta configuración persistida — así se puede "decidir qué modelo usar en
# cada cosa" desde la propia interfaz, sin editar código (pedido explícito
# del fundador tras encontrar, con precios reales, que ningún proveedor
# ofrece hoy "tan inteligente como Sonnet" y "notablemente más barato" a la
# vez — ver ADR de esta ronda).
ROLES = (
    "orchestrator",
    "gmail_digest",
    "drive_vision",
    "project_summary",
    "conversation_title",
    "dashboard_curator",
    # Inteligencia Ejecutiva (ver COGNITION.md, ADR 0094/0098) — 7 roles
    # asesores, cada uno con su propio rol de ruteo (igual criterio que
    # gmail_digest/dashboard_curator: tarea acotada, modelo barato por
    # default, elegible aparte desde la interfaz sin tocar código).
    "executive_cto",
    "executive_coo",
    "executive_research",
    "executive_ceo",
    "executive_cfo",
    "executive_cmo",
    "executive_creative",
)

# Default = EXACTAMENTE el comportamiento de siempre (ver GMAIL_DIGEST_MODEL/
# DRIVE_VISION_MODEL en orchestrator.py) — cero cambio hasta que el fundador
# elija otra cosa explícitamente.
DEFAULT_ROUTING = {
    "orchestrator": {"provider": "anthropic", "model": "claude-sonnet-5"},
    "gmail_digest": {"provider": "anthropic", "model": "claude-haiku-4-5"},
    "drive_vision": {"provider": "anthropic", "model": "claude-haiku-4-5"},
    "project_summary": {"provider": "anthropic", "model": "claude-haiku-4-5"},
    "conversation_title": {"provider": "anthropic", "model": "claude-haiku-4-5"},
    "dashboard_curator": {"provider": "anthropic", "model": "claude-haiku-4-5"},
    "executive_cto": {"provider": "anthropic", "model": "claude-haiku-4-5"},
    "executive_coo": {"provider": "anthropic", "model": "claude-haiku-4-5"},
    "executive_research": {"provider": "anthropic", "model": "claude-haiku-4-5"},
    "executive_ceo": {"provider": "anthropic", "model": "claude-haiku-4-5"},
    "executive_cfo": {"provider": "anthropic", "model": "claude-haiku-4-5"},
    "executive_cmo": {"provider": "anthropic", "model": "claude-haiku-4-5"},
    "executive_creative": {"provider": "anthropic", "model": "claude-haiku-4-5"},
}

# Cada proveedor mapea a una de las 3 Capacidades reales. xai/groq_llama
# reusan OpenAICompatibleLLM (su API es compatible con el formato de OpenAI,
# ver investigación real de esta ronda) — solo cambia base_url/api_key_env,
# no hace falta una clase por proveedor. groq_llama reusa el mismo
# GROQ_API_KEY que ya existe para STT, sin credencial nueva.
PROVIDER_PRESETS = {
    "anthropic": {"capability": "anthropic"},
    "gemini": {"capability": "gemini"},
    "openai": {"capability": "openai_compatible", "base_url": None, "api_key_env": "OPENAI_API_KEY"},
    "xai": {"capability": "openai_compatible", "base_url": "https://api.x.ai/v1", "api_key_env": "XAI_API_KEY"},
    "groq_llama": {
        "capability": "openai_compatible",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key_env": "GROQ_API_KEY",
    },
}


def _normalize(raw: dict) -> dict:
    routing = {}
    for role in ROLES:
        entry = raw.get(role) if isinstance(raw, dict) else None
        if (
            isinstance(entry, dict)
            and entry.get("provider") in PROVIDER_PRESETS
            and isinstance(entry.get("model"), str)
            and entry["model"]
        ):
            routing[role] = {"provider": entry["provider"], "model": entry["model"]}
        else:
            routing[role] = dict(DEFAULT_ROUTING[role])
    return routing


def load_routing() -> dict:
    if not ROUTING_PATH.exists():
        return dict(DEFAULT_ROUTING)
    return _normalize(json.loads(ROUTING_PATH.read_text(encoding="utf-8")))


def save_routing(raw: dict) -> dict:
    routing = _normalize(raw)
    ROUTING_PATH.parent.mkdir(parents=True, exist_ok=True)
    ROUTING_PATH.write_text(json.dumps(routing, ensure_ascii=False, indent=2), encoding="utf-8")
    return routing


_PROVIDER_API_KEY_ENV = {
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "xai": "XAI_API_KEY",
    "groq_llama": "GROQ_API_KEY",
}


def available_providers() -> list[str]:
    """Proveedores con una credencial real cargada AHORA MISMO — para que la
    interfaz nunca ofrezca elegir un proveedor que en la práctica todavía no
    va a funcionar."""
    return [p for p, env_var in _PROVIDER_API_KEY_ENV.items() if os.environ.get(env_var)]


def build_llm(role: str):
    """Devuelve la Capacidad de LLM configurada para `role` (ver ROLES). El
    proveedor se elige por configuración persistida, nunca hardcodeado — así
    Snarf no queda atado a un solo proveedor de LLM."""
    entry = load_routing().get(role, DEFAULT_ROUTING[role])
    preset = PROVIDER_PRESETS[entry["provider"]]
    if preset["capability"] == "anthropic":
        return AnthropicLLM(model=entry["model"])
    if preset["capability"] == "gemini":
        return GeminiLLM(model=entry["model"])
    return OpenAICompatibleLLM(model=entry["model"], base_url=preset["base_url"], api_key_env=preset["api_key_env"])
