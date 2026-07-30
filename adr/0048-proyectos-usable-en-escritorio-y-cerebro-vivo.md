# ADR 0048 — Proyectos usable de verdad en escritorio, menú contextual, copiar y cerebro vivo

**Fecha:** 2026-07-29
**Estado:** Aceptado

## Contexto

El fundador usó Proyectos Mark II (ADR 0047) de verdad en escritorio y reportó una lista de problemas concretos, la mayoría bugs reales encontrados al usar la interfaz, no pedidos de diseño:

1. Entrar a un proyecto desde la barra lateral en escritorio llevaba a "una pantalla sin nada" — sin botón de nueva conversación, sin caja de texto — y solo aparecía el home real del proyecto al tocar el botón de dashboard.
2. Las conversaciones nuevas de un proyecto se quedaban mostrando el placeholder "(nueva conversación)" para siempre en las listas.
3. El cajón del hamburguesa en escritorio seguía mostrando las pestañas Conversaciones/Proyectos, redundantes con el bloque de historial que ya vive fijo en la grilla del dashboard.
4. Sin forma de volver al home de un proyecto sin salir de la conversación abierta.
5. El icono suelto 📁 (mover a un proyecto) y ✕ (quitar del proyecto) no convencían como interacción — pidió un menú contextual (⋮) en su lugar, y señaló que dentro de la vista de un proyecto tampoco había forma de reasignar una conversación a OTRO proyecto (solo quitarla).
6. Conversaciones sin título — investigado con los datos reales del log: el título en sí se genera bien (primer mensaje), el bug real era la falta de refresco tras el primer mensaje.
7. Pidió botones de copiar en las respuestas de Snarf (la respuesta completa, y cada bloque de código/entregable por separado, para no arrastrar el comentario alrededor).
8. El cerebro de Snarf (ADR 0038/0040) no se sentía "vivo" ni creciente fuera de la pantalla completa, y pidió reemplazar los títulos de texto de cada nodo por un ícono.

## Decisión

### 1. Bug raíz de navegación en escritorio — `enterProject()`

`showChat()` apaga el modo Jarvis (`applyJarvisMode()` solo lo activa si `currentView === "dashboard"`). En escritorio el chat/home de proyecto vive reparentado dentro de `#dashGridDesktop`; apagar Jarvis no vacía esa grilla, solo la oculta y muestra `#viewChat`, vacío desde que su contenido real se reparentó al arrancar — de ahí la pantalla en blanco. `enterProject()` ahora solo llama `showChat()` fuera de escritorio (`if (!isDesktopDashboard())`). Con esto, el resto de los síntomas reportados (sin botón de nueva conversación, sin caja de texto) desaparecen solos: eran consecuencia del mismo bug, no problemas independientes.

### 2. Listas que no se refrescaban

`sendText()` ahora llama `refreshConvLists()`/`refreshProjectList()` al completar un envío exitoso — antes nada volvía a pedir la lista tras el primer mensaje de una conversación nueva, así que el placeholder "(nueva conversación)" quedaba pegado indefinidamente.

### 3. Hamburguesa en escritorio sin duplicar el historial

`body.jarvis-mode #sidebar .sidebar-tabs, body.jarvis-mode #sidebar .sidebar-tab-panel { display: none; }` — selector con `#sidebar` a propósito: `#dashHistoryParked`/`[data-widget-id="history"]` reusa las mismas clases y no debe verse afectado. El cajón en escritorio queda solo para lo que no tiene otro camino: configuración del dashboard y cerrar sesión.

### 4. Botón fijo "🏠 home del proyecto"

Nuevo botón (mismo slot que `.mode-fab`, oculto en escritorio) visible solo mientras `currentProjectId` y `conversationId` están ambos seteados (una conversación de proyecto cargada) — `goToProjectHome()` limpia `conversationId`, vuelve a mostrar el home y se oculta a sí mismo.

### 5. Menú contextual (⋮) en vez de iconos sueltos

`buildConvMenu(actions)` — mismo patrón visual que `.user-menu`/`.user-menu-popover` ya existente (wrapper con `.open`, cerrado por click afuera), en vez del icono 📁/✕ suelto de la primera versión. Lista general: una acción ("mover a un proyecto"). Lista propia de un proyecto: dos acciones ("mover a otro proyecto" — ausente hasta ahora — y "quitar del proyecto"). `showMoveSubmenu()` reemplaza el `<select>` anidado por una segunda vista del mismo popover con los proyectos disponibles como botones.

### 6. Copiar respuesta y copiar bloque de código

`addMessage()` agrega un botón "📋 copiar respuesta" (texto plano original, no el HTML renderizado) junto al de "▶ escuchar". Cada `<pre>` de un bloque ` ``` ` recibe además su propio "📋 copiar" (`addCodeBlockCopyButtons()`) — copia solo `code.textContent`, sin el comentario de Snarf alrededor.

### 7. Cerebro: widget vivo + íconos por nodo

El widget colapsado del dashboard (`brainMiniBodyHTML`) era una foto fija, refrescada solo junto con el resto del dashboard — nunca se sentía "creciente" salvo abriendo la pantalla completa. Ahora hace poll propio cada 4s (`startBrainMiniPolling`/`stopBrainMiniPolling`) mientras el dashboard está a la vista, pausado si la pestaña está oculta o si la pantalla completa (que ya tiene su propio poll más rico, con pulsos y flujo animado) está abierta — nunca se piden dos snapshots del mismo estado a la vez.

Cada nodo del grafo (pantalla completa) reemplaza su título de texto por un ícono (`BRAIN_NODE_ICONS`, un emoji elegido por dominio real — ⚙️ orquestador, 🧠 razonamiento, 🗂️ Proyectos, etc.) — el nombre completo no se pierde, queda como tooltip nativo SVG (`<title>`) al pasar el mouse, y el feed de eventos lo antepone al nombre completo para no perder legibilidad ahí.

Confirmado con el fundador que el mecanismo de "el especialista se ilumina y genera flujo hacia sus herramientas/hacia el orquestador" que describió ya existe (pulsos, `brain-edge-flow`, radio de nodo creciente con `log2(count)`) — solo era invisible fuera de la pantalla completa, que es lo que este ADR corrige.

## Verificado

- 398/398 tests de backend (ningún archivo Python tocado esta ronda — todo el trabajo fue en `web/index.html`).
- Playwright de punta a punta contra una instancia real aislada, viewport de escritorio (1400×900): crear un proyecto desde el widget de la grilla, confirmar que el modo Jarvis sigue activo y el home es visible de entrada (antes pantalla en blanco), confirmar que el cajón del hamburguesa oculta las pestañas pero muestra el menú de usuario, crear una conversación real del proyecto y enviar un mensaje real, confirmar que el botón 🏠 aparece, volver al home con él, abrir el menú contextual dentro del proyecto y confirmar sus dos opciones, copiar una respuesta real y confirmar el cambio de texto del botón, mandar un segundo mensaje real y confirmar que el widget de cerebro colapsado cambia solo sin abrir pantalla completa, y confirmar los íconos por nodo en el grafo. Cero errores de consola.

## Consecuencias

- Los emoji de `BRAIN_NODE_ICONS` son una elección editorial, no un pedido literal del fundador carácter por carácter — señalado como ajustable si alguno no convence en el uso real.
- El refresco de listas tras `sendText()` es puro polling accionado por el propio envío (no un push del servidor) — coherente con el resto de la app (sin websockets todavía).
