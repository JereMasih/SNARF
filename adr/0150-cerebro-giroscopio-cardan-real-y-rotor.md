# ADR 0150 — Cerebro "giroscopio": cardán real (orientación anidada) + rotor con giro propio

**Fecha:** 2026-08-11
**Estado:** Aceptado

## Contexto

Feedback real del fundador sobre ADR 0147-0149, con una imagen física concreta: *"lo que quiero es un
giroscopio de cardán (gimbal gyroscope de tres ejes). Tiene un rotor central que gira a alta velocidad
sobre su eje, rodeado por anillos concéntricos (los cardanes o gimbals) que permiten que el rotor
mantenga su orientación mientras los anillos giran libremente en los tres ejes del espacio, con momentos
angulares que se contrarrestan."*

Hasta ADR 0149, los 3 anillos principales (`input`/`specialist`/`capability`) eran **hermanos**: cada uno
tenía su propio plano fijo en espacio-mundo (`BRAIN_RING_TILT`), pero ninguno dependía de la orientación
viva de otro — 3 elipses independientes que solo compartían el punto central, no anillos montados unos
dentro de otros. Solo el sub-anillo de la junta ejecutiva anidaba **posición** (su origen era la posición
viva de `specialist_executive_board`), nunca **orientación**. El orquestador, por su parte, nunca tenía
giro propio — quedaba estable por no moverse nunca, no por ninguna física de cardán.

Un cardán real anida **orientaciones**: el anillo externo sostiene los pivots del medio, que sostiene los
del interno, que sostiene el rotor — si el externo se inclina o gira, arrastra a todo lo que tiene
montado adentro. Eso era lo que faltaba para que la representación fuera un cardán real y no una
aproximación visual.

## Decisión

**Cadena real de anidado de orientación** (`BRAIN_RING_PARENT_CHAIN`, `web/index.html`), de afuera hacia
adentro, mismo orden que los radios reales del layout (`buildBrainGraphSkeleton`: input=65,
specialist=125, capability=195): Capacidades (más externo, lo que más lejos toca el mundo real, sin
padre — ancla al espacio-mundo fijo) → Especialistas (montado sobre la orientación viva de Capacidades) →
Input (montado sobre la de Especialistas). La junta ejecutiva se monta sobre Especialistas también, un
nivel más adentro. `brainApplyTierOrientation(vec, tier)` aplica el giro propio + inclinación de ese
tier y, si tiene padre en la cadena, sigue subiendo recursivamente aplicando también la orientación del
padre — así un anillo arrastra de verdad a los que tiene montados adentro. `brainRingWorldPos` (única
fórmula real de posición, ya lo era desde ADR 0148) pasó a construirse sobre esa función en vez de una
fórmula de tilt plana por tier.

**Rotor con giro propio, constante y no-reactivo**: el orquestador gana `BRAIN_RING_SPIN_BASE.orchestrator
= 0.9` (antes `0`) y un marcador visual dedicado (`brain-rotor-ring`, anillo punteado rotado en vivo en
`applyBrain3DProjection`). A diferencia de los demás anillos, el rotor queda **deliberadamente afuera**
de la reactividad de velocidad/dirección de ADR 0149 (`renderBrainFrame` lo avanza en un branch propio,
sin pasar por `brainTierHasRecentActivity`/`brainRingDirection`): un cardán real estabiliza precisamente
porque el rotor gira a ritmo constante, sin que lo que pase alrededor lo perturbe — hacerlo reactivo
rompería la metáfora en vez de reforzarla.

**Momentos que se contrarrestan**: se mantiene el signo alternado ya existente entre tiers
(`input +0.09 / specialist -0.13 / capability +0.06`) como la expresión real de "se contrarrestan", en
vez de construir una compensación dinámica entre anillos — eso agregaría reactividad por evento, algo que
ADR 0149 ya evitó a propósito para no generar un tembleque visual. Se revisa con evidencia real si, ya
con la orientación anidada en producción, no se percibe como equilibrado.

## Verificado

- Sin cambios de backend — sin regresión esperada en la suite de tests (solo `web/index.html`).
- Playwright real, puerto 8001 (nunca 8002): panel abierto, 41 nodos, cero errores de consola.
- Acoplamiento real de la cadena confirmado numéricamente (`brainRingWorldPos`, antes/después de mover el
  ángulo de giro de un tier):
  - `specialist_gmail` cambia de posición real cuando se mueve el giro de `capability` (su padre de
    orientación) — de `(300.2, 136.0, -10.4)` a `(346.6, 236.8, -78.3)`.
  - `input_text` cambia de posición cuando se mueve el giro de `specialist` (su padre).
  - `memory` (tier `capability`, raíz de la cadena) permanece **sin cambios** cuando se mueve el giro de
    `input` (su hijo) — la propagación es de padre a hijo, nunca al revés, como corresponde a pivots
    reales de cardán.
  - Ningún nodo con posición no-finita (`NaN`/`Infinity`) tras la composición de rotaciones encadenada.
  - `brainRingSpinAngle.orchestrator` avanza con el tiempo real y el `transform` del marcador
    `.brain-rotor-ring` se actualiza en cada frame, independiente de la actividad de los demás anillos.
