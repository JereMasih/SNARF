# ADR 0026 — Refresco de Gmail bajo demanda, reusabilidad de Capacidades/Especialistas, costo de tokens

**Fecha:** 2026-07-27
**Estado:** Aceptado

## Contexto

Tras probar ADR 0025 en vivo, el fundador corrigió una decisión tomada en esa misma ronda: no quiere que la interpretación de Gmail se refresque en segundo plano sin que el dashboard esté abierto — el costo de tokens debe ser proporcional al uso real, no un latido constante. También reportó tres bugs reales de interfaz (arrastre de paneles roto en navegador de escritorio, botón de modo de entrada sin efecto en el layout Jarvis, tipografía poco legible), pidió que quedara establecido cómo reusar Capacidades/Especialistas desde un futuro agente/proyecto, y pidió una revisión activa de costo de tokens con recomendación de modelo/proveedor.

## Decisión

### 1. Refresco de Gmail: 100% impulsado por el navegador, nunca el servidor

Se eliminó por completo el loop de `asyncio` en segundo plano de `app.py` (el `startup`/`shutdown` hook y `GMAIL_DIGEST_REFRESH_MINUTES` de ADR 0025). En su lugar:

- Al abrir el dashboard (o volver a él tras estar oculto), el navegador compara el `id` del último mensaje que ya tiene (de la llamada normal, barata, que ya hace para mostrar la lista) contra el `latest_message_id` guardado en la última interpretación cacheada. Si difieren — o no hay interpretación todavía — dispara el refresco real (la llamada cara al LLM).
- Mientras el dashboard sigue abierto y la pestaña visible, ese mismo chequeo barato se repite cada 5 minutos (`GMAIL_DIGEST_POLL_MS`), pausado con la Page Visibility API (`document.hidden`) y detenido explícitamente al volver al chat.
- `GmailDigestSpecialist.refresh()` ahora guarda `latest_message_id` en la caché para hacer posible esta comparación sin ningún endpoint nuevo — el chequeo barato reutiliza datos que el widget ya pedía para mostrarse.
- El "buenos días / qué tenemos para hoy" en el chat sigue funcionando igual que en ADR 0025 (la herramienta `gmail_summarize_inbox` ya devolvía la interpretación cacheada o generaba una nueva) — no necesitó cambios, solo una descripción más explícita mencionando esa frase.

### 2. Bugs reales corregidos

- **Arrastre de paneles roto en navegador de escritorio**: el mousedown disparaba selección de texto nativa (arrastraba todo el contenido de la columna) antes de que el código de arrastre llegara a engancharse — faltaba `e.preventDefault()` en el propio `pointerdown`. Además, los listeners de `pointermove`/`pointerup` estaban en el asa (`.dash-drag-handle`, un elemento chico) en vez de en `document`: en cuanto el cursor se alejaba del asa — inevitable al arrastrar — dejaban de recibir eventos. Ambos corregidos; verificado con un arrastre de mouse real simulado por Playwright (no sintético como en ADR 0024), confirmando que el orden de paneles cambia y no se selecciona texto.
- **Botón de modo de entrada sin efecto**: al reemplazar el emoji por un ícono SVG (ADR 0023), el listener que cierra el popover al hacer clic afuera comparaba `e.target !== modeFab` — pero un clic sobre el ícono SVG hijo tiene como `target` al propio `<svg>`, no al `<button>`, así que el popover se abría y cerraba en el mismo evento. Cambiado a `modeFab.contains(e.target)`. Bug latente desde ADR 0023, no detectado porque la verificación de esa ronda nunca hizo clic en el botón después del cambio de íconos — lección de proceso: probar la interacción real después de un cambio, no solo la presencia visual.
- **Tipografía**: reemplazada la fuente monoespaciada (`SF Mono`/`Menlo`) por la pila de San Francisco (`-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui...`) en `web/index.html` y `web/login.html` — más legible, coherente con el estilo Jarvis sin sacrificarlo (mayúsculas y espaciado de letras ya hacían ese trabajo estético).

### 3. Reusabilidad de Capacidades y Especialistas desde otro agente/proyecto futuro

