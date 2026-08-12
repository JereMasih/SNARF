"""Generador de workflows n8n (Fase 18 del plan de observabilidad/n8n — ver
ROADMAP_OBSERVABILIDAD_MULTIUSUARIO_N8N.md, ADR 0159). Reemplaza el trabajo
manual de ADR 0154 (llamadas HTTP sueltas hechas a mano contra la API de n8n
durante una sesión de Claude Code, sin quedar como módulo reusable) por
funciones puras, testeables sin red, que reconstruyen la rama del Executive
Board desde la fuente de verdad real: snarf/runtime/agent_registry.py — no
un snapshot fijo escrito a mano.

Esta ronda (Fase 18) cubre solo la rama del Executive Board (los 7 roles con
receta completa vía agent_registry.get_agent_recipe(), ver ADR 0157) —
regenerar las otras 8 ramas de Specialists (agency/community/.../raíz) sigue
el mismo patrón que ya estableció ADR 0154 a mano; migrarlas a este
generador es trabajo de seguimiento, no bloquea esta fase.

Separación real: build_executive_board_workflow() es pura (nodos +
conexiones, ningún I/O) — testeable sin n8n corriendo. push_workflow() sí
hace la llamada HTTP real contra la API pública de n8n
(POST/PUT /api/v1/workflows, mismo endpoint que ya usó ADR 0154) y necesita
la instancia real corriendo con N8N_API_KEY configurada — no se ejerce
automáticamente en ningún test ni en ningún camino de escritura de Snarf
todavía; queda invocable a mano (o vía la Skill n8n-map-sync) por el
fundador, mismo criterio de "clic manual" que ya dejó pendiente ADR 0154."""

import os
import threading
from pathlib import Path

import requests

from snarf.executive.roles import ROLE_CONFIGS
from snarf.runtime import agent_registry

IDS_PATH = Path("n8n_workflows/ids.json")
# N8N_PROTOCOL=http en docker-compose.n8n.yml — instancia local, sin TLS.
N8N_BASE_URL = os.environ.get("N8N_BASE_URL", "http://127.0.0.1:5678")

# Contadores de resiliencia (Fase 19, ADR 0160) — mismo criterio que
# snarf/telemetry/n8n_webhook_sink.py: la regeneración automática tras un
# `apply()` real nunca puede tumbar la escritura ya aplicada (los registros
# de la Fase 16 ya quedaron guardados aunque n8n esté caído o sin
# N8N_API_KEY) — el fallo se traga y se cuenta acá, nunca se propaga.
_lock = threading.Lock()
_sync_attempts = 0
_sync_failures = 0
_last_sync_error: str | None = None

_INFO_X = -100
_EDIT_X = 200
_ROW_HEIGHT = 200
_FIRST_ROW_Y = -600


def _role_summary_note(role: str) -> str:
    """Texto real del nodo `noOp` de un rol — recalculado en cada corrida
    desde agent_registry.get_agent_recipe(), nunca un texto fijo escrito a
    mano (a diferencia de las `notes` estáticas que dejó ADR 0154)."""
    recipe = agent_registry.get_agent_recipe(role)
    tools = ", ".join(recipe["tools"]["active"]) or "(ninguna)"
    routing = recipe["routing"]["active"]
    return (
        f"rol Executive Board · subproceso MCP propio, solo lectura de datos · "
        f"prompt_id: {recipe['prompt']['prompt_id']} · tools: {tools} · "
        f"modelo: {routing['provider']}/{routing['model']}"
    )


def build_executive_board_workflow(editar_prompt_workflow_id: str) -> dict:
    """Nodos + conexiones reales de la rama 'Snarf - Executive Board': un
    `noOp` por rol con su receta real (prompt_id/tools/modelo) + un edge
    hacia 'Snarf - Editar prompt' (misma superficie de edición centralizada
    de ADR 0154, hasta que Fase 19 sume 'Snarf - Editar agente'). Las
    conexiones desde 'Empezar' reflejan las stages reales de
    agent_graph_registry (vía agent_registry): sin overrides, fan-out plano
    idéntico al de ADR 0154 — cero regresión visual. Con overrides, una
    stage conecta a la siguiente en el propio canvas (trazabilidad visual
    real, el pedido original de esta serie de fases).

    n8n no tiene un concepto nativo de "barrera" — encadenar desde el
    primer nodo de una stage hacia todos los de la siguiente alcanza para
    reflejar el orden real en el canvas, que es lo que este pedido necesita
    (trazabilidad visual), no un motor de ejecución dentro de n8n: quien
    ejecuta de verdad las stages es snarf/executive/specialist.py (Fase 17),
    n8n solo lo representa."""
    roles = list(ROLE_CONFIGS.keys())
    recipe = agent_registry.get_agent_recipe(roles[0])
    stages: list[list[str]] = recipe["stages"]["active"]
    display_name_of = {role: ROLE_CONFIGS[role].display_name for role in roles}

    nodes = [
        {
            "id": "trigger",
            "name": "Empezar",
            "type": "n8n-nodes-base.manualTrigger",
            "typeVersion": 1,
            "position": [-400, 0],
            "parameters": {},
        }
    ]
    connections: dict[str, dict] = {}

    y = _FIRST_ROW_Y
    for role in roles:
        display_name = display_name_of[role]
        nodes.append(
            {
                "id": f"info-{role}",
                "name": display_name,
                "type": "n8n-nodes-base.noOp",
                "typeVersion": 1,
                "position": [_INFO_X, y],
                "notesInFlow": True,
                "notes": _role_summary_note(role),
                "parameters": {},
            }
        )
        nodes.append(
            {
                "id": f"edit-{role}",
                "name": f"Editar prompt: executive_board_{role}",
                "type": "n8n-nodes-base.executeWorkflow",
                "typeVersion": 1.2,
                "position": [_EDIT_X, y],
                "parameters": {
                    "source": "database",
                    "workflowId": {
                        "__rl": True,
                        "value": editar_prompt_workflow_id,
                        "mode": "list",
                        "cachedResultName": "Snarf - Editar prompt",
                    },
                },
            }
        )
        connections[display_name] = {
            "main": [[{"node": f"Editar prompt: executive_board_{role}", "type": "main", "index": 0}]]
        }
        y += _ROW_HEIGHT

    if len(stages) <= 1:
        # Default sin overrides: "Empezar" dispara a los 7 roles en
        # paralelo — idéntico al workflow original de ADR 0154.
        entry_targets = roles
    else:
        entry_targets = stages[0]
        for prev_stage, next_stage in zip(stages, stages[1:]):
            # El primer nodo de la stage anterior actúa de "ancla" visual —
            # ya tiene una conexión hacia su propio "Editar prompt"; se le
            # suma acá la conexión hacia la stage siguiente, sin pisarla.
            anchor = display_name_of[prev_stage[0]]
            connections[anchor]["main"][0].extend(
                {"node": display_name_of[role], "type": "main", "index": 0} for role in next_stage
            )

    connections["Empezar"] = {
        "main": [[{"node": display_name_of[role], "type": "main", "index": 0} for role in entry_targets]]
    }

    return {
        "name": "Snarf - Executive Board",
        "nodes": nodes,
        "connections": connections,
        "settings": {"executionOrder": "v1"},
    }


