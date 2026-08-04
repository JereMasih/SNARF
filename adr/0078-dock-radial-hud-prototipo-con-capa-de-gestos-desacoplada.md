# ADR 0078 — Dock radial HUD (prototipo, Fase 2) con capa de gestos desacoplada del render

**Fecha:** 2026-08-03
**Estado:** Aceptado

## Contexto

Fase 2 del plan de HUD (ver `SESSION_STATE.md`): construir el componente de
dock radial — widgets en arco alrededor de un punto focal, con perspectiva
3D real, tres estados de interacción (collapsed/focus/select) y la
traducción de gestos separada del render para poder reemplazar mouse por
otra fuente de señal (eye-tracking, Fase 9) sin rehacer el componente. Datos
mock, todavía sin backend real.

## Decisión

### `web/hud_gestures.js` (nuevo) — capa de gestos, agnóstica de la fuente

`HUDGestureController` no toca el DOM salvo en `bindPointerSource()` (el
único método que traduce mouse/touch reales a las llamadas abstractas
`.focus(id)`/`.blur(id)`/`.select(id)`/`.deselect()`). Cualquier fuente
futura (ej. un puente de visionOS) llama directo a esos métodos sin que el
render se entere de qué generó el evento. Invariante: como mucho un nodo
seleccionado a la vez — seleccionar uno nuevo deselecciona el anterior
automáticamente.

### `web/hud_dock_prototype.html` (nuevo) — prototipo autocontenido

Arco de 9 nodos mock (vocabulario real de `brain.py`: `drive`, `llm`,
`specialist_gmail`, etc.) sobre un contenedor con `perspective`, posicionado
por proyección cilíndrica real (`x = R·sin(θ)`, `z = R·(cos(θ)-1)`) — los
nodos en los bordes del arco quedan genuinamente más lejos en Z, no es un
efecto simulado con `scale()`. Estados: collapsed (ícono) → focus (hover,
se expande, no persiste) → select (click, ancla un panel con feed mock
usando el verbo temático real de `verbs.py`, hasta cerrarlo explícito).
Construido sobre `web/hud_design_tokens.css` (Fase 0). Todavía no se enlaza
desde `web/index.html` — Fase 5 decide esa integración cuando reemplace los
datos mock por reales.

## Tres bugs reales encontrados y corregidos verificando con Playwright

1. **Posición 3D pisada por la animación de estado.** `translate3d()` puesto
   por JS y la animación `hud-materialize` (que anima `transform: scale()`)
   competían sobre la misma propiedad del mismo elemento — la animación
   ganaba y los 9 nodos terminaban en la misma posición. Mismo bug ya
   documentado y resuelto en el cerebro actual (ver ADR 0069: "los nodos ya
   pulsan con animaciones CSS propias sobre `transform`, que le ganan a un
   `transform` puesto por JS"). Resuelto igual: envolver cada nodo en un
   `.hud-node-slot` que solo carga la posición, separado del `.hud-node`
   interactivo que carga estado + animación.
2. **Doble binding de la fuente de gestos.** Se bindeó `bindPointerSource`
   tanto en `dock` como en `document.body` (para que el backdrop, fuera del
   dock, también cerrara al click) — un click en un nodo burbujeaba y
   disparaba `select()` dos veces (el segundo revertía el primero por el
   toggle), dejando el nodo en collapsed en vez de select. Un solo binding
   en `document.body` cubre ambos casos sin duplicar.
3. **Contexto de apilado: el backdrop tapaba a los demás nodos.** `.hud-dock`
   tiene `perspective`, que crea su propio contexto de apilado — el
   `z-index` de `.hud-node` solo ganaba *dentro* de ese contexto, no contra
   el backdrop (hermano, con `z-index` propio a nivel de `body`). Con un
   nodo ya seleccionado, no se podía clickear otro directamente. Resuelto
   dándole `z-index` explícito a `.hud-dock` para que todo el contenedor
   compita correctamente contra el backdrop.

## Verificado

Playwright/Chromium headless contra el archivo real (no un mock del DOM):
9 posiciones 3D distintas confirmadas, hover→focus sin persistencia,
click→select con panel anclado y verbo temático correcto en el feed mock,
selección persiste al sacar el mouse, cierre por botón × y por click en
backdrop, cambio directo de selección entre nodos (exclusiva, sin forzar
cerrar primero), toggle al reclickear el mismo nodo seleccionado, cero
errores de consola. Screenshots guardados durante la verificación.

## Consecuencias

- Fase 4-b (Vista HUD del cerebro) y Fase 5 (motor de relevancia, datos
  reales) reusan `HUDGestureController` tal cual — ninguna lógica de gesto
  para reescribir.
- `snarf/telemetry/verbs.py` (Fase 1) ya se ve reflejado en el prototipo,
  aunque todavía mockeado en JS — confirma que el vocabulario elegido en
  Fase 0/1 funciona visualmente antes de conectar el backend real.
