import json
import os
import time
from pathlib import Path

import anthropic
import openai
from google.genai import errors as genai_errors

from snarf.capabilities.anthropic_llm import AnthropicLLM
from snarf.capabilities.gemini_llm import GeminiLLM
from snarf.capabilities.openai_compatible_llm import OpenAICompatibleLLM

ROUTING_PATH = Path("data/llm_routing.json")
# Registro trazable de cada fallback automático real (ver
# generate_with_fallback más abajo, ADR de esta ronda) — nunca se pisa, solo
# se agrega, mismo criterio que el resto de los logs JSONL del proyecto
# (activity_log/usage_log/events).
FALLBACK_LOG_PATH = Path("data/llm_fallback_log.jsonl")

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
    # Fase I, rama Productivity (ver plan de expansión) — mismo criterio de
    # gmail_digest: tarea acotada, modelo barato por default.
    "calendar_brief",
    # Fase I, rama Research — un rol de ruteo por modo (ResearchSpecialist,
    # una sola clase con 3 configs, ver snarf/specialists/research/mode.py).
    "research_deep_research",
    "research_trend_scan",
    "research_competitor_watch",
    # Fase I, rama Content — un rol de ruteo por modo (ContentSpecialist,
    # una sola clase con 3 configs, ver snarf/specialists/content/mode.py).
    "content_blog_post",
    "content_social_post",
    "content_newsletter",
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
    "calendar_brief": {"provider": "anthropic", "model": "claude-haiku-4-5"},
    "research_deep_research": {"provider": "anthropic", "model": "claude-sonnet-5"},
    "research_trend_scan": {"provider": "anthropic", "model": "claude-haiku-4-5"},
    "research_competitor_watch": {"provider": "anthropic", "model": "claude-haiku-4-5"},
    "content_blog_post": {"provider": "anthropic", "model": "claude-sonnet-5"},
    "content_social_post": {"provider": "anthropic", "model": "claude-haiku-4-5"},
    "content_newsletter": {"provider": "anthropic", "model": "claude-sonnet-5"},
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


def _build(provider: str, model: str):
    preset = PROVIDER_PRESETS[provider]
    if preset["capability"] == "anthropic":
        return AnthropicLLM(model=model)
    if preset["capability"] == "gemini":
        return GeminiLLM(model=model)
    return OpenAICompatibleLLM(model=model, base_url=preset["base_url"], api_key_env=preset["api_key_env"])


def build_llm(role: str):
    """Devuelve la Capacidad de LLM configurada para `role` (ver ROLES). El
    proveedor se elige por configuración persistida, nunca hardcodeado — así
    Snarf no queda atado a un solo proveedor de LLM."""
    entry = load_routing().get(role, DEFAULT_ROUTING[role])
    return _build(entry["provider"], entry["model"])


# --- Fallback automático entre proveedores (ADR de esta ronda) ------------
#
# Pedido real del fundador tras encontrarse el rol "dashboard_curator" roto
# por falta de crédito en Anthropic mientras "orchestrator" (ya cambiado a
# mano a xAI) seguía andando: que un fallo real de PROVEEDOR (crédito
# agotado, rate limit, credencial inválida, 5xx) reintente solo con otro
# proveedor disponible, en vez de mostrar el error crudo — que avise cuando
# pasa, y deje un registro trazable.
#
# A propósito NO es un reintento genérico ante cualquier excepción: un 400
# por una forma de request rota (bug real nuestro, ej. un tool_choice mal
# armado) no se arregla cambiando de proveedor — reintentar ahí solo
# demoraría la respuesta antes de mostrar el mismo error real. Se reintenta
# únicamente ante una excepción de status real del SDK del proveedor
# (`APIStatusError` de anthropic/openai, `APIError` de google-genai) con un
# código que es honestamente "culpa del proveedor, no del request":
#
#   400 — sí, incluido a propósito: así es como Anthropic devuelve
#         "credit balance is too low" (no hay un tipo de error dedicado para
#         eso en su SDK). Riesgo conocido y aceptado: un 400 real por bug
#         nuestro también dispara el intento con otros proveedores antes de
#         fallar — probablemente falle igual en todos (mismo request roto),
#         así que solo agrega latencia, nunca esconde el error real (la
#         excepción que se propaga al final si TODOS fallan es la del
#         intento ORIGINAL, la más informativa).
#   401/403 — credencial inválida/revocada para ESE proveedor puntual.
#   429 — rate limit.
#   500/502/503/504/529 — el proveedor tiene un problema real de su lado.
#
# Errores de conexión/timeout (sin status code, ej. la red cayó) NO
# disparan fallback en esta versión — alcance deliberadamente acotado al
# caso real reportado (el proveedor respondió con un error real), no a
# cualquier falla de red posible.
_PROVIDER_LEVEL_STATUS_CODES = {400, 401, 403, 429, 500, 502, 503, 504, 529}
_PROVIDER_STATUS_ERROR_TYPES = (anthropic.APIStatusError, openai.APIStatusError, genai_errors.APIError)

