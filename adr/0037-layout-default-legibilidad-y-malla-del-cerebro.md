# ADR 0037 — Layout default del dashboard, legibilidad a 1920×1080, y malla volumétrica del cerebro

**Fecha:** 2026-07-29
**Estado:** Aceptado

## Contexto

Con la grilla unificada y el modo enfoque ya andando (ADR 0035) y el cacheo de tokens resuelto (ADR 0036), el fundador pidió tres cosas más antes de pasar a "Proyectos" en una sesión nueva: (1) un orden default concreto para el dashboard de escritorio — historial a la izquierda, cerebro arriba centrado, costo/tokens al lado del cerebro, chat debajo, y Drive/Gmail/Calendar/YouTube a la derecha bajando; (2) tipografía más legible, pensada para una pantalla real de 1920×1080 a pantalla completa; (3) retomar el rediseño visual del cerebro con nuevas capturas de referencia de Jarvis/Ultron (*Avengers: Age of Ultron*, la escena de creación de Ultron) — dos masas volumétricas de luz suspendidas en el aire, hechas de una malla densísima de filamentos finos tipo sinapsis, con chispas en los nudos, semitransparentes.

Aclaración hecha al fundador antes de tocar el cerebro: ADR 0006 ya fijó el principio de no reproducir interfaces de ficción con derechos de autor — se toma el *estilo* (densidad de malla, volumen, chispas) pero no el esquema literal celeste-contra-dorado de Iron Man/Ultron; la paleta real Jere Masih Trader (ADR 0033) se mantiene sin cambios.

De paso, el fundador preguntó por qué Snarf no usa MCP (Model Context Protocol) y pasó una transcripción sobre cuándo usar Skills de Claude Code vs. servidores MCP — se responde y se deja registrada la política en `CLAUDE.md` (no es una decisión de arquitectura de Snarf-producto, es una convención de cómo se trabaja en este repo).

## Decisión

### 1. Orden y tamaño default del dashboard de escritorio

`WIDGET_IDS` (backend `snarf/runtime/dashboard_prefs.py` y su espejo en `web/index.html`) pasa de `["history","chat","system","conversations","memory","cost","drive","gmail","calendar","youtube","brain"]` a `["history","brain","system","cost","chat","conversations","memory","drive","gmail","calendar","youtube"]`. Combinado con nuevos `DEFAULT_SPANS` (historial `col_span=3` a lo alto completo; cerebro `col_span=6` arriba; sistema/costo `col_span=3` cada uno, al lado del cerebro; chat `col_span=6` debajo del cerebro; conversaciones/memoria/drive/gmail/calendar/youtube todos `col_span=3`, para que el auto-flow disperso de la grilla los apile en una sola columna a la derecha en vez de desparramarlos a lo ancho), el resultado visual es exactamente el pedido: historial | cerebro+chat centro | columna derecha de paneles.

El archivo real de preferencias del fundador (`data/dashboard_prefs/fundador.json`, ya personalizado desde antes) se reescribió directamente al nuevo `panel_order`/`widget_options` — no alcanza con cambiar el default de Python, que sólo rige para preferencias nuevas o claves ausentes (`_normalize()` no pisa valores ya guardados). Se preservó su elección manual de ocultar YouTube (igual criterio que la migración de ADR 0035: lo que el fundador ocultó a propósito sigue oculto).

### 2. Legibilidad a 1920×1080

`rem` es siempre relativo al `<html>` raíz, nunca al ancestro más cercano — no alcanza con subir el tamaño en `body.jarvis-mode` (que además no es seleccionable desde `html`). Se agregó `html { font-size: 18px; }` dentro del mismo `@media (min-width: 900px)` que ya gatilla el resto del modo escritorio (antes 16px, el default del navegador, sin ningún ajuste). Efecto: todo el texto dimensionado en `rem` en el dashboard de escritorio crece ~12.5% de una sola vez, sin tocar cada clase suelta. Mobile no se toca (la media query no aplica bajo 900px).

### 3. Cerebro: malla de filamentos, aura volumétrica, más brillo

Sin tocar ninguna lógica real de datos (nodos, colores por tier, latido activo/idle/fantasma, pulsos, flujo de edges, cámara) se agregó una capa puramente atmosférica en el mismo `<canvas>` de partículas ya existente (ADR 0034):

- **Malla de filamentos** (`initBrainMesh`/`drawBrainMesh`): alrededor de cada nodo real (incluido el centro) se generan 9 puntos satélite dentro de un radio corto, coloreados con el mismo `currentColor` real de ese nodo (incluye a los nodos fantasma, que ya heredan gris). Cada punto se enlaza con sus ~4 vecinos más cercanos dentro de un radio de 78 unidades — lo bastante grande como para que satélites de nodos *distintos* se toquen y la malla lea como una sola masa conectada, no triángulos aislados por nodo. Se genera una sola vez al construir el grafo (no por frame); la animación es solo un jitter sinusoidal de posición por punto.
- **Aura volumétrica** (`drawBrainAura`): gradiente radial violeta/aqua muy tenue centrado en la cámara, con una respiración lenta (`sin`) — la sensación de "entidad de luz" pedida, sin inventar ningún dato.
- Viñeta radial nueva en el fondo de `.brain-graph` (CSS) para que el grafo se lea como un objeto flotando en un volumen oscuro.
- Brillo (`drop-shadow`) del nodo central y del latido activo, aumentado (9px→14px, 11px→16px).

Ambas capas se dibujan antes que las partículas ambiente/estallido ya existentes, en el mismo `globalCompositeOperation = "lighter"`, así que nodos y etiquetas (SVG, capa aparte) siguen siempre legibles encima.

## Verificado

- 288 tests (sin cambios de conteo — este ADR es puramente frontend, salvo el ajuste de orden default que sí tiene test de regresión ya existente, actualizado). Regenerado el archivo real de preferencias del fundador.
- Verificado en vivo con Playwright a 1920×1080 contra un servidor descartable (no el real de producción, puerto 8002): orden de bloques en pantalla coincide exactamente con el pedido, `font-size` raíz confirmado en 18px, cero errores de consola. Confirmado en un viewport angosto (390×844) que el tamaño de fuente vuelve a 16px y `jarvis-mode` nunca se activa — mobile intacto.
- Cerebro verificado en vivo a pantalla completa (desktop y mobile): malla generada (135 puntos, 335 enlaces con la densidad final), aura visible, cero errores de consola, loop de animación confirmado apagado al cerrar (sin fugas, mismo chequeo que ADR 0034).

## Consecuencias

- `DEFAULT_SPANS`/`WIDGET_IDS` siguen viviendo en dos lugares en espejo (`snarf/runtime/dashboard_prefs.py` y `web/index.html`) — cualquier cambio futuro de orden/tamaño default debe tocar ambos, señalado ya en ADR 0035.
- La malla es atmósfera pura, igual que las partículas ambiente: no representa ningún dato propio y no debe usarse como si lo hiciera. Si se necesita más densidad/intensidad a futuro, los puntos de ajuste son `BRAIN_MESH_SATELLITES_PER_NODE`, `BRAIN_MESH_LINK_DIST` y `BRAIN_MESH_NEIGHBORS`.
- Política Skills vs. MCP para este repo (no para Snarf-producto) registrada en `CLAUDE.md`, no acá — es una convención de cómo se trabaja con Claude Code en este proyecto, distinta de una decisión de arquitectura de Snarf.
