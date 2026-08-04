# ADR 0081 — Motor de relevancia contextual, conectado al dock radial (Fase 5)

**Fecha:** 2026-08-03
**Estado:** Aceptado

## Contexto

Fase 5 del plan de HUD (ver `SESSION_STATE.md`): construir el servicio que
decide qué widgets del dock (Fase 2) se muestran con más prioridad, en base
a tarea activa, alertas pendientes, eventos recientes y telemetría en
tiempo real (ej. gasto del día sobre un umbral → el widget de costo sube de
prioridad y se mueve al centro) — y reemplazar los datos mock del dock por
datos reales.

Dos de las cuatro señales pedidas ("tarea activa", "alertas pendientes") no
tienen ningún sistema real detrás en Snarf hoy. Se resolvieron con
honestidad, no inventando infraestructura que no existe:

- **"Alertas pendientes"** → la única noción real de alerta que existe es
  un error reciente en un evento de telemetría (`estado == "error"`, Fase
  1). No hay un sistema de alertas separado.
- **"Tarea activa"** → no existe un tracker de tarea activa (Proyectos es
  otra cosa: organización de archivos/notas, no una cola de tareas en
  curso). Se interpreta como el nodo con la actividad más reciente — la
  señal real más cercana a "en qué está trabajando Snarf ahora mismo".

## Decisión

### `snarf/telemetry/relevance.py` (nuevo)

- `rank_nodes(events, node_ids, now)`: score por nodo = recencia (decae
  linealmente dentro de una ventana de 1h) + frecuencia (eventos en la
  ventana, con techo para que un nodo ruidoso no tape al resto) + boost
  fuerte si hay un error reciente (la "alerta").
- `cost_alert(day_summary, threshold_usd, today_key)`: reusa
  `cost_history.by_day()` (Fase 3) — si el gasto de hoy cruza
  `DAILY_COST_ALERT_THRESHOLD_USD` (**decisión de diseño nueva de esta
  fase, $1.00/día — no un valor que el fundador haya fijado**, declarado
  como tal), devuelve una entrada de prioridad máxima (`nodo: "cost"`,
  score fijo por encima de cualquier nodo real). `None` si no hay alerta
  real — nunca se inventa una.
- `dock_priority(events, node_ids, day_summary, today_key)`: combina
  ambos, ordenado por score descendente. `DOCK_NODE_IDS` reusa el mismo
  subconjunto de 9 nodos que ya eligió el prototipo de Fase 2 — cuáles
  nodos entran al dock es una decisión visual, no de este motor.

### `GET /dashboard/dock_priority` (nuevo, `app.py`)

Arma el ranking real (`events.all_events()` + `cost_history.by_day()` +
la fecha real de hoy en `FOUNDER_TIMEZONE`) y lo devuelve.

### `web/hud_dock_prototype.html` — datos mock reemplazados por reales

- `fetch('/dashboard/dock_priority')` reemplaza el `MOCK_NODES` de orden
  fijo de Fase 2. Si falla (ej. `file://`, sin servidor), cae al mismo
  orden default de siempre — mismo patrón ya establecido en Fase 2/3.
- `centerOutPositions(rankedIds)` (nuevo): reordena el ranking (mejor
  primero) a posiciones de arco centro-hacia-afuera — el rank 0 cae en el
  slot central, el de mayor perspectiva/cercanía real. Así "sube de
  prioridad y se mueve al centro" es literal, no solo un cambio de orden
  en una lista.
- La alerta de costo (`nodo: "cost"`) es una entrada sintética nueva en
  `NODE_META` — no es un nodo real de `brain.py`, solo aparece en el dock
  cuando el backend real la reporta. Se distingue en ámbar incluso
  colapsada (`[data-alert="1"]`), reusando el token de atención de Fase 0.
- **Fuera de alcance a propósito**: el contenido del panel al seleccionar
  un nodo sigue usando el feed mock de Fase 2 (`MOCK_VERB`/
  `buildMockFeed`) — Fase 5 conecta la *prioridad* del dock a datos
  reales, no el feed del panel. `GET /dashboard/telemetry_feed` (Fase 4)
  ya existe para ese momento, cuando se decida la integración final del
  dock al dashboard real.

## Verificado

- `.venv/bin/python -m pytest -q` — 598/598 passed. 10 tests nuevos en
  `tests/test_relevance.py` (recencia, frecuencia con techo, boost de
  error, alerta de costo con/sin umbral cruzado, ranking combinado), 2 en
  `tests/test_app.py` para el endpoint.
- Playwright contra el prototipo servido por HTTP real (no `file://` —
  necesario para poder interceptar el `fetch` con `page.route` y simular
  la respuesta real del backend, ya que un `fetch` a `file://` falla antes
  de llegar a la capa de red que Playwright intercepta): con un ranking
  simulado (misma forma exacta que devuelve el endpoint real, ya
  verificada por los tests de arriba) donde `cost` es rank 0, confirmado
  que cae en el slot central exacto (índice `floor((n-1)/2)`), con el
  atributo de alerta correcto y el panel mostrando "gasto del día". Cero
  errores de consola.

## Consecuencias

- Fase 6/7/8 pueden reusar `relevance.py` si necesitan priorizar algo más
  (ej. el panel de optimización de entrada de Fase 6 podría alertar de la
  misma forma).
- El umbral de $1.00/día es un default razonable pero arbitrario — si el
  fundador quiere ajustarlo, es un solo número en `relevance.py`, no
  requiere tocar la lógica de ranking.
