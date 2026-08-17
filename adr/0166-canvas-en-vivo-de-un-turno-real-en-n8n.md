# ADR 0166 — Canvas en vivo de un turno real en n8n

**Fecha:** 2026-08-14
**Estado:** Aceptado

## Contexto

ADR 0165 (Fase 22) dejó el pipeline real de Snarf con etapas reales (Project Manager, área) que antes no
existían — prerrequisito explícito que pidió el fundador antes de visualizar nada (Principio VI,
FOUNDATION.md: no fingir en un canvas algo que el código no hace). Con eso hecho, esta ADR cierra el pedido
original: ver un turno real de Snarf procesándose EN VIVO dentro del canvas de n8n — no un mapa estático
(lo que ya existía, ADR 0154/0159/0164), sino nodos que se iluminan a medida que Snarf realmente los
ejecuta, para TODO turno real (sin acotar a "solo cuando el fundador quiere mirar") — y doble click sobre
cualquier nodo para ver el detalle real de esa etapa.

## Investigación real antes de escribir el generador (Fase 23, spike)

Se armaron y borraron varios workflows descartables (`ZZZ-spike-*`) contra la instancia real de n8n para
verificar mecánica que la documentación no dejaba clara del todo. Resultado, con dos rondas reales
(la primera con hallazgos incompletos, la segunda con el propio fundador armando el patrón a mano en la UI
como control real — ver el detalle completo en "Sesión 2026-08-14" de
`ROADMAP_OBSERVABILIDAD_MULTIUSUARIO_N8N.md`):

- Un nodo `Webhook`/`Wait` creado vía la API pública de n8n necesita un campo `webhookId` (UUID) explícito
  en el nodo — sin eso, n8n nunca lo registra de verdad para tráfico real, aunque el workflow quede
  `active: true`.
- Un nodo `Wait` con `resume: "webhook"` necesita `httpMethod: "POST"` explícito si el resume va a mandar
  payload por POST (default: GET).
- `GET /api/v1/executions` (endpoint de LISTA) no devuelve ejecuciones en estado `waiting` en esta versión
  de n8n (1.121.0) — pero `GET /api/v1/executions/{id}` (por ID directo) sí funciona. Irrelevante para el
  diseño real: nunca hace falta listar, el `execution_id` se captura directo de la respuesta del trigger.
- La URL de resume es 100% predecible: `{n8n_base}/webhook-waiting/{execution_id}` — no hace falta leer
  `$execution.resumeUrl` desde dentro del workflow.
- `EXECUTIONS_DATA_SAVE_ON_PROGRESS=true` se activó en `docker-compose.n8n.yml` (default de n8n es
  `false`) — necesario para que una ejecución en curso sea consultable por ID mientras espera.
- **Ciclo completo verificado real de punta a punta:** trigger → `[{"executionId": "..."}]` en la
  respuesta → POST a la URL de resume construida solo con ese id → la ejecución real pasa de `waiting` a
  `success`.

## Decisión

**`snarf/runtime/n8n_generator.py::build_live_turn_workflow()`** (nueva función pura, mismo patrón que
`build_agent_edit_workflow()`): `Webhook (responseMode: responseNode, webhookId fijo)` → `Code` (captura
`$execution.id`) → `Respond to Webhook` (lo devuelve en el body) → `LIVE_TURN_STAGE_COUNT` (5) nodos `Wait`
encadenados ("Etapa 1".."Etapa 5"), cada uno con `webhookId` fijo propio, `httpMethod: POST`, y un timeout
real (`LIVE_TURN_STAGE_TIMEOUT_MINUTES` = 10 minutos) — nunca esperan para siempre si el turno se cae a
mitad de camino. `sync_live_turn_workflow()` la empuja (`push_workflow()` ya existente), persiste el id en
`n8n_workflows/ids.json` (clave `live_turn`), y activa el workflow con un ciclo real
desactivar→activar (hallazgo de la Fase 23: dejarlo en `active` sin ese ciclo no siempre re-registra el
webhook).