Se verificó que esto **ya era cierto** por cómo está construido el código, y se dejó garantizado con un test (`tests/test_architecture_boundaries.py`): ningún archivo de `snarf/capabilities/` ni `snarf/specialists/` importa `snarf.core` (el Orchestrator), `snarf.runtime` (lo específico del servidor web) ni `app.py`. Reciben todo por inyección en el constructor (ej. `GmailDigestSpecialist(gmail, llm, user_id)`), nunca instancian sus propias dependencias buscándolas en un contexto global.

**Qué significa en la práctica**: un proyecto futuro puede agregar este repositorio como dependencia (path o git) e importar `snarf.capabilities.google_gmail.GoogleGmail` o `snarf.specialists.gmail_digest.GmailDigestSpecialist` directamente, instanciarlos con lo que ese proyecto tenga (su propia `GoogleAuth`, su propio cliente LLM), sin arrastrar el Orchestrator, FastAPI, ni el resto de Snarf. **Qué no se hizo, y por qué**: no se extrajo esto a un paquete instalable separado — sería construir para un segundo consumidor que todavía no existe, exactamente lo que el proyecto ya se prohíbe (ADR 0019, ADR 0022). El test deja el contrato fijo para que no se erosione mientras tanto.

### 4. Costo de tokens: dos cambios concretos, más una recomendación

**Hechos ahora, de bajo riesgo:**

- **Prompt caching en el system prompt de Snarf** (`snarf/capabilities/anthropic_llm.py`): el system prompt (FOUNDATION+CONSTITUTION+CHARACTER, ~2500 palabras, muy por encima del mínimo cacheable de Sonnet 5) es idéntico en *cada* llamada, de *cualquier* conversación. Antes se enviaba entero y a precio completo en cada mensaje del chat. Ahora se marca con `cache_control: {type: "ephemeral"}`, lo que además cachea las herramientas (`TOOLS`, también idénticas siempre) por el orden de renderizado de la API (`tools → system → messages`). Sin costo si por algún motivo no llega al mínimo cacheable — simplemente no cachea, no hay penalidad.
- **Modelo más barato para la interpretación de Gmail**: `GmailDigestSpecialist` ahora usa `claude-haiku-4-5` ($1/$5 por millón de tokens) en vez del modelo principal de Snarf (`claude-sonnet-5`, $2/$10 intro), con su propia instancia de `AnthropicLLM` — categorizar correos es una tarea acotada y mecánica, no conversación con identidad, coherente con que un Especialista puede (y en este caso, debería) usar una Capacidad de LLM distinta a la de Snarf.

**Evaluado y no implementado — recomendación, no decisión mía:**

Cambiar de proveedor (Gemini, GPT, Grok) para el LLM principal de Snarf no se implementó. Se conversa por separado con el fundador la recomendación (mantener Claude para la identidad de Snarf por calidad de carácter/razonamiento; considerar un proveedor más barato solo para tareas acotadas como el propio patrón ya probado con Haiku, si en el futuro se agregan más Especialistas de ese tipo).

## Verificado

- 93 tests (91 de ADR 0025 + 2 nuevos: el test de architecture boundaries corre 2 assertions separadas, y el de prompt caching en `AnthropicLLM`).
- Arrastre de paneles y botón de modo de entrada verificados con Playwright usando eventos de mouse **reales** (no sintéticos) — confirmando que ambos bugs estaban genuinamente rotos antes del fix y funcionan después.
- Sin loop de `asyncio` en segundo plano: confirmado que el servidor arranca sin lanzar ninguna tarea, y que `/dashboard/widgets/gmail/digest` nunca cambia sin que el navegador lo pida.

## Consecuencias

- El costo de la interpretación de Gmail ahora es proporcional al uso real del dashboard, no una tarea recurrente fija — más difícil de tener un número exacto de costo mensual, pero acotado por diseño a "mientras el fundador lo está mirando".
- El próximo Especialista que se agregue tiene dos precedentes de este ADR para copiar: cómo elegir su propio modelo de LLM más barato cuando la tarea lo permite, y cómo estar seguro de que sigue siendo reusable fuera de Snarf (correr `pytest tests/test_architecture_boundaries.py`).
