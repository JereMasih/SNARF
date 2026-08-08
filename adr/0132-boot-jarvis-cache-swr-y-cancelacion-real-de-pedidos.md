# ADR 0132 — Pantalla de boot "Jarvis-style", cache SWR del cliente, y cancelación real de un pedido en curso

**Fecha:** 2026-08-07
**Estado:** Aceptado

## Contexto

Tres fricciones reales reportadas por el fundador en el uso diario de Snarf:

1. Al abrir la app había una ventana donde no era claro si Snarf ya estaba listo para recibir texto —
   el overlay de arranque (`#connectingOverlay`) solo esperaba `GET /status` (servidor arriba), nunca
   a que cargaran conversaciones/dashboard. Si el fundador escribía en esa ventana, el pedido tardaba
   mucho sin ninguna explicación visible.
2. Cada F5 repetía TODOS los fetches de arranque (conversaciones, proyectos, preferencias/resumen del
   dashboard, widgets) sin ningún cacheo, aunque los datos no hubieran cambiado desde el último reload.
3. No había forma de frenar un pedido en curso — solo esperar a que terminara la respuesta completa,
   aunque el fundador se hubiera arrepentido de lo escrito o quisiera corregirlo.

Las primeras dos son puramente de frontend/UX, sin decisión arquitectónica que justificar aparte. La
tercera sí lo es: se evaluaron dos profundidades posibles — cancelación solo visual (el navegador deja
de mostrar la respuesta, el backend sigue generando igual hasta el final) vs. cancelación real (corta
la generación de Anthropic a mitad de camino). El fundador, consultado explícitamente, eligió la
segunda — ahorra costo real de tokens, no solo maquilla la espera — así que este ADR documenta
sobre todo esa parte.

## Decisión

### 1. Pantalla de boot

`#connectingOverlay` (ya cubría pantalla completa en mobile y desktop) se extiende en vez de
reemplazarse: reusa `brainMiniSvgMarkup()` — la misma función que ya arma el cerebro del widget de
dashboard y del indicador de "pensando", nunca una animación decorativa aparte — con datos vacíos
entra en estado "ghost" real (honesto: nunca actividad inventada) y se actualiza con datos reales de
`/dashboard/brain` apenas están disponibles. `bootSequence()` recién oculta el overlay (y recién ahí
rehabilita `textInput`/`textSendBtn`/`micBtn`, deshabilitados mientras tanto) cuando `/status`
respondió Y las conversaciones/proyectos (y el dashboard, en desktop) terminaron de cargar — con un
timeout duro de 15s como red de seguridad honesta (nunca spinner infinito fingiendo que sigue
cargando). La reconexión tras un corte de red a mitad de sesión sigue usando el spinner simple de
siempre (clase `.reconnect`, oculta el cerebro) — la animación completa queda reservada a la primera
carga real.

### 2. Cache cliente con stale-while-revalidate

Helper nuevo (`readCache`/`writeCache`/`cachedGET`-style por call site) sobre `localStorage`, con un
`freshMs` propio por tipo de dato: conversaciones/resumen del dashboard 15-20s (cambian seguido),
proyectos 60s, preferencias del dashboard 5min (solo cambian por acción explícita en Configuración),
widgets 30s (ya tienen su propio polling una vez montados, esto solo ayuda al primer paint). Dentro de
la ventana fresca, un reload no repite el pedido de red — confirmado con Playwright: cero requests a
`/conversations` en un segundo reload inmediato. Mutaciones que ya actualizaban estado en memoria
(`persistPrefs`) también escriben al cache, para que un F5 inmediato después de cambiar una
preferencia no la muestre vieja.

### 3. Cancelación real de un pedido en curso

**Backend**, en tres capas:

- `snarf/telemetry/cancellation.py` (nuevo): registro en memoria de proceso (`register`/`cancel`/
  `is_cancelled`/`finish`), protegido por lock. Vive en `snarf.telemetry`, no en `snarf.runtime` —
  `snarf.capabilities` tiene prohibido importar `snarf.runtime` (ver
  `tests/test_architecture_boundaries.py`, que lo confirmó en el momento de implementar esto).
- `snarf/telemetry/context.py` gana `set_request_id`/`get_request_id`/`clear_request_id`, mismo patrón
  ya existente de `set_conversation_id`. El `request_id` viaja por contexto (`threading.local`), NO
  por `generate_kwargs` — ese dict se pasa sin cambios a `AnthropicLLM`, `OpenAICompatibleLLM` y
  `GeminiLLM`, las tres con firma estricta; agregarlo ahí rompería las otras dos con `TypeError`. Solo
  `AnthropicLLM` lee el contexto — Gemini/OpenAI-compatible no implementan cancelación real todavía,
  el ruteo puede mandarlos igual sin romper nada, simplemente sin poder frenarlos a mitad de camino.
