# ADR 0126 — HUD: la profundidad 3D real rompía la clickeabilidad; el dock bloqueaba el grafo detrás

**Fecha:** 2026-08-06
**Estado:** Aceptado

## Contexto

Pedido explícito: reforzar visualmente el contenedor de mensajes en HUD, y "dejar que la conversación
sea clickeable más allá del mensaje actual — actualmente no deja clickear sobre el desplegable
transcripción." El reporte de exploración previo no había encontrado un bloqueo explícito
(`stopPropagation`/`pointer-events`) en el toggle — pidió investigación en vivo antes de tocar código.

## Hallazgo 1 (con Playwright, `elementFromPoint()`): la profundidad 3D real rompía el hit-testing

El efecto "canvas 3D" del chat en HUD (`#chatDock .msg`, Decisión 4) usaba `perspective: 900px` en
`.chat` + `transform: translateZ(...) translateY(...) scale(...)` por `--depth` (0 = mensaje más nuevo).
Confirmado en vivo: para un mensaje con `--depth > 0` (cualquiera que no sea el último), el punto central
del botón "▾ transcripción" —según su propio `getBoundingClientRect()`— resolvía con
`document.elementFromPoint()` a `#chatInner` (el contenedor padre), nunca al botón real. Un click ahí
literalmente no hacía nada, sin lanzar ningún error.

**Causa real**: `perspective` + `translateZ` proyectan cada burbuja en 3D real — la posición de pantalla
resultante puede no coincidir con lo que el layout 2D normal reportaría, y en una pila vertical con
varios mensajes, dos burbujas pueden terminar superponiéndose en pantalla en el punto exacto de un
control interactivo. Verificado empíricamente: sacando `perspective`/`translateZ`/`translateY` (dejando
solo `scale`, `opacity`, `filter: brightness` — 2D puro, mismo efecto visual de "achica y oscurece hacia
atrás") el mismo `elementFromPoint()` vuelve a resolver al botón real, y el click funciona.

## Hallazgo 2: `#chatDock` sin `pointer-events` bloqueaba el grafo de nodos detrás

`.chat-dock` es un rectángulo fijo de 760px de ancho por casi toda la altura de la pantalla, sin
`pointer-events: none` en ningún punto — cualquier zona vacía (el `margin-top: auto` arriba de una
conversación corta, el padding entre elementos) capturaba el click igual que si hubiera contenido real
ahí, tapando el grafo de nodos de HUD que vive detrás (`z-index` 2-3, contra el 9 del dock). Confirmado
con un nodo de prueba inyectado detrás del dock: el click nunca lo alcanzaba antes del fix.

## Decisión

- CSS de profundidad simplificado a `scale`+`opacity`+`filter` únicamente — sin `perspective`/
  `translateZ`/`translateY`. Mismo efecto visual ("los mensajes viejos se achican y oscurecen"), sin el
  desajuste entre layout e interacción.
- `pointer-events: none` en los contenedores puramente estructurales del dock (`#chatDock`,
  `.chat-dock-body`, `.chat`, `.chat-inner`), reactivado explícitamente solo donde de verdad hace falta
  recibir clicks: cada `.msg`, `.project-context-bar`, `#jumpToBottomBtn`, `.chat-dock-toolbar`,
  `.control-bar` (input/mic). El resto del rectángulo queda transparente a eventos — un click ahí llega
  directo al grafo de nodos real detrás.
- Ambos cambios scopeados a `#chatDock` — Vista Clásica y modo Foco (donde el chat es una lista plana
  sin este contenedor) quedan exactamente igual que antes, verificado.

## Verificado

- Playwright contra el server real (sin tocar datos, conversación de prueba interceptada): el toggle de
  transcripción de un mensaje viejo (`--depth > 0`) se abre con un click real; una zona vacía real del
  dock resuelve al grafo HUD real (`dashHudWidgets`) en vez de al propio dock; el último mensaje sigue
  siendo clickeable; el micrófono/input siguen recibiendo eventos con normalidad. Cero errores de consola
  reales.
- Verificado por separado que Vista Clásica no cambió: `#chat`/`.msg` mantienen `pointer-events: auto`
  normal ahí (las reglas nuevas están scopeadas a `#chatDock`, que solo existe físicamente ocupado
  mientras HUD está activo).
- `.venv/bin/python -m pytest -q` — 990 passed (esta fase es 100% frontend, sin cambios esperados).

## Consecuencias

- El "canvas 3D real" (perspective+translateZ) queda descartado como técnica en este chat — cualquier
  futuro efecto de profundidad ahí debe evitar depender de `perspective`/transforms 3D reales por el
  mismo motivo (desajuste de hit-testing), o aplicarse solo a elementos sin contenido interactivo propio.
