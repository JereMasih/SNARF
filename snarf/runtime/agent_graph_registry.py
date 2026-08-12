"""Agent Graph Registry (Fase 16 del plan de observabilidad/n8n — ver
ROADMAP_OBSERVABILIDAD_MULTIUSUARIO_N8N.md, ADR 0157). Versiona el orden de
ejecución del Executive Board — hoy fijo (fan-out 100% paralelo en
snarf/executive/specialist.py::ExecutiveBoardSpecialist.consult()), este
registro permite definir "stages": una lista de listas de roles, donde cada
stage corre en paralelo puertas adentro, y las stages sucesivas corren en
secuencia, recibiendo el resultado de la stage anterior como contexto
adicional. Esta Fase 16 solo construye y valida el registro — el motor que
lo lee y ejecuta en ese orden es Fase 17 (ADR 0158).

Mismo shape "JSON-por-entidad" que prompt_registry.py/tool_subset_registry.py
(data/agent_graph.json), clave = un `group_id` (hoy solo "executive_board",
el único grupo real con este concepto — ver snarf/runtime/agent_registry.py
para por qué no se generaliza a los demás Specialists todavía). Sin ninguna
versión guardada, el default es una única stage con los 7 roles — el fan-out
actual, sin cambio de comportamiento el día del corte."""

import json
import time
from pathlib import Path

from snarf.executive.roles import ROLE_CONFIGS

AGENT_GRAPH_PATH = Path("data/agent_graph.json")

DEFAULT_GROUP_ID = "executive_board"
DEFAULT_STAGES: tuple[tuple[str, ...], ...] = (tuple(ROLE_CONFIGS.keys()),)


def _load_all() -> dict:
    if not AGENT_GRAPH_PATH.exists():
        return {}
    return json.loads(AGENT_GRAPH_PATH.read_text(encoding="utf-8"))


def _save_all(data: dict) -> None:
    AGENT_GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)
    AGENT_GRAPH_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _as_stage_lists(stages) -> list[list[str]]:
    return [list(stage) for stage in stages]


def _seed_entry(default) -> dict:
    return {"active_version": 1, "versions": [{"version": 1, "stages": _as_stage_lists(default), "created_at": time.time()}]}


def _validate_stages(stages: list[list[str]]) -> None:
    seen: set[str] = set()
    for stage in stages:
        if not stage:
            raise ValueError("Ninguna stage puede estar vacía")
        for role in stage:
            if role not in ROLE_CONFIGS:
                raise ValueError(f"Rol desconocido: {role!r}. Roles válidos: {', '.join(ROLE_CONFIGS)}")
            if role in seen:
                raise ValueError(f"Rol {role!r} repetido en más de una stage — cada rol corre una sola vez por consulta")
            seen.add(role)


def get_active_stages(group_id: str = DEFAULT_GROUP_ID, default=DEFAULT_STAGES) -> list[list[str]]:
    """Las stages reales que deben usarse ahora mismo: el default (una sola
    stage, fan-out plano) si nunca se guardó una versión nueva, o la versión
    activa si sí. Llamada en cada consulta real, no cacheada a nivel de
    import — mismo criterio que get_active_text/get_active_subset."""
    entry = _load_all().get(group_id)
    if not entry:
        return _as_stage_lists(default)
    versions = {v["version"]: v["stages"] for v in entry["versions"]}
    return versions.get(entry["active_version"], _as_stage_lists(default))


def history(group_id: str = DEFAULT_GROUP_ID, default=DEFAULT_STAGES) -> list[dict]:
    """Historial real de versiones, con `active=True` en la vigente. Si
    nunca se guardó nada, el propio default cuenta como v1 implícito."""
    entry = _load_all().get(group_id)
    if not entry:
        entry = _seed_entry(default)
        entry["versions"][0]["created_at"] = None
    return [{**v, "active": v["version"] == entry["active_version"]} for v in entry["versions"]]


def save_new_version(stages: list[list[str]], group_id: str = DEFAULT_GROUP_ID, default=DEFAULT_STAGES) -> dict:
    """Guarda `stages` como versión nueva y la activa, tras validarla. Si es
    la primera vez que se toca este grupo, siembra la v1 real (el fan-out
    plano actual) antes de agregar la v2 — nunca se pierde el comportamiento
    original."""
    _validate_stages(stages)
    data = _load_all()
    entry = data.get(group_id) or _seed_entry(default)
    next_version = max(v["version"] for v in entry["versions"]) + 1
    entry["versions"].append({"version": next_version, "stages": _as_stage_lists(stages), "created_at": time.time()})
    entry["active_version"] = next_version
    data[group_id] = entry
    _save_all(data)
    return entry


def rollback(group_id: str, version: int, default=DEFAULT_STAGES) -> dict:
    """Activa una versión ya existente del historial — nunca borra ninguna
    (mismo criterio que prompt_registry.rollback)."""
    data = _load_all()
    entry = data.get(group_id) or _seed_entry(default)
    valid_versions = {v["version"] for v in entry["versions"]}
    if version not in valid_versions:
        raise ValueError(f"Versión {version} no existe para el grafo {group_id!r}")
    entry["active_version"] = version
    data[group_id] = entry
    _save_all(data)
    return entry
