# ADR 0112 — Cerebro de Snarf: visualiza los 9 Especialistas nuevos de la Fase I

**Fecha:** 2026-08-05
**Estado:** Aceptado

## Contexto

A pedido del fundador ("actualiza el widget de cerebro de snarf para que se visualice todo lo
nuevo"). El backend (`snarf/telemetry/brain.py::NODE_TIER`) ya conocía los 9 nodos `specialist_*`
nuevos de la Fase I (calendar/research/content/sales/finance/community/agency/executive_board/
skill_factory) desde que se construyó cada rama — pero `web/index.html` mantiene, aparte, seis
tablas propias en JS con la lista de nodos reales (posición en el anillo, label, ícono SVG, color,
entrada del feed mini del HUD, familia visual de los globos) que nunca se actualizaron en el camino.
Sin esto, esos 9 nodos existían en el backend pero jamás se dibujaban — el widget "Cerebro" (y el
feed en vivo, y la Vista HUD) seguían mostrando exactamente el mismo grafo que antes de toda la
Fase I.

## Decisión

Las seis tablas de `web/index.html` se completan con los 9 IDs reales
(`snarf.telemetry.brain.NODE_TIER`, tier "specialist"), verificado contra el backend real antes de
tocar nada:

1. `BRAIN_SPECIALIST_ORDER` — posición en el anillo de Especialistas.
2. `BRAIN_NODE_LABELS` — tooltip/nombre completo.
3. `BRAIN_NODE_ICON_PATHS` — ícono SVG nuevo, dibujado a mano en el mismo lenguaje monolínea
   (viewBox 0-20, stroke 1.6) que el resto: lupa (Research), lápiz (Content), sobre con destello
   (Sales), barras (Finance), dos personas (Community), portapapeles (Agency), calendario con
   estrella (Calendar), tres cabezas sobre una mesa (Executive Board — mesa de directorio real),
   llave inglesa (Skill Factory — construcción).
4. `BRAIN_NODE_COLOR_CLASS` — mismo magenta que ya comparten los 4 Especialistas existentes (la
   paleta por tier ya está asignada completa; se distinguen por ícono/posición, no por color
   individual — mismo criterio ya documentado en el propio archivo).
5. `HUD_MINI_NODE_META` — entrada en el feed mini de la Vista HUD (label corto + código de 3
   letras), que el propio comentario del archivo ya declaraba con la intención de cubrir "TODOS los
   nodos reales de brain.NODE_TIER".
6. `HUD_BUBBLE_FAMILY` — familia visual del globo en la Vista HUD, elegida por lo que cada
   Especialista realmente hace: `scan` (Calendar/Research/Sales/Community — leen/interpretan),
   `document` (Content/Agency — publican un documento real), `think` (Executive Board — sintetiza
   opiniones, mismo criterio que `llm`), `admin` (Finance/Skill Factory — categoriza/construye, mismo
   criterio que Proyectos).

## Verificado

- **En un navegador real (Playwright), no solo que compile** — mismo criterio de CLAUDE.md para
  cambios de `web/index.html`. Contra el server real de producción (puerto 8002, ya con datos
  reales): login real, apertura del panel "Cerebro de Snarf", los 32 nodos reales confirmados en el
  DOM (`#brainEdges path[id^="edge-"]`, ningún método interno de JS asumido), los 9 tooltips nuevos
  confirmados por texto exacto, cada ícono nuevo confirmado con contenido SVG real y no vacío
  (118-334 caracteres cada uno). Cero errores de consola/página.
- Capturas de pantalla reales confirmaron visualmente el feed en vivo mostrando eventos reales
  (`Investigación · research_deep_dive`) con su ícono nuevo (lupa) correctamente renderizado.
- Sin cambios de backend — no aplica correr la suite de Python, igual se corrió (928/928) para
  confirmar que nada se rompió.

## Consecuencias

- `web/index.html` es un solo archivo estático servido con `FileResponse` — no requiere reinicio del
  server real para entrar en vigencia (a diferencia de un cambio de `snarf/*.py`).
