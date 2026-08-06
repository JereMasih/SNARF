# ADR 0129 — `morning_routine`: Especialista Cognitivo nuevo, no más tool-calling libre para la rutina del día

**Fecha:** 2026-08-06
**Estado:** Aceptado

## Contexto

Revisando en vivo la conversación real del fundador de esta misma jornada (14:31-14:43,
`data/episodic_memory.jsonl`, conv `c95c2bfb...`) contra `activity_log.jsonl`/`usage_log.jsonl` de esa
ventana exacta: al pedir "¿qué tenemos para hoy?", el Orchestrator (rol `orchestrator`, rutea a
`mlx_local_fast`/Qwen3-4B local) llamó `gmail_summarize_inbox` + `calendar_brief`, identificó
correctamente un correo de la Municipalidad de Córdoba como urgente (categorización real, solo por
snippet), pero nunca llamó `gmail_read_message` para leer su cuerpo. Al pedirle después el detalle de
ESE correo puntual, el modelo local inventó un `message_id` falso
(`168902345678901234567890` → error real de Gmail "Invalid id value"), inventó una tool inexistente
(`gmail_search`), agotó las 5 rondas de tool-calling del turno (`MAX_TOOL_ROUNDS`,
`openai_compatible_llm.py`) sin usar el id real que sí tenía disponible de una llamada exitosa a
`gmail_list_messages` en el medio, y terminó diciéndole al fundador que no podía acceder al correo.

Primer fix de esa misma ronda (no revertido acá): tool descriptions de `gmail_read_message`/
`gmail_summarize_inbox` reforzadas para que el modelo sepa de dónde sale un id válido y nunca lo
invente. Corrige el caso puntual, pero deja intacta la causa estructural: un modelo local de 4B
encadenando 3-5 tool calls en el orden correcto, en un turno con 88 tools disponibles, para llegar a
un resultado accionable — la clase de tarea en la que un modelo chico falla con más frecuencia.

Nota real de ADR 0103 (Fase I, rama Productivity, misma jornada de ayer): "Deliberadamente no se
construye una 'Morning Routine' wireada completa en esta ronda — el plan solo pedía la infraestructura
de scheduling en sí ... queda como el primer consumidor real futuro". Esta ADR es esa construcción.

## Decisión

`MorningRoutineSpecialist` (`snarf/specialists/productivity/morning_routine.py`) — mismo patrón
cache-first que `GmailDigestSpecialist`/`CalendarBriefSpecialist`, pero resuelve en **Python
determinístico** la parte que rompió en producción: qué correo leer completo y cuándo.

1. **Composición, no reemplazo**: toma `GoogleGmail`/`GoogleCalendar` directo (mismos primitivos que
   ya usan `GmailDigestSpecialist`/`CalendarBriefSpecialist`, no una dependencia entre Specialists —
   sin precedente real en el repo, cada uno construye desde sus propias Capacidades inyectadas).
   `gmail_summarize_inbox`/`calendar_brief` siguen existiendo tal cual para un pedido acotado a solo
   correo o solo agenda; sus descripciones ahora redirigen el disparador "¿qué tenemos para hoy?" a
   `morning_routine`.
2. **Dos llamadas LLM acotadas, nunca una cadena de tool-calling libre**:
   - *Clasificar*: listado real (con id real inline por correo) + agenda real → interpretación en
     Markdown + una línea `PRIORITY_IDS: id1, id2` (o `ninguno`) con los correos que ameritan leer el
     cuerpo completo.
   - *Sintetizar*: solo si hubo prioritarios — mismo texto de arriba + el cuerpo real (ya leído en
     Python, no por el modelo) de esos correos → versión final con detalle real en vez de la
     referencia genérica.
3. **La validación real, no la promesa de "nunca inventes un id"**: `_extract_priority_ids()` filtra
   cualquier id que el modelo haya escrito en `PRIORITY_IDS` contra el `set` real de ids devueltos por
   `gmail_list_messages` — un id inventado (exactamente el bug de esta misma jornada) se descarta en
   silencio, nunca llega a `self._gmail.read_message()`. `MAX_PRIORITY_READS = 5` pone además un tope
   duro a cuántos se leen de verdad, independiente de cuántos pida el modelo clasificador.
4. **Tool nuevo `morning_routine(force_refresh, max_messages, max_events)`** — mismo patrón
   cache-first que los otros dos; nodo nuevo `specialist_morning_routine` en el cerebro (un usuario
   mirando el grafo reconocería esto como algo distinto de los otros dos: junta ambos Y ya lee cuerpos
   reales, no una operación más de un nodo existente — protocolo de `brain.py`/ADR 0054).
5. **Deliberadamente NO expuesto vía MCP** (`snarf/mcp/tools.py`): su resultado incluye
   `priority_messages[].body` — contenido crudo personal, mismo motivo exacto por el que
   `gmail_read_message` ya está excluido del allowlist (el propio docstring del archivo: "se excluyen
   también los tools de lectura CRUDA de contenido personal").
6. **Rol nuevo `morning_routine` en `llm_routing.ROLES`** — default `mlx_local_fast`, mismo criterio
   que `calendar_brief`/`gmail_digest` (tarea acotada, modelo barato).

## Deliberadamente NO resuelto en esta ronda

- Disparo automático a una hora de reloj (`snarf/runtime/scheduler.py::next_run_at`, construido y
  probado en ADR 0103 pero todavía sin ningún consumidor real): esta ronda construye el Specialist
  invocable on-demand (tool real del Orchestrator), no una entrega programada sin que el fundador la
  pida. Sigue siendo el primer candidato real para usar ese helper.
- No reemplaza la posibilidad de que el Orchestrator lea un correo cualquiera fuera de la rutina
  matutina (ajeno a lo que `morning_routine` marcó como prioritario) — ese camino sigue siendo
  tool-calling libre, ahora con las descripciones reforzadas del fix anterior de esta misma ronda.

## Verificado

- 17 tests nuevos: `tests/test_morning_routine.py` (12, incluye el caso explícito de un id
  alucinado no presente en el listado real — regresión directa del bug de producción — y el tope de
  `MAX_PRIORITY_READS`), más cobertura de wiring en `tests/test_orchestrator.py` (4) y
  `tests/test_telemetry_detail.py` (1).
- 1034/1034 tests de la suite completa.

## Consecuencias

- La clase de bug diagnosticada esta misma jornada (id inventado, tool inexistente, rondas de
  tool-calling agotadas) queda estructuralmente imposible para el flujo de rutina matutina — no
  depende de que un modelo local de 4B razone bien una secuencia de varias tool calls en el mismo
  turno, porque esa secuencia ya no existe como tal desde su perspectiva: es una sola tool.
- Segundo skill real bajo `snarf/specialists/productivity/` (después de `calendar_brief`, ADR 0103) —
  primer caso del repo de un Specialist que compone dos fuentes de datos reales (Gmail + Calendar) en
  una sola interpretación.
