# ADR 0063 — "Escuchar" vs "escuchar entregable" reemplaza resumen/completa

**Fecha:** 2026-07-30
**Estado:** Aceptado

## Contexto

El diseño de dos botones "escuchar resumen" / "escuchar completa" (ADR 0056 y su addendum) dejó de ser útil en la práctica: el fundador reportó que la distinción no aportaba y hasta confundía — "completa" leía el texto crudo en pantalla (con sintaxis Markdown incluida) y, para respuestas donde el modelo decidía que el tema ameritaba desarrollo completo, terminaba siendo indistinguible en duración de "resumen". El pedido del fundador fue repensar el modelo de fondo: la respuesta en pantalla debe seguir siendo lo más completa posible, y debe poder **escucharse tal cual está en pantalla** (no un resumen acortado). Por separado, cuando la respuesta incluye un entregable puntual pedido explícitamente (un plan, un documento, una copia) distinto de la charla alrededor, tiene que poder escucharse **solo eso** — sin el encuadre ni los comentarios de Snarf antes o después.

## Decisión

Se reemplaza el par resumen/completa por dos conceptos con propósitos distintos, no por longitud:

- **`speech`** (botón "escuchar"): ya no es un resumen con tope de caracteres — es la narración hablada de la MISMA respuesta completa que está en pantalla, fraseada naturalmente para voz (sin markdown, sin URLs deletreadas). Se eliminó `SPEECH_HARD_CAP_CHARS` y la instrucción de "SIEMPRE menos de 400 caracteres" del system prompt: si la respuesta en pantalla es larga, la narración también lo es, y eso ahora es correcto, no un bug.
- **`deliverable`** (botón "escuchar entregable", NUEVO): nuevo marcador `---ENTREGABLE---`/`---FIN-ENTREGABLE---` que el modelo agrega SOLO cuando la respuesta contiene un entregable puntual y pedido explícitamente, claramente distinguible de la charla alrededor. Contiene únicamente ese contenido, fraseado para voz, sin el encuadre ni el comentario de Snarf antes/después. El botón solo aparece en la burbuja cuando este campo viene poblado — en la mayoría de las respuestas (puramente conversacionales) no existe.

`LLMResponse` gana el campo `deliverable: str | None = None`; `split_speech()` lo extrae junto con `speech`. `EpisodicMemory.append()`, `SendResponse` y `addMessage()` en el frontend propagan el campo de punta a punta.

**Bug real encontrado y corregido durante la verificación en vivo de esta misma ronda**: el modelo a veces encadena `---ENTREGABLE---` directo después de la narración sin cerrar `---FIN-HABLA---` antes — sin manejar este caso, los marcadores quedaban crudos dentro del audio de "escuchar" y el entregable nunca se extraía (quedaba `None`). `split_speech()` ahora busca `DELIVERABLE_START` primero y lo trata como el corte real del bloque de habla si aparece antes que (o en ausencia de) `FIN-HABLA` — robusto a que el modelo no siga el formato al pie de la letra, mismo criterio que ya existía para el caso de `stop_reason == max_tokens`.

## Verificado

- 467/467 tests (nuevos: extracción del entregable con y sin `FIN-HABLA` cerrado, narración larga sin tope, propagación por `episodic.py`/`orchestrator.py`/`/send`).
- Playwright + llamadas reales a Anthropic en instancia aislada: un mensaje puramente conversacional muestra solo "escuchar" (sin botón de entregable); un pedido de plan de negocios de Instagram muestra ambos botones, con el entregable conteniendo solo el plan (sin la charla alrededor) y sin marcadores crudos.

## Consecuencias

- El modelo decide caso a caso si una respuesta amerita un entregable aislado — es una decisión de criterio (instruida, no forzada estructuralmente), así que dos pedidos similares pueden no comportarse idéntico (ej. una bio corta de Instagram a veces no se consideró lo bastante distinguible del resto como para separarla). Es el mismo tipo de criterio que ya rige el resto del prompt (sarcasmo, generación de documentos), no una regresión.
- Los botones "escuchar resumen"/"escuchar completa" y sus IDs de descarga (`respuesta-completa`) quedan retirados; conversaciones viejas guardadas antes de este cambio no tienen `deliverable` (default `None` vía `.get`), se comportan como si nunca hubiera existido — solo aparece "escuchar".
