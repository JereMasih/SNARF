# ADR 0181 — Second Brain: decisión de UX del árbol de drilldown Área→Proyecto

**Fecha:** 2026-08-20
**Estado:** Aceptado

## Contexto

Fase C1 del plan Second Brain (`ROADMAP_SECOND_BRAIN_NOTION.md`, ver ADR 0179). El fundador pidió
explícitamente investigar mejores prácticas de UX para la nueva jerarquía Área→Proyecto→Conversaciones
antes de tocar `web/index.html` — evita rediseñar la interacción a mitad de Track C (Fase C2 en adelante).
Es una decisión puramente de diseño, sin dependencia de código de otras fases, por eso se ejecuta en
paralelo con A1.

## Decisión

**Progressive disclosure de un solo nivel expandido a la vez, in-place, nunca un árbol multi-expandido con
indentación.** El detalle completo (justificación punto por punto, con referencias reales a
`enterProject()`/`renderProjectPanelHeaderInto`/`appendChild` ya existentes en el repo) vive en
`ROADMAP_SECOND_BRAIN_NOTION.md`, sección "Fase C1" — este ADR registra la decisión, el roadmap la
mantiene viva para que la Fase C2 la implemente sin tener que rederivarla.

Resumen de los cuatro pilares de la decisión:
1. Un nivel visible a la vez, reemplazando la lista anterior — mismo patrón que `enterProject()` ya usa
   para Proyectos, extendido a un nivel más (Área) por encima.
2. Migaja de pan siempre visible, cada segmento clicable — extiende el botón "← todos" parcial que ya
   existe en `renderProjectPanelHeaderInto`.
3. Carga lazy estricta por nivel — Áreas al abrir el tab, Proyectos de un Área recién al expandirla,
   conversaciones/home recién al entrar. Mismo criterio de costo de ADR 0067.
4. Un solo componente reparentado entre mobile y desktop, nunca dos implementaciones paralelas — mismo
   patrón ya establecido desde ADR 0035/0048.

Se descartó explícitamente un árbol multi-expandido (varias ramas abiertas a la vez): con profundidad fija
de ≤3 niveles y contenido potencialmente numeroso en cada uno, crece verticalmente sin límite y pierde la
ventaja de "una sola pantalla, una sola decisión" que ya funciona bien hoy para Proyectos — sin ganar
ninguna capacidad real que el fundador haya pedido.

## Verificado

Fase puramente documental — no hay código que testear. `.venv/bin/python -m pytest -q` corrido igual, sin
cambio de conteo respecto a ADR 0180 (1549/1549).

## Consecuencias

Fase C2 (Tab "Second Brain" con jerarquía Área→Proyecto) implementa este patrón directamente — cualquier
sesión que la ejecute debe leer la sección "Fase C1" del roadmap antes de escribir la interacción, no
rederivar el diseño desde cero.
