# ADR 0058 — Cerebro: flujo bidireccional de partículas (ida/vuelta, dos colores)

**Fecha:** 2026-07-30
**Estado:** Aceptado

## Contexto

El fundador señaló que el flujo de partículas del cerebro (ADR 0053) viaja en un solo sentido — del orquestador hacia el nodo activo — y pidió partículas en ambos sentidos, de colores distintos, representando cuándo la información va del orquestador a un nodo y cuándo vuelve.

No existe hoy una señal real de "cuándo vuelve" el dato de una tool call — `activity_log` registra la llamada ya completa (con su `duration_ms`), no un evento de ida separado de uno de vuelta. Se aproxima con flujo simultáneo en ambos sentidos mientras el nodo está activo, en vez de inventar una cronología que no existe.

## Decisión

`spawnFlowParticle(nodeId, direction)` (`web/index.html`) ahora recibe una dirección: `"out"` (orquestador→nodo, color propio del nodo — igual que antes) o `"in"` (nodo→orquestador, color blanco — el mismo blanco del nodo central, ver `.brain-node-center`). `updateAndDrawFlowParticle` usa el mismo reloj `p.t` (0→1) para el fade en ambas puntas, pero invierte hacia dónde cae la posición visible según la dirección (`travel = direction === "in" ? 1 - p.t : p.t`). `spawnActiveFlowParticles` tira ambas direcciones por separado, cada una a la mitad de la tasa total de antes (3.5/seg en vez de 7), para que el total de partículas en pantalla no se duplique.

## Verificado

- 444/444 tests (sin cambios de backend — esto es 100% frontend/canvas).
- Playwright: con nodos forzados a activos, 19 partículas de flujo en pantalla, ~mitad "out" mitad "in", exactamente 2 colores distintos presentes (el del nodo + blanco). Captura visual confirma partículas blancas nítidas entre la malla de constelaciones, distinguibles del color propio de cada tier. Cero errores de consola.

## Consecuencias

- Es una aproximación (ida y vuelta simultáneas durante toda la ventana de actividad), no una animación literal de "salió ahora, vuelve en X ms" — no hay dato real para eso hoy. Si en el futuro se quisiera esa precisión, haría falta instrumentar el inicio y el fin de una tool call como dos eventos separados en `activity_log`, no solo el resultado final.
- Pendiente, todavía sin construir (pedido explícito del fundador en la misma ronda, de mayor alcance): efecto de cámara con perspectiva/paneo 3D que revele profundidad entre los anillos del cerebro al cambiar el ángulo de vista — se propone como próximo paso, ver mensaje de seguimiento al fundador.
