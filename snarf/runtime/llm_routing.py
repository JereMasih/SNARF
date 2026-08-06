import json
import os
import time
from pathlib import Path

import anthropic
import openai
from google.genai import errors as genai_errors

from snarf.capabilities.anthropic_llm import AnthropicLLM
from snarf.capabilities.gemini_llm import GeminiLLM
from snarf.capabilities.openai_compatible_llm import LocalPromptTooLargeError, OpenAICompatibleLLM
from snarf.telemetry import context

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
    # Resumen real de entradas de historial demasiado largas antes de
    # retransmitirlas al modelo principal (ver _capped_for_replay en
    # orchestrator.py) — reemplaza el corte duro por caracteres de antes,
    # que perdía contenido en silencio en vez de condensarlo fielmente.
    "history_compaction",
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
    # Rutina matutina real (gmail+calendar compuestos, ver ADR de esta
    # ronda) — mismo criterio que calendar_brief: dos llamadas LLM acotadas
    # (clasificar, sintetizar), modelo barato por default.
    "morning_routine",
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
    # Fase I, rama Sales.
    "sponsor_inbox_triage",
    # Fase I, rama Finance. monthly_pnl es determinístico (sin LLM), no
    # necesita rol de ruteo.
    "books_categorize",
    # Fase I, rama Agency.
    "client_status",
    # Motor de escritura de código de la Skill Factory (ver ADR 0095/0102/
    # 0130) — reemplaza al CLI real de Claude Code, que no tiene forma
    # soportada de apuntar a un modelo no-Claude. Mismo criterio que el
    # resto: elegible desde Configuración sin tocar código: si el default
    # rápido no alcanza para código real, cambiar acá a mlx_local/
    # mlx_local_mid (más capaces, más lentos) sin reiniciar el server.
    "skill_factory_writer",
)

# Definida acá arriba (no junto a MLX_LOCAL_FAST_BASE_URL más abajo, donde
# viviría por tema) porque DEFAULT_ROUTING la necesita al importar el módulo
# — Python ejecuta top-to-bottom, así que una referencia antes de la
# definición sería un NameError real, no solo un problema de estilo.
MLX_LOCAL_FAST_MODEL = os.environ.get("MLX_LOCAL_FAST_MODEL", "mlx-community/Qwen3-4B-Instruct-2507-4bit")

