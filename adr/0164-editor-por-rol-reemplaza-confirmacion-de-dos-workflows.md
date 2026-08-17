# ADR 0164 — Editor por rol (Prototipo E) reemplaza la confirmación de dos workflows separados

**Fecha:** 2026-08-13
**Estado:** Aceptado

## Contexto

ADR 0160 (Fase 19) implementó la categoría (b) de ADR 0156 — escritura confirmada por el fundador en
vivo — con **dos workflows separados** (`Snarf - Proponer cambio de agente` → el fundador copia el
`change_id` real al segundo → `Snarf - Confirmar cambio de agente`). Esa ADR ya dejaba anotado el motivo:
no se pudo verificar en esa sesión el patrón nativo de formularios multi-página de n8n contra una instancia
real, así que se optó por el patrón más simple y ya probado.

ADR 0162 (Fase 21) verificó la mitad `propose` de ese ciclo contra n8n real, pero **deliberadamente no
corrió `apply`** — no valía la pena mutar un agente de producción solo para probar el endpoint. El primer
`apply` real de este camino quedó pendiente.

El 2026-08-12/13, iterando en vivo con el fundador sobre la UX del mapa de n8n (ver "Iteración de UX de
n8n con el fundador" en `ROADMAP_OBSERVABILIDAD_MULTIUSUARIO_N8N.md` para las ~5 rondas de prototipo, cada
una con un hallazgo real — B/C, D descartado, E), el fundador pidió explícitamente que aplicar un cambio
**no requiera una confirmación en un segundo workflow aparte**: "estoy haciendo las cosas yo, no es
necesario confirmar otra vez". Esto es una enmienda directa al diseño de superficie de ADR 0160 (no a su
protocolo `propose`/`apply` en sí, que sigue intacto — ver más abajo).

## Decisión

**Un único workflow por rol** (`Snarf - Editar <Rol>`, 7 en total — uno por cada rol del Executive Board),
en vez de dos workflows genéricos compartidos. Cada uno con:

- Un único trigger manual (el botón "Test workflow" de arriba del canvas) — lección real del Prototipo D,
  descartado porque con varios triggers compartiendo un canvas no había forma inequívoca de correr "solo
  este rol" con ese botón.
- Un nodo `Set` con los valores reales actuales (prompt, provider/modelo, un booleano por cada tool MCP
  posible) como default editable.
- `Proponer` → `Aplicar`, **encadenados en el mismo workflow** — un solo gesto real del fundador (editar
  el `Set` + apretar "Test workflow") corre el ciclo completo `propose`→`apply`.

**Lo que NO cambia — ADR 0156/0160 siguen vigentes en lo demás:**

- El protocolo `propose`/`apply` en sí (optimistic locking contra el `baseline`, TTL de 15 minutos,
  `StaleChangeError` → 409) no se toca — sigue siendo `snarf/runtime/agent_change_proposals.py`, sin
  cambios de código en esta ADR.
- La categoría (b) de ADR 0156 sigue exigiendo que sea el propio fundador, mirando la UI de n8n en el
  momento, quien dispare el cambio — eso no cambió. Lo que cambió es la forma de la confirmación: en vez
  de "revisar un diff en un workflow, copiar un `change_id`, confirmarlo en otro", ahora es "editar los
  valores reales ya precargados en un `Set`, apretar un botón" — sigue siendo una acción humana directa y
  deliberada (Artículo VII, Prueba de Alto Impacto), no una escritura de un clic sobre un formulario
  genérico sin contexto.
- `Orchestrator._handle_tool()` sigue siendo el único motor de ejecución real — n8n sigue sin decidir nada
  por su cuenta, solo dispara la escritura a los registros versionados (invariante de ADR 0156, sin
  cambios).

**Retirado:** `Snarf - Proponer cambio de agente` (`lc8o7tp6vqcvUA0Q`) y `Snarf - Confirmar cambio de
agente` (`qANAzKhGCULNwFxq`) — borrados de la instancia real de n8n. Nunca tuvieron un `apply` real
disparado por el fundador (ver ADR 0162): el primer `apply` real de este camino completo terminó siendo el
de hoy, ya con el patrón nuevo. Sus exports estáticos (`n8n_workflows/snarf_proponer_cambio_agente.json`,
`snarf_confirmar_cambio_agente.json`) se borraron del repo. El mapa raíz (`Snarf - Mapa`,
`LmND41v00r1kG4dN`) tenía un link directo a cada uno — se quitaron esos dos nodos y su conexión desde
"Empezar"; `n8n_workflows/snarf_mapa.json` se regeneró desde el estado real para que el export no mienta.