# Orden de intento cuando el proveedor configurado de un rol falla — mismo
# orden que ya venía usando el fundador a mano (Anthropic primero por
# calidad, xAI como alternativa barata ya probada en producción).
FALLBACK_ORDER = ("anthropic", "xai", "gemini", "openai", "groq_llama")

# drive_vision necesita un modelo con soporte real de imágenes — no hay
# confirmación de que xai/groq_llama lo tengan (ver investigación de esta
# ronda), así que ese rol usa una lista más chica y conservadora en vez del
# orden general: mejor un fallback más corto que arriesgar una descripción
# de imagen rota en un proveedor sin soporte real de visión.
VISION_FALLBACK_ORDER = ("anthropic", "gemini")

# Modelo a usar al caer a un proveedor nuevo por primera vez para un rol —
# mismo modelo "barato" que ya ofrece la interfaz de Configuración → LLM por
# rol para cada proveedor (ver LLM_PRESETS en web/index.html), nunca uno
# elegido al azar.
RECOMMENDED_MODEL = {
    "anthropic": "claude-haiku-4-5",
    "gemini": "gemini-3.1-flash-lite",
    "openai": "gpt-5",
    "xai": "grok-4-1-fast",
    "groq_llama": "llama-4-scout",
}


def _provider_error_status_code(exc: Exception) -> int | None:
    if not isinstance(exc, _PROVIDER_STATUS_ERROR_TYPES):
        return None
    # anthropic/openai exponen `.status_code`; google-genai expone `.code`
    # con el mismo significado (confirmado leyendo su SDK real).
    code = getattr(exc, "status_code", None)
    if code is None:
        code = getattr(exc, "code", None)
    return code if isinstance(code, int) else None


def is_provider_level_error(exc: Exception) -> bool:
    code = _provider_error_status_code(exc)
    return code is not None and code in _PROVIDER_LEVEL_STATUS_CODES


def _append_fallback_log(entry: dict) -> None:
    FALLBACK_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with FALLBACK_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def recent_fallback_events(n: int = 20, since: float | None = None) -> list[dict]:
    """Registro trazable de fallbacks reales — nunca inventa entradas, un
    archivo vacío o inexistente devuelve `[]` (mismo criterio que
    activity_log.recent/events.recent)."""
    if not FALLBACK_LOG_PATH.exists():
        return []
    content = FALLBACK_LOG_PATH.read_text(encoding="utf-8").strip()
    if not content:
        return []
    entries = [json.loads(line) for line in content.splitlines()]
    if since is not None:
        entries = [e for e in entries if e["timestamp"] > since]
    return entries[-n:]