# Default = modelo rápido local en TODOS los roles (decisión explícita del
# fundador, 2026-08-05: "quiero poner de ahora en mas el modelo rapido local
# como defoult en todos lados, para probar todo absolutamente") — con una
# única excepción real: drive_vision necesita soporte real de imágenes
# (ver VISION_FALLBACK_ORDER más abajo) y Qwen3-4B-Instruct-2507 es
# texto-solo, así que ese rol se queda en un proveedor con visión real.
# Cambiar acá es solo el punto de partida para una instalación nueva /
# manifest.json borrado — `data/llm_routing.json` (vía PUT /llm-routing) es
# la fuente de verdad real en producción.
DEFAULT_ROUTING = {
    "orchestrator": {"provider": "mlx_local_fast", "model": MLX_LOCAL_FAST_MODEL},
    "gmail_digest": {"provider": "mlx_local_fast", "model": MLX_LOCAL_FAST_MODEL},
    "drive_vision": {"provider": "anthropic", "model": "claude-haiku-4-5"},
    "project_summary": {"provider": "mlx_local_fast", "model": MLX_LOCAL_FAST_MODEL},
    "conversation_title": {"provider": "mlx_local_fast", "model": MLX_LOCAL_FAST_MODEL},
    "dashboard_curator": {"provider": "mlx_local_fast", "model": MLX_LOCAL_FAST_MODEL},
    "history_compaction": {"provider": "mlx_local_fast", "model": MLX_LOCAL_FAST_MODEL},
    "executive_cto": {"provider": "mlx_local_fast", "model": MLX_LOCAL_FAST_MODEL},
    "executive_coo": {"provider": "mlx_local_fast", "model": MLX_LOCAL_FAST_MODEL},
    "executive_research": {"provider": "mlx_local_fast", "model": MLX_LOCAL_FAST_MODEL},
    "executive_ceo": {"provider": "mlx_local_fast", "model": MLX_LOCAL_FAST_MODEL},
    "executive_cfo": {"provider": "mlx_local_fast", "model": MLX_LOCAL_FAST_MODEL},
    "executive_cmo": {"provider": "mlx_local_fast", "model": MLX_LOCAL_FAST_MODEL},
    "executive_creative": {"provider": "mlx_local_fast", "model": MLX_LOCAL_FAST_MODEL},
    "calendar_brief": {"provider": "mlx_local_fast", "model": MLX_LOCAL_FAST_MODEL},
    "morning_routine": {"provider": "mlx_local_fast", "model": MLX_LOCAL_FAST_MODEL},
    "research_deep_research": {"provider": "mlx_local_fast", "model": MLX_LOCAL_FAST_MODEL},
    "research_trend_scan": {"provider": "mlx_local_fast", "model": MLX_LOCAL_FAST_MODEL},
    "research_competitor_watch": {"provider": "mlx_local_fast", "model": MLX_LOCAL_FAST_MODEL},
    "content_blog_post": {"provider": "mlx_local_fast", "model": MLX_LOCAL_FAST_MODEL},
    "content_social_post": {"provider": "mlx_local_fast", "model": MLX_LOCAL_FAST_MODEL},
    "content_newsletter": {"provider": "mlx_local_fast", "model": MLX_LOCAL_FAST_MODEL},
    "sponsor_inbox_triage": {"provider": "mlx_local_fast", "model": MLX_LOCAL_FAST_MODEL},
    "books_categorize": {"provider": "mlx_local_fast", "model": MLX_LOCAL_FAST_MODEL},
    "client_status": {"provider": "mlx_local_fast", "model": MLX_LOCAL_FAST_MODEL},
    "skill_factory_writer": {"provider": "mlx_local_fast", "model": MLX_LOCAL_FAST_MODEL},
}

# Cada proveedor mapea a una de las 3 Capacidades reales. xai/groq_llama
# reusan OpenAICompatibleLLM (su API es compatible con el formato de OpenAI,
# ver investigación real de esta ronda) — solo cambia base_url/api_key_env,
# no hace falta una clase por proveedor. groq_llama reusa el mismo
# GROQ_API_KEY que ya existe para STT, sin credencial nueva.
#
# mlx_local: cerebro local corriendo en esta misma Mac vía mlx_lm.server
# (nativo, sin Docker — Colima acá no tiene acceso a Metal/GPU, ver ADR de
# esta ronda), OpenAI-compatible igual que xai/groq_llama, así que reusa la
# misma Capacidad sin código nuevo — solo local=True (sin API key real, ver
# OpenAICompatibleLLM). El puerto/modelo reales se configuran por env var,
# nunca hardcodeados: distintas Macs pueden preferir otro puerto o modelo.
#
# Qwen3-8B (denso, 4-bit, ~4.6GB en disco) — no Qwen3-14B (probado primero,
# ~8.3GB): con el prompt real de Snarf (system prompt + 88 tools, ~16.000
# caracteres / 15.630 tokens) medido en vivo esta ronda, 14B y 8B tardan
# prácticamente lo mismo en "caliente" (14-29s vs 14.4s) una vez que
# mlx_lm.server cachea el prefijo system+tools — ese prefijo es idéntico en
# CADA request de CUALQUIER conversación, así que el costo de prefill real
# (~90-100s, dominado por ese prefijo fijo, confirmado con logs de progreso
# de mlx_lm.server) se paga UNA sola vez por arranque del server, no por
# mensaje. Como el tiempo de respuesta es equivalente, 8B gana por usar
# ~la mitad de memoria residente (~7GB en caliente con cache completo vs
# ~14GB de 14B) — este server corre 24/7 vía LaunchAgent (ver
# com.snarf.mlx-heavy.plist), así que esa diferencia de memoria se paga
# todo el día, todos los días, y el fundador la señaló como preocupación
# real (Activity Monitor mostrando 29.57GB usados con 14B+4B a la vez).
# Qwen3-30B-A3B (MoE, probado antes que 8B) directamente crasheó por falta
# de memoria de GPU (Metal) contra el mismo contexto real — sigue sin ser
# candidato viable acá.
MLX_LOCAL_BASE_URL = os.environ.get("MLX_LOCAL_BASE_URL", "http://localhost:8990/v1")
MLX_LOCAL_MODEL = os.environ.get("MLX_LOCAL_MODEL", "mlx-community/Qwen3-8B-4bit")

