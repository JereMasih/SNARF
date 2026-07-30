# ADR 0052 — Cerebro: pulso de activación suave y haces de luz reales entre nodos

**Fecha:** 2026-07-29
**Estado:** Aceptado

## Contexto

El fundador confirmó que los íconos propios de ADR 0049 le gustan y van en la dirección correcta, pero señaló dos problemas concretos de la animación:

1. El "latido" de un nodo activo (`brain-heartbeat`, doble golpe con escala hasta 1.2×) se veía como un "tac-tac" feo y poco prolijo, sobre todo con varios nodos activos al mismo tiempo (todos rebotando sin sincronía). Distinguió esto explícitamente del latido de espera (`brain-breathe`, escala sutil 1.04×), que sí le gusta.
2. Pidió que la diferenciación de un nodo activo sea sobre todo de **luminosidad/color/brillo/transparencia**, con movimiento mínimo si lo hay, y que los **haces de luz entre nodos** (el flujo por los edges) sean más reales/visibles — "que se desprendan haces de luz del ícono y del nodo".

## Decisión

- `brain-heartbeat` pasa de un doble golpe (`scale(1.2)` → `scale(1.02)` → `scale(1.16)`) a un solo pulso suave (`scale(1.05)` máximo), con la diferenciación real llevada al glow (`drop-shadow` de 4px a 18px).
- Nueva regla `.brain-node-icon.brain-node-active` (más específica, pisa a la anterior): el ícono en sí **no escala nada** — pulsa solo opacidad y glow (`brain-icon-glow`, 3px a 11px). El círculo de fondo (una mancha difusa) tolera bien un rebote sutil; el ícono (una línea con detalle real) no.
- `.brain-edge-flow` (el haz que viaja del orquestador a cada nodo activo) se vuelve más grueso (1.8→2.2px), con segmentos más largos (`stroke-dasharray` 5 9 → 10 16) y más brillo (drop-shadow 4px→7px) — se lee como un haz de luz real, no una línea punteada genérica.
- **Bug real encontrado en el camino**: `.brain-edge-flow` estaba declarada ANTES de `.brain-edge` en la hoja de estilos — como ambas clases conviven en el mismo `<path>` con igual especificidad, el orden de la hoja decide, y `.brain-edge` (declarada después) le pisaba el `stroke-width` en silencio desde que existe el efecto de flujo. Los haces nunca se vieron tan gruesos como el código decía — corregido reordenando `.brain-edge-flow` para que quede después de `.brain-edge`.

## Verificado

- 414/414 tests (sin cambios de backend).
- Playwright contra una instancia real aislada: tras un mensaje real, se confirmó que el ícono activo usa `animation-name: brain-icon-glow` (sin transform) y que el `stroke-width` computado del haz de luz es 2.2px real (antes quedaba en 0.7px por el bug de orden). Captura visual: un haz de luz punteado grueso y brillante conectando el orquestador con el nodo de razonamiento activo.

## Consecuencias

- Ninguna nueva — ajuste puramente visual sobre un mecanismo ya existente (ADR 0038/0040/0049).
