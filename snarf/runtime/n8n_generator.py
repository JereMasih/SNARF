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

Sumado 2026-08-13 (ADR 0164): build_agent_edit_workflow() genera los 7
'Snarf - Editar <Rol>' (Prototipo E, editor completo por rol — prompt/
tools/routing, con propose→apply encadenado en un solo click), y
build_executive_board_workflow() ahora enlaza cada rol del canvas de
overview a su propio editor en vez de al editor genérico de solo texto de
ADR 0154. Reemplaza también el patrón de dos workflows separados
('Snarf - Proponer/Confirmar cambio de agente', ADR 0160) — el fundador
pidió explícitamente que aplicar no requiera una confirmación en un
workflow aparte.

Separación real: build_executive_board_workflow()/build_agent_edit_workflow()
son puras (nodos + conexiones, ningún I/O) — testeables sin n8n corriendo.
push_workflow() sí
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
from snarf.mcp.tools import MCP_EXPOSED_TOOLS
from snarf.runtime import agent_registry

IDS_PATH = Path("n8n_workflows/ids.json")
_ALL_MCP_TOOLS = sorted(MCP_EXPOSED_TOOLS)
# N8N_PROTOCOL=http en docker-compose.n8n.yml — instancia local, sin TLS.
N8N_BASE_URL = os.environ.get("N8N_BASE_URL", "http://127.0.0.1:5678")

# Fase 24 (ADR 0166) — canvas en vivo de un turno real. Path fijo, no
# aleatorio: snarf/telemetry/n8n_live_canvas_sink.py necesita saber de
# antemano a qué URL disparar sin leer n8n_workflows/ids.json en el hot
# path de cada turno real.
LIVE_TURN_WEBHOOK_PATH = "snarf-turno-en-vivo"
# Cantidad de nodos `Wait` genéricos del canvas — un turno real puede tener
# más o menos eventos de ciclo de vida que esto (ver ADR 0166: no hay forma
# de saber de antemano cuántos va a tener, y n8n no tiene un concepto nativo
# de "repetir N veces"), así que este es un techo razonable, no un conteo
# exacto. El sink manda el evento de cierre del turno (workflow.finished/
# failed de "turn") como el próximo resume disponible sea cual sea, así que
# el turno SIEMPRE termina de verdad en el canvas, tenga más o menos etapas
# reales que huecos.
LIVE_TURN_STAGE_COUNT = 5
LIVE_TURN_STAGE_TIMEOUT_MINUTES = 10
# webhookId fijos (Fase 23, hallazgo real: un nodo Webhook/Wait creado vía
# la API pública necesita este campo explícito, además de `parameters.path`,
# o n8n nunca lo registra de verdad aunque `active` quede en `true`) —
# constantes, no `uuid.uuid4()` en cada llamada, para que
# build_live_turn_workflow() siga siendo idempotente entre corridas (mismo
# criterio que el resto de este módulo).
_LIVE_TURN_TRIGGER_WEBHOOK_ID = "3d8c7320-b0e9-4bd5-9dcf-b753b1578e16"
_LIVE_TURN_STAGE_WEBHOOK_IDS = [
    "b5c9ce17-c3c4-459c-9e54-b6267a2718df",
    "7cafe331-7409-48b8-9a57-a78712009ce4",
    "395109d2-871f-4911-b4d7-c4a783ffb68e",
    "9ef08d34-2d97-46bf-b215-cfbe80ecb826",
    "e33fb402-b896-4be2-8660-ecab9b11c3bc",
]

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