**Generador movido de script suelto a módulo real:** el Prototipo E vivía en
`n8n_workflows/_prototype_e_editar_agente.py`, un script standalone no testeado. Se migró a
`snarf/runtime/n8n_generator.py` (Fase 18, ADR 0159) — `build_agent_edit_workflow(role)` (pura, testeable
sin red) + `sync_agent_edit_workflows()` (con red, idempotente, persiste en `n8n_workflows/ids.json` bajo
la clave nueva `agent_edit`). El script de prototipo se borró.

**"Snarf - Executive Board" pasa de superficie de edición a superficie de overview + navegación:**
`build_executive_board_workflow()` ahora requiere `agent_edit_workflow_ids` (los 7 ids de arriba, no un
único `editar_prompt_workflow_id` genérico) y enlaza cada `noOp` de rol a su propio editor dedicado
(`Editar CTO`, `Editar COO`, etc.) en vez del editor de texto genérico de ADR 0154. Ese editor genérico
(`Snarf - Editar prompt`) sigue existiendo y sigue siendo el camino real para las 8 ramas de Specialists,
que no tienen (todavía) receta completa vía `agent_registry` — ver alcance honesto en el docstring de ese
módulo, sin cambios acá.

**Límite real, ya conocido, que se mantiene sin resolver esta ronda:** el `Set` de cada editor por rol
queda con los valores fijos en el momento en que se generó — si el prompt/tools/routing de ese rol cambia
después (por un `apply` real posterior, o por el cockpit), el editor va a mostrar un default viejo hasta
que se corra `sync_agent_edit_workflows()` de nuevo. Esto es el mismo límite que ya tenía el canvas de
overview desde el incidente del 2026-08-12 (regeneración automática tras un `apply` desactivada a
propósito, ver nota en `app.py::n8n_apply_agent_change` — sospecha de acoplamiento reentrante n8n↔Snarf,
nunca confirmada con certeza pero la mitigación se mantiene). La Skill `n8n-map-sync` queda actualizada
para cubrir ambas superficies (los 7 editores + el overview) y documentar que hay que correrla después de
un `apply` real.

## Verificado

- **Primer `apply` real de este camino completo, hoy, contra producción:** el fundador abrió
  `Snarf - Editar CTO` (`K74wbPPll8HOKB19`) y apretó "Test workflow". Confirmado del lado del server real
  (no solo por la UI de n8n, mismo criterio de honestidad que ADR 0139/0154/0162): `POST
  /n8n/agent/cto/propose` → 200 y `POST /n8n/agent/cto/apply` → 200 en el mismo instante
  (`2026-08-13 22:23:45`), ejecución de n8n `2844` (`mode: manual`, `status: success`), y `GET
  /n8n/agent/cto` posterior confirma el prompt del CTO en versión 2 activa. El `change_id` no quedó
  reusable (el ciclo lo consume, mismo comportamiento ya cubierto por los tests de ADR 0160).
- 14 tests en `tests/test_n8n_generator.py` (10 originales, actualizados a la firma nueva de
  `build_executive_board_workflow()` + 4 nuevos de `build_agent_edit_workflow`/
  `sync_agent_edit_workflows`) — cero llamadas de red, mismo patrón de aislamiento que ya usaba el archivo.
- Regeneración real corrida contra la instancia real de n8n tras el cambio de código:
  `sync_agent_edit_workflows()` + `sync_executive_board()` — ambas `PUT` sobre los ids ya existentes
  (mismos 7 ids del Prototipo E + `3Qewxl21NTY4Q9LO`), confirmado idempotente (cero duplicados). Leído de
  vuelta vía la API real: los 7 nodos "Editar `<Rol>`" del canvas de overview apuntan a los ids correctos.
- 1388/1388 tests de la suite completa (`.venv/bin/python -m pytest -q`), 1384 previos (post ADR 0163) + 4
  nuevos de esta ronda.
