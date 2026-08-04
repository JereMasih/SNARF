# ADR 0079 — Historial de costos por día/agente/sesión (Fase 3 del plan de HUD)

**Fecha:** 2026-08-03
**Estado:** Aceptado

## Contexto

Fase 3 del plan de HUD (ver `SESSION_STATE.md`): con el evento unificado de
telemetría ya guardándose (Fase 1), construir un endpoint que agregue costo
y tokens por día, por agente y por sesión, más un componente visual en el
lenguaje de Fase 0 que lo muestre como historial.

"Por sesión" resultó requerir una pieza nueva: el evento unificado (Fase 1)
no tenía forma de saber a qué conversación pertenecía cada tool-call/llamada
de vendor — `Orchestrator.handle()` sí recibe `conversation_id`, pero nunca
se propagaba hasta `activity_log.record()`/`usage_tracker.record()`.

## Decisión

### `snarf/telemetry/context.py` (nuevo) — conversation_id por thread

`threading.local()`, no un atributo de instancia de `Orchestrator` — mismo
criterio ya real de ADR 0041 (el `_service` cacheado de cada Capacidad tenía
la misma clase de bug: FastAPI corre cada request en un thread del pool, un
singleton compartido pisa el estado de otro request en curso). Cada evento
unificado (`events.py`) lee `context.get_conversation_id()` automáticamente
al construirse — no hizo falta agregar un parámetro `conversation_id` a
ninguna de las ~10 funciones `record_*` existentes.

`Orchestrator.handle()` setea el conversation_id real al entrar y lo limpia
en un `finally` (sobrevive exactamente la duración del turno, incluida
cualquier ronda de tool-use del loop de `AnthropicLLM.generate()`, que corre
sincrónico en el mismo thread). `generate_conversation_title()` hace lo
mismo. Eventos fuera de un turno real (digest de Gmail en background,
resumen de proyecto) quedan con `conversation_id: null` — honesto, no hay
sesión real a la que atribuirlos.

### `snarf/telemetry/cost_history.py` (nuevo)

`by_day`/`by_agente`/`by_session`/`summary` — agregan una lista de eventos
unificados (`events.all_events()`, todos los guardados, no solo los
últimos N — una agregación histórica recortada mentiría el total). Cada
bucket separa `costo_usd` (suma solo de lo conocido) de
`llamadas_sin_costo_estimado`, mismo criterio ya real de
`usage_tracker.summarize()`: un costo desconocido nunca se trata como cero
(Principio VI de FOUNDATION.md). `by_session` excluye eventos sin
`conversation_id` — agregarlos bajo una clave `null` inventaría una sesión
que no existe. Día agrupado por calendario en `America/Argentina/Buenos_Aires` (mismo
valor real que `FOUNDER_TIMEZONE` de `orchestrator.py`, duplicado a
propósito: `snarf/telemetry/` no importa `snarf/core/`, mismo criterio de
capas de ADR 0026).

### `GET /dashboard/cost_history` (nuevo, `app.py`)

Devuelve `cost_history.summary(events.all_events())` — mismo patrón de auth
(`Depends(require_user)`) que el resto de `/dashboard/*`.

### `web/hud_cost_history_prototype.html` (nuevo)

Componente visual en el lenguaje de Fase 0: costo por día (barras
horizontales), ranking por agente y por sesión (barra proporcional al
máximo, el primero en ámbar). Hace `fetch('/dashboard/cost_history')`
same-origin; si falla (ej. abierto por `file://` para verificación visual,
sin servidor detrás), cae a datos mock con la MISMA forma exacta que
devuelve el endpoint real — mismo criterio que el prototipo de Fase 2.
Todavía no enlazado desde `web/index.html` — misma decisión que Fase 2, la
integración final queda para cuando se decida la ubicación en el dashboard
real.

## Verificado

- `.venv/bin/python -m pytest -q` — 584/584 passed. Tests nuevos:
  `tests/test_telemetry_context.py`, `tests/test_cost_history.py` (7 casos,
  incluye el caso "costo desconocido nunca es cero"), 4 casos nuevos en
  `tests/test_orchestrator.py` (conversation_id real propagado a un evento
  de tool-call, contexto limpiado tras `handle()` incluso si el LLM tira
  excepción, eventos de background sin conversation_id), 1 caso en
  `tests/test_app.py` para el endpoint nuevo.
- El endpoint se verificó a nivel HTTP real contra la app de FastAPI
  (`TestClient`, no un mock) — no una llamada directa a la función Python.
- El componente visual se verificó con Playwright/Chromium real contra el
  archivo: 3 filas de día, ranking de agente/sesión con el primero
  destacado en ámbar, barras animando a su ancho real, cero errores de
  consola más allá del fetch esperado a `file://` (dispara el fallback a
  mock, comportamiento intencional).
- **Gap real encontrado durante esta fase, corregido en el camino:**
  `tests/test_app.py` redirigía `activity_log`/`usage_tracker`/`input_log`
  pero no `events.DEFAULT_PATH` — el evento unificado seguía escribiendo al
  archivo real. Corregido agregando ese monkeypatch a la fixture `client`.
  Documentado también en ADR 0077 (corrección de una afirmación imprecisa
  de esa ADR).

## Consecuencias

- El campo `conversation_id` del evento unificado es nuevo respecto al
  esquema original de `TELEMETRY_SCHEMA.md` (Fase 0) — no estaba en la
  lista de campos de esa fase, se agregó acá porque "por sesión" lo
  requería con honestidad. `TELEMETRY_SCHEMA.md` queda desactualizado en
  ese punto — pendiente de una pasada de actualización, no bloqueante.
- Fase 4/5 pueden reusar `cost_history.py` tal cual para lo que necesiten
  mostrar en el dock/HUD sobre gasto — ninguna lógica de agregación para
  reescribir.