def push_workflow(workflow: dict, workflow_id: str | None, base_url: str = N8N_BASE_URL, api_key: str | None = None) -> str:
    """Crea (POST, sin `workflow_id`) o actualiza (PUT) `workflow` contra la
    API real de n8n — mismo endpoint que ya usó ADR 0154 a mano
    (`/api/v1/workflows`). Idempotente: correrlo dos veces seguidas con el
    mismo `workflow` y el mismo `workflow_id` deja el mismo resultado en
    n8n, nunca crea un duplicado.

    Nunca se llama automáticamente desde ningún camino de escritura de
    Snarf en esta fase — es la mitad "con red" de este módulo, invocable a
    mano (o vía la Skill n8n-map-sync) apuntando a una instancia de n8n real
    corriendo con N8N_API_KEY configurada. Levanta RuntimeError explícito
    si falta la API key, nunca intenta una llamada sin credencial real."""
    api_key = api_key or os.environ.get("N8N_API_KEY")
    if not api_key:
        raise RuntimeError("N8N_API_KEY no configurada — no se puede hablar con la API real de n8n")
    headers = {"X-N8N-API-KEY": api_key, "Content-Type": "application/json"}
    payload = {
        "name": workflow["name"],
        "nodes": workflow["nodes"],
        "connections": workflow["connections"],
        "settings": workflow["settings"],
    }
    if workflow_id:
        response = requests.put(f"{base_url}/api/v1/workflows/{workflow_id}", json=payload, headers=headers, timeout=30)
    else:
        response = requests.post(f"{base_url}/api/v1/workflows", json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()["id"]


def sync_executive_board() -> str:
    """Punto de entrada real: lee n8n_workflows/ids.json, reconstruye la
    rama del Executive Board desde el estado actual (agent_registry) y la
    empuja a la instancia de n8n real — crea la entrada en ids.json si es
    la primera vez. Requiere N8N_API_KEY en el entorno y la instancia de
    n8n realmente corriendo (ver docker-compose.n8n.yml)."""
    import json

    ids = json.loads(IDS_PATH.read_text(encoding="utf-8")) if IDS_PATH.exists() else {}
    editar_prompt_id = ids.get("editar_prompt")
    if not editar_prompt_id:
        raise RuntimeError(
            "n8n_workflows/ids.json no tiene 'editar_prompt' — correr primero la importación inicial de "
            "ADR 0154 (Snarf - Editar prompt tiene que existir en n8n antes de poder enlazarlo acá)."
        )
    workflow = build_executive_board_workflow(editar_prompt_id)
    branch_id = ids.get("branches", {}).get("executive_board")
    new_id = push_workflow(workflow, branch_id)
    ids.setdefault("branches", {})["executive_board"] = new_id
    IDS_PATH.write_text(json.dumps(ids, ensure_ascii=False, indent=2), encoding="utf-8")
    return new_id


def sync_executive_board_safe() -> bool:
    """Como sync_executive_board(), pero nunca levanta — pensado para
    dispararse en background después de un apply() real (Fase 19): la
    escritura a los registros ya quedó guardada, la regeneración del mapa
    visual es best-effort. Devuelve True/False según si funcionó; el
    detalle del error queda en sync_health() para diagnóstico, nunca se
    pierde en silencio total."""
    global _sync_attempts, _sync_failures, _last_sync_error
    with _lock:
        _sync_attempts += 1
    try:
        sync_executive_board()
        return True
    except Exception as exc:
        with _lock:
            _sync_failures += 1
            _last_sync_error = f"{type(exc).__name__}: {exc}"
        return False


def sync_health() -> dict:
    with _lock:
        return {"attempts": _sync_attempts, "failures": _sync_failures, "last_error": _last_sync_error}
