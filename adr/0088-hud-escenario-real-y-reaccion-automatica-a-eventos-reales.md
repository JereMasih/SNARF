# ADR 0088 — La rueda como escenario principal, con reacción automática a eventos reales

**Fecha:** 2026-08-03
**Estado:** Aceptado

## Contexto

Viendo el dock v2 (ADR 0087) ya en producción, el fundador reportó el
problema de fondo: el dock era clickear-para-abrir (patrón "widget Omega"
de la transcripción de Iron Man) — por default aparecía colapsado a un
orbe en standby, y sin un click explícito no mostraba nada. Pedido
textual: "quiero que la rueda ocupe el escenario principal y que empiece
a mostrar cosas de relevancia de una vez... la idea es que sea una
manifestación de los procesos de Snarf." También pidió reducir la tabla de
texto de abajo a un renglón mínimo.

## Decisión

### La rueda pasa a ser el escenario principal

- `.hud-mini-dock`: de una franja fija de 190px a `flex: 1 1 auto` —
  ocupa todo el espacio disponible del panel.
- `.hud-feed-live`: de una lista con scroll a `height: 28px; overflow:
  hidden` — un solo renglón visible, siempre el más reciente (ya venía
  ordenado así).
- Radio del arco, tamaño del hub SVG y de los chips escalados ~1.5-1.7x
  para aprovechar el espacio nuevo (`HUD_MINI_RADIUS` 150→260,
  `HUD_MINI_ARC_DEGREES` 120→150, chips 40×34→58×48).
- `#hudMiniDock` arranca con `data-open="1"` (antes `"0"`) — el abanico de
  widgets está visible desde el primer instante, sin requerir click.
  Etiquetas de cada chip visibles por defecto (antes solo en hover/select).

### Reacción automática a cada evento real (no solo la alerta de costo)

Generalización del principio de "story moment" de ADR 0087/0086 (antes
acotado solo a la alerta de costo): **cada evento real nuevo** que llega
por `GET /dashboard/telemetry_feed` dispara un destello (`pulseHudDockNode`)
en el chip y la línea guía del nodo correspondiente — `filter: brightness`
en vez de `transform`, a propósito, para no competir con el `transform`
que ya controla el estado focus/select del mismo elemento (mismo tipo de
bug de animaciones pisándose ya resuelto antes esta sesión, ADR 0069/0078).
Solo se dispara en polls incrementales, nunca en la primera carga con todo
el historial de una — eso sería ruido, no una reacción a algo que "está
pasando" ahora.

Orden de polling corregido en el camino: `pollBrainHudDock()` (reconstruye
el arco) tiene que correr ANTES que `pollBrainHudFeed()` (dispara los
pulsos) en cada ciclo — al revés, el rebuild del arco borra el pulso recién
disparado antes de que se llegue a ver.

## Verificado

- `.venv/bin/python -m pytest -q` — 605/605 passed (cambio 100%
  frontend).
- Playwright contra un servidor real: dock abierto por default
  (`data-open="1"`), alto del dock ~23x el de la tira de feed (646px vs
  28px), etiquetas con opacity>0 sin hover. Sembrado un evento real nuevo
  mientras el panel estaba abierto (`gmail_summarize_inbox`) y capturado
  en vivo, sondeando cada 200ms, el chip `specialist_gmail` recibiendo la
  clase de pulso ~1.8s después del evento real (dentro de la ventana de
  poll de 3.5s) — confirma la reacción automática de punta a punta, no
  solo el código escrito. Cero errores de consola.
- No hizo falta reiniciar el servidor de producción (cambio 100%
  frontend) — alcanza con recargar la pestaña del navegador.

## Consecuencias

- La escala más grande + etiquetas siempre visibles puede sentirse
  recargada con los ~9-10 nodos reales simultáneos — si el fundador lo ve
  saturado en uso real, la siguiente iteración podría atenuar por
  relevancia real (ya calculada en Fase 5) en vez de mostrar todo con el
  mismo peso visual.
