# ADR 0031 — Cerebro de Snarf: visualización tipo Jarvis del Orchestrator

**Fecha:** 2026-07-29
**Estado:** Aceptado

## Contexto

Fase 3 del roadmap de dashboard (ver `MASTER_MAP.md`, y su corrección en ADR 0029) fijó el orden: primero el registro real de actividad del Orchestrator (construido en ADR 0029), después la visualización sobre ese dato real. El fundador retomó hoy el trabajo y decidió reordenar el plan general: antes de migrar a un VPS o seguir indexando Drive (video/imágenes/audio/"other" pendientes), construir esta visualización — es lo que más necesita ahora mismo para entender el estado del sistema, y el prerrequisito ya estaba listo.

Antes de diseñar, se relevaron todas las fuentes de datos reales disponibles (`activity_log.jsonl`, `usage_log.jsonl`, el manifiesto de indexación de Drive, `episodic_memory`). Hallazgo central: `activity_log.jsonl` — el prerrequisito nombrado explícitamente en ADR 0029 — estaba vacío en la práctica (cero eventos desde que se instrumentó, porque todavía no se había ejecutado ninguna herramienta del Orchestrator desde entonces). La fuente realmente rica en datos reales hoy es `usage_log.jsonl` (4.126 líneas, de la corrida de indexación con Voyage) y el manifiesto de indexación ya persistido (4.618 archivos indexados). El diseño final combina las tres fuentes en vez de basarse solo en la nombrada originalmente — se acordó con el fundador vía preguntas directas (forma visual, arranque no vacío, ubicación como widget expandible, y el pedido explícito de que el pulso "viaje por los flujos entre nodos, como sinapsis").

## Decisión

### 1. Modelo de datos: 9 nodos de Capacidad + 1 nodo central

Nuevo `snarf/telemetry/brain.py`, módulo puro sin dependencias de `snarf.core`/`snarf.runtime`/`app` (mismo criterio de reusabilidad que `snarf/knowledge/` y `snarf/capabilities/`, ADR 0026). Mapea las 35 herramientas reales del Orchestrator (`TOOL_TO_NODE`) y los 3 vendors reales de `usage_log` (`VENDOR_TO_NODE`) a 9 nodos de Capacidad — `memory`, `drive`, `knowledge`, `documents`, `gmail`, `calendar`, `youtube`, `llm`, `voice` — más el nodo central `orchestrator`, que representa todo despacho por `Orchestrator._handle_tool` (incluidas las llamadas con `tool_name` inventado por el modelo, `status="unknown_tool"`, que iluminan el centro en vez de una Capacidad — la falla es del modelo, no de la Capacidad). `snapshot()` agrega conteos reales por nodo (incluyendo el manifiesto de indexación, plegado en `knowledge`) y normaliza ambos logs en una lista de eventos cronológica, con un test de regresión que compara `TOOL_TO_NODE` contra la lista real de herramientas del Orchestrator para que una herramienta nueva nunca quede sin mapear en silencio.

Dos piezas nuevas de bajo nivel para alimentar esto: `usage_tracker.recent(n)` (no existía, solo `summarize()`) y `DriveIndexer.manifest_summary()` (cuenta por estado del manifiesto ya persistido, sin disparar ningún escaneo).

### 2. Endpoint `GET /dashboard/brain?since=<epoch>`

Combina `activity_log.recent()` + `usage_tracker.recent()` + `DriveIndexer.manifest_summary()` vía `brain.snapshot()`. Protocolo de `since`: el cliente siempre reenvía el `server_time` de la respuesta anterior (no un timestamp de evento), así el filtro estricto (`timestamp > since`) nunca pierde ni duplica eventos entre polls.

### 3. Dos niveles de interfaz, nuevo widget `"brain"` en `WIDGET_IDS`

- **Widget colapsado** (dashboard existente): mini-grafo SVG estático, tamaño de cada nodo por escala logarítmica de su conteo real acumulado (nunca vacío — la corrida real de Voyage ya hace que `knowledge` se vea grande desde el primer load) + una línea de stat real. Sin polling propio: se refresca junto con el resto del dashboard, igual que Drive/Calendar/YouTube.
- **Pantalla completa al tocar el widget**: grafo grande (mismo layout trigonométrico, más grande) + feed cronológico en vivo al costado (desktop, ≥900px) o abajo (mobile) — layout confirmado en vivo con Playwright en ambos tamaños. Acá sí corre un polling propio (cada 3.5s), arrancado solo al abrir y detenido al cerrar, al salir a Chat, o cuando la pestaña se oculta — mismo patrón exacto que el auto-refresh del digest de Gmail (ADR 0026): `setInterval` + `visibilitychange` + parada explícita, sin ningún loop del lado del servidor.

### 4. Pulso de luz viajando por los edges

Cada evento real nuevo dispara un `<circle>` con SVG `<animateMotion>`/`<mpath>` que viaja del centro al nodo correspondiente en ~0.9s (declarativo, sin loop de animación a mano; se prefirió sobre CSS `offset-path` por soporte más estable en iOS Safari, navegador principal de este proyecto mobile-first) y una iluminación breve del nodo al llegar. Salvaguardas contra fugas en sesiones largas: tope de 12 pulsos animados por lote de poll, feed limitado a 60 filas, limpieza total del layer de pulsos al cerrar. Colores: se reusó la paleta ya existente del HUD (`--glow`/`--glow-soft`/`--glow-dim`/`--error`) — no se introdujo ninguna paleta nueva.

## Verificado

- 253 tests (todos los anteriores + nuevos: `usage_tracker.recent()`, `DriveIndexer.manifest_summary()`, `snarf/telemetry/brain.py` completo incluido el test de regresión contra las herramientas reales del Orchestrator, el endpoint `GET /dashboard/brain` con y sin `since`, y el nuevo widget en `dashboard_prefs.WIDGET_IDS`).
- Verificación en vivo con Playwright (mismo precedente puntual de ADR 0024): login real, apertura del dashboard, confirmación de que el widget colapsado y la pantalla completa renderizan sin errores de consola ni requests fallidos, en viewport desktop (1280×900, grafo y feed lado a lado) y mobile (390×844, apilados) — capturas confirman nodos de tamaño real distinto (`Conocimiento` y `Voz` visiblemente más grandes, reflejando la corrida real de Voyage) y el feed mostrando eventos reales (`voyage:voyage-4-lite`) con su antigüedad real.

## Consecuencias

- El "cerebro" queda honesto por diseño: todo lo que se ve — tamaño de nodo, contenido del feed, pulsos — traza a un evento real en `activity_log.jsonl`, `usage_log.jsonl` o el manifiesto de indexación. Nada inventado (Principio VI de Foundation).
- `activity_log.jsonl` sigue mayormente vacío hasta que el fundador use herramientas del Orchestrator vía chat de nuevo — el nodo central y las 7 Capacidades basadas en tool_name van a verse chicos hasta entonces, mientras `knowledge` y `voice`/`llm` (basados en `usage_log`, que ya tiene actividad real) se ven activos desde el día uno. Esto es correcto, no un bug: refleja qué parte del sistema tuvo actividad real y por qué canal.
- Con esto cerrado, el orden acordado con el fundador sigue con la migración a VPS (`VPS_MIGRATION.md`, preparada, sin ejecutar) y recién al final el resto del indexado de Drive (video, imágenes, audio, revisión de "other").