def build_executive_board_workflow(agent_edit_workflow_ids: dict[str, str]) -> dict:
    """Nodos + conexiones reales de la rama 'Snarf - Executive Board': un
    `noOp` por rol con su receta real (prompt_id/tools/modelo) + un edge
    hacia su propio editor dedicado ('Snarf - Editar <Rol>', ver
    build_agent_edit_workflow() — Prototipo E, confirmado en vivo por el
    fundador 2026-08-13, ver ADR 0164). `agent_edit_workflow_ids` debe traer
    los 7 roles (ver sync_agent_edit_workflows()). Las conexiones desde
    'Empezar' reflejan las stages reales de
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
                "name": f"Editar {display_name}",
                "type": "n8n-nodes-base.executeWorkflow",
                "typeVersion": 1.2,
                "position": [_EDIT_X, y],
                "parameters": {
                    "source": "database",
                    "workflowId": {
                        "__rl": True,
                        "value": agent_edit_workflow_ids[role],
                        "mode": "list",
                        "cachedResultName": f"Snarf - Editar {display_name}",
                    },
                },
            }
        )
        connections[display_name] = {
            "main": [[{"node": f"Editar {display_name}", "type": "main", "index": 0}]]
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


def build_agent_edit_workflow(role: str) -> dict:
    """Nodos + conexiones reales de 'Snarf - Editar <Rol>' — Prototipo E
    (ver "Iteración de UX de n8n con el fundador" en
    ROADMAP_OBSERVABILIDAD_MULTIUSUARIO_N8N.md, confirmado en vivo por el
    fundador 2026-08-13, formalizado en ADR 0164). Un único trigger manual
    ("Test workflow" corre la cadena completa sin ambigüedad — la lección
    real del Prototipo D, que fallaba con varios triggers compartiendo un
    canvas) → un nodo `Set` con los valores reales actuales (prompt_text,
    routing, un booleano por cada tool posible) como default editable →
    Proponer → Aplicar, encadenados sin una confirmación en un segundo
    workflow aparte (pedido explícito del fundador: "estoy haciendo las
    cosas yo, no es necesario confirmar otra vez").

    Los valores del `Set` quedan fijos en el momento en que se genera este
    workflow — si el prompt/tools/routing del rol cambia después (por un
    apply real, o por el cockpit), hay que correr sync_agent_edit_workflows()
    de nuevo para que el editor deje de mostrar un default viejo (mismo
    límite ya conocido del canvas de overview, ver docstring de
    sync_executive_board_safe: la regeneración automática tras un apply está
    desactivada a propósito, es manual vía la Skill n8n-map-sync)."""
    recipe = agent_registry.get_agent_recipe(role)
    config = ROLE_CONFIGS[role]
    display_name = config.display_name
    active_tools = set(recipe["tools"]["active"])

    tool_assignments = [
        {"id": f"tool-{i}", "name": f"tool_{tool}", "type": "boolean", "value": tool in active_tools}
        for i, tool in enumerate(_ALL_MCP_TOOLS)
    ]

    nodes = [
        {
            "id": "trigger",
            "name": "▶ Ejecutar (Test workflow)",
            "type": "n8n-nodes-base.manualTrigger",
            "typeVersion": 1,
            "position": [-680, 0],
            "notesInFlow": True,
            "notes": (
                "Usá el botón 'Test workflow' de arriba del canvas (no el play de un nodo individual) "
                "-- corre la cadena completa: editar -> proponer -> aplicar, de una."
            ),
            "parameters": {},
        },
        {
            "id": "set",
            "name": display_name,
            "type": "n8n-nodes-base.set",
            "typeVersion": 3.4,
            "position": [-400, 0],
            "notesInFlow": True,
            "notes": f"Doble clic para editar prompt/tools/modelo reales de {display_name}. Después apretá 'Test workflow' arriba.",
            "parameters": {
                "assignments": {
                    "assignments": [
                        {"id": "a1", "name": "agent_id", "type": "string", "value": role},
                        {"id": "a2", "name": "prompt_text", "type": "string", "value": recipe["prompt"]["active_text"]},
                        {"id": "a3", "name": "routing_provider", "type": "string", "value": recipe["routing"]["active"]["provider"]},
                        {"id": "a4", "name": "routing_model", "type": "string", "value": recipe["routing"]["active"]["model"]},
                        *tool_assignments,
                    ]
                },
                "options": {},
            },
        },
        {
            "id": "propose",
            "name": "Proponer",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [-120, 0],
            "parameters": {
                "method": "POST",
                "url": f"=http://host.docker.internal:8002/n8n/agent/{{{{ $json.agent_id }}}}/propose",
                "authentication": "genericCredentialType",
                "genericAuthType": "httpHeaderAuth",
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": (
                    "={{ JSON.stringify({ prompt_text: $json.prompt_text, "
                    "tools: Object.keys($json).filter(k => k.startsWith('tool_') && $json[k]).map(k => k.slice(5)), "
                    "routing: { provider: $json.routing_provider, model: $json.routing_model } }) }}"
                ),
                "options": {},
            },
            "credentials": {"httpHeaderAuth": {"id": "", "name": "Snarf n8n token"}},
        },
        {
            "id": "apply",
            "name": "Aplicar",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [160, 0],
            "notesInFlow": True,
            "notes": "Si termina en verde, el cambio quedó aplicado de verdad (historial/rollback real desde el cockpit).",
            "parameters": {
                "method": "POST",
                "url": f"=http://host.docker.internal:8002/n8n/agent/{role}/apply",
                "authentication": "genericCredentialType",
                "genericAuthType": "httpHeaderAuth",
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": "={{ JSON.stringify({ change_id: $json.change_id }) }}",
                "options": {},
            },
            "credentials": {"httpHeaderAuth": {"id": "", "name": "Snarf n8n token"}},
        },
    ]
    connections = {
        "▶ Ejecutar (Test workflow)": {"main": [[{"node": display_name, "type": "main", "index": 0}]]},
        display_name: {"main": [[{"node": "Proponer", "type": "main", "index": 0}]]},
        "Proponer": {"main": [[{"node": "Aplicar", "type": "main", "index": 0}]]},
    }
    return {
        "name": f"Snarf - Editar {display_name}",
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


def sync_agent_edit_workflows() -> dict[str, str]:
    """Punto de entrada real: reconstruye y empuja los 7 workflows 'Snarf -
    Editar <Rol>' (uno por rol del Executive Board) desde el estado actual
    (agent_registry) — crea las entradas en ids.json (clave 'agent_edit') la
    primera vez, actualiza (PUT) las que ya existen. Requiere N8N_API_KEY en
    el entorno y la instancia de n8n realmente corriendo."""
    import json

    ids = json.loads(IDS_PATH.read_text(encoding="utf-8")) if IDS_PATH.exists() else {}
    agent_edit_ids: dict[str, str] = dict(ids.get("agent_edit", {}))
    for role in ROLE_CONFIGS:
        workflow = build_agent_edit_workflow(role)
        agent_edit_ids[role] = push_workflow(workflow, agent_edit_ids.get(role))
    ids["agent_edit"] = agent_edit_ids
    IDS_PATH.write_text(json.dumps(ids, ensure_ascii=False, indent=2), encoding="utf-8")
    return agent_edit_ids


def sync_executive_board() -> str:
    """Punto de entrada real: lee n8n_workflows/ids.json, reconstruye la
    rama del Executive Board desde el estado actual (agent_registry) y la
    empuja a la instancia de n8n real — crea la entrada en ids.json si es
    la primera vez. Requiere que los 7 workflows 'Snarf - Editar <Rol>' ya
    existan (correr sync_agent_edit_workflows() primero) y que N8N_API_KEY
    esté en el entorno con la instancia de n8n realmente corriendo (ver
    docker-compose.n8n.yml)."""
    import json

    ids = json.loads(IDS_PATH.read_text(encoding="utf-8")) if IDS_PATH.exists() else {}
    agent_edit_ids = ids.get("agent_edit", {})
    missing = [role for role in ROLE_CONFIGS if role not in agent_edit_ids]
    if missing:
        raise RuntimeError(
            f"n8n_workflows/ids.json no tiene 'agent_edit' para: {', '.join(missing)} — correr primero "
            "sync_agent_edit_workflows() (los 7 'Snarf - Editar <Rol>' tienen que existir en n8n antes de "
            "poder enlazarlos acá)."
        )
    workflow = build_executive_board_workflow(agent_edit_ids)
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


def build_live_turn_workflow() -> dict:
    """Canvas real de un turno en vivo (Fase 24, ADR 0166) — Prototipo/spike
    verificado a mano contra la instancia real de n8n el 2026-08-14 (ver
    "Sesión 2026-08-14" en ROADMAP_OBSERVABILIDAD_MULTIUSUARIO_N8N.md antes
    de tocar esta función: documenta los hallazgos reales de n8n 1.121.0 que
    esta forma respeta).

    `Webhook (responseMode: responseNode)` → `Code` (captura `$execution.id`)
    → `Respond to Webhook` (lo devuelve en el body, sin que
    n8n_live_canvas_sink.py tenga que leer `$execution.resumeUrl` desde
    dentro del workflow) → LIVE_TURN_STAGE_COUNT nodos `Wait` genéricos
    encadenados ("Etapa 1", "Etapa 2", ...), cada uno con
    `resume: webhook`/`httpMethod: POST` y un timeout real (nunca esperan
    para siempre si el sink nunca les manda el resume — turno caído a mitad
    de camino, o Snarf reiniciado).

    Genéricos a propósito, no "Junta Directiva"/"Project Manager"/"área"
    fijos: un turno real no siempre consulta al board, no siempre rutea una
    tool a un área, y puede rutear más de una — forzar esos nombres fijos
    mentiría sobre turnos que no pasan por ahí (Principio VI, FOUNDATION.md).
    El contenido real de cada etapa (qué pasó de verdad) viaja en el payload
    del resume — visible con doble click sobre el nodo ya avanzado, que es
    el pedido real del fundador (ver el turno, no adivinar su forma de
    antemano)."""
    nodes = [
        {
            "id": "trigger", "name": "Webhook", "type": "n8n-nodes-base.webhook", "typeVersion": 2.1,
            "position": [-800, 0], "webhookId": _LIVE_TURN_TRIGGER_WEBHOOK_ID,
            "notesInFlow": True,
            "notes": "Snarf dispara esto solo (snarf/telemetry/n8n_live_canvas_sink.py) al arrancar un turno real — nunca a mano.",
            "parameters": {"httpMethod": "POST", "path": LIVE_TURN_WEBHOOK_PATH, "responseMode": "responseNode", "options": {}},
        },
        {
            "id": "capture-id", "name": "CapturarExecutionId", "type": "n8n-nodes-base.code", "typeVersion": 2,
            "position": [-600, 0],
            "parameters": {"jsCode": "return [{ json: { executionId: $execution.id } }];"},
        },
        {
            "id": "respond", "name": "DevolverExecutionId", "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.4,
            "position": [-400, 0],
            "parameters": {"respondWith": "allIncomingItems", "options": {}},
        },
    ]
    connections: dict[str, dict] = {
        "Webhook": {"main": [[{"node": "CapturarExecutionId", "type": "main", "index": 0}]]},
        "CapturarExecutionId": {"main": [[{"node": "DevolverExecutionId", "type": "main", "index": 0}]]},
    }
    previous_name = "DevolverExecutionId"
    for i in range(LIVE_TURN_STAGE_COUNT):
        name = f"Etapa {i + 1}"
        nodes.append(
            {
                "id": f"stage-{i + 1}", "name": name, "type": "n8n-nodes-base.wait", "typeVersion": 1.1,
                "position": [-200 + i * 200, 0], "webhookId": _LIVE_TURN_STAGE_WEBHOOK_IDS[i],
                "notesInFlow": True,
                "notes": "Doble click, después de que avance, muestra el evento real de telemetría que la disparó.",
                "parameters": {
                    "resume": "webhook", "httpMethod": "POST",
                    "limitWaitTime": True, "resumeAmount": LIVE_TURN_STAGE_TIMEOUT_MINUTES, "resumeUnit": "minutes",
                    "options": {},
                },
            }
        )
        connections[previous_name] = {"main": [[{"node": name, "type": "main", "index": 0}]]}
        previous_name = name

    return {
        "name": "Snarf - Turno en vivo",
        "nodes": nodes,
        "connections": connections,
        "settings": {"executionOrder": "v1"},
    }


def sync_live_turn_workflow(base_url: str = N8N_BASE_URL, api_key: str | None = None) -> str:
    """Punto de entrada real: reconstruye y empuja 'Snarf - Turno en vivo' —
    crea la entrada en ids.json (clave 'live_turn') la primera vez, actualiza
    (PUT) si ya existe. A diferencia de los demás workflows generados acá
    (disparados a mano con "Test workflow"), este necesita estar `active`
    de verdad para recibir tráfico real del sink — se activa explícito acá
    (ciclo desactivar→activar, hallazgo real de la Fase 23: dejarlo
    simplemente en `active` sin ese ciclo no siempre re-registra el
    webhook). Requiere N8N_API_KEY en el entorno y la instancia de n8n
    realmente corriendo."""
    import json

    api_key = api_key or os.environ.get("N8N_API_KEY")
    if not api_key:
        raise RuntimeError("N8N_API_KEY no configurada — no se puede hablar con la API real de n8n")
    ids = json.loads(IDS_PATH.read_text(encoding="utf-8")) if IDS_PATH.exists() else {}
    workflow = build_live_turn_workflow()
    existing_id = ids.get("live_turn")
    new_id = push_workflow(workflow, existing_id, base_url=base_url, api_key=api_key)
    ids["live_turn"] = new_id
    IDS_PATH.write_text(json.dumps(ids, ensure_ascii=False, indent=2), encoding="utf-8")
    headers = {"X-N8N-API-KEY": api_key}
    requests.post(f"{base_url}/api/v1/workflows/{new_id}/deactivate", headers=headers, timeout=30)
    requests.post(f"{base_url}/api/v1/workflows/{new_id}/activate", headers=headers, timeout=30).raise_for_status()
    return new_id


def sync_health() -> dict:
    with _lock:
        return {"attempts": _sync_attempts, "failures": _sync_failures, "last_error": _last_sync_error}
