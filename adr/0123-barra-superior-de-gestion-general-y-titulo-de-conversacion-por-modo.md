# ADR 0123 — Barra superior de gestión general (#topChrome) y título de conversación en el lugar propio de cada modo

**Fecha:** 2026-08-05
**Estado:** Aceptado

## Contexto

El fundador pidió una barra superior nueva con estado de sistemas/modelo de LLM y avatar (reemplazando
la hamburguesa en Clásica desktop), más el nombre de la conversación/proyecto visible en cada modo
(HUD/Clásica/Foco). Al revisar el plan inicial, corrigió un punto central: **la barra superior nunca debe
mostrar datos de conversación/proyecto** — es solo gestión general de la app. El nombre de la conversación
tiene que vivir en el lugar propio de cada modo, integrado a la UI ya existente.

Investigación previa confirmó que cada modo ya tenía (o casi) un header propio reutilizable:

- **Clásica desktop**: el widget de chat ya arma un `<h3>` real en `.dash-widget-head`
  (`wrapExistingAsBlock`/`reparentChatIntoDashboard`) — solo hacía falta poder actualizar su texto.
- **HUD**: `#chatDockToolbar` ya existía en el lugar correcto (arriba de `#chatDockBody`), pero estaba
  `display:none` — se usaba solo como "estacionamiento" de los botones ☰/⤢, que se reubicaban a mano
  dentro de `.text-row` mientras el dock estaba activo (porque el toolbar era invisible).
- **Foco**: `#chatFocusPanel` solo tenía el botón de cerrar, sin header.
- **Proyecto**: ya resuelto de antes (`.project-home-head h2` + `#projectContextBar`) — sin cambios.

## Decisión 1: `#topChrome` — solo gestión general, nunca datos de conversación

Barra nueva (`position:fixed; top:0`), oculta por default, aparece con `mouseenter` sobre una franja de
64px en la parte superior de la ventana (listener global en `document`, porque el elemento arranca con
`pointer-events:none` y no puede "sentir" su propio hover hasta hacerse visible). Contenido:

- **Derecha**: `#topChromeStatus` (deriva de `GET /status`, mismo endpoint que ya usa el resto de la
  app) y `#topChromeModel` (deriva de `GET /llm-routing`, el modelo vigente del rol `orchestrator`) —
  se refrescan una vez al cargar, cada 30s, y al instante después de cambiar el ruteo desde
  Configuración. Verificado en vivo: reflejó el estado REAL de producción (`xAI — Grok 4.1 Fast`, un rol
  que estaba en fallback automático en el momento de probar).
- **Izquierda** (`#topChromeLeft`, solo Clásica desktop): el `.user-menu` real (avatar+nombre+popover,
  el mismo nodo de siempre, nunca clonado) se reubica acá con `syncTopChromeAvatar()` — llamada desde
  `applyJarvisMode()`, `setDashboardView()` y `deactivateDashHudSideEffectsOnly()`, los tres puntos que
  ya tocaban `jarvis-mode`/`dash-hud-active`. El popover, que en la sidebar abre hacia arriba, se
  reescribe con CSS scopeado a `#topChromeLeft` para abrir hacia abajo (`#topChrome` está pegado arriba
  de todo).
- `#menuBtn` (hamburguesa) se oculta en Clásica desktop
  (`body.jarvis-mode:not(.dash-hud-active) .menu-btn`) — ya no hace falta ahí porque Clásica desktop
  tiene el bloque "Historial" fijo en la grilla. Mobile y HUD conservan su hamburguesa/drawer de siempre.
- Solo visible en desktop (`@media (min-width: 900px)`) — mobile no cambia.

## Decisión 2: título de conversación, integrado a cada modo — nunca en `#topChrome`

`updateChatTitleDisplays()` centraliza esto, leyendo de `conversationTitleCache` (un `Map` poblado en
`renderConvListInto()`/`renderProjectConversationsInto()`, sin fetches nuevos — el título ya viaja en
esas respuestas). Escribe el mismo texto en los tres lugares reales:

