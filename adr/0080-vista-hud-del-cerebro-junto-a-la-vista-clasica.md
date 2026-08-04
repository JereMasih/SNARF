# ADR 0080 — Vista HUD del cerebro, en paralelo a la Vista clásica (Fase 4)

**Fecha:** 2026-08-03
**Estado:** Aceptado

## Contexto

Fase 4 del plan de HUD (ver `SESSION_STATE.md`): el widget cerebro actual
(grafo SVG/canvas, ADR 0031-0038) no se toca ni se reemplaza. Se agrega una
segunda vista ("Vista HUD") con el lenguaje visual de Fase 0 — feed de
texto con verbo temático + resumen por evento — más un selector entre
ambas, sin perder datos ni recargar el dashboard. Primera vez que este plan
toca `web/index.html` (4983 líneas, único archivo de frontend).

## Decisión

### `GET /dashboard/telemetry_feed` (nuevo, `app.py`)

Lee `events.all_events()` (el log unificado de Fase 1) y lo devuelve
anotado con `verbo` (`verbs.verbo_tematico(nodo, agente, estado)`) y
`resumen` (recorte mecánico de `skill` a 80 caracteres — nunca una llamada
nueva al modelo, ver TELEMETRY_SCHEMA.md). Mismo patrón `since`/
`server_time` que `/dashboard/brain` para poll incremental sin duplicar ni
perder eventos.

Deliberado: la Vista HUD consume este endpoint nuevo, no
`/dashboard/brain` — `brain.snapshot()` no tiene `agente` por evento ni el
vocabulario `completo`/`truncado`/`error` de estado (solo `ok`/`error`/
`unknown_tool`), y extender `brain.py` para cargar esos dos vocabularios
hubiera duplicado lógica que ya vive en `verbs.py`/`events.py`. Las dos
vistas siguen "alimentándose de los mismos eventos de telemetría" en el
sentido real: ambas derivan de las mismas llamadas a
`activity_log.record()`/`usage_tracker.record()`/`input_log.record()` — la
Vista clásica vía `brain.snapshot()` sobre los tres logs originales, la
Vista HUD vía el evento unificado que esos mismos `record()` ya emiten
desde Fase 1.

### Integración en `web/index.html`

- Nuevo toggle (`Vista clásica` / `Vista HUD`) en el header de
  `#brainPanel`, entre el título y el botón de cerrar.
- `.brain-layout` original (grafo + feed clásico) ahora tiene id
  `brainLayoutClassic` — **cero cambios a su contenido, estilos o
  comportamiento**, solo el id nuevo para poder ocultarla/mostrarla.
- `#brainHudView` (nuevo, hermano de `.brain-layout` dentro de
  `#brainPanel`): feed de texto, una fila por evento real
  (`verbo` + `resumen` + tiempo relativo), coloreado por `estado`
  (cian=completo, ámbar=truncado, rojo=error) con la animación de
  materialización de Fase 0.
- Tokens nuevos agregados al `:root` existente: `--hud-amber` (decisión de
  diseño nueva, no de una fuente real — ver Fase 0) y `--hud-font-mono`.
  El resto reusa `--glow`/`--text`/`--text-dim` ya existentes, sin paleta
  paralela.
- **Poll propio para la Vista HUD** (`pollBrainHudFeed`/
  `startBrainHudPolling`/`stopBrainHudPolling`), corriendo en paralelo al
  poll de la Vista clásica mientras el panel esté abierto — sin importar
  qué pestaña esté activa. Así cambiar de vista nunca pierde datos ni
  recarga nada (pedido explícito del fundador).
- **Decisión sobre archivos de Fase 0/2/3** (`web/hud_design_tokens.css`,
  `web/hud_gestures.js`): no se enlazaron acá. `web/index.html` no tiene
  ningún mecanismo de archivos estáticos servidos (`app.py` solo expone
  `FileResponse("web/index.html")`, sin `StaticFiles`) — es un archivo
  único por convención deliberada del proyecto (ver CLAUDE.md). Agregar un
  mount nuevo solo para esto hubiera sido una decisión de infraestructura
  aparte, no pedida. Se copiaron los ~20 valores/reglas que hacían falta
  directo al `<style>` existente, consistente con el resto del archivo.

## Bug real encontrado y corregido verificando con Playwright contra la app real

`el.hidden = true` (vía JS) no ocultaba el elemento: tanto `.brain-layout`
como `.brain-hud-view` ya tenían `display: flex` puesto por una regla de
autor — el `[hidden] { display: none }` es una regla del **user-agent**, de
prioridad de origen más baja que cualquier regla de autor (incluso con
igual o menor especificidad, el origen gana). Resultado real observado:
las dos vistas quedaban visibles a la vez, superpuestas. Corregido con
`#brainLayoutClassic[hidden] { display: none; }` /
`#brainHudView[hidden] { display: none; }` — especificidad de id+atributo,
gana siempre.

## Verificado

- `.venv/bin/python -m pytest -q` — 586/586 passed (2 tests nuevos para el
  endpoint en `tests/test_app.py`).
- **Verificación en vivo contra la app real** (no un prototipo aislado):
  servidor de prueba levantado en un directorio temporal (`data/` aislada
  ahí, `credentials/` ausente — cero riesgo para datos reales; confirmado
  después que `data/activity_log.jsonl`/`usage_log.jsonl` del repo real no
  cambiaron), login real con `SNARF_ACCESS_PASSWORD` de test, eventos
  reales sembrados (incluido uno con `stop_reason=max_tokens`). Playwright
  contra `http://127.0.0.1:8001`: login → abrir el panel del cerebro →
  Vista clásica intacta (grafo + feed de siempre) → toggle a Vista HUD →
  3 filas reales, incluida `"conteniéndose en pontificando ·
  anthropic:claude-sonnet-5"` (confirma el modificador de `truncado` de
  Fase 3 funcionando de punta a punta) → toggle de vuelta a clásica sin
  perder nada → cero errores de consola en todo el flujo.

## Consecuencias

- No se decide todavía cuál vista queda como principal — pedido explícito
  del fundador, se evalúa después de tener las dos funcionando en
  paralelo (ya cumplido).
- `web/hud_dock_prototype.html`/`web/hud_cost_history_prototype.html`
  siguen sin integrarse al dashboard real — quedan para Fase 5 (motor de
  relevancia, reemplaza datos mock del dock) decidir su ubicación final.