def attempt_fallback(role: str, entry: dict, first_exc: Exception, **generate_kwargs):
    """Núcleo real del fallback, compartido por `_ResilientLLM.generate()` y
    por Orchestrator (para sus dos roles de instancia fija, ver
    handle()/generate_conversation_title() — no pueden usar `_ResilientLLM`
    ahí sin romper los tests que hoy hacen `monkeypatch.setattr(orchestrator
    ._llm, "_client"/"generate", ...)` reaching directo a la Capacidad
    concreta; esta función deja esa parte sin envolver y solo se llama
    explícitamente en el except).

    Si `first_exc` no es un error real de proveedor (ver
    is_provider_level_error), devuelve `(None, None)` sin tocar nada — el
    llamador decide qué hacer (típicamente re-propagar `first_exc` tal
    cual). Si SÍ lo es, prueba cada proveedor disponible en orden
    (FALLBACK_ORDER, o VISION_FALLBACK_ORDER si `role == "drive_vision"`) y
    devuelve `(response, new_entry)` del primero que funcione — ya persistido
    en data/llm_routing.json y registrado en FALLBACK_LOG_PATH. Si ninguno
    funciona, devuelve `(None, None)` — nunca inventa un éxito."""
    if not is_provider_level_error(first_exc):
        return None, None
    candidates = VISION_FALLBACK_ORDER if role == "drive_vision" else FALLBACK_ORDER
    available = set(available_providers())
    for provider in candidates:
        if provider == entry["provider"] or provider not in available:
            continue
        model = RECOMMENDED_MODEL[provider]
        try:
            response = _build(provider, model).generate(**generate_kwargs)
        except Exception:
            continue
        new_entry = {"provider": provider, "model": model}
        save_routing({**load_routing(), role: new_entry})
        _append_fallback_log(
            {"timestamp": time.time(), "role": role, "from": entry, "to": new_entry, "error": str(first_exc)[:300]}
        )
        return response, new_entry
    return None, None


class _ResilientLLM:
    """Envuelve el LLM real de un rol con el mismo contrato que cualquier
    Capacidad de LLM (`.available`, `.generate(**kwargs)`) — pero si
    `.generate()` falla con un error real de proveedor, reintenta sola con
    el siguiente proveedor disponible (ver attempt_fallback).

    Vive acá (snarf/runtime) porque necesita conocer el ruteo — el punto
    importante es que Capacidades/Especialistas (snarf/capabilities,
    snarf/specialists, snarf/knowledge) NUNCA importan este módulo
    directamente (deben ser reusables fuera de Snarf, ver
    test_capabilities_and_specialists_never_import_orchestrator_or_web_runtime):
    reciben esta clase ya armada a través del mismo `llm_factory` que
    siempre recibieron, sin saber que el fallback existe.

    Usada para los 4 roles resueltos vía factory (gmail_digest,
    drive_vision, project_summary, dashboard_curator) — los 2 roles de
    instancia fija de Orchestrator (orchestrator, conversation_title) NO
    pasan por acá (ver comentario en attempt_fallback): siguen siendo la
    Capacidad concreta sin envolver, porque muchos tests reales necesitan
    poder reemplazar `orchestrator._llm._client`/`.generate` directamente.

    Nunca inventa éxito: un error que no es de proveedor se propaga tal
    cual, sin reintentar; si TODOS los proveedores disponibles fallan, se
    propaga la excepción del intento ORIGINAL (la más informativa)."""

    def __init__(self, role: str):
        self._role = role
        self._entry = load_routing().get(role, DEFAULT_ROUTING[role])
        self._llm = _build(self._entry["provider"], self._entry["model"])

    @property
    def available(self) -> bool:
        return self._llm.available

    def generate(self, **generate_kwargs):
        try:
            return self._llm.generate(**generate_kwargs)
        except Exception as first_exc:
            response, new_entry = attempt_fallback(self._role, self._entry, first_exc, **generate_kwargs)
            if response is None:
                raise first_exc
            # Este mismo objeto sigue viviendo entre llamadas (guardado como
            # atributo fijo del Specialist dueño) — la próxima ya tiene que
            # usar el proveedor que funcionó.
            self._llm, self._entry = _build(new_entry["provider"], new_entry["model"]), new_entry
            return response


def build_resilient_llm(role: str) -> _ResilientLLM:
    """Como build_llm(role), pero el objeto devuelto reintenta solo con otro
    proveedor ante un fallo real de proveedor (ver _ResilientLLM) — este es
    el que hay que usar en toda la capa de wiring real (Orchestrator/app.py)
    en vez de build_llm a secas. build_llm queda tal cual para quien
    necesite la Capacidad concreta sin el envoltorio (ej. los tests de
    test_llm_routing.py que ya verifican isinstance contra las Capacidades
    reales)."""
    return _ResilientLLM(role)
