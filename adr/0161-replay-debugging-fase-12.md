# ADR 0161 — Replay/debugging (Fase 12 del roadmap original, nunca arrancada)

**Fecha:** 2026-08-12
**Estado:** Aceptado

## Contexto

El fundador pidió poder "ver el agente por dentro" en ambos sentidos: la receta estática (prompt, tools,
modelo — ya cubierto por Fase 16/ADR 0157) y la traza de una ejecución real (qué herramienta llamó cada
rol, en qué orden, qué devolvió). Esto es exactamente la Fase 12 del roadmap original
(`ROADMAP_OBSERVABILIDAD_MULTIUSUARIO_N8N.md`), "Replay/debugging" — nunca arrancada hasta ahora, a pesar
de que la infraestructura real que necesita (`event_id`/`parent_event_id`/`trace_id`, ADR 0135) existe
desde la Fase 1.

## Decisión

**El replay vive en el HUD/cerebro 3D existente (`snarf/telemetry/brain.py` + su frontend en
`web/index.html`), no dentro de n8n.** n8n es un DAG estático sin ningún primitivo nativo para animar una
secuencia temporal de eventos de una traza puntual — construir eso ahí sería reimplementar, con peor
herramienta, algo que el HUD ya sabe dibujar. n8n pasa a ser el **lanzador** (workflow `Snarf - Ver
trazas`), el HUD el **visor** real.

**Backend — `snarf/telemetry/replay.py`** (nuevo, dos funciones puras sobre `data/telemetry_events.jsonl`,
nunca vuelve a ejecutar nada ni a llamar a ningún LLM — Principio VI, FOUNDATION.md):
- `list_recent_traces(n, path)`: una fila por `trace_id` con `workflow.started` real, con estado final si
  ya cerró y qué roles participaron.
- `events_for_trace(trace_id, path)`: secuencia completa ordenada de una traza, con el mismo verbo temático
  determinístico que ya usa `/dashboard/telemetry_feed` (`snarf/telemetry/verbs.py`, nunca generado por el
  LLM) — nunca una segunda implementación de esa lógica.

Dos bugs reales encontrados y corregidos por los tests antes de este ADR: el campo `"nodo"` de un evento
de workflow es siempre `brain.CENTER_NODE` ("orchestrator", ver `spans.start_workflow`) — el tipo real de
traza vive en `"skill"`, no en `"nodo"`. Y el campo `"agente"` de un evento de agente es el TIER
("specialist"), no el rol — el rol real vive en `"skill"` también (ver `spans.start_agent`). Ambos
corregidos en `replay.py` antes de mergear, no quedaron como deuda.

**Endpoints nuevos en `app.py`:**
- `GET /n8n/traces` (`require_n8n_token`) — lista para que n8n arme un menú de qué traza mirar.
- `GET /traces/{trace_id}` (`require_user`, el founder logueado en el HUD — nunca n8n, no tiene sentido
  que n8n reciba el detalle completo si su único rol acá es lanzar el link).

**Frontend — `web/index.html`:** `startTraceReplay(traceId)` reusa el pipeline visual que YA anima
actividad en vivo (`spawnPulse()`, `renderBrainFeed()`, `openBrainFullscreen()`) — nunca una vista nueva
desde cero. Traduce el shape de evento v2 (`nodo`/`skill`/`estado`) al shape que esas funciones ya esperan
(`node`/`label`/`status`), congela el polling en vivo mientras dura el replay
(`stopBrainPolling()`), y anima cada evento real con un paso fijo (`REPLAY_STEP_MS`). Se dispara una sola
vez al cargar la página si la URL trae `?replay=<trace_id>` (pensado para el link que da el workflow
`Snarf - Ver trazas` de n8n).

**Nota de no-determinismo, explícita:** el replay reproduce lo que YA pasó (tool calls/resultados/texto
grabados), nunca vuelve a ejecutar el LLM — un "replay" de una consulta al board muestra la respuesta real
que dio cada rol esa vez, no genera una nueva. Los timestamps del feed durante el replay muestran la edad
REAL de cada evento (ej. "18 min"), nunca se disfrazan como "ahora" — mismo criterio de honestidad que el
resto del HUD.

## Verificado

- 7 tests nuevos en `tests/test_replay.py`: orden correcto de eventos de una traza real, filtrado estricto
  por `trace_id` (una traza no relacionada nunca contamina el resultado), traza desconocida devuelve vacío
  (nunca inventa), `kind`/`estado`/`roles` reales en `list_recent_traces`, estado `"en_curso"` cuando nunca
  cerró, orden por más reciente primero, límite `n` respetado.
- 4 tests nuevos en `tests/test_app.py`: los dos endpoints nuevos con su auth correcta
  (`require_n8n_token`/`require_user`), y que devuelven datos reales de una traza sembrada con `spans.py`.
- **Verificado en un navegador real (Playwright, no solo tests)** — instancia de prueba en el puerto 8000
  (nunca el 8002 de producción, LaunchAgent), sesión minteada con `create_session_token()` y el
  `SESSION_SECRET` real del `.env` (sin usar la contraseña del fundador), navegando a
  `?replay=<trace_id>` con una traza REAL ya existente en `data/telemetry_events.jsonl` (nunca datos
  inventados, ni se escribió nada nuevo ahí — todo el ciclo fue de solo lectura). Resultado: cero errores
  de consola, el panel "CEREBRO DE SNARF" se abre solo, el grafo 3D renderiza, y el feed lateral muestra
  los 8 eventos reales de la traza elegida (`Orchestrator·executive_board` → 3 roles con started/finished
  → `Orchestrator·executive_board`) con sus timestamps reales. Screenshot real tomado y revisado, no solo
  "no tiró excepción". Instancia de prueba cerrada al terminar, puerto 8002 nunca tocado.
- 1384/1384 tests de la suite completa (`.venv/bin/python -m pytest -q`, corrida real, no estimada),
  1373 previos (post ADR 0160, incluidos los 3 tests ajenos de `test_document_to_reader_optimized.py`) +
  11 nuevos (7 + 4).
