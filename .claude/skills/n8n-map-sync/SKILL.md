---
name: n8n-map-sync
description: Use when the founder asks to regenerate, sync, update, or refresh the n8n map/canvas of Snarf's Executive Board (e.g. "actualizá el mapa de n8n", "sincronizá n8n", "regenerá el workflow del Executive Board"), after changing tool_subset/routing/stages for a board role and wanting that reflected visually in n8n, right after a real `apply` from one of the "Snarf - Editar <Rol>" workflows (their editable defaults go stale otherwise — auto-regeneration is deliberately disabled, see ADR 0164), or to (re)create/activate the "Snarf - Turno en vivo" live-canvas workflow (ADR 0166). Pushes the current real state (snarf/runtime/agent_registry.py) to the live n8n instance via its REST API — never edits n8n_workflows/branches/*.json by hand.
---

# n8n Map Sync

Regenera y empuja tres superficies del mapa de n8n desde el estado real del código (ver ADR
0154/0159/0164/0166) — nunca edites `n8n_workflows/branches/*.json` a mano, esos archivos son espejos
generados, no la fuente de verdad:

1. Los 7 workflows **"Snarf - Editar `<Rol>`"** (editor completo por rol: prompt/tools/routing, con
   `propose→apply` encadenado en un solo click — Prototipo E, confirmado en vivo por el fundador
   2026-08-13). Sus valores editables quedan **fijos en el momento en que se generan** — si el prompt de
   un rol cambió desde la última sync (por un `apply` real, o por el cockpit), hay que correr esta skill
   de nuevo antes de que el editor deje de mostrar un default viejo.
2. La rama **"Snarf - Executive Board"** (overview: un `noOp` por rol con su receta real + un link hacia
   su propio editor de arriba).
3. **"Snarf - Turno en vivo"** (Fase 24, ADR 0166) — el canvas que se ilumina en vivo mientras Snarf
   procesa un turno real, alimentado por `snarf/telemetry/n8n_live_canvas_sink.py`. A diferencia de 1 y 2
   (disparados a mano con "Test workflow"), este workflow necesita quedar **activo** de verdad — la sync
   lo activa con un ciclo real desactivar→activar (hallazgo de la Fase 23: dejarlo en `active` sin ese
   ciclo no siempre re-registra el webhook en esta versión de n8n).

## Antes de correr

1. Confirmá que Colima + el contenedor `snarf-n8n` están corriendo: `docker ps | grep snarf-n8n`. Si no,
   avisá al fundador — no lo arranques vos sin confirmar (ver CLAUDE.md, gotcha de TCC de Colima/Docker).
2. Confirmá que `N8N_API_KEY` está en el entorno (`.env` o exportada). Si falta, pedile al fundador que la
   genere en `http://127.0.0.1:5678` → Settings → n8n API (mismo paso a paso que ADR 0154).
3. Confirmá que `n8n_workflows/ids.json` tiene `agent_edit` con los 7 roles — si es la primera vez,
   `sync_agent_edit_workflows()` los crea solo (`POST`), no hace falta nada manual antes.

## Correr la sincronización

```bash
.venv/bin/python -c "
from snarf.runtime.n8n_generator import sync_agent_edit_workflows, sync_executive_board, sync_live_turn_workflow
print(sync_agent_edit_workflows())
print(sync_executive_board())
print(sync_live_turn_workflow())
"
```

El primer paso reconstruye los 7 editores por rol (receta real vía `agent_registry.get_agent_recipe()`) y
el segundo, la rama de overview enlazándolos — siempre en ese orden, `sync_executive_board()` levanta
`RuntimeError` si a algún rol le falta su editor en `ids.json`. El tercero reconstruye y activa el canvas
en vivo — independiente de los otros dos, no requiere ningún orden particular respecto a ellos. Los tres
son idempotentes vía `PUT` contra la instancia real de n8n (`POST` solo si el id todavía no existe) —
correrlos sin cambios reales deja el mismo resultado, nunca crea duplicados.

**Para que el canvas en vivo reciba tráfico real** (no solo exista en n8n), además hace falta
`N8N_LIVE_CANVAS_ENABLED=1` en el entorno del server real (puerto 8002) — sin eso, `snarf/telemetry/
n8n_live_canvas_sink.py` ni se instala (mismo criterio no-op-seguro que el resto de los sinks de
telemetría). Si el fundador pide "prender" el canvas en vivo, confirmá primero que quiere sumar esa
variable al `.env` real y reiniciar el server (mismo criterio de confirmación que cualquier cambio al
server de producción, ver CLAUDE.md).

## Después de correr

Reportá al fundador en español: qué cambió (si hubo overrides de tools/routing/stages, o un `apply` real
reciente que motivó la sync, mencionalo), y recordale que la verificación visual final (abrir
`http://127.0.0.1:5678`, mirar el canvas) es manual — la API pública de n8n no permite confirmar el render
desde acá (mismo límite ya documentado en ADR 0154).

## Alcance actual

Solo la rama del Executive Board y sus 7 editores por rol (Fases 18/Prototipo E, ADR 0159/0164). Las otras
8 ramas de Specialists (agency/community/content/finance/productivity/research/sales/raíz) siguen editadas
a mano como en ADR 0154, con edición de texto únicamente (`Snarf - Editar prompt`) — si el pedido es sobre
esas ramas, avisá que ese generador todavía no existe en vez de intentar editar sus JSON a mano vos mismo.
