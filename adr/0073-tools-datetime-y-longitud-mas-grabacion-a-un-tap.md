# ADR 0073 — Tools `get_current_datetime`/`measure_text_length`, y grabación de voz a un tap

**Fecha:** 2026-07-31
**Estado:** Aceptado

## Contexto

El fundador trajo un registro crudo de bugs/ideas de uso real (desktop + mobile) de Snarf. Dos de esos ítems son cambios de arquitectura real (agregan superficie nueva al Orchestrator o cambian una interacción ya documentada en un ADR anterior), a diferencia del resto del backlog de esta sesión (convenciones de texto en el prompt del sistema, que no alteran ningún contrato de código):

1. Snarf no tenía ninguna fuente confiable de "qué día es hoy" — dependía del propio sentido de tiempo de entrenamiento del modelo, que ya se vio desactualizado en la práctica (un documento quedó timestampeado con una fecha equivocada). Tampoco tenía forma de medir longitud de texto con precisión — al pedir "reducí esto a N caracteres", el modelo reportaba cifras estimadas ("~2.100 caracteres") en vez de un conteo real.
2. La grabación de voz (ADR 0049, Decisión 3: mantener presionado + deslizar para bloquear) rompía en iPhone — mantener el dedo sobre el botón disparaba la lupa de aumento nativa de iOS (pensada para cajas de texto sobre las que se mantiene el dedo), no el gesto de grabación. El fundador pidió eliminar por completo el gesto de mantener+deslizar y el estado intermedio de "bloqueado".

## Decisión

### 1. `get_current_datetime`

Tool de solo lectura nueva (`snarf/core/orchestrator.py`), sin parámetros: devuelve `iso`/`date`/`time`/`weekday`/`timezone` reales del servidor, con timezone fija `FOUNDER_TIMEZONE = "America/Argentina/Buenos_Aires"` (constante nueva, no configurable todavía — un solo usuario real hoy). El `SYSTEM_PREFIX` instruye usarla antes de timestampear cualquier cosa, en vez de asumir la fecha.

### 2. `measure_text_length`

Tool de solo lectura nueva, recibe `text`, devuelve `characters` (`len()` real) y `words` (`text.split()`). El `SYSTEM_PREFIX` instruye un pipeline explícito para tareas con límite duro de longitud: generar → medir con la tool → recortar/regenerar si excede → volver a medir → recién ahí responder. Snarf no tiene ejecución de código en ningún otro lugar del repo (confirmado por grep) — esta tool es la única fuente de verdad determinística para conteo, reemplazando la estimación del modelo.

Ambas tools se mapean a un nodo nuevo del cerebro, `utility` (tier `capability`), en `snarf/telemetry/brain.py` y su espejo en `web/index.html` (`BRAIN_CAPABILITY_ORDER`, `BRAIN_NODE_LABELS`, `BRAIN_NODE_ICON_PATHS` — ícono nuevo, un engranaje de líneas monoline) — protocolo de crecimiento del cerebro (ADR 0054), no una decisión opcional.

### 3. Grabación de voz: tap simple, sin estado de "bloqueado"

Reemplaza por completo la Decisión 3 de ADR 0049 (mantener presionado / deslizar para cancelar / deslizar para bloquear) por: un tap en el mic entra directo a grabar, manos libres desde el primer instante — no existe más un estado intermedio de "bloqueado" ni el gesto de deslizar.

- Se elimina toda la lógica de Pointer Events con hold-timer y detección de swipe (`pointerdown`/`pointermove`/`pointerup`/`pointercancel` sobre `micBtn`, `RECORD_HOLD_DELAY_MS`, `RECORD_LOCK_THRESHOLD_PX`, `RECORD_CANCEL_THRESHOLD_PX`, `setPointerCapture`), reemplazada por un único listener `click`.
- Se elimina el elemento `#recordLockHint` (HTML, CSS y sus referencias JS) — ya no hay nada que bloquear.
- Se mantienen: el hint "manos libres, tocá enviar" (ahora fijo desde el primer tap, no solo tras deslizar), el botón de borrar (`#recordCancelBtn`, ahora siempre visible mientras se graba en vez de solo tras bloquear) y la flecha de enviar (`#textSendBtn`, mismo rol de siempre: termina y envía).
- **Agregado nuevo**: waveform en vivo (`#recordWave`, 5 barras) impulsado por un `AnalyserNode` real sobre el `MediaStream` del mic (`startWaveform()`/`stopWaveform()` en `web/index.html`) — crece con la amplitud de voz real, vuelve a un punto quieto en silencio. Degrada con gracia (recording sigue andando) si `AudioContext`/`AnalyserNode` no está disponible.

## Verificado

- `.venv/bin/python -m pytest -q` — 529 passed (incluye `test_tool_to_node_covers_every_orchestrator_tool` y `test_no_specialist_node_absorbs_too_many_tools`, que hubieran fallado sin el nodo `utility` nuevo).
- Smoke-check real en navegador (Playwright, viewport mobile 390×844, `getUserMedia`/`MediaRecorder` mockeados): confirma título del botón ("Tocá para grabar"), ausencia de `#recordLockHint` en el DOM, que un solo click entra a `.text-row.recording` con el hint correcto, que tacho y flecha quedan visibles y el mic oculto, que existen las 5 barras de `#recordWave`, y que cancelar vuelve limpio al estado idle sin errores de consola nuevos.

## Consecuencias

- `get_current_datetime`/`measure_text_length` son la primera pareja de tools que no envuelven ninguna Capacidad externa (Drive, Gmail, LLM) — son utilidades puras del propio Orchestrator. El nodo `utility` del cerebro documenta esto como una categoría legítima, no una excepción a ocultar.
- La grabación de voz pierde el modo "manos ocupadas" (soltar para enviar directo) que tenía ADR 0049 antes de bloquear — ahora todo tap es manos libres. Si en el futuro se quiere recuperar un modo de "grabación corta, soltar para enviar", es una decisión de UX nueva, no una regresión de este cambio.
