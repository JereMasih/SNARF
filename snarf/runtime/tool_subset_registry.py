"""Tool Subset Registry (Fase 16 del plan de observabilidad/n8n — ver
ROADMAP_OBSERVABILIDAD_MULTIUSUARIO_N8N.md, ADR 0157). Generaliza
snarf/runtime/prompt_registry.py al eje de "qué herramientas MCP tiene cada
rol del Executive Board" — hoy fijo como constante Python
(ROLE_TOOL_SUBSETS, snarf/mcp/tools.py), ahora versionado con
historial/rollback real, mismo shape "JSON-por-entidad" que
prompt_registry.py (data/tool_subsets.json).

Un `role` que nunca se tocó no tiene entrada en el archivo — en ese caso
ROLE_TOOL_SUBSETS[role] (el default hardcodeado) sigue siendo lo que corre,
tal cual antes de esta ADR ("nada cambia el día del corte", mismo criterio
que prompt_registry.get_active_text/DEFAULT_ROUTING).

Validación en save_new_version(): toda versión nueva debe ser subconjunto de
MCP_EXPOSED_TOOLS (snarf/mcp/tools.py) — nunca dejar guardado un nombre de
tool que ni siquiera está en el allowlist general que el servidor MCP podría
llegar a exponer. Esto es un rechazo temprano, no la superficie de
seguridad real: el gate final y autoritativo sigue siendo
snarf/mcp/server.py::build_server() (MCP_EXPOSED_TOOLS - HIGH_IMPACT_TOOLS -
BULK_READ_GATED_TOOLS), y snarf/executive/process.py::_MCPToolBridge.start()
ya filtra `listed.tools` (lo que el server realmente sirve) por este
tool_subset — un nombre guardado acá que el server no sirve en la práctica
simplemente nunca aparece en `tools`, nunca se llega a exponer. No se
importa snarf.core.orchestrator acá a propósito (evita un ciclo real:
orchestrator.py ya importa snarf.executive.specialist, que en Fase 17 pasa a
importar este módulo)."""

import json
import time
from pathlib import Path

from snarf.mcp.tools import MCP_EXPOSED_TOOLS

TOOL_SUBSETS_PATH = Path("data/tool_subsets.json")


def _load_all() -> dict:
    if not TOOL_SUBSETS_PATH.exists():
        return {}
    return json.loads(TOOL_SUBSETS_PATH.read_text(encoding="utf-8"))


def _save_all(data: dict) -> None:
    TOOL_SUBSETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOOL_SUBSETS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _seed_entry(default: frozenset[str]) -> dict:
    return {"active_version": 1, "versions": [{"version": 1, "tools": sorted(default), "created_at": time.time()}]}


def get_active_subset(role: str, default: frozenset[str]) -> frozenset[str]:
    """El subset real que debe usarse ahora mismo para este rol: el default
    hardcodeado si nunca se guardó una versión nueva, o el de la versión
    activa si sí. Llamada en cada consulta real (no cacheada a nivel de
    import), mismo criterio que get_active_text — un rollback/edición queda
    vivo de inmediato, sin reiniciar el server."""
    entry = _load_all().get(role)
    if not entry:
        return frozenset(default)
    versions = {v["version"]: v["tools"] for v in entry["versions"]}
    return frozenset(versions.get(entry["active_version"], default))


def history(role: str, default: frozenset[str]) -> list[dict]:
    """Historial real de versiones, con `active=True` en la vigente. Si
    nunca se guardó nada, el propio default cuenta como v1 implícito —
    nunca reporta un historial vacío cuando en la práctica sí hay un subset
    real corriendo."""
    entry = _load_all().get(role)
    if not entry:
        entry = _seed_entry(default)
        entry["versions"][0]["created_at"] = None
    return [{**v, "active": v["version"] == entry["active_version"]} for v in entry["versions"]]


def save_new_version(role: str, tools: list[str] | frozenset[str], default: frozenset[str]) -> dict:
    """Guarda `tools` como versión nueva y la activa. Si es la primera vez
    que se toca este rol, siembra la v1 real (el default hardcodeado) antes
    de agregar la v2 — nunca se pierde el subset original."""
    invalid = set(tools) - MCP_EXPOSED_TOOLS
    if invalid:
        raise ValueError(
            f"Tool(s) fuera del allowlist general de MCP (MCP_EXPOSED_TOOLS): {', '.join(sorted(invalid))}"
        )
    data = _load_all()
    entry = data.get(role) or _seed_entry(default)
    next_version = max(v["version"] for v in entry["versions"]) + 1
    entry["versions"].append({"version": next_version, "tools": sorted(set(tools)), "created_at": time.time()})
    entry["active_version"] = next_version
    data[role] = entry
    _save_all(data)
    return entry


def rollback(role: str, version: int, default: frozenset[str]) -> dict:
    """Activa una versión ya existente del historial — nunca borra ninguna
    (mismo criterio que prompt_registry.rollback)."""
    data = _load_all()
    entry = data.get(role) or _seed_entry(default)
    valid_versions = {v["version"] for v in entry["versions"]}
    if version not in valid_versions:
        raise ValueError(f"Versión {version} no existe para el tool_subset del rol {role!r}")
    entry["active_version"] = version
    data[role] = entry
    _save_all(data)
    return entry