**Etapas genéricas ("Etapa N"), no nombres fijos ("Junta Directiva"/"Project Manager"/"área") —
deliberado, no un recorte de alcance silencioso.** Un turno real no siempre consulta a la Junta Directiva,
no siempre rutea una tool a un área, y puede rutear más de una en el mismo turno — forzar esos nombres fijos
en el canvas mentiría sobre turnos que no pasan por ahí (mismo principio que ya citó ADR 0165 para no fingir
etapas que el código no ejecuta). El contenido real de cada etapa (qué pasó de verdad — `skill`,
`event_type`, `attributes`) viaja en el payload del resume, visible con doble click sobre el nodo ya
avanzado en la propia UI de n8n — eso es lo que el fundador pidió ver, no una forma fija adivinada de
antemano. Con 5 etapas como techo: turnos más simples avanzan menos nodos (sobra canvas, sin daño real);
turnos con más eventos de los que hay nodos igual **siempre terminan de verdad** — el cierre real del turno
(`workflow.finished`/`failed` de `skill="turn"`) se manda como el próximo resume disponible sea cual sea,
así que el turno nunca queda "colgado" en el canvas aunque haya tenido más etapas reales que huecos.

**`snarf/telemetry/n8n_live_canvas_sink.py`** (nuevo módulo, no una edición de `n8n_webhook_sink.py` — ese
sink no tiene estado, manda cada evento a una URL fija; este necesita recordar, por `trace_id`, en qué
ejecución de n8n está esperando el próximo evento de ESE turno). Suscripto ASYNC al dispatcher, filtrado a
los 12 tipos de evento de ciclo de vida reales (`workflow.*`/`agent.*`/`tool.*`/`llm.*` × started/finished/
failed — no todo lo que pasa por el dispatcher, solo lo que tiene `trace_id` real). Comportamiento:

- `workflow.started` de `skill="turn"` con un `trace_id` nuevo → dispara una ejecución real nueva en n8n,
  guarda `{execution_id, stage: 0, updated_at}`.
- Cualquier otro evento de ciclo de vida con un `trace_id` ya conocido → avanza esa ejecución un nodo
  `Wait` (hasta el techo de 5), incrementa `stage`.
- El cierre real del turno libera el estado local apenas se manda el resume, sea cual sea la etapa en la
  que haya caído.
- Barrido de limpieza por edad máxima (alineada al mismo timeout real del `Wait`, 10 minutos) — sin thread
  nuevo, corre en cada evento entrante, mismo criterio "chequeo barato salvo que importe" ya usado en
  `orchestrator.py`.
- Cualquier falla (n8n caído, error de red, `trace_id` desconocido) se traga y se cuenta en `health()`,
  nunca se propaga — mismo criterio de resiliencia que `n8n_webhook_sink.py` y el resto del dispatcher
  (`dispatcher.py`: "un subscriber roto nunca puede tumbar un turno real").
- Activación explícita por variable de entorno nueva (`N8N_LIVE_CANVAS_ENABLED`), no automática — el
  workflow real tiene que existir en n8n primero (`sync_live_turn_workflow()`, o la Skill n8n-map-sync).

**Hallazgo real adicional, encontrado en la verificación de punta a punta (no en el spike):**
`responseMode: "responseNode"` puede devolver el `execution_id` real ANTES de que la ejecución termine de
llegar/pausarse en el primer nodo `Wait` — un turno real con varias tools ruteadas dispara sus eventos de
telemetría casi instantáneamente (mismo proceso, sin latencia real entre ellos), y el primer resume podía
llegar antes de que n8n estuviera listo para aceptarlo, respondiendo `409 Conflict` (la ejecución existe
de verdad, solo no está lista todavía — no es un error real de Snarf ni una ejecución perdida). Corregido:
`_post_resume_with_retry()` reintenta hasta 3 veces, solo ante un 409 puntual, con backoff corto
(0.15s/0.3s/0.6s) — cualquier otro código de error se propaga tal cual, sin reintentar. Verificado real: un
turno con una tool ruteada (`finance_monthly_pnl`) generó 7 eventos de ciclo de vida reales — los primeros
5 (el techo de `Wait` nodes) se resumieron con 0 fallos gracias al retry (antes del fix: 5 de 7 fallaban
con 409), la ejecución real en n8n terminó `status: success`/`finished: true`.

