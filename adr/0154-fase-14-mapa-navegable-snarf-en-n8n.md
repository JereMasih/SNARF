# ADR 0154 — Fase 14: mapa navegable de Snarf en n8n

**Fecha:** 2026-08-12
**Estado:** Aceptado

## Contexto

Pedido del fundador: no los dos workflows simples de `n8n_workflows/` (ver/editar prompts), sino una
representación completa y navegable de la arquitectura real de Snarf en n8n — Orchestrator con todos los
agentes/skills debajo, poder entrar (drill-down) a cada rama, ver su contenido, y editar cada nodo con
`prompt_id` desde ahí. Bloqueado en la ronda anterior por falta de una API key de n8n (ver
`ROADMAP_OBSERVABILIDAD_MULTIUSUARIO_N8N.md`, Fase 14, y el plan detallado en
`~/.claude/plans/effervescent-wandering-hammock.md`). El fundador generó la key y la pasó esta ronda.

## Decisión

**Jerarquía real reflejada, no inventada:** la taxonomía usada es la misma que ya existe en
`snarf/telemetry/brain.py` (`NODE_PARENT`/`NODE_TIER`) y en `snarf/specialists/` — 13 Specialists
agrupados en 7 carpetas (`agency/community/content/finance/productivity/research/sales`) + 4 en la raíz
(`gmail_digest`, `dashboard_curator`, `project_manager`, `skill_factory`), más Executive Board como rama
separada con 7 sub-roles. Nunca se creó una segunda jerarquía en paralelo.

**Estructura de workflows (13 en n8n, todos importados y verificados vía API real, IDs en
`n8n_workflows/ids.json`):**

- `Snarf - Mapa` (raíz): un nodo `noOp` "Orchestrator" (informativo) + un `executeWorkflow` por cada una
  de las 9 ramas + acceso directo a `Snarf - Ver prompts` / `Snarf - Editar prompt`.
- 9 workflows de rama (`Snarf - Specialists (raiz|agency|community|content|finance|productivity|
  research|sales)`, `Snarf - Executive Board`): un nodo `noOp` por Specialist/rol real, con `notes` +
  `notesInFlow: true` (visible en el propio canvas sin abrir el nodo) describiendo su `prompt_id` real
  (o por qué no tiene uno), y — solo si tiene `prompt_id` editable — un `executeWorkflow` contiguo hacia
  `Snarf - Editar prompt`.
- **Reutilización deliberada, no una segunda implementación:** ningún nodo hoja es un mini-workflow nuevo
  por `prompt_id` — los ~24 nodos "editar" de las 9 ramas apuntan todos al mismo `Snarf - Editar prompt`
  ya construido (Fase 9.3), que ya lista los 27 `prompt_id` reales en un dropdown. El "drill-down" que
  pidió el fundador es real (clic → entra a la rama → ve el Specialist puntual → clic → entra a editar),
  pero la superficie de edición sigue siendo una sola, igual que `/n8n/prompts` es la única superficie de
  escritura real en el backend.
- **Gaps marcados explícitamente, nunca simulados:** `SkillFactory` (meta-prompt con guardrails, ver ADR
  0153), `CommunityPulseSpecialist` y `MonthlyPnlSpecialist` (determinísticos, sin LLM) tienen nodo `noOp`
  con `notes` explicando por qué no hay nodo "editar" contiguo — no se ofrece una edición que no existe.

**Autenticación real hacia Snarf:** credencial `httpHeaderAuth` nueva en n8n (`Snarf n8n token`, header
`X-Snarf-Token`, valor = `N8N_CONTROL_TOKEN` de `.env`) creada vía la misma API — reemplaza el credential
id vacío que traían `snarf_ver_prompts.json`/`snarf_editar_prompt.json` desde la ronda anterior (esos dos
archivos en el repo se mantienen con id vacío a propósito, son la plantilla portable; el id real vive solo
en la instancia de n8n de esta Mac).

## Verificado

- Los 13 workflows se crearon vía `POST/PUT https://127.0.0.1:5678/api/v1/workflows` real (API key nueva)
  y se confirmaron con `GET` de vuelta — conteo de nodos y de conexiones del árbol completo sin targets
  huérfanos (`Snarf - Mapa` fan-out desde "Empezar" resuelve los 12 nodos hijos, cero `missing targets`).
- La llamada HTTP real que hace cada nodo "editar"/"ver prompts" (`GET/PUT http://host.docker.internal:8002
  /n8n/prompts...` con header `X-Snarf-Token`) se probó de punta a punta contra el server real de
  producción (puerto 8002) **desde dentro del contenedor `snarf-n8n`** (`docker exec ... wget
  --header="X-Snarf-Token: ..." http://host.docker.internal:8002/n8n/prompts` → 200 con el JSON real de
  prompts) — no solo desde la Mac.
- **Pendiente real, no verificado esta ronda:** la ejecución del *trigger* de cada workflow (manual
  trigger / form trigger) dentro de la UI de n8n — la API pública de n8n (edición community) no expone un
  endpoint para disparar una ejecución de un workflow con manual/form trigger, solo `POST /workflows` para
  crear/actualizar. Queda para cuando el fundador entre a la UI (`http://127.0.0.1:5678`) y haga clic en
  "Test workflow" sobre `Snarf - Mapa` al menos una vez — la parte que sí se pudo probar de verdad (la
  llamada HTTP subyacente) es la que tenía riesgo real de estar mal configurada (URL/header/credential).

## Consecuencias

- `n8n_workflows/` pasa de 2 a 12 archivos versionados en git (`snarf_mapa.json`, `snarf_ver_prompts.json`,
  `snarf_editar_prompt.json`, `branches/snarf_specialists_*.json` ×9) + `ids.json` (IDs reales asignados
  por esta instancia de n8n — no portable a otra instancia, es un registro de estado, no una plantilla).
- Cualquier Specialist nuevo que se agregue a futuro (protocolo de crecimiento del cerebro, `CLAUDE.md`)
  debería sumar su nodo `noOp` a la rama correspondiente en el mismo cambio — mismo principio que ya rige
  `brain.py`, extendido acá.
- Si a futuro n8n Enterprise/una versión más nueva expone un endpoint real de "run" en la API pública, vale
  la pena reabrir la verificación de ejecución end-to-end sin depender de un clic manual del fundador.
