# ADR 0053 — Cerebro: flujo de partículas orgánico (reemplaza el pulso de guiones) y más niebla volumétrica

**Fecha:** 2026-07-29
**Estado:** Aceptado

## Contexto

El fundador confirmó que la dirección general del cerebro (constelación de nodos, íconos propios) le convence, pero señaló que la implementación concreta del "haz de luz" entre nodos no lo hacía: era una línea de guiones en movimiento (`stroke-dasharray` + `stroke-dashoffset`), un efecto que describió como mecánico, tipo "tac, tac, tac". Pidió en cambio un **flujo de partículas** que se acomodan como neuronas/viento/luz en la dirección del vector — imperfecto, orgánico, no una línea sobre rieles. Además pidió: más sensación de profundidad/volumen (luz y sombra), un zoom de cámara más memorable (hoy siempre el mismo valor exacto), y más partículas/niebla de luz — referencia explícita, otra vez, a Jarvis/Ultron.

## Decisión

### 1. El movimiento pasa de la línea SVG al canvas de partículas

`.brain-edge-flow` deja de animarse (se retira `stroke-dasharray`/`stroke-dashoffset`/`@keyframes brain-flow`) — queda como una guía estática, apenas más brillante que en reposo (`stroke-opacity: 0.55`, glow suave). El movimiento real ahora es `spawnFlowParticle()`/`updateAndDrawFlowParticle()`: partículas que nacen en el orquestador y viajan hacia cada nodo activo (`activeBrainNodeIds`, actualizado en `applyBrainSnapshot`), con:
- Velocidad distinta por partícula (nunca todas sincronizadas, evita el efecto "en fila").
- Deriva perpendicular al vector que se atenúa cerca de las puntas (`taper`) — se lee como "hacia ese nodo", no una nube sin dirección, pero tampoco una línea perfecta.
- Fade in/out orgánico en los extremos del recorrido.

Tasa de nacimiento probabilística (`BRAIN_FLOW_SPAWN_RATE`, ~7/seg por nodo activo en promedio, nunca exacta) para que varios nodos activos a la vez no se vean sincronizados entre sí.

### 2. Más niebla/profundidad

`spawnMistParticle()`: partículas grandes (10-32px), lentas, muy tenues (alpha 0.03-0.08) — distintas de las partículas ambiente puntuales ya existentes. Sumadas a `initBrainParticles()` (22 en escritorio, 12 en mobile). `BRAIN_MAX_PARTICLES` sube de 400 a 550 para hacer lugar a niebla + flujo + partículas ambiente coexistiendo.

### 3. Zoom de cámara más memorable

`triggerBrainCameraFocus()` dejaba de ser siempre el mismo valor exacto (`1.07`, blend `0.18`) — ahora varía dentro de un rango en cada evento (`zoom: 1.05-1.14`, `blend: 0.15-0.23`, duración del foco 2.2-2.7s), para que no se sienta repetitivo.

## Verificado

- 414/414 tests (sin cambios de backend).
- Playwright contra una instancia real aislada: confirmado que el edge activo ya no tiene `animation-name` ni `stroke-dasharray` (antes marchaba); confirmado que `activeBrainNodeIds` se puebla con actividad real y que `brainParticles` incluye partículas de tipo `flow` mientras hay un nodo activo; dos capturas separadas por 600ms muestran las partículas de flujo en posiciones distintas a lo largo del mismo vector (movimiento real, no una foto estática), con la niebla volumétrica visible de fondo.

## Consecuencias

- Pendiente de exploración futura (pedido por el fundador en la misma ronda, no implementado todavía): revisar si `TOOL_TO_NODE` puede desagregarse en más nodos reales usando datos que `activity_log` ya registra hoy sin costo nuevo (por ejemplo, separar las ~14 tools de `specialist_projects` en sub-categorías) — evaluado por separado, ver conversación, antes de tocar la taxonomía de nodos.