**Gobernanza (ADR 0093/0139/0156/0164, sin cambios):** el sentido de la flecha sigue siendo estrictamente
unidireccional — Snarf dispara dos POSTs por evento relevante (arrancar o avanzar), n8n nunca inicia una
llamada de vuelta a Snarf durante este camino. No es el mismo patrón reentrante que causó el incidente real
del 2026-08-12 (n8n → Snarf → n8n disparado DESDE un handler de n8n) — acá la dirección siempre es
Snarf → n8n, y la única "respuesta" que Snarf recibe es la respuesta HTTP síncrona a su propio POST saliente
(mismo patrón ya seguro de `n8n_webhook_sink.py`).

`snarf/telemetry/n8n_live_canvas_sink.py` importa dos constantes de `snarf.runtime.n8n_generator`
(`LIVE_TURN_WEBHOOK_PATH`, `N8N_BASE_URL`) — excepción puntual y documentada a la preferencia general de
que `snarf.telemetry` no dependa de `snarf.runtime` (ver docstring de `spans.py`): el costo real de
duplicar el path del webhook (y poder desincronizarlo entre lo que genera el workflow y lo que el sink
dispara) es peor que esta excepción. No hay ciclo de importación real (`n8n_generator.py` no importa
`snarf.telemetry`).

## Verificado

- 6 tests nuevos en `tests/test_n8n_generator.py` (estructura del workflow generado, cadena de conexiones,
  `webhookId`/timeout reales en cada nodo, idempotencia, `sync_live_turn_workflow()` seedea `ids.json` y
  hace el ciclo desactivar→activar, rechaza sin `N8N_API_KEY`).
- 16 tests nuevos en `tests/test_n8n_live_canvas_sink.py`: instalación condicionada a la env var; arranca
  una ejecución real en `workflow.started`/`turn`; resuelve la ejecución correcta por `trace_id`; nunca
  resume más del techo real de etapas; libera el estado al cerrar el turno; dos `trace_id` concurrentes no
  se cruzan entre sí; errores de red reales (arrancando y resumiendo) se tragan sin romper; barrido de
  limpieza por edad real; reintento real ante un 409 puntual y abandono real tras agotar el presupuesto de
  reintentos.
- `tests/conftest.py` actualizado: `n8n_live_canvas_sink.reset()` sumado al fixture de aislamiento entre
  tests (mismo criterio que `n8n_webhook_sink`/`redis_sink`), `N8N_LIVE_CANVAS_ENABLED` limpiada por
  hermeticidad.
- 1421/1421 tests de la suite completa (`.venv/bin/python -m pytest -q`), 1399 previos (post ADR 0165) + 22
  nuevos de esta ronda.
- **Verificación real de punta a punta, fuera de los tests unitarios** (mismo estándar que toda ADR de este
  roadmap): `sync_live_turn_workflow()` corrido contra la instancia real de n8n (workflow real creado y
  activado, `iBPAvv1qSFDoA5u6`). Con `N8N_LIVE_CANVAS_ENABLED` seteada en un proceso Python aislado (no en
  el server de producción — prender esto ahí es una decisión aparte del fundador, requiere reiniciar el
  puerto 8002), un turno real con `Orchestrator._handle_tool("finance_monthly_pnl", ...)` real (sin
  mockear) generó 7 eventos de ciclo de vida reales; los primeros 5 (techo real de nodos `Wait`) se
  resumieron con 0 fallos; la ejecución real en n8n (`3175`) terminó confirmada `status: "success"`,
  `finished: true`.
- **Pendiente real, explícito:** `N8N_LIVE_CANVAS_ENABLED` NO está activa en el server de producción
  (puerto 8002) todavía — el código está probado y verificado, pero prenderlo para tráfico real de
  cualquier turno requiere sumar la variable a `.env` y reiniciar el server, decisión que se confirma con
  el fundador aparte (mismo criterio de CLAUDE.md para cualquier reinicio de producción).
