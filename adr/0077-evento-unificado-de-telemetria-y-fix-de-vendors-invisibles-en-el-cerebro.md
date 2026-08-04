# ADR 0077 — Evento unificado de telemetría (Fase 1 del plan de HUD) y fix de vendors invisibles en el cerebro

**Fecha:** 2026-08-03
**Estado:** Aceptado

## Contexto

El fundador pidió una sesión larga por fases para construir un dock radial
tipo HUD sobre el dashboard, con historial de costos y una segunda vista del
cerebro alimentados por telemetría real. Fase 0 (mismo día, sin ADR propio
por ser solo diseño/documentación) definió el esquema en
`TELEMETRY_SCHEMA.md`: un evento único (`nodo`, `agente`, `skill`, `modelo`,
`tokens_in`/`tokens_out`, `costo_usd`, `latencia_ms`, `estado`) que
consumirían el dock, la Vista HUD del cerebro y el historial de costos, sin
reemplazar los tres logs reales ya existentes (`activity_log.jsonl`,
`usage_log.jsonl`, `input_log.jsonl`) ni la normalización ya real de
`snarf/telemetry/brain.py`.

Esta Fase 1 engancha ese esquema en código real.

## Decisión

### Instrumentación por chokepoint, no por call site

Las ~80 tools y los ~9 vendors reales de Snarf no se instrumentaron uno por
uno. Las tres funciones `record()` (`activity_log.py`, `usage_tracker.py`,
`input_log.py`) ya son el único punto de paso de **todo** tool-call/llamada
de vendor/entrada real — instrumentar ahí adentro cubre todos los nodos de
una vez, sin agregar ninguna llamada nueva al modelo (cumple el pedido
explícito del fundador) y sin tocar decenas de call sites dispersos en
`Orchestrator`, especialistas y providers de voz.

- `snarf/telemetry/events.py` (nuevo): `record_tool_event`,
  `record_vendor_event`, `record_input_event` — cada uno deriva `nodo`/
  `agente` reusando `brain.TOOL_TO_NODE`/`VENDOR_TO_NODE`/`CHANNEL_TO_NODE`/
  `NODE_TIER`, la misma normalización que ya pinta el cerebro actual. Un
  tool/vendor/canal sin nodo mapeado no emite evento (nunca inventa un
  nodo) — mismo criterio que ya usaba `brain.snapshot()`.
- Guardado en `data/telemetry_events.jsonl` — mismo patrón JSONL append-only
  que los tres logs existentes, agregado a `.gitignore` junto a ellos.
- Los tres `record()` originales quedan intactos en su forma pública salvo
  un parámetro nuevo `events_path` (redirección opcional, mismo patrón que
  `path`) y, adentro, una línea que llama al hook nuevo con el mismo
  `timestamp` ya generado — cero riesgo para los consumidores actuales de
  esos tres logs (el cerebro actual, el panel de costo, etc.).

### `snarf/telemetry/verbs.py` (nuevo)

Tabla determinística `nodo`→verbo temático, definida en `TELEMETRY_SCHEMA.md`
(Fase 0) y ahora en código: `verbo_tematico(nodo, agente, estado)`. Nunca
generada por el LLM. Fallback por `agente` (tier) para un nodo nuevo sin
entrada propia. Modificador de `estado` (`error`→"tropezando con",
`truncado`→"conteniéndose en") antepuesto al verbo base, nunca lo reemplaza.

### Gap de `estado="truncado"` cerrado

`anthropic_llm.py:202` ya detectaba `response.stop_reason == "max_tokens"`
pero nunca lo registraba en ningún log (gap documentado explícitamente en
`TELEMETRY_SCHEMA.md`, Fase 0). Ahora `_record_usage()` pasa
`stop_reason=response.stop_reason` a `usage_tracker.record_anthropic_call()`,
que lo traduce a `estado="truncado"` en el evento unificado. No toca los dos
breakpoints de cache existentes (system+tools, último mensaje por ronda) —
solo agrega un parámetro nuevo a una llamada ya existente.

### Bug real encontrado y corregido: vendors sin nodo en el cerebro

Al construir `record_vendor_event`, `brain.VENDOR_TO_NODE` resultó no cubrir
`gemini`/`openai`/`xai`/`groq_llama` (LLM multi-proveedor, ADR 0067/0068) ni
`groq` (STT, ADR 0056) ni `local` (STT/TTS local, ADR 0056) — pese a que
estos vendors ya generan entradas reales en `usage_log.jsonl` desde esas
ADRs, **el cerebro actual (no solo la instrumentación nueva) los mostraba
invisibles**, sin que ningún test lo detectara. Corregido:

- `VENDOR_TO_NODE` suma `gemini`/`openai`/`xai`/`groq_llama` → `"llm"`
  (mismo nodo que Anthropic — la Capacidad que representan es la misma
  desde la perspectiva de quien mira el grafo, el proveedor es un detalle
  de ruteo interno) y `groq` → `"stt"`.
