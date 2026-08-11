# ADR 0148 — Cerebro "giroscopio" v2: planos de órbita inclinados reales

**Fecha:** 2026-08-11
**Estado:** Aceptado

## Contexto

Feedback real del fundador sobre el primer corte de ADR 0147, antes de que llegara a producción de
verdad: *"los anillos orbitan alrededor del orquestador, pero no rotan de manera circular... deberíamos
tener anillos concéntricos que orbiten, giren y roten en todas direcciones, terminando en una esfera
holográfica conformada por el movimiento de los anillos... el eje central del giroscopio debe ser el
orquestador."*

Diagnóstico real del v1: cada nodo vivía en el plano XY plano de siempre, con una profundidad Z FIJA por
tier (`BRAIN_RING_Z`) y una rotación aplicada también en el plano XY (`brainApplyRingSpin`). Resultado
real: tres discos planos apilados a distinta profundidad, girando todos alrededor del mismo eje vertical
— se leía como platos de un tocadiscos, no como los aros de un giroscopio/esfera armilar real.

## Decisión

**Cada anillo pasa a vivir en su propio plano 3D inclinado, no en el plano XY compartido.** Reemplaza
`BRAIN_RING_Z` (Z fija por tier) + `brainApplyRingSpin` (rotación solo en XY) por:

- `BRAIN_RING_TILT`: dos ángulos de inclinación fijos por tier (`tiltX`, `tiltZ`) — distintos y
  deliberadamente no paralelos entre sí (input casi vertical, specialist y capability en diagonales
  opuestas), más uno propio para el sub-anillo de la junta directiva. Nunca decorativos al azar: son
  constantes fijas elegidas para que los tres planos se crucen entre sí, como los aros reales de una
  esfera armilar.
- `brainRingWorldPos(id)`: única función real que calcula la posición 3D VIVA de cualquier nodo —
  combina su ángulo de órbita real (`angle0`, fijo por su posición en el layout, + `brainRingSpinAngle`
  del tier, que sigue avanzando como en v1) con la inclinación fija de su anillo, dando una posición
  `(x, y, z)` donde **la Z ya no es una constante — depende de en qué punto de su órbita inclinada está
  el nodo en este instante**. Eso es lo que hace que de verdad "orbite" (acercándose y alejándose de la
  cámara en su recorrido) en vez de solo "girar en el lugar" a una distancia fija.
- El orquestador sigue siendo el único punto fijo real (`BRAIN_ORCHESTRATOR_Z = 90`, nunca orbita) — el
  eje real del giroscopio, tal como se pidió.
- **Nunca una segunda función de proyección**: `brainRingWorldPos()` alimenta el mismo `project3D()` de
  siempre (motor de cámara compartida, sin tocar) — se compone la rotación de anillo con la rotación de
  cámara, igual criterio que v1, solo que ahora la rotación de anillo ocurre en un plano real distinto
  por tier, no en el plano de la cámara.
- Todo punto que antes leía `brainNodeBasePos[id].z` + `brainApplyRingSpin` (nodos, bursts, foco de
  cámara, flujo de partículas, chips del anillo 4, malla de partículas ambiente) pasa a leer
  `brainRingWorldPos(id)` — un solo cambio real, propagado a los mismos 6 puntos reales de consumo que
  v1 ya había identificado y sincronizado, nunca una función nueva paralela.

## Verificado

- Sin cambios de backend — la suite completa sigue en 1288/1288.
- Playwright real, servidor aislado: la Z real de cada tier varía en un rango amplio (~87-204 unidades
  de spread, según tier) en vez de ser una constante — confirma que los nodos orbitan de verdad, no solo
  giran en el plano. La posición completa `(x,y,z)` de un nodo real cambia entre dos lecturas separadas
  por 3s reales. Los 4 planos de inclinación (`BRAIN_RING_TILT`) confirmados distintos entre sí. Dos
  capturas separadas por ~4s muestran una estructura visiblemente distinta (rotación real, no estática).
  Cero errores de consola.
