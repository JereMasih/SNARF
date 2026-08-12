---
name: n8n-map-sync
description: Use when the founder asks to regenerate, sync, update, or refresh the n8n map/canvas of Snarf's Executive Board (e.g. "actualizá el mapa de n8n", "sincronizá n8n", "regenerá el workflow del Executive Board"), or after changing tool_subset/routing/stages for a board role and wanting that reflected visually in n8n. Pushes the current real state (snarf/runtime/agent_registry.py) to the live n8n instance via its REST API — never edits n8n_workflows/branches/*.json by hand.
---

# n8n Map Sync

Regenera y empuja la rama "Snarf - Executive Board" del mapa de n8n (ver ADR 0154/0159) desde el estado
real del código — nunca edites `n8n_workflows/branches/snarf_specialists_executive_board.json` a mano,
ese archivo es un espejo generado, no la fuente de verdad.

## Antes de correr

1. Confirmá que Colima + el contenedor `snarf-n8n` están corriendo: `docker ps | grep snarf-n8n`. Si no,
   avisá al fundador — no lo arranques vos sin confirmar (ver CLAUDE.md, gotcha de TCC de Colima/Docker).
2. Confirmá que `N8N_API_KEY` está en el entorno (`.env` o exportada). Si falta, pedile al fundador que la
   genere en `http://127.0.0.1:5678` → Settings → n8n API (mismo paso a paso que ADR 0154).
3. Confirmá que `n8n_workflows/ids.json` existe y tiene `editar_prompt` — si no, esta skill no puede
   enlazar los nodos de edición (correr primero la importación inicial de ADR 0154).

## Correr la sincronización

```bash
.venv/bin/python -c "from snarf.runtime.n8n_generator import sync_executive_board; print(sync_executive_board())"
```

Esto reconstruye la rama completa (7 roles, receta real vía `agent_registry.get_agent_recipe()`, conexiones
reflejando las stages activas de `agent_graph_registry`) y la empuja vía `PUT`/`POST /api/v1/workflows`
contra la instancia real de n8n. Es idempotente — correrlo sin cambios reales deja el mismo resultado.

## Después de correr

Reportá al fundador en español: qué cambió (si hubo overrides de tools/routing/stages, mencionalos), y
recordale que la verificación visual final (abrir `http://127.0.0.1:5678`, mirar el canvas) es manual — la
API pública de n8n no permite confirmar el render desde acá (mismo límite ya documentado en ADR 0154).

## Alcance actual

Solo la rama del Executive Board (Fase 18, ADR 0159). Las otras 8 ramas de Specialists
(agency/community/content/finance/productivity/research/sales/raíz) siguen editadas a mano como en ADR
0154 — si el pedido es sobre esas ramas, avisá que ese generador todavía no existe en vez de intentar
editar sus JSON a mano vos mismo.
