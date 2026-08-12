"""Camino de escritura n8n → Snarf con confirmación de dos pasos (Fase 19
del plan de observabilidad/n8n — ver ROADMAP_OBSERVABILIDAD_MULTIUSUARIO_N8N.md,
ADR 0160). Implementa en código la categoría (b) de ADR 0156 ("iniciada y
confirmada por el fundador en vivo"): `propose()` calcula un diff real
contra el estado activo y lo deja pendiente con un `change_id`, sin aplicar
nada todavía; `apply()` revalida que el estado activo no cambió desde el
propose (optimistic locking — si cambió, rechaza en vez de aplicar sobre un
estado que ya no existe) y recién ahí escribe a los cuatro registros reales
de la Fase 16 (prompt_registry, tool_subset_registry, llm_routing,
agent_graph_registry).

Esta es la única superficie que puede tocar prompt+tools+routing+stages
juntos — autorizada por ADR 0156 específicamente porque hay una
confirmación real con diff visible de por medio antes de aplicar, nunca una
escritura autónoma sin que alguien la haya visto. `/n8n/prompts`/
`/n8n/generation-config` (ADR 0145, escritura directa de un paso) siguen
existiendo tal cual, sin cambios — esta es una categoría nueva, no un
reemplazo."""

import json
import time
import uuid
from pathlib import Path

from snarf.executive.roles import ROLE_CONFIGS
from snarf.runtime import agent_graph_registry, agent_registry, llm_routing, prompt_registry, tool_subset_registry

PENDING_PATH = Path("data/n8n_pending_changes.json")
TTL_SECONDS = 900

FIELDS = ("prompt_text", "tools", "routing", "stages")


class StaleChangeError(ValueError):
    """El estado activo cambió desde que se propuso este cambio — nunca se
    aplica un diff calculado sobre un estado que ya no existe."""


def _load_all() -> dict:
    if not PENDING_PATH.exists():
        return {}
    return json.loads(PENDING_PATH.read_text(encoding="utf-8"))


def _save_all(data: dict) -> None:
    PENDING_PATH.parent.mkdir(parents=True, exist_ok=True)
    PENDING_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _prune_expired(data: dict) -> dict:
    now = time.time()
    return {change_id: entry for change_id, entry in data.items() if entry["expires_at"] > now}


def _current_values(recipe: dict) -> dict:
    return {
        "prompt_text": recipe["prompt"]["active_text"],
        "tools": recipe["tools"]["active"],
        "routing": recipe["routing"]["active"],
        "stages": recipe["stages"]["active"],
    }


def propose(agent_id: str, changes: dict) -> dict:
    """Calcula el diff real contra el estado activo de `agent_id` y lo deja
    pendiente — no aplica nada todavía. `changes` puede traer cualquier
    subconjunto no vacío de FIELDS. Lanza ValueError (agent_id desconocido,
    vía agent_registry) o campos inválidos."""
    unknown_fields = set(changes) - set(FIELDS)
    if unknown_fields:
        raise ValueError(f"Campo(s) desconocido(s): {', '.join(sorted(unknown_fields))}. Válidos: {', '.join(FIELDS)}")
    if not changes:
        raise ValueError(f"La propuesta debe incluir al menos uno de: {', '.join(FIELDS)}")

    recipe = agent_registry.get_agent_recipe(agent_id)  # valida agent_id, lanza ValueError si no existe
    baseline = _current_values(recipe)
    diff = {field: {"before": baseline[field], "after": changes[field]} for field in changes}

    change_id = uuid.uuid4().hex
    now = time.time()
    data = _prune_expired(_load_all())
    data[change_id] = {
        "agent_id": recipe["agent_id"],
        "changes": changes,
        "baseline": baseline,
        "created_at": now,
        "expires_at": now + TTL_SECONDS,
    }
    _save_all(data)
    return {"change_id": change_id, "agent_id": recipe["agent_id"], "diff": diff, "expires_at": data[change_id]["expires_at"]}


def apply(change_id: str) -> dict:
    """Aplica una propuesta ya confirmada. Revalida que el estado activo de
    cada campo propuesto no cambió desde el propose (StaleChangeError si
    sí), y recién ahí escribe a los registros reales. Devuelve la receta
    completa ya actualizada. Lanza ValueError si `change_id` no existe o ya
    expiró (TTL_SECONDS desde el propose, nunca aplicado sobre algo que
    nadie confirmó a tiempo)."""
    data = _prune_expired(_load_all())
    entry = data.get(change_id)
    if entry is None:
        raise ValueError(f"change_id {change_id!r} no existe o ya expiró")

    agent_id = entry["agent_id"]
    recipe = agent_registry.get_agent_recipe(agent_id)
    current = _current_values(recipe)
    stale = [field for field in entry["changes"] if current[field] != entry["baseline"][field]]
    if stale:
        raise StaleChangeError(
            f"El estado de {', '.join(stale)} cambió desde que se propuso este cambio ({change_id}) — "
            f"volvé a proponerlo con el estado actual antes de confirmar."
        )

    role = recipe["agent_id"]
    config = ROLE_CONFIGS[role]
    changes = entry["changes"]
    if "prompt_text" in changes:
        prompt_registry.save_new_version(recipe["prompt"]["prompt_id"], changes["prompt_text"], config.system_prompt)
    if "tools" in changes:
        tool_subset_registry.save_new_version(role, changes["tools"], config.mcp_tool_subset)
    if "routing" in changes:
        llm_routing.save_routing_versioned(
            recipe["routing"]["routing_role"], provider=changes["routing"]["provider"], model=changes["routing"]["model"]
        )
    if "stages" in changes:
        agent_graph_registry.save_new_version(changes["stages"])

    del data[change_id]
    _save_all(data)
    return agent_registry.get_agent_recipe(agent_id)
