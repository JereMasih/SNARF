# ADR 0135 — Fase 1 de observabilidad: modelo de evento v2 + dispatcher in-process

**Fecha:** 2026-08-10
**Estado:** Aceptado

## Contexto

El fundador trajo tres documentos (una "Constitución" de sistema cognitivo, una guía de auditoría, y
un prompt de misión de 33 secciones) pidiendo evolucionar Snarf hacia un sistema observable, con
tablero visual en n8n, memoria semántica más rica, control de infraestructura para el fundador, y
arquitectura estilo Jarvis. Se auditó el código real (no los documentos aspiracionales) y se armó un
plan de 12 fases + tracks paralelos (ver plan aprobado). Esta ADR cubre la Fase 1: el modelo de evento
correlacionado y el dispatcher in-process que todas las fases siguientes (event bus con Redis, API de
introspección, n8n, cockpit del fundador) necesitan como base.

`TELEMETRY_SCHEMA.md` (Fase 0 del plan de HUD, previo) ya documentaba honestamente 3 gaps sin resolver:
`latencia_ms` ausente para llamadas de vendor puro, `estado="truncado"` nunca emitido (aunque el gap
#2 ya se había cerrado para Anthropic en una ronda posterior, confirmado al auditar el código real), y
ningún `event_id` de correlación entre `activity_log`/`usage_log`/el evento unificado. Esta ADR cierra
los tres.

## Decisión

**Correlación real, aditiva, sin infraestructura nueva.** Cada evento del esquema v2 (`snarf/telemetry/
events.py`) suma `schema_version=2`, `event_id`, `parent_event_id`, `trace_id`, `event_type`
(`workflow|agent|tool|llm`.`started`/`finished`/`failed`, más `vendor.finished`/`input.received` para
lo que no tiene ciclo de vida propio), `origin_pid` y `user_id` — los 14 campos v1 no cambian de
nombre/posición/significado. Un allowlist positivo (`LEGACY_EVENT_TYPES`, mismo criterio que
`snarf/mcp/tools.py::MCP_EXPOSED_TOOLS`) hace que los `event_type` nuevos queden invisibles por
default para `all_events()`/`recent()` — ningún consumidor existente (los 6 call-sites de `app.py`,
`cost_history`, `relevance`, `widget_summary`) tuvo que tocarse.

**`snarf/telemetry/context.py`: `threading.local()` → `contextvars.ContextVar`.** Motivo real, no
estilo: FastAPI corre handlers síncronos en un worker de threadpool que anyio SÍ copia (el
`contextvars.Context` del caller), pero `threading.local()` no propaga; y el fan-out de la
Inteligencia Ejecutiva (`ThreadPoolExecutor`) no hereda ninguno de los dos sin `contextvars.
copy_context()` explícito. De paso corrige un bug real ya presente: `_ResilientLLM.generate()`
(`llm_routing.py`) hacía `context.clear_llm_role()` en un `finally`, borrando a `None` en vez de
restaurar el rol del llamador — una llamada de Specialist anidada dentro de un turno de
`Orchestrator.handle()` (que ya seteó `llm_role="orchestrator"`) le borraba el rol al resto del turno.
Fix: `context.scoped_llm_role()`, basado en `Token.reset()` (restaura, nunca limpia a ciegas).

**Dos chokepoints reales, no noventa puntos de instrumentación dispersos.** `snarf/telemetry/spans.py`
(nuevo) abre un span (`start_tool`/`start_llm`/`start_workflow`/`start_agent`) y lo cierra
(`finish`/`fail`), resolviendo `nodo`/`agente` con la misma taxonomía de `brain.py` que ya usa
`events.py` — un tool/vendor sin nodo mapeado devuelve `NULL_SPAN` y ni el `.started` ni el
`.finished`/`.failed` se emiten (drop simétrico, nunca un evento huérfano).

- **Chokepoint A** — `Orchestrator._handle_tool` (`snarf/core/orchestrator.py`): abre `tool.started`,
  envuelve la ejecución del handler en `with spans.active(span)` (así cualquier llamada LLM que el
  handler dispare adentro queda parentada a este tool call automáticamente, sin que el Specialist
  sepa nada de spans — cierra el gap #3 de `TELEMETRY_SCHEMA.md`), cierra con
  `tool.finished`/`tool.failed` vía `activity_log.record(..., span=span)`.
- **Borde de turno** — `Orchestrator.handle()`: `spans.start_workflow("turn", ...)` es la raíz de la
  traza (`trace_id = event_id` de este span) — todo lo que pase dentro (tools, LLM, board ejecutivo)
  comparte esa traza. `generate_conversation_title()` recibe el mismo tratamiento (traza propia,
  independiente del turno de chat que la disparó como background task).
- **Chokepoint B, por vendor** — `AnthropicLLM._create_and_record` (nuevo, colapsa los 3 call sites
  reales de `_create()` en uno), `OpenAICompatibleLLM._complete_once` (ya era un chokepoint real, se
  le agrega el span alrededor), `GeminiLLM.generate` (único call site). Los tres abren `llm.started`,
  cierran con `llm.finished`/`llm.failed` vía `usage_tracker.record_*_call(..., span=span)`. Edge case
  cubierto en los tres: si `usage` viene `None` (solo visto en tests con fakes incompletos), el span
  se cierra igual a mano — nunca queda un `.started` sin su cierre.
- **Inteligencia Ejecutiva** (`snarf/executive/specialist.py`): `consult()` abre un
  `workflow.started("executive_board")`; cada rol corre en su propio `_consult_one` con
  `agent.started`/`agent.finished`/`agent.failed`. Bug real encontrado y corregido en el mismo cambio:
  un `Context` de `contextvars` copiado una sola vez y reusado en los N `pool.submit()` revienta
  ("cannot enter context: already entered") porque `Context.run()` no es reentrante entre threads —
  cada rol necesita su propia copia (`contextvars.copy_context()` llamado DENTRO del loop, no una vez
  afuera).
- **Límite de proceso real** (`snarf/executive/process.py` + `mcp_server.py`): el subproceso MCP de
  cada rol no hereda `contextvars` — `StdioServerParameters.env=context.env_for_child_process()`
  (mergea con el allowlist default del SDK de MCP, nunca lo reemplaza) propaga `SNARF_TRACE_ID`/
  `SNARF_PARENT_EVENT_ID`; `mcp_server.py::main()` los adopta con `context.adopt_from_env()`. Diccionario
  vacío/no-op cuando no hay traza activa — nunca se inventa una.

**Dispatcher in-process** (`snarf/telemetry/dispatcher.py`, nuevo): pub/sub con `queue.Queue` (nunca
`asyncio.Queue` — hay publishers sin ningún event loop: `main.py`, `mcp_server.py`, el
`ThreadPoolExecutor` de la Ejecutiva) + un worker thread. `events._emit()` reemplaza el `_write()`
directo: escribe a JSONL primero, síncrono (piso real de durabilidad, sin cambios), y recién después
publica al dispatcher — que nunca bloquea ni levanta hacia el llamador (un subscriber roto o lento no
puede tumbar un turno real; cola acotada, descarta el evento nuevo si está llena). Hoy no tiene
consumidores reales más allá de los tests — es la base sobre la que la Fase 2 (Redis Streams opcional)
va a colgar un sink adicional sin tocar este módulo.

## Riesgos/trade-offs

1. **`telemetry_events.jsonl` crece más rápido** (cada `.started` es una fila nueva, además de su
   `.finished`/`.failed`) — a los ~200 eventos/día actuales, irrelevante; se revisita si el volumen
   cambia (ver Fase 2 del plan, SSE reduce además el polling que hoy re-lee el archivo entero en 6
   endpoints).
2. **Un `event_type` nuevo (`llm.failed`) queda en el allowlist legacy** aunque antes una llamada LLM
   fallida no emitía nada — cambio de comportamiento deliberado (recuperación honesta de una señal de
   error que antes era invisible en el HUD), documentado acá en vez de ocultado.
3. **`spans.py`/`dispatcher.py` no tienen consumidores reales todavía** — quedan listos para la Fase 2,
   sin uso productivo inmediato más allá de la correlación ya visible en `telemetry_events.jsonl`.

## Verificado

- 38 tests nuevos: `tests/test_telemetry_dispatcher.py` (8), `tests/test_telemetry_spans.py` (7),
  extensión de `tests/test_telemetry_context.py` (+10: `scoped_llm_role`, `span()` anidado,
  `env_for_child_process`/`adopt_from_env`, aislamiento real entre `asyncio.Task`, propagación real
  vía `contextvars.copy_context()` a un `ThreadPoolExecutor`), `tests/test_telemetry_events.py` (+7:
  `schema_version`/`event_id`/`origin_pid`, `event_type` correcto por status, `include_lifecycle`,
  fila v1 sin `event_type` tratada como legacy), `tests/test_orchestrator.py` (+3: ciclo de vida real
  de `_handle_tool`, tool fallido emite `tool.failed`, una llamada LLM abierta dentro de un handler
  queda parentada al tool span real), `tests/test_anthropic_llm.py` (+3: un round real emite
  exactamente un `llm.started`+`llm.finished` con el mismo `event_id`, `usage=None` cierra el span
  igual, un error real del cliente cierra el span como `llm.failed` y re-lanza la excepción).
- 1132/1132 tests de la suite completa (`.venv/bin/python -m pytest -q`), incluidos los dos tests de
  cache breakpoint de `anthropic_llm.py` (CLAUDE.md los marca como no-tocar) y los 6 endpoints de
  dashboard de `test_app.py` — misma forma/conteo que antes de esta fase, sin ningún cambio de código
  en `app.py`, `brain.py`, `verbs.py`, `relevance.py`, `cost_history.py`, `detail.py` ni `web/index.html`.