- Clásica: `.dash-widget-head h3` del widget de chat.
- HUD: `#chatDockTitle`, un `<span>` nuevo dentro de `#chatDockToolbar` — que dejó de ser
  `display:none` y pasó a ser un header real y visible. Los botones ☰/⤢ ya NO se reubican a
  `.text-row` (código eliminado de `reparentChatIntoDock`/`reparentChatOutOfDock`): con el toolbar
  visible, se quedan siempre ahí.
- Foco: `#chatFocusTitle`, un `<span>` nuevo dentro de `#chatFocusPanel`.

Fallback siempre a `WIDGET_LABELS.chat` ("Chat con Snarf") cuando no hay conversación con título todavío
— nunca queda vacío. Llamado desde `loadConversation()`/`resetConversationPagination()` (conversaciones
nuevas), `openChatFocus()`/`closeChatFocus()`, `reparentChatIntoDock()`/`reparentChatOutOfDock()` y las
dos funciones de render de listas — cualquier punto donde `conversationId` o el modo activo cambian.

La coherencia entre modos (pedido explícito: la conversación en primer plano tiene que ser la misma al
cambiar de HUD a Clásica a Foco) sale gratis de esto: `conversationId` es una única variable global que
nunca se toca en los cambios de modo, y los tres headers leen del mismo cache — verificado en vivo
(Playwright): el mismo título aparece en Clásica, HUD y Foco sin ninguna lógica de sincronización extra.

## Decisión 3: se retira `#modeFab`/`#modePopover` (selector de modo de entrada en mobile)

Confirmado sin uso real ("no se usa hace muchísimo", superado por la interfaz de input actual) — HTML,
CSS y JS (`modeFab`, `modePopover`, `modeOptions`, `MODE_ICONS`, `openModePopover`/`closeModePopover`)
retirados por completo. El *estado* `mode`/`setMode()` en sí se mantiene intacto (sigue controlando
`orbWrap`/`textRow`, otros callers dependen de él) — solo se retiró el selector manual, no el mecanismo.

## Verificado

Playwright contra el server real de producción (puerto 8002, sin tocar datos reales — `/conversations`
y la conversación de prueba interceptadas con `page.route`, nunca escritas de verdad):

- Clásica desktop: hamburguesa oculta, avatar reubicado en `#topChromeLeft`, popover abre y funciona,
  `#topChromeStatus`/`#topChromeModel` con datos reales, título del widget correcto.
- HUD: `dash-hud-active` aplicado, hamburguesa sigue oculta (drawer propio), avatar vuelve solo a la
  sidebar, `#chatDockToolbar` visible, título sincronizado, ☰ se queda dentro del toolbar (ya no se
  reubica).
- Foco (abierto desde HUD): título sincronizado, igual al de los otros dos modos.
- Mobile: hamburguesa sigue visible, `#modeFab` ya no existe en el DOM, `#topChrome` con
  `display:none`.
- Cero errores de consola en los dos contextos (desktop 1280×800, mobile 390×844).
- `.venv/bin/python -m pytest -q` — 976 passed (sin cambios esperados, esta fase es 100% frontend).

## Consecuencias

- `.chat-dock-toolbar` pasa de ser un "estacionamiento" invisible a un header real — cualquier lógica
  futura que asumiera que estaba vacío/oculto debe revisarse (ninguna encontrada al auditar el resto del
  archivo).
- El popover del avatar ahora tiene DOS variantes de posicionamiento CSS (`bottom` en la sidebar, `top`
  en `#topChromeLeft`) scopeadas por selector de ancestro — si el markup del popover cambia, hay que
  actualizar ambas.
- Riesgo menor aceptado, no resuelto en esta ronda: `.project-home-btn` (arriba a la derecha, solo
  visible dentro de una conversación de proyecto) puede superponerse visualmente con `#topChrome` cuando
  ambos están visibles a la vez en desktop — impacto bajo (un ícono chico, la mayor parte del tiempo
  `#topChrome` está oculto) pero queda pendiente si se vuelve molesto en el uso real.
