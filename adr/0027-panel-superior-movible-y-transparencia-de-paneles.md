# ADR 0027 — Panel superior movible y transparencia de paneles/burbujas

**Fecha:** 2026-07-27
**Estado:** Aceptado

## Contexto

Al usar el layout Jarvis ya con ADR 0026 corregido, el fundador notó que todos los paneles se podían arrastrar excepto el de arriba (Conversaciones) — confirmó que la columna izquierda (lista de conversaciones + estado del sistema) está bien que quede fija, pero el panel superior no debería estarlo. También pidió que los paneles y las burbujas de chat dejen de ser un tinte plano y tengan un degradé del centro (más visible) hacia los bordes (más oscuro), coherente con el resto de la estética Jarvis, cuidando que la línea de escaneo de fondo siga pasando por detrás de todo.

## Decisión

1. **Panel superior movible**: `TOP_ZONE` (fijo, un solo widget) y `RIGHT_ZONE` se fusionaron en un solo grupo reordenable, `TOP_AND_RIGHT_ZONE` (los 6 widgets salvo "Estado del sistema", que sigue fijo a la izquierda por decisión explícita del fundador). El primer widget de ese orden combinado ocupa la franja superior (ancho completo); el resto cae en la columna derecha. Arrastrar cualquier widget al principio lo "asciende" a la franja de arriba; arrastrar el que estaba arriba hacia abajo lo "baja" a la columna derecha.
2. **`makeReorderable` generalizada** para operar sobre varios contenedores como si fueran una sola lista (antes solo aceptaba un contenedor): al soltar, se recalculan los ids combinando ambas zonas y se vuelve a renderizar el dashboard completo, que reasigna automáticamente cuál widget va arriba y cuáles a la derecha según el nuevo orden.
3. Las funciones de refresco de Gmail (`checkGmailForNewMail`, `startGmailDigestPolling`) ya no asumen que el widget de Gmail vive en una zona fija — ahora lo buscan por id en todo el documento, porque después de este cambio puede terminar en la franja de arriba o en la columna derecha según cómo el fundador lo haya movido.
4. **Transparencia de paneles y burbujas**: `.dash-widget`, `.msg.user` y `.msg.snarf` pasan de un `background` plano semitransparente a un `radial-gradient` (más tinte/brillo en el centro, oscureciendo hacia el borde) más `backdrop-filter: blur(6px)` para el efecto de vidrio esmerilado ya usado en el sidebar y el panel de configuración. Verificado que la línea de escaneo de fondo (`.scanline`) sigue pasando detrás: ya pintaba por debajo de `#appRoot` desde el fix de stacking de ADR 0024 (`#appRoot` tiene su propio `z-index:2`, mayor al `z-index:1` de `.scanline`) — lo que se veía "por encima" antes era la línea transparentándose a través de un fondo casi 100% translúcido, no un problema real de orden de apilamiento.

## Verificado

- Con Playwright (mouse real): arrastrar el primer widget de la columna derecha hasta la franja superior efectivamente lo promueve, y el que estaba arriba pasa a la columna derecha.
- Suite completa: 93/93 (sin tests nuevos — cambio de CSS y de mecánica de arrastre ya cubierta por el patrón existente).
- Captura de pantalla real confirmando el degradé aplicado y la línea de escaneo pasando por detrás de los paneles.

## Consecuencias

- La zona de cada widget (arriba/izquierda/derecha) ya no es un dato fijo por id — se deriva en cada render de la posición en `panel_order`. Cualquier código que asuma "Gmail siempre está en la columna derecha" (como pasaba antes en las funciones de refresco) queda roto por diseño; ya corregido en este mismo ADR, pero vale tenerlo presente para futuros widgets.
