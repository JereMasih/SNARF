"""Configuración de generación versionada por rol (Fase 7 del plan de
observabilidad/n8n — ver ROADMAP_OBSERVABILIDAD_MULTIUSUARIO_N8N.md, ADR
0142). Mismo criterio que `snarf/runtime/prompt_registry.py` (Fase 6): un
solo archivo (`data/generation_config.json`), versión activa + historial,
rollback. Un rol nunca tocado usa los defaults hardcodeados de siempre (ver
`snarf/capabilities/anthropic_llm.py::MAX_OUTPUT_TOKENS`/
`MAX_CONTINUATIONS`, `openai_compatible_llm.py::LOCAL_TIMEOUT_SECONDS`) —
"nada cambia el día del corte", mismo criterio que `DEFAULT_ROUTING`/Prompt
Registry.

A diferencia de Prompt Registry (un texto completo, siempre se reemplaza
entero), acá una edición real puede ser PARCIAL: guardar solo `temperature`
para un rol no debe pisar su `max_output_tokens` ya configurado — el resto
de los campos hereda el valor de la versión activa anterior (o el default,
si es la primera vez)."""

import json
import time
from pathlib import Path

GENERATION_CONFIG_PATH = Path("data/generation_config.json")

# Uno por cada parámetro que hoy es una constante fija de módulo compartida
# entre los 3 proveedores (ver ADR 0142): max_output_tokens/temperature
# aplican a los tres; timeout_seconds solo tiene efecto real hoy para
# proveedores locales (OpenAICompatibleLLM); max_continuations es el único
# "retry" real que existe en el código — cuántas veces el loop de
# continuación reintenta automáticamente cuando el modelo corta por tope de
# tokens (no reintentos de red/conexión, ya cubiertos por el fallback entre
# proveedores de llm_routing.py).
FIELDS = ("max_output_tokens", "temperature", "timeout_seconds", "max_continuations")


def _load_all() -> dict:
    if not GENERATION_CONFIG_PATH.exists():
        return {}
    return json.loads(GENERATION_CONFIG_PATH.read_text(encoding="utf-8"))


def _save_all(data: dict) -> None:
    GENERATION_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    GENERATION_CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _seed_entry(default: dict) -> dict:
    return {"active_version": 1, "versions": [{"version": 1, **{f: default.get(f) for f in FIELDS}, "created_at": time.time()}]}


def get_active_config(role: str, default: dict) -> dict:
    """La config real vigente para este rol: el default hardcodeado si nunca
    se guardó nada, o los valores de la versión activa (cada campo cae al
    default si esa versión no lo trae — permite overrides parciales)."""
    entry = _load_all().get(role)
    if not entry:
        return {f: default.get(f) for f in FIELDS}
    versions = {v["version"]: v for v in entry["versions"]}
    active = versions.get(entry["active_version"], {})
    return {f: active.get(f, default.get(f)) for f in FIELDS}


def history(role: str, default: dict) -> list[dict]:
    entry = _load_all().get(role)
    if not entry:
        entry = _seed_entry(default)
        entry["versions"][0]["created_at"] = None
    return [{**v, "active": v["version"] == entry["active_version"]} for v in entry["versions"]]


def save_new_version(role: str, overrides: dict, default: dict) -> dict:
    """`overrides` puede ser parcial — los campos no incluidos heredan el
    valor de la versión ACTIVA actual (nunca de la última agregada, que
    puede diferir tras un rollback)."""
    data = _load_all()
    entry = data.get(role) or _seed_entry(default)
    versions_by_number = {v["version"]: v for v in entry["versions"]}
    active = versions_by_number.get(entry["active_version"], {})
    merged = {f: overrides.get(f, active.get(f, default.get(f))) for f in FIELDS}
    next_version = max(v["version"] for v in entry["versions"]) + 1
    entry["versions"].append({"version": next_version, **merged, "created_at": time.time()})
    entry["active_version"] = next_version
    data[role] = entry
    _save_all(data)
    return entry


def rollback(role: str, version: int, default: dict) -> dict:
    """Activa una versión ya existente del historial — nunca borra ninguna,
    mismo criterio que Prompt Registry/`fallback_expires_at`."""
    data = _load_all()
    entry = data.get(role) or _seed_entry(default)
    valid_versions = {v["version"] for v in entry["versions"]}
    if version not in valid_versions:
        raise ValueError(f"Versión {version} no existe para el rol {role!r}")
    entry["active_version"] = version
    data[role] = entry
    _save_all(data)
    return entry