# mlx_local_fast: segundo server MLX local, en otro puerto, con un modelo
# bastante más chico (Qwen3-4B-Instruct-2507, 4-bit, ~2.3GB en disco —
# tamaño real confirmado vía huggingface_hub, no estimado) — pensado para
# roles baratos/acotados (ej. history_compaction, conversation_title,
# dashboard_curator) que hoy corren en Haiku: mismo espíritu ("tarea acotada,
# modelo barato"), pero sin costo de tokens ni límite de contexto de un
# proveedor pago. Corre en paralelo al server "pesado" (mlx_local) en un
# puerto distinto — ambos procesos conviven, cada rol elige el que le
# corresponde desde la interfaz igual que cualquier otro proveedor.
MLX_LOCAL_FAST_BASE_URL = os.environ.get("MLX_LOCAL_FAST_BASE_URL", "http://localhost:8991/v1")
# MLX_LOCAL_FAST_MODEL está definida más arriba, junto a DEFAULT_ROUTING.

# mlx_local_mid: tercer server MLX local (puerto 8992), Qwen3.5-9B — generación
# más nueva que el Qwen3-8B de mlx_local, tamaño en disco similar (~5GB),
# instalado 2026-08-05 para comparar "más parámetros, generación vieja" vs
# "menos parámetros, generación nueva" con evidencia real antes de fijar
# routing definitivo (ver ADR pendiente de esta ronda).
MLX_LOCAL_MID_BASE_URL = os.environ.get("MLX_LOCAL_MID_BASE_URL", "http://localhost:8992/v1")
MLX_LOCAL_MID_MODEL = os.environ.get("MLX_LOCAL_MID_MODEL", "mlx-community/Qwen3.5-9B-MLX-4bit")
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
    "mlx_local": {
        "capability": "openai_compatible",
        "base_url": MLX_LOCAL_BASE_URL,
        "api_key_env": None,
        "local": True,
    },
    "mlx_local_fast": {
        "capability": "openai_compatible",
        "base_url": MLX_LOCAL_FAST_BASE_URL,
        "api_key_env": None,
        "local": True,
    },
    "mlx_local_mid": {
        "capability": "openai_compatible",
        "base_url": MLX_LOCAL_MID_BASE_URL,
        "api_key_env": None,
        "local": True,
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
            normalized = {"provider": entry["provider"], "model": entry["model"]}
            # fallback_expires_at (ver attempt_fallback/maybe_revert_expired_
            # fallback más abajo) se preserva acá a propósito — es lo único
            # que distingue "esto quedó así por un fallback automático" de
            # "el fundador lo eligió a mano desde Configuración" (un PUT
            # manual nunca manda este campo, así que se pierde solo al
            # elegir a mano, que es exactamente el comportamiento correcto:
            # una elección real del fundador nunca debe revertirse sola).
            if isinstance(entry.get("fallback_expires_at"), (int, float)):
                normalized["fallback_expires_at"] = entry["fallback_expires_at"]
            routing[role] = normalized
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
    # mlx_local/mlx_local_fast no exigen ninguna credencial real (corren en
    # esta Mac) — ver PROVIDER_PRESETS. None acá significa "siempre
    # disponible", nunca "sin env var configurada".
    "mlx_local": None,
    "mlx_local_fast": None,
    "mlx_local_mid": None,
}


def available_providers() -> list[str]:
    """Proveedores con una credencial real cargada AHORA MISMO — para que la
    interfaz nunca ofrezca elegir un proveedor que en la práctica todavía no
    va a funcionar. Un proveedor sin env var asociada (mlx_local) no
    necesita ninguna credencial, así que siempre cuenta como disponible —
    su disponibilidad real depende de que el proceso local esté corriendo,
    no de una env var (ver el fallback ante error de conexión más abajo)."""
    return [p for p, env_var in _PROVIDER_API_KEY_ENV.items() if env_var is None or os.environ.get(env_var)]


