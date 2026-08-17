# ADR 0165 — Project Manager y áreas como etapas reales del pipeline

**Fecha:** 2026-08-14
**Estado:** Aceptado

## Contexto

El fundador quiere ver, en un canvas de n8n, un turno real de Snarf procesándose en vivo: Orquestador →
Junta Directiva → Project Manager → área → especialista, con doble click para entrar al detalle de
cualquier etapa. Antes de construir esa visualización (Fase 24, ADR futura), se investigó el pipeline real
del Orchestrator y se confirmó que **esas etapas no existen hoy**: el flujo real es `turn` → (a veces)
`executive_board` (7 roles) → y por separado, llamadas planas de herramienta directo bajo `turn`
(`Orchestrator._handle_tool`, sin ninguna etapa intermedia de Project Manager ni de área). El módulo
`snarf/specialists/project_manager.py` que ya existe es otra cosa (administra carpetas de Proyecto en
Drive), no un router entre etapas.

Ante ese hallazgo, el fundador confirmó explícitamente (Principio VI, FOUNDATION.md — nunca visualizar
como real algo que el código no hace) que el orden correcto es reestructurar el Orchestrator primero, y
recién después construir el canvas. Confirmó también dos decisiones de diseño:

- **Project Manager es un router real**: dado el trabajo de un turno, decide a qué área(s) corresponde.
- **Las 4 áreas del boceto (Operaciones, Administración, I+D, Marketing) reagrupan los 7 dominios de
  Specialists que ya existen** (agency, community, content, finance, productivity, research, sales) — no
  se construyen especialistas nuevos.

## Decisión

**Mapeo área ↔ dominio**, verificado leyendo qué hace cada Specialist de verdad (no solo el nombre del
dominio) — nuevo módulo puro **`snarf/runtime/areas.py`**:

| Área | Dominios que agrupa | Tools reales |
|---|---|---|
| Administración | finance | `finance_books_categorize`, `finance_monthly_pnl` |
| I+D | research | `research_deep_dive`, `research_trend_scan`, `research_competitor_watch` |
| Marketing | content, community | `content_write_blog_post`, `content_write_social_post`, `content_write_newsletter`, `community_pulse`, `community_post_message` |
| Operaciones | agency, productivity (2 specialists: `calendar_brief`/`morning_routine`), sales | `agency_client_status`, `calendar_brief`, `morning_routine`, `sales_sponsor_inbox_triage` |

`sales` cae en Operaciones (triage de inbox, tarea operativa) — no encaja mejor en ninguna de las otras
tres. El directorio `productivity/` tiene dos Specialists con dos `domain` distintos
(`calendar`, `productivity`, ver `snarf/telemetry/brain.py::TOOL_TO_NODE`), ambos a Operaciones por
directorio, no por el valor exacto de `domain`. `area_for_tool(tool_name) -> str | None` es un lookup
determinístico puro — 14 tools cubiertas, todo lo demás (Executive Board, Drive/Gmail/Calendar/Skill
Factory, etc.) sigue devolviendo `None`, sin ruteo de área, sin cambios de comportamiento.

**Ruteo real, sin teatro — deliberadamente NO una clasificación por LLM.** El área se deriva de la propia
tool que el Orchestrator ya decidió llamar, nunca de una segunda lectura de la síntesis del board. Un
clasificador por LLM podría discrepar de la tool real a punto de ejecutarse, generando telemetría que
miente sobre lo que pasó (Principio VI). Cuando la Junta Directiva sí fue consultada antes en el mismo
turno, queda anotado como contexto auditable — nunca decide el área. Nuevo `ContextVar` en
`snarf/telemetry/context.py` (`set_board_consulted`/`get_board_consulted`/`clear_board_consulted`), mismo
ciclo de vida ya real de `conversation_id`/`user_id` (seteado al entrar a `Orchestrator.handle()`, limpiado
en su `finally`).

