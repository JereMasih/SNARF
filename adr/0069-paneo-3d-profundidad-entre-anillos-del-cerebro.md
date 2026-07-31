# ADR 0069 — Paneo 3D: profundidad real entre los anillos del cerebro

**Fecha:** 2026-07-30
**Estado:** Aceptado

## Contexto

Pendiente de varias rondas anteriores: el fundador pidió un efecto de cámara 3D/perspectiva con paneo por capas que revelara profundidad real entre los anillos del cerebro (Entrada / Especialistas Cognitivos / Capacidades, más el núcleo del Orchestrator), estilo holograma Jarvis/Ultron — distinto del zoom-hacia-un-nodo que ya existía (`brainCamera`/`triggerBrainCameraFocus`), que mueve todo el grafo como una sola unidad plana.

## Decisión

Sin WebGL ni una librería 3D nueva: el mismo desvío orbital de cámara que ya existía (`driftX`/`driftY` en `updateBrainCamera`, antes un wobble casi imperceptible de ±3 unidades) ahora se aplica a cada nodo con una intensidad distinta según su anillo — `brainDepthFactorFor(id)`: núcleo (orchestrator) ×1.7, anillo de Entrada ×1.0, Especialistas ×0.55, Capacidades (el más externo) ×0.2. El núcleo se corre notablemente más que el anillo externo, dando la sensación de volumen real (lo "cercano" reacciona más al movimiento de cámara que el "fondo"), en vez de un dibujo plano.

Se aumentó también el radio del drift orbital (de ±3 a ±18 unidades del viewBox) para darle recorrido real al efecto — antes era demasiado sutil para leerse como movimiento de cámara.

**Problema técnico real encontrado y resuelto**: los nodos ya tienen animaciones CSS propias sobre `transform` (`brain-breathe`/`brain-heartbeat`, el pulso de reposo/actividad) — una animación CSS activa sobre `transform` le gana al atributo `transform` de SVG puesto por JS, no se combinan. Aplicar el paralaje directo sobre el círculo/ícono lo habría dejado invisible en la práctica (los nodos casi siempre están pulsando). Se resolvió envolviendo cada nodo+ícono en su propio `<g>` (`brainNodeGroupEls`, nuevo) — el paralaje va en el `<g>` padre, la animación de pulso sigue intacta en el hijo, ambos transforms se componen sin conflicto.

Los edges (líneas del centro a cada nodo) no tienen animación de `transform`, así que se recalculan directo: el atributo `d` de cada línea se reconstruye cada frame con el punto de inicio (centro + su propio desvío) y el punto final (nodo + el desvío de SU anillo) — server ~35 elementos por frame, costo insignificante.

## Verificado

- 529/529 tests (sin cambios de backend — 100% frontend).
- Playwright: tras 2.5s de animación, el núcleo se desplazó ~31 unidades mientras un nodo del anillo de Capacidades se desplazó ~3.6 (más de 8x de diferencia, confirmando el paralaje diferencial real, no solo visual). Los `d` de los edges se recalculan correctamente. Cero errores de consola. El foco de zoom existente (`triggerBrainCameraFocus`) se verificó intacto (`getComputedStyle(...).transform` mostró el zoom activo normalmente).
- Capturas en dos momentos distintos confirman visualmente el desplazamiento entre capas, sin glitches ni saltos.

## Consecuencias

- La mini-animación del dashboard (`brainMiniSvgMarkup`) es una función completamente separada, sin cámara ni canvas — no se ve afectada por este cambio.
- El pendiente de la versión "contenida en la caja de chat" del cerebro completo en desktop (hoy sigue siendo el overlay global) sigue explícitamente pospuesto, a pedido del fundador.
