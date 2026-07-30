# ADR 0049 — Grabación estilo WhatsApp, cerebro con íconos propios, y más pulido de Proyectos

**Fecha:** 2026-07-29
**Estado:** Aceptado

## Contexto

Tras usar ADR 0048 en escritorio, el fundador reportó una segunda tanda de problemas y pedidos concretos:

1. El modo enfoque en escritorio no funcionaba — regresión real introducida por el propio ADR 0048 (ver Decisión 1).
2. Dentro de un proyecto, ninguna conversación mostraba en qué proyecto estaba parada.
3. La grabación de voz en modo texto usaba un toggle de click simple: el micrófono se ponía en rojo al lado de la flecha de enviar, y esa flecha parecía "terminar" la grabación pero en realidad la dejaba colgada sin transcribir — pidió el patrón de WhatsApp/Telegram/ChatGPT (mantener presionado, deslizar para cancelar, deslizar para bloquear).
4. Los emoji del cerebro (ADR 0048) "no quedan lindos" — pidió íconos propios en el mismo estilo visual ya establecido en la app, con el mismo pulso de luz que ya tienen los nodos activos, aplicado también al ícono.
5. El swipe lateral en mobile (chat↔dashboard) interfería con el scroll horizontal real dentro de los globos de chat (bloques de código, tablas).
6. Ajustes menores de Proyectos: botón "+ nueva conversación" también en la barra lateral dentro de un proyecto (no solo en el home), botón "borrar proyecto" reubicado al fondo del home (antes al lado del link a Drive, muy a mano de un click accidental).
7. Pidió revisar el backlog real de "Incubadora de Ideas" (snapshot en Drive) antes de seguir — leído, ninguna tarea ahí se pisa con lo de esta sesión.

**Hallazgo no relacionado, urgente**: durante la verificación con un mensaje real se confirmó que el crédito de la cuenta de Anthropic está agotado (`Your credit balance is too low to access the Anthropic API`) — bloquea cualquier respuesta real, en esta instancia de prueba y en producción (misma cuenta). Señalado al fundador aparte; no es parte de este ADR de UI.

## Decisión

### 1. Fix del modo enfoque (regresión de ADR 0048)

La regla que oculta las pestañas Conversaciones/Proyectos del cajón del hamburguesa en escritorio (`body.jarvis-mode #sidebar .sidebar-tabs`) no distinguía el estado `.docked` (la misma barra reutilizada como panel fijo dentro del modo enfoque) — quedaba vacía ahí también. Selector corregido a `:not(.docked)`.

### 2. `#projectContextBar`

Nuevo elemento sticky en la parte superior de `#chat`, oculto salvo que `currentProjectId` y `conversationId` estén ambos seteados (mismas condiciones que ya usa el botón 🏠 de ADR 0048) — muestra "📁 {nombre del proyecto}". `currentProjectName` se fija en cada `renderProjectHome(project)` real.

### 3. Grabación estilo WhatsApp/Telegram/ChatGPT

Se retira el toggle de click de `micBtn` (`handleMicClick`) y se reemplaza por Pointer Events reales con captura de puntero (`setPointerCapture`), igual para mouse y touch:
- **Mantener presionado**: `pointerdown` arranca `startRecording()` (mismo helper ya existente), reemplaza visualmente `attachBtn`+`textInput` por un overlay con punto rojo, timer (`0:00` en vivo) y el hint "‹ deslizá para cancelar".
- **Soltar sin deslizar**: transcribe y **envía directo** (`sendText(transcript)`) — sin paso de revisión manual, a pedido explícito ("hagamos como ellos"), distinto del flujo de "Toque" (`handleClickMode`, sin tocar, sigue mostrando la revisión de siempre).
- **Deslizar > 80px a la izquierda**: cancela — descarta el blob sin transcribir, no envía nada.
- **Deslizar > 60px hacia arriba**: bloquea (manos libres) — soltar el dedo/mouse ya NO corta la grabación; aparece un botón de basurero (cancelar) y el botón de enviar existente (`textSendBtn`) se reutiliza para terminar y enviar la grabación bloqueada, en vez de sumar un botón nuevo.

### 4. Cerebro: íconos propios + pulso

`BRAIN_NODE_ICON_PATHS`: 17 glifos dibujados a mano (viewBox 20×20, stroke 1.6, mismo lenguaje monolínea que el resto de `ICONS` en esta interfaz — varios directamente reusan el path exacto de mic/attach ya existentes), reemplazan los emoji de ADR 0048. Cada ícono es un `<svg>` anidado (`createBrainNodeIconEl`), no texto — el nombre completo sigue de tooltip nativo (`<title>`). `applyBrainSnapshot()` ahora sincroniza las mismas clases de estado (`brain-node-active`/`idle`/`ghost`) sobre el ícono además del círculo, así el pulso (`brain-breathe`/`brain-heartbeat`, ya existentes) y un nuevo glow (`filter: drop-shadow` cuando está activo) se aplican también al ícono — confirmado con el fundador que el mecanismo de "iluminarse y generar flujo" ya existía (ADR 0038/0040); esto solo lo extiende al ícono mismo.

### 5. Swipe lateral retirado

Los listeners `touchstart`/`touchend` que cambiaban chat↔dashboard en mobile se eliminan por completo — interferían con el scroll horizontal real dentro de bloques de código/tablas en los globos de chat. `dashBtn` sigue siendo el camino real para cambiar de vista.

### 6. Ajustes de Proyectos

- `renderProjectConversationsInto` suma un botón "+ nueva conversación" justo debajo de "← todos los proyectos", mismo lugar donde vive "+ nuevo proyecto" en la lista general — antes solo se podía arrancar desde el home.
- `#projectHomeDeleteBtn` se mueve al final del home (`.project-home-delete-btn`, estilo sutil de peligro) — separado de "abrir carpeta en Drive", que quedaba al lado de un click de borrado real.

## Verificado

- 398/398 tests de backend (sin cambios de Python esta ronda).
- Playwright en escritorio (1400×900) contra una instancia real aislada: modo enfoque muestra la barra con tabs adentro, botón borrar cerca del fondo del home, `#projectContextBar` con el nombre real del proyecto tras mandar un mensaje real, botón "+ nueva conversación" presente en el drilldown de la barra lateral, 17 íconos SVG reales (no emoji) en el grafo del cerebro.
- Playwright en mobile (430×900, con `--use-fake-device-for-media-stream`): mantener presionado activa `.recording` y el overlay con timer en vivo; soltar sin deslizar transcribe (cae en "no se escuchó nada" con audio falso en silencio, sin dejar nada colgado); deslizar a la izquierda cambia el hint a "soltá para cancelar" y cancela limpio al soltar; deslizar hacia arriba bloquea (🔒), soltar el mouse NO corta la grabación, y el botón de enviar existente la termina y envía. Cero errores de consola en ambas corridas.

## Consecuencias

- El envío directo al soltar (sin paso de revisión) es una diferencia de comportamiento real respecto del modo "Toque" — quedó así a pedido explícito; si en el uso real resulta que los errores de transcripción molestan sin poder corregirlos antes de enviar, es la primera pieza a reconsiderar.
- Los 17 íconos son un primer dibujo — señalado como ajustable si alguno no se lee bien a pantalla completa en el uso real (a diferencia del widget chico del dashboard, que sigue sin etiquetas por ser demasiado pequeño para cualquier ícono legible).