**Dos spans `workflow` nuevos, mismo `kind` que `turn`/`executive_board` (no un 5to valor de
`Span.kind`)** — `spans.py` solo tiene 4 kinds reales (`workflow`/`agent`/`tool`/`llm`); inventar uno
nuevo para esto no compra nada que `skill` no resuelva ya (mismo patrón: `turn` y `executive_board`
son ambos `kind="workflow"`, distinguidos solo por `skill`):

- `spans.start_workflow("project_manager", detalle=f"tool={name} area={area_id}")`.
- `spans.start_workflow(f"area:{area_id}")`, anidado adentro.

Cambio real en `Orchestrator._handle_tool` (`snarf/core/orchestrator.py`): antes de llamar al handler,
`area_id = areas.area_for_tool(name)`. Si es `None`, camino sin cambios (la mayoría de las tools). Si no,
la llamada queda envuelta: `project_manager` cierra apenas decide el área (su trabajo real es ese lookup,
nada más — no fingir un span "vivo" haciendo algo que no hace) mientras sigue siendo el padre ambiente
(`context.span()` solo libera el ambiente al salir del `with`, así que abrir `area_span`/el `tool` span de
siempre DESPUÉS de `finish(pm)` igual los anida correctamente bajo `pm`). El `tool.started/finished` de
siempre queda ahora anidado dentro del área en vez de directo bajo `turn`. `_handle_tool` original se
extrajo tal cual a `_handle_tool_span` (sin cambios de lógica), reusado por ambos caminos.

`spans.finish()` ganó un parámetro `attributes` (ya soportado por `events.record_lifecycle_event`, solo no
se exponía) — usado para que el `workflow.finished` de `project_manager` registre `{area, tool,
board_consulted}` de forma estructurada.

**Cerebro/giroscopio (`snarf/telemetry/brain.py`) — deferido a propósito, no en silencio.** `turn`/
`executive_board` (mismo `kind="workflow"`) ya no se visualizan hoy como nodos del giroscopio —
`snapshot()` solo trata especial `agent.*`, nunca `workflow.*`. Project Manager/área heredan ese mismo
comportamiento (invisibles en el giroscopio) sin trabajo extra. Esto es una excepción explícita a la regla
de crecimiento del cerebro (`brain.py:6-47`: "cualquier funcionalidad nueva real... se incorpora al cerebro
como parte de construirla") — se documenta acá en vez de omitirse. Sumarlos al giroscopio queda como
follow-up real si el fundador lo pide, no bloqueante para esta fase ni para la Fase 24 (canvas de n8n, que
consume estos mismos eventos por otro camino).

## Verificado

- 11 tests nuevos: `tests/test_areas.py` (5, cobertura completa de la tabla + valores correctos + `None`
  fuera de las 4 áreas), `tests/test_orchestrator.py` (4, anidado real de spans para una tool ruteada, cero
  spans nuevos para una no ruteada, `attributes` correctos, `board_consulted` real cuando el board fue
  consultado antes en el turno), `tests/test_telemetry_context.py` (2, roundtrip del `ContextVar` nuevo).
- 1399/1399 tests de la suite completa (`.venv/bin/python -m pytest -q`), 1388 previos (post ADR 0164) + 11
  nuevos de esta ronda.
- Riesgo de hot path, explícito: `_handle_tool` es el chokepoint de cada tool call de cada turno real — el
  cambio agrega un lookup de diccionario siempre, y 4 escrituras síncronas más a JSONL solo para las 14
  tools ruteadas (de 2 a 6 por llamada). Sin I/O de red nuevo en este camino — los POSTs a n8n del sink
  existente siguen 100% async, sin cambios acá.
- Pendiente real, siguiente fase: verificar contra el server real (turno real con una tool ruteada,
  confirmar en `data/telemetry_events.jsonl` los `workflow.started/finished` de `project_manager`/`area:*`
  bien anidados) — mismo estándar de honestidad que ADR 0164 (no alcanza con que los tests pasen).
