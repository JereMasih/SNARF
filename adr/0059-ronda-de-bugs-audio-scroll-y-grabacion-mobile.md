# ADR 0059 — Ronda de bugs reales: audio duplicado, scroll, grabación mobile

**Fecha:** 2026-07-30
**Estado:** Aceptado

## Contexto

El fundador probó en vivo lo construido hasta acá y reportó, en la misma ronda, varios bugs reales concretos: la versión hablada de una respuesta larga ("plan de monetización de una marca de Instagram") salió idéntica a la respuesta completa (4:58 los dos audios); las barras de desplazamiento quedan siempre visibles en vez de aparecer solo al usarlas; el scroll del chat en desktop "se escapa" hacia toda la página al llegar al final; y en iPhone, un toque rápido sobre el micrófono deja la interfaz grabando sin ninguna forma real de pararla. Pidió además que, si una respuesta no entra en el límite de un mensaje, Snarf genere un archivo Markdown en vez de truncarla en silencio.

## Decisión

### 1. Audio de resumen idéntico al completo — tope de seguridad + prompt más firme

La instrucción de `SYSTEM_PREFIX` ("menos de 400 caracteres") es una guía, no algo estructuralmente forzado — en una respuesta larga e "importante", el modelo puede decidir por su cuenta que amerita el desarrollo completo y pegarlo entero dentro del bloque `---HABLA---`. Dos cambios: (a) el prompt ahora aclara explícitamente que la importancia del tema NUNCA es motivo para alargar la versión hablada — es motivo para que la pantalla sea completa y la hablada siga siendo solo el resumen; (b) `split_speech()` (`snarf/capabilities/anthropic_llm.py`) suma `SPEECH_HARD_CAP_CHARS = 600` como tope de seguridad real: si lo que el modelo puso dentro del marcador de habla supera ese largo, se le aplica igual `fallback_speech()` (el mismo recorte mecánico del caso "sin marcador") — nunca puede volver a pasar que el audio de "resumen" sea, de hecho, la respuesta entera.

### 2. Respuesta que no entra en el límite → archivo Markdown, no truncar en silencio

Nuevo párrafo en `SYSTEM_PREFIX`: si una respuesta en pantalla no entra en un solo mensaje, generar el contenido completo con `drive_create_document(format='markdown')`, avisar en la respuesta que se hizo y dar el link/`download_url` — preguntando el destino como con cualquier documento, salvo que ya se lo hayan dicho.

### 3. Barras de desplazamiento — ocultas por default, visibles solo durante scroll activo

Nueva regla CSS universal (`* { scrollbar-color: transparent transparent }` + equivalente `::-webkit-scrollbar-thumb` transparente) combinada con un único listener global de `scroll` en `document` (con `capture: true`, porque `scroll` no burbujea salvo en `window`) que agrega `.scrollbar-visible` al elemento que se está scrolleando de verdad y se la saca a los 800ms de inactividad. Resuelve de paso el caso puntual del textarea `#textInput`: con una sola línea no hacía falta overflow real para que el navegador ya pintara una barra visible con `overflow-y: auto` — ahora queda invisible hasta que de verdad haga falta.

### 4. Scroll chaining del chat hacia toda la página

`overscroll-behavior: contain` en `.chat` (el contenedor real del historial de mensajes), `.conv-list` y `.brain-feed` — llegar al final scrolleando rápido ya no "se escapa" hacia el resto de la página/dashboard.

### 5. Grabación mobile: tap accidental sin forma de pararla

Causa real: `pointerdown` llamaba a `startRecording()` (que pide `getUserMedia`, asincrónico) de inmediato. En un tap rápido, el `pointerup` llegaba ANTES de que esa promesa resolviera — como en ese instante `state` todavía era `"idle"` (no `"listening"`), el guard existente en `pointerup` lo ignoraba en silencio. Para cuando `getUserMedia` finalmente resolvía, la grabación arrancaba igual (`state` pasaba a `"listening"`, el mic se ponía rojo) pero el único evento que podía terminarla ya había pasado y había sido descartado — quedaba grabando sin ningún control que la parara.

Arreglado con un delay de hold real (`RECORD_HOLD_DELAY_MS = 180`): `pointerdown` ya no llama a `startRecording()` directo — arma un timer, y solo si el dedo sigue apretando cuando ese timer vence llama a `beginActualRecording()`. Si `pointerup` llega antes (un tap real), se cancela el timer y nunca se pide el micrófono — nada que parar. Además, mientras se está grabando (bloqueado o no), el ícono del mic se reemplaza por un cuadrado rojo de "stop" (antes solo se teñía de rojo el mismo ícono de mic) — más intuitivo sobre qué pasa si se suelta/toca ahí.

## Verificado

- 445/445 tests (1 nuevo: el tope de seguridad de `split_speech`).
- Playwright con micrófono simulado (`--use-fake-device-for-media-stream`): un tap de 60ms nunca agrega la clase `recording` ni pide el micrófono; un hold real de 400ms sí graba (`ESCUCHANDO...`, ícono de stop), y soltar normal transcribe (con audio simulado en silencio, reporta honestamente "no se escuchó nada" en vez de quedar colgado).
- Confirmado que el textarea de una sola línea no tiene `scrollbar-visible` antes de ningún scroll real.

## Consecuencias

- `overscroll-behavior: contain` se aplicó a los tres contenedores de scroll más señalados/relevantes (`.chat`, `.conv-list`, `.brain-feed`) — si el fundador reporta el mismo escape en otro panel scrolleable de la interfaz, es la misma línea a agregar ahí.
- El tope de `SPEECH_HARD_CAP_CHARS = 600` es una elección razonable, no un número pedido por el fundador — ajustable si en el uso real resulta muy bajo o muy alto para una habla legítimamente un poco más larga que 400 caracteres.
- Pendiente, sin construir todavía (pedido nuevo en la misma ronda): una animación del cerebro durante el estado "pensando" del chat, clickeable para expandir el cerebro completo como un holograma (mobile) o dentro de la caja de chat (desktop), que vuelve sola al chat cuando la respuesta llega. Alcance mayor, propuesto para la próxima ronda.