- `AnthropicLLM._create()`: si hay `request_id` real en contexto, itera el stream de Anthropic evento
  por evento (en vez de ir directo a `get_final_message()`) chequeando `cancellation.is_cancelled()`;
  al detectarlo, levanta `GenerationCancelled` con el texto parcial ya generado (leído de
  `stream.current_message_snapshot`). `MessageStreamManager.__exit__` ya cierra la conexión real al
  salir del `with` — un `raise` adentro corta la generación de verdad, ahorra el output que faltaba
  generar. Sin `request_id` (llamadas internas: título de conversación, compactación de historial, y
  todos los tests existentes) el comportamiento es idéntico al de siempre. `generate()` además chequea
  cancelación al tope de cada ronda del loop de herramientas.
- `orchestrator.handle()` gana el parámetro `request_id`, lo setea/limpia en el mismo `try/finally` que
  ya envolvía `conversation_id`/`llm_role`, y persiste `cancelled=response.cancelled` en la memoria
  episódica — la respuesta cancelada **queda en el historial**, marcada, nunca desaparece.
- `app.py`: `SendRequest.request_id` (generado en el frontend con `crypto.randomUUID()`),
  `cancellation.register()`/`finish()` alrededor de `orchestrator.handle()`, y `POST /cancel/{request_id}`
  nuevo — 404 si el pedido ya terminó o no existe (nunca finge éxito).

**Frontend**: `postAndHandleSend()` genera el `request_id`, pasa un `AbortController.signal` al fetch
de `/send`. El botón "■ frenar" (nuevo, en la burbuja de "pensando") llama `stopActiveRequest()`
(aborta el fetch + `POST /cancel/{id}` fire-and-forget) y reusa el panel de revisión que ya existía
para notas de voz transcriptas (`#review`/`#reviewText`, con sus botones "cancelar"/"enviar" intactos)
prellenado con el texto original — sin construir una interfaz de edición nueva. La burbuja cancelada
queda marcada con `.msg.snarf.cancelled` (opacidad reducida, borde en `--brain-red`, badge "⏹ pedido
cancelado") en vez de desaparecer; `loadConversation()` propaga `entry.cancelled` para que el marcador
sobreviva a un reload real.

## Riesgos/trade-offs (documentados a propósito, no ocultos)

1. **Costo real**: los tokens de output ya generados hasta el punto de corte se cobran igual — el
   ahorro es "lo que faltaba generar", significativo en respuestas largas, casi nulo si se cancela
   cerca del final.
2. **Una tool en ejecución no se interrumpe a mitad de un side-effect real** (ej. mandar un mail) — el
   chequeo de cancelación corre al tope de cada ronda y dentro del streaming, nunca mientras
   `tool_handler()` está corriendo. Decisión deliberada: cortar un side-effect real a mitad de camino
   es más riesgoso que dejarlo terminar.
3. **Carrera esperable**: si `/cancel/{id}` llega después de que la respuesta ya terminó, el backend
   devuelve 404 y el frontend lo trata como no-error (silencioso, nunca un toast de fallo).
4. **Registro en memoria de un solo proceso** — válido mientras Snarf corra con un solo worker de
   uvicorn (como hoy); si algún día corre con `--workers > 1`, `/cancel` podría no llegar al proceso
   que está generando la respuesta.

## Verificado

- 18 tests nuevos: `tests/test_cancellation.py` (6, registro puro), `tests/test_context.py` (3,
  `request_id` por thread), `tests/test_anthropic_llm.py` (3, cancelar a mitad de stream con texto
  parcial preservado / cancelar entre rondas del tool-loop sin llamar al stream / comportamiento
  idéntico sin `request_id`), `tests/test_orchestrator.py` (3, `request_id` taggeado y limpiado /
  respuesta cancelada persistida marcada en memoria), `tests/test_app.py` (3, incluida una carrera
  real con `threading.Thread` — un `/send` bloqueado de verdad en un LLM falso lento, frenado por un
  `POST /cancel` disparado desde otro hilo mientras tanto, no una simulación).
- 1076/1076 tests de la suite completa.
- Verificado con Playwright contra una instancia de prueba (puerto 8000, nunca el LaunchAgent de
  producción en 8002): `textInput.disabled` es `true` inmediatamente tras cargar la página y vuelve a
  `false` recién cuando el overlay se oculta; un segundo reload inmediato no dispara ningún request a
  `/conversations` (cache fresca) y las 10 claves de cache esperadas quedan pobladas; con `/send` y
  `/cancel` interceptados del lado del navegador (sin gastar tokens reales ni tocar la memoria
  episódica real), el botón "■ frenar" aparece, dispara `POST /cancel/{id}` con el id real, despliega
  el panel de revisión con el texto original prellenado, y la burbuja queda marcada con el badge
  "⏹ pedido cancelado" — cero errores de consola en todo el flujo.
