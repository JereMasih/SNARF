# ADR 0149 — Cerebro "giroscopio": dirección orbital reactiva + regla de crecimiento ampliada

**Fecha:** 2026-08-11
**Estado:** Aceptado

## Contexto

Feedback real del fundador sobre ADR 0148 (planos de órbita inclinados): confirmó que cada anillo debe
tener su propio eje de rotación (ya resuelto en ADR 0148, `BRAIN_RING_TILT`), y agregó un requisito
nuevo — *"ese anillo además debe tener movimiento orbital en una u otra dirección, que debe cambiar ante
el ingreso de nuevos datos."* Hasta acá, la actividad real reciente solo modulaba la VELOCIDAD del anillo
(`×1.8`), nunca su dirección — el signo de giro era fijo por tier (`BRAIN_RING_SPIN_BASE`), decorativo en
ese sentido.

Además, el fundador estableció una regla general para el desarrollo del cerebro de acá en más: *"cada
nueva funcionalidad debe incorporarse al cerebro como parte de su construcción"* — no una tarea de UI
aparte, diferida para después.

## Decisión

**Dirección orbital real por anillo, reactiva a datos reales — nunca al azar decorativo:**
`brainRingDirection[tier]` (±1) arranca con el signo de `BRAIN_RING_SPIN_BASE`. Se invierte en el flanco
real ocioso→activo de cada tier (`brainTierWasActive[tier]`, un frame de `renderBrainFrame`) — es decir,
cuando una ráfaga NUEVA de actividad real arranca después de un período sin actividad, ese anillo invierte
su sentido de giro. **Deliberadamente no en cada evento individual**: con la frecuencia real de eventos
(sobre todo el board ejecutivo, decenas por minuto en uso real), flipear en cada uno se vería como un
tembleque sin sentido, no como una reacción legible a que "algo nuevo está pasando". El flanco
ocioso→activo es la señal real más cercana a "llegaron datos nuevos" que ya existe en el código
(`brainTierHasRecentActivity`, mismo criterio que ya modulaba la velocidad).

**Regla de crecimiento del cerebro, ampliada** (`snarf/telemetry/brain.py`, punto 6 nuevo del protocolo
ya existente de ADR 0054): cualquier funcionalidad nueva real de Snarf se incorpora al cerebro como parte
de construirla, en el mismo cambio — nunca una tarea de UI aparte para después. Caso real que motivó
esto, citado en el propio comentario: la junta directiva existió varias rondas antes de tener sus 7 nodos
reales (recién en ADR 0147).

## Verificado

- Sin cambios de backend — 1288/1288 tests de la suite completa.
- Playwright real: dirección de `capability` confirmada estable (`1`) sin actividad; se invierte a `-1`
  en la primera ráfaga real (transición ociosa→activa); vuelve a `1` en una segunda ráfaga tras un período
  ocioso intermedio; se mantiene estable mientras el tier sigue activo sin nueva transición. Cero errores
  de consola.
