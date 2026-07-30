# ADR 0064 — Fix: carrera del permiso de micrófono en mobile + íconos del reproductor

**Fecha:** 2026-07-30
**Estado:** Aceptado

## Contexto

El fundador reportó, probando en un teléfono real, que la primera vez que mantenía apretado el micrófono, el navegador mostraba el diálogo nativo de permiso de micrófono — y al tocar "permitir", la grabación quedaba arrancada para siempre, sin haber hecho el gesto de deslizar para bloquear y sin ninguna forma de cortarla (ni tocando el botón, ni deslizando) — solo se resolvía refrescando la página. Por separado, marcó que el botón de play/pausa del mini reproductor de audio se veía como un emoji (▶/⏸ como texto), no coherente con el resto de íconos del branding (SVG propios, sin emojis).

## Decisión

**Carrera del permiso de micrófono** (ADR 0059 ya había resuelto el caso de un tap accidental con `RECORD_HOLD_DELAY_MS`, pero no este): al mostrarse el diálogo nativo de permiso, el navegador corta el toque real en curso — dispara `pointercancel` mientras `getUserMedia()` (dentro de `beginActualRecording`) todavía está pendiente. El handler de `pointercancel` solo limpiaba `recordPointerId` cuando `state === "listening"` — si el diálogo interrumpía ANTES de eso (que es siempre el caso, porque `setState("listening", ...)` recién corre después de que `getUserMedia()` resuelve), no pasaba nada: `recordPointerId` seguía apuntando al pointer viejo. Cuando el usuario tocaba "permitir" y la promesa resolvía más tarde, `beginActualRecording` encontraba que `recordPointerId` seguía "vigente" y arrancaba a grabar igual — pero ya no quedaba ningún pointer real sostenido, así que ningún `pointerup`/`pointercancel` futuro podía terminarlo.

Dos cambios en `web/index.html`:
1. `pointercancel` ahora limpia `recordPointerId = null` siempre (no solo cuando ya estaba "listening"), y chequea `e.pointerId` como ya hacía `pointerup`.
2. `beginActualRecording` vuelve a chequear `recordPointerId !== pointerId` DESPUÉS de que `getUserMedia()` resuelve (no solo antes) — si el gesto ya no está vivo, corta los tracks del stream recién abierto y vuelve a `idle` sin arrancar a grabar. El permiso queda otorgado para la próxima vez, pero esa grabación en particular requiere un gesto nuevo y deliberado — exactamente lo que pidió el fundador.

**Íconos del reproductor**: `ICONS.play`/`ICONS.pause` (SVG rellenos, mismo criterio que el resto de `ICONS`) reemplazan los glifos de texto `"▶"`/`"⏸"` en los tres lugares donde se pintaban (estado activo, desactivación, construcción inicial del botón).

## Verificado

- 467/467 tests (sin cambios de backend).
- Playwright: se simuló la carrera exacta (un `getUserMedia` cuya resolución se controla a mano, con un `pointercancel` disparado mientras la promesa sigue pendiente, imitando el diálogo nativo interrumpiendo el toque) — el mic ya NO queda trabado grabando tras "otorgar" el permiso, y un segundo press (gesto nuevo) graba con normalidad. Se confirmó también que `.vn-play-btn` ya renderiza un `<svg>` real, sin texto.

## Consecuencias

- Ninguna: es un fix de un bug real sin cambiar el modelo de interacción pedido en ADR 0059 (tap vs. hold, deslizar para bloquear/cancelar) — solo endurece el caso donde el gesto se interrumpe por una razón externa a la propia interacción (el diálogo de permiso).