def _build(provider: str, model: str):
    preset = PROVIDER_PRESETS[provider]
    if preset["capability"] == "anthropic":
        return AnthropicLLM(model=model)
    if preset["capability"] == "gemini":
        return GeminiLLM(model=model)
    return OpenAICompatibleLLM(
        model=model,
        base_url=preset["base_url"],
        api_key_env=preset.get("api_key_env") or "OPENAI_API_KEY",
        local=preset.get("local", False),
    )


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
# disparaban fallback en la versión original de esto — alcance
# deliberadamente acotado al caso real reportado entonces (el proveedor
# respondió con un error real), no a cualquier falla de red posible.
#
# Reabierto (ver ADR de esta ronda, migración del rol "orchestrator" a
# mlx_local): un proveedor LOCAL (mlx_lm.server corriendo en esta Mac) no
# devuelve nunca un error de status HTTP cuando está caído o todavía
# cargando el modelo — devuelve un error de CONEXIÓN (APIConnectionError),
# porque no hay nada escuchando en ese puerto. Sin este caso, el rol
# orchestrator se quedaba completamente mudo (sin respuesta y sin fallback)
# apenas el server local no estaba corriendo. Se agrega ACOTADO a errores de
# conexión (no cualquier excepción) — mismo criterio de honestidad que el
# resto de este mecanismo: nunca esconde un error real, solo reintenta con
# otro proveedor disponible antes de rendirse.
_PROVIDER_LEVEL_STATUS_CODES = {400, 401, 403, 429, 500, 502, 503, 504, 529}
_PROVIDER_STATUS_ERROR_TYPES = (anthropic.APIStatusError, openai.APIStatusError, genai_errors.APIError)
_PROVIDER_CONNECTION_ERROR_TYPES = (anthropic.APIConnectionError, openai.APIConnectionError)

