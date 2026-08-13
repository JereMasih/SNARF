"""PROTOTIPO exploratorio (2026-08-12), no la versión oficial todavía — ver
"Iteración de UX de n8n con el fundador" en ROADMAP_OBSERVABILIDAD_MULTIUSUARIO_N8N.md
para el detalle completo de por qué se llegó a esta forma (prototipos B/C/D
descartados en el camino, cada uno con un hallazgo real).

Genera/actualiza 7 workflows SEPARADOS en n8n, uno por rol del Executive
Board ("Snarf - Editar <Rol>"), cada uno con: un único trigger manual
("Test workflow" corre la cadena completa sin ambigüedad — la lección real
del prototipo D, que fallaba con 7 triggers compartiendo un canvas) → un
nodo Set con campos editables reales (prompt_text, routing, y un checkbox
por cada una de las 19 tools posibles) → Proponer → Aplicar, encadenados
(el fundador pidió explícitamente NO tener una confirmación en un segundo
workflow aparte — "estoy haciendo las cosas yo, no es necesario confirmar
otra vez").

Si el fundador confirma que este diseño sirve de verdad: llevar este
patrón a snarf/runtime/n8n_generator.py (generalizado, con tests reales,
integrado al flujo de idempotencia vía n8n_workflows/ids.json) en vez de
seguir corriendo este script suelto — y escribir la ADR de enmienda real a
0156/0160 (apply encadenado sin confirmación de dos pasos separada) antes
de generalizar a las otras 8 ramas de Specialists.

Uso: .venv/bin/python n8n_workflows/_prototype_e_editar_agente.py
(requiere N8N_API_KEY en el entorno, Colima + snarf-n8n corriendo)."""

import os

import requests

from snarf.executive.roles import ROLE_CONFIGS
from snarf.mcp.tools import MCP_EXPOSED_TOOLS
from snarf.runtime import agent_registry

BASE = "http://127.0.0.1:5678"

# IDs reales ya creados en la instancia del fundador (2026-08-12) — correr
# este script de nuevo actualiza estos mismos workflows (PUT), nunca crea
# duplicados. Si esta instancia de n8n es otra, borrar este dict entero:
# el script crea (POST) los que falten y completa el dict de nuevo.
KNOWN_IDS = {
    "cto": "K74wbPPll8HOKB19",
    "coo": "iDzcBKCwjAx5Zlyr",
    "research": "5banqA7qoKUeYAqZ",
    "ceo": "iY91KHc0ixQNdltR",
    "cfo": "2jjQE22nggMW1mim",
    "cmo": "del2dYdbbk1QisyY",
    "creative": "ZmlhrtKO40YadiE9",
}

ALL_TOOLS = sorted(MCP_EXPOSED_TOOLS)


def build_workflow(role: str) -> dict:
    recipe = agent_registry.get_agent_recipe(role)
    config = ROLE_CONFIGS[role]
    display_name = config.display_name
    active_tools = set(recipe["tools"]["active"])

    tool_assignments = [
        {"id": f"tool-{i}", "name": f"tool_{tool}", "type": "boolean", "value": tool in active_tools}
        for i, tool in enumerate(ALL_TOOLS)
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


def main() -> None:
    api_key = os.environ["N8N_API_KEY"]
    headers = {"X-N8N-API-KEY": api_key, "Content-Type": "application/json"}
    for role in ROLE_CONFIGS:
        workflow = build_workflow(role)
        existing_id = KNOWN_IDS.get(role)
        if existing_id:
            res = requests.put(f"{BASE}/api/v1/workflows/{existing_id}", json=workflow, headers=headers, timeout=30)
        else:
            res = requests.post(f"{BASE}/api/v1/workflows", json=workflow, headers=headers, timeout=30)
        res.raise_for_status()
        wf_id = res.json()["id"]
        KNOWN_IDS[role] = wf_id
        print(f"{workflow['name']}: {BASE}/workflow/{wf_id}")
    print()
    print("KNOWN_IDS actualizado:", KNOWN_IDS)


if __name__ == "__main__":
    main()
