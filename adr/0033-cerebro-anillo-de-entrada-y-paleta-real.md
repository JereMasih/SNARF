# ADR 0033 — Cerebro de Snarf: anillo de entrada, paleta real de marca, nodos fantasma

**Fecha:** 2026-07-29
**Estado:** Aceptado

## Contexto

Con capturas de referencia del cerebro luminoso de Jarvis en *Avengers: Age of Ultron*, el fundador pidió una tercera vuelta sobre la visualización (ADR 0031/0032): nodos de entrada que muestren cómo la información/energía fluye hacia adentro de Snarf, distinguibles según el canal (texto, voz, archivo) y —para archivos— según su tipo real (una imagen es distinta a una canción), múltiples niveles de profundidad con distinta velocidad, y una paleta de colores "extremadamente saturados" estilo Iron Man/neón/cyberpunk (fucsia, aqua, gris, negro, blanco, rojo, verde, poco amarillo, mucho violeta).

Antes de tocar código se resolvieron dos cosas explícitamente con el fundador:

1. **Límite honesto (Principio VI)**: se puede distinguir por tipo real de archivo (imagen/audio/video/PDF/doc — ya existe, `categorize_mime()`), pero no por género semántico (canción vs. podcast, nota de voz vs. reunión) — nada en el pipeline clasifica eso hoy, y agregarlo como distinción visual sin ese dato real detrás violaría el principio de nunca mostrar algo inventado.
2. **Origen de la paleta**: en vez de inventar colores, se buscó en el Drive ya indexado del fundador (`drive_search_knowledge`) y se encontró el documento real `PALETA DE COLORES JERE MASIH TRADER` — su paleta de marca personal de trading, con los hex exactos que pidió (Magenta `#ff00ee`, Aqua `#00ffde`, Violeta `#a124ff`, Verde `#00ff0a`, sobre negro/violeta oscuro `#16003e`). Se usó esa paleta real tal cual, sumando rojo/blanco/gris/amarillo para los estados que le faltaban.

## Decisión

### 1. Nuevo `snarf/telemetry/input_log.py` — el punto de entrada real, instrumentado por primera vez

Ni `/send` (texto), ni `/transcribe` (voz), ni `/files/upload` (archivo) emitían ningún evento hasta ahora — el cerebro no tenía cómo saber que algo había entrado a Snarf antes de que el Orchestrator hiciera algo con eso. Nuevo módulo, mismo patrón append-only que `activity_log`/`usage_tracker` (`data/input_log.jsonl`): `record(channel, category=None)`, `recent(n)`. Los tres endpoints ahora registran su canal real (`"text"`/`"voice"`/`"file"`), y para archivos, su categoría real vía `categorize_mime()` (ya existente en `snarf/knowledge/extraction.py`, reusado sin duplicar lógica de clasificación).

### 2. Tercer anillo en el cerebro: Entrada

`snarf/telemetry/brain.py` suma `input_text`/`input_voice`/`input_file` (tier `"input"`, el anillo más interno — lo primero que pasa, antes que nada) además de los anillos de Especialistas y Capacidades (ADR 0032). `snapshot()` gana un parámetro `input_entries` (con default `None` para no romper las llamadas existentes) y rutea cada entrada por su canal real.

### 3. Nodos fantasma: un tercer estado, no solo activo/idle

Un nodo con historia real pero sin actividad reciente está "en espera" (idle, latido lento — ADR 0032). Un nodo que **nunca** tuvo ninguna actividad real registrada ahora es "fantasma" (`brain-node-ghost`): gris, opaco, sin animación — potencial todavía sin usar, distinto de "en espera". Es honesto por diseño: hoy `specialist_gmail` e `input_file`/`input_voice` aparecen fantasma en la práctica porque el fundador no usó esos canales recientemente en esta instancia — no es un bug, es el reflejo real de qué partes del sistema se usaron y cuáles no.

### 4. Paleta real, aplicada por tier vía `currentColor`

Nuevas variables `--brain-*` en `:root` (magenta/aqua/violeta/violeta-oscuro/verde/rojo/amarillo/blanco/gris — los valores reales encontrados en el Drive, más los que faltaban) — escopeadas al cerebro, el resto de la interfaz se queda monocromática cian a propósito, sin romper la identidad visual ya establecida. Cada nodo/edge/pulso toma su color de una clase `brain-color-*` (`color: var(--brain-X)`) leída vía `currentColor` en `fill`/`stroke`/`filter`, para no repetir la lógica de color en tres lugares:

- Orchestrator (centro): blanco, con halo violeta constante ("ambiente épico").
- Especialistas Cognitivos: magenta.
- Entrada — texto: aqua: voz: violeta; archivo: gris (el nodo en sí es neutro — el color real va en el pulso puntual, no en el nodo permanente).
- Capacidades: aqua (continuidad con la identidad cian ya existente del resto de Snarf).
- Pulso de un archivo real, coloreado por su categoría real: imagen=amarillo, audio=magenta, video=verde, documento=aqua.
- Error (cualquier nodo/pulso): rojo, siempre gana sobre cualquier otro color.

**Bug real encontrado y corregido durante la verificación en vivo**: la regla base `.brain-node`/`.brain-pulse` traía un `color` propio por defecto (pensado como *fallback*), pero al estar declarada *después* de las clases `.brain-color-*` en la hoja de estilos, con la misma especificidad, siempre ganaba — todos los nodos se veían aqua sin importar su clase de color real. Corregido quitando el color por defecto de esas reglas base: cada nodo real siempre lleva una clase `brain-color-*` explícita (asignada en `buildBrainGraphSkeleton`), así que el fallback nunca hacía falta y solo estaba pisando el color correcto.

## Verificado

- 273 tests (todos los anteriores + 19 nuevos: `input_log.py` completo; instrumentación real de `/send`, `/transcribe` — incluido que audio demasiado corto NO registra entrada — y `/files/upload` con su categoría real; `brain.py` con el ruteo por canal del anillo de entrada).
- Verificación en vivo con Playwright: los 15 nodos (Orchestrator + 3 de Entrada + 1 Especialista + 10 Capacidades) renderizan sin recorte de etiquetas, desktop y mobile, sin errores de consola. El bug de color descripto arriba se encontró comparando el color computado real (`getComputedStyle`) contra la clase esperada, no solo mirando la captura. Confirmado con un snapshot inyectado con actividad real en todos los tiers: Especialista Gmail en magenta, Voz en violeta, Orchestrator en blanco con halo violeta, Capacidades en aqua — la paleta completa funcionando junta.

## Consecuencias

- El cerebro ya tiene cuatro niveles reales (Entrada → Especialistas → Capacidades, más el centro) — coherente con la arquitectura de tres capas del proyecto y con margen para crecer (más Especialistas, ver Roadmaps) sin rediseñar el layout.
- La paleta ampliada vive solo en `--brain-*`, nunca en las variables globales (`--glow`, `--error`, etc.) — el resto de Snarf no cambia de aspecto.
- `input_log.jsonl` es el tercer log append-only del proyecto (junto a `activity_log`/`usage_log`) — mismo patrón, mismo criterio de nunca perder ni inventar un evento.