# Cuánto tiempo se queda un rol en el proveedor de fallback antes de
# reintentar solo el proveedor local por defecto (ver
# maybe_revert_expired_fallback más abajo). Pedido real del fundador
# ("necesitamos... algo para que vuelva al modelo correcto después de
# resolver el requisito por timeout") — antes de esto, attempt_fallback
# persistía el cambio PARA SIEMPRE: un timeout puntual (server local
# ocupado, no caído) dejaba el rol en un proveedor pago indefinidamente,
# sin ninguna señal de que ya podía volver.
FALLBACK_COOLDOWN_SECONDS = 600

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
#
# groq_llama corregido esta ronda: "llama-4-scout" ya no existe en la API
# real de Groq (confirmado en vivo con GROQ_API_KEY real: 404 model_not_found
# — cualquier fallback a este proveedor fallaba siempre, en silencio, desde
# antes de esta ronda). "llama-3.3-70b-versatile" sí existe (confirmado
# contra client.models.list() real) — OJO: el tier on-demand real de esta
# cuenta tiene un límite de 12.000 tokens por minuto, y el prompt completo
# de Snarf (system+tools del rol orchestrator) ya son ~16.000 tokens por sí
# solo — este proveedor NUNCA es un fallback viable para el rol
# "orchestrator" tal cual está, pero sí lo es para el resto de los roles
# (prompts propios mucho más chicos, ej. gmail_digest/calendar_brief).
RECOMMENDED_MODEL = {
    "anthropic": "claude-haiku-4-5",
    "gemini": "gemini-3.1-flash-lite",
    "openai": "gpt-5",
    "xai": "grok-4-1-fast",
    "groq_llama": "llama-3.3-70b-versatile",
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
    # LocalPromptTooLargeError (openai_compatible_llm.py, ADR de esta
    # ronda): un prompt demasiado grande para el hardware local no es "el
    # request está roto" (a diferencia de un 400 real) — es honestamente
    # "este proveedor puntual no puede con esto ahora", el mismo criterio
    # que ya justifica reintentar con otro proveedor para el resto de los
    # casos de acá abajo.
    if isinstance(exc, (LocalPromptTooLargeError, *_PROVIDER_CONNECTION_ERROR_TYPES)):
        return True
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
        # fallback_expires_at marca esto como un fallback AUTOMÁTICO (ver
        # maybe_revert_expired_fallback) — vencido el cooldown, se reintenta
        # solo el proveedor local por defecto antes de seguir gastando
        # tokens pagos indefinidamente por un timeout que ya pasó.
        new_entry = {"provider": provider, "model": model, "fallback_expires_at": time.time() + FALLBACK_COOLDOWN_SECONDS}
        save_routing({**load_routing(), role: new_entry})
        _append_fallback_log(
            {"timestamp": time.time(), "role": role, "from": entry, "to": new_entry, "error": str(first_exc)[:300]}
        )
        return response, new_entry
    return None, None


def maybe_revert_expired_fallback(role: str, entry: dict, **generate_kwargs):
    """Si `entry` es un fallback automático (tiene `fallback_expires_at`,
    ver attempt_fallback) y ya venció, intenta volver al proveedor local por
    defecto del rol (DEFAULT_ROUTING) con una llamada REAL — mismo criterio
    de honestidad que attempt_fallback: nunca revierte a ciegas, solo si el
    intento tuvo éxito. Devuelve `(response, new_entry)` del intento
    revertido si funcionó; `(None, None)` si no correspondía revertir
    (no es un fallback vencido) o si el intento de volver falló — en ese
    caso extiende el cooldown para no reintentar en cada turno mientras el
    proveedor local sigue sin responder.

    Nunca toca una elección manual del fundador (una entrada sin
    fallback_expires_at, ver _normalize) — solo actúa sobre lo que
    attempt_fallback dejó."""
    expires_at = entry.get("fallback_expires_at")
    if expires_at is None or time.time() < expires_at:
        return None, None
    default_entry = dict(DEFAULT_ROUTING[role])
    if entry.get("provider") == default_entry["provider"] and entry.get("model") == default_entry["model"]:
        # Ya está en el default (no debería tener fallback_expires_at, pero
        # por las dudas se limpia el flag para no seguir evaluando esto).
        save_routing({**load_routing(), role: default_entry})
        return None, None
    try:
        response = _build(default_entry["provider"], default_entry["model"]).generate(**generate_kwargs)
    except Exception:
        extended = {**entry, "fallback_expires_at": time.time() + FALLBACK_COOLDOWN_SECONDS}
        save_routing({**load_routing(), role: extended})
        return None, None
    save_routing({**load_routing(), role: default_entry})
    _append_fallback_log(
        {"timestamp": time.time(), "role": role, "from": entry, "to": default_entry, "reverted": True}
    )
    return response, default_entry


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
        # context.set_llm_role (ADR de esta ronda): para que usage_log/
        # telemetry_events sepan qué ROL disparó esta llamada real — nunca
        # sobrevive más allá de esta llamada (mismo criterio que
        # conversation_id en Orchestrator.handle()).
        context.set_llm_role(self._role)
        try:
            # Chequeo barato (un compare de timestamps, sin red) salvo que
            # self._entry sea realmente un fallback vencido — ahí sí intenta
            # volver al proveedor local antes de usar el de fallback (ver
            # maybe_revert_expired_fallback).
            reverted_response, reverted_entry = maybe_revert_expired_fallback(self._role, self._entry, **generate_kwargs)
            if reverted_response is not None:
                self._llm, self._entry = _build(reverted_entry["provider"], reverted_entry["model"]), reverted_entry
                return reverted_response
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
        finally:
            context.clear_llm_role()


def build_resilient_llm(role: str) -> _ResilientLLM:
    """Como build_llm(role), pero el objeto devuelto reintenta solo con otro
    proveedor ante un fallo real de proveedor (ver _ResilientLLM) — este es
    el que hay que usar en toda la capa de wiring real (Orchestrator/app.py)
    en vez de build_llm a secas. build_llm queda tal cual para quien
    necesite la Capacidad concreta sin el envoltorio (ej. los tests de
    test_llm_routing.py que ya verifican isinstance contra las Capacidades
    reales)."""
    return _ResilientLLM(role)