- `LOCAL_MODEL_TO_NODE` (nuevo) separa el vendor `"local"` por modelo
  (`faster-whisper`→`"stt"`, `kokoro`→`"tts"`), mismo criterio ya usado para
  ElevenLabs (`ELEVENLABS_MODEL_TO_NODE`).
- `brain.snapshot()` actualizado para consultar `LOCAL_MODEL_TO_NODE` igual
  que ya hacía con ElevenLabs.

Ningún nodo nuevo se agregó a `NODE_TIER`/`NODE_IDS` — estos vendors caen en
nodos ya existentes (`llm`/`stt`/`tts`), consistente con el protocolo de
crecimiento del cerebro (ver comentario en `brain.py` y ADR 0054): son la
misma subcapacidad real, distinto proveedor por debajo.

### Segundo bug encontrado y corregido en el camino: fuga de datos sintéticos a un archivo real

La primera versión de `events.record_*` no aceptaba una ruta de override
independiente de `path` — cualquier test o script que redirigiera `path`
(el log original) igual escribía el evento unificado en el
`data/telemetry_events.jsonl` real por default. Se detectó por evidencia
directa (líneas sintéticas ya en el archivo real antes del fix, más de una
vez durante esta misma sesión) y se corrigió agregando `events_path` a las
tres funciones `record()` y a los 8 wrappers de `usage_tracker.py`. Los
tests unitarios de cada log (`test_activity_log.py`/`test_usage_tracker.py`/
`test_input_log.py`, que llaman `record()` directo con `path=tmp_path/...`)
ya redirigen `events_path` de la misma forma.

**Fuente real remanente, encontrada recién al correr la suite completa:**
`tests/test_app.py` (los tests de `/send`, `/transcribe`, etc. contra la app
real de FastAPI) redirige `activity_log.DEFAULT_PATH`/
`usage_tracker.DEFAULT_PATH`/`input_log.DEFAULT_PATH` vía
`monkeypatch.setattr` en su fixture `client` — pero nunca redirigía
`events.DEFAULT_PATH`, así que cada test de esa suite seguía escribiendo el
evento unificado al archivo real. **No es comportamiento preexistente**: es
un gap real de esta misma instrumentación, corregido agregando
`monkeypatch.setattr(events, "DEFAULT_PATH", tmp_path / "telemetry_events.jsonl")`
a esa misma fixture, mismo patrón que los otros tres. El archivo real
polucionado se borró (nunca tenía datos reales — no existía antes de esta
sesión).

**Gap remanente, este sí preexistente, verificado (no fuera de esta ADR):**
`tests/test_gemini_llm.py`, `tests/test_kokoro_tts.py` (varios tests salvo
uno) y `tests/test_llm_routing.py` llaman Capacidades reales
(`GeminiLLM`/`KokoroTTS`) con un cliente stub, pero nunca redirigen
`usage_tracker.DEFAULT_PATH` — ya escribían en el `data/usage_log.jsonl`
real antes de esta sesión. El evento unificado nuevo hereda esa misma fuga
(ahora también en `telemetry_events.jsonl`). No corregido acá — cerrar la
fuga completa de estos tres archivos de test es trabajo aparte, fuera del
alcance del plan de HUD de 9 fases.

## Verificado

- `.venv/bin/python -m pytest -q` — 570/570 passed. Tests nuevos: 6 en
  `tests/test_telemetry_events.py`, 5 en `tests/test_verbs.py`, 4 en
  `tests/test_brain.py` (vendors nuevos), varios agregados a
  `tests/test_activity_log.py`/`tests/test_usage_tracker.py`/
  `tests/test_input_log.py` para la emisión del evento unificado
  (incluido `estado="truncado"` real).
- Demo manual contra archivos temporales: `drive_list_files` → evento
  `nodo="drive"`, `agente="capability"`; llamada Anthropic con
  `stop_reason="max_tokens"` → `estado="truncado"`. Confirmado que
  `data/telemetry_events.jsonl` real queda vacío tras correr la suite
  completa (ningún test poluciona el archivo real).

## Consecuencias

- Fase 2 (dock radial) y Fase 3 (historial de costos) y Fase 4-b (Vista HUD
  del cerebro) pueden leer un solo log (`data/telemetry_events.jsonl`) en
  vez de cruzar tres, para todo lo que necesiten mostrar en el lenguaje de
  `TELEMETRY_SCHEMA.md`.
- El cerebro actual (Vista clásica, sin tocar en esta fase) ahora también
  se beneficia del fix de vendors — la próxima vez que el fundador rutee a
  Gemini/xAI/Grok o use STT/TTS local, esa actividad real va a aparecer en
  el grafo por primera vez.
- Gap restante, documentado ya en `TELEMETRY_SCHEMA.md`: `latencia_ms` sigue
  sin existir para llamadas de vendor puro (solo `activity_log` la mide
  hoy). No cerrado en esta fase — no era parte del pedido explícito ni
  bloqueaba nada de lo construido.
