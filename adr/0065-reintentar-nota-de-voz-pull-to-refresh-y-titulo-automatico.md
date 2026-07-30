# ADR 0065 — Reintentar nota de voz, pull-to-refresh del historial, título automático

**Fecha:** 2026-07-30
**Estado:** Aceptado

## Contexto

Tres pedidos del fundador en la misma ronda: (1) un envío real de nota de voz falló con "Load failed" (el mensaje típico de un error de red real en Safari) y no había forma de reintentar sin perder la grabación — había que grabar todo de nuevo; (2) el historial de conversaciones en la barra lateral no se actualiza solo si se creó una conversación nueva en otra sesión/pestaña, y pidió poder refrescarlo deslizando hacia abajo; (3) el título de cada conversación seguía siendo el substring crudo de los primeros 60 caracteres del primer mensaje (sin nombrarla de verdad), pendiente de una ronda anterior.

## Decisión

**Reintentar una nota de voz fallida** (`web/index.html`): se separó cada paso de la nota de voz en una función retomable, y un `pendingRetry` global (con botón `#retryBtn`, visible solo cuando hay algo para reintentar) guarda exactamente lo que hace falta reintentar:
- Si falla `/transcribe` (red o el STT en sí): `attemptTranscribe(blob, onSuccess)` guarda el MISMO `blob` ya grabado — reintentar no vuelve a grabar nada, solo reenvía el audio existente.
- Si la transcripción ya salió bien pero falla `/send`: `postAndHandleSend(text, inputAudioId)` (extraído de `sendText`, que ahora solo agrega la burbuja del usuario una vez y delega el POST reintentable) guarda el texto YA transcripto — reintentar reenvía la transcripción, no vuelve a transcribir. Esto aplica también a mensajes de texto normales (mismo mecanismo, sin código nuevo).
- Aplica tanto al modo mantener-apretado (`finishRecording`) como al modo click clásico (`handleClickMode`), vía un helper compartido.

**Pull-to-refresh del historial**: `enablePullToRefresh(listEl, indicatorEl, onRefresh)`, aplicado a `#convList` y `#dashConvList`. El indicador vive AFUERA de la lista (como hermano, justo antes) porque `renderConvListInto()` hace `container.innerHTML = ""` en cada refresh y borraría cualquier cosa insertada adentro. Dispara solo cuando `scrollTop === 0` (ya no hay más para scrollear hacia arriba) y el arrastre hacia abajo supera 60px — al soltar, llama a `refreshConvLists()` (la misma función que ya existía).

**Título automático de conversación**: `EpisodicMemory` suma `data/conversation_titles.json` (mismo patrón que `conversation_projects.json`) con `set_title`/`get_title`; `list_conversations()` prefiere el título guardado sobre el substring crudo, degradando a este último si todavía no se generó. `Orchestrator.generate_conversation_title(conversation_id)` usa un LLM barato (mismo `GMAIL_DIGEST_MODEL`, ya reusado por `ProjectManager`) sobre el primer intercambio real (input + primeros 500 caracteres de la respuesta) para producir un título de hasta 6 palabras. `/send` en `app.py` la dispara vía `BackgroundTasks` (no le suma latencia a la respuesta que el fundador está esperando) únicamente cuando la conversación no tenía ningún mensaje previo — nunca en turnos siguientes.

## Verificado

- 475/475 tests (nuevos: `set_title`/`get_title` roundtrip y preferencia sobre el substring en `test_episodic_memory.py`; `generate_conversation_title` — persiste, limpia comillas/punto final, se degrada sin LLM disponible, se degrada ante una excepción, no rompe con una conversación inexistente — en `test_orchestrator.py`; disparo único en el primer turno vía `/send` en `test_app.py`).
- Playwright con una falla de red real simulada (`route.abort("failed")` sobre `/transcribe`, produce el mismo `Failed to fetch`/`Load failed` que reportó el fundador): aparece "no se pudo transcribir...", el botón reintentar reenvía el MISMO audio grabado sin pedir grabar de nuevo, y al arreglarse la red el reintento se completa solo.
- Playwright del gesto de pull-to-refresh: arrastre real (vía `page.mouse`) desde arriba del todo del listado dispara un nuevo `GET /conversations`.
- El título automático no pudo verificarse con una llamada real a Anthropic en esta ronda — **la cuenta real se quedó sin crédito** ("Your credit balance is too low to access the Anthropic API"), descubierto durante esta misma verificación. La lógica está cubierta por 5 tests unitarios con el LLM mockeado; falta la confirmación end-to-end en vivo hasta que se recargue crédito.

## Consecuencias

- **Hallazgo operativo urgente, no relacionado con el código**: la cuenta de Anthropic real se quedó sin crédito — cualquier conversación real en producción ahora mismo degrada al mensaje `[error real del LLM, no pude responder: ...Your credit balance is too low...]`. Esto afecta a TODO Snarf (no solo el título), no es algo que este cambio pueda arreglar — hace falta cargar crédito en la cuenta.
- Contaminación real detectada y corregida en esta ronda: dos rondas de verificación en vivo de sesiones anteriores (incluida esta) escribieron conversaciones de prueba (`titulo-test-1`, `check-quality*`, `check-round2-*`) directamente en `data/episodic_memory.jsonl` de producción por un error propio al lanzar un servidor "aislado" sin cambiar el directorio de trabajo del proceso (`--app-dir` de uvicorn no hace `cd`). Se identificaron y removieron esas líneas puntuales. Se detectó además contaminación de prueba MÁS VIEJA y no relacionada con esta sesión (`test-confirm-*`, `timing-*`, `test-eventfix-*`, etc.) — se dejó intacta, fuera de alcance de esta corrección.
