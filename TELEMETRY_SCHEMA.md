# TELEMETRY_SCHEMA

## Esquema canónico de eventos de telemetría (HUD/dock radial)

**Versión:** 0.1 (Fase 0 del plan de HUD — diseño, sin instrumentación todavía)
**Estado:** documento vivo. Fase 1 lo conecta a código real; cualquier campo que
Fase 1 encuentre imposible de poblar con honestidad se corrige acá, no se
inventa un valor de relleno (Principio VI de FOUNDATION.md).

## Relación con lo que ya existe

Snarf **ya** tiene tres logs append-only reales, en uso desde ADR 0029/0031/0033:

- `data/activity_log.jsonl` (`snarf/telemetry/activity_log.py`) — cada tool que
  despacha el Orchestrator: `tool_name`, `status` (`ok`/`error`/`unknown_tool`),
  `duration_ms`, `error`.
- `data/usage_log.jsonl` (`snarf/telemetry/usage_tracker.py`) — cada llamada
  real a un vendor (Anthropic/Gemini/OpenAI/xAI/Groq/ElevenLabs/Voyage/local):
  `vendor`, `model`, `cost_usd`, más métricas específicas (`input_tokens`,
  `output_tokens`, `characters`, `duration_seconds`).
- `data/input_log.jsonl` (`snarf/telemetry/input_log.py`) — cada entrada real
  a Snarf (`channel`: `text`/`voice`/`file`, `category` del archivo si aplica).

`snarf/telemetry/brain.py` ya normaliza los tres en un grafo de nodos
(`TOOL_TO_NODE`, `VENDOR_TO_NODE`, `CHANNEL_TO_NODE`, `NODE_TIER`) para el
widget cerebro actual. **Este esquema no reemplaza esos tres logs ni
`brain.py`** — define la forma de evento único (`TelemetryEvent`) que Fase 1
va a *emitir además*, reusando exactamente esa misma normalización, para que
el dock HUD, la Vista HUD del cerebro (Fase 4) y el historial de costos (Fase
3) lean una sola forma de dato en vez de tres logs distintos con lógica de
cruce repetida en cada consumidor nuevo. Los tres logs originales siguen
existiendo (no se tocan en Fase 0; su eventual fusión física es decisión de
Fase 1, no de este documento).

## Campo por campo

| Campo | Tipo | Origen real | Notas |
|---|---|---|---|
| `timestamp` | float (epoch, segundos) | `time.time()`, idéntico a los tres logs actuales | — |
| `nodo` | string | `node_id` de `brain.py` (`TOOL_TO_NODE`/`VENDOR_TO_NODE`/`CHANNEL_TO_NODE`), ej. `"drive"`, `"specialist_gmail"`, `"llm"`, `"input_voice"` | Es el mismo vocabulario que ya pinta el cerebro — un tool nuevo que no entre en `TOOL_TO_NODE` no genera evento, por diseño (ver protocolo de crecimiento en `brain.py`). |
| `agente` | string | `NODE_TIER[nodo]` de `brain.py`: `"orchestrator"` / `"input"` / `"specialist"` / `"capability"` | Mapea directo a la arquitectura de tres capas real de `COGNITION.md`/ADR 0003 (Capacidades / Especialistas / Orchestrator) — no es una taxonomía nueva, es la que ya existe. |
| `skill` | string | `tool_name` de `activity_log`, o `f"{vendor}:{model}"` para eventos de vendor sin tool asociado | Para eventos de `input_log` (sin tool ni vendor), `skill` = `channel` (`"text"`/`"voice"`/`"file"`). |
| `modelo` | string \| null | `model` de `usage_log` (ej. `"claude-sonnet-5"`, `"gemini-3.1-flash-lite"`, `"kokoro"`) | `null` en eventos de dispatch puro de `activity_log` que no involucran un vendor (ej. `drive_move_file`, que no llama a ningún LLM). |
| `tokens_in` | int \| null | `input_tokens` de `usage_log` | Solo poblado en llamadas LLM (Anthropic/Gemini/OpenAI/xAI/Groq-Llama). `null` en STT/TTS/Voyage/eventos de dispatch. |
| `tokens_out` | int \| null | `output_tokens` de `usage_log` | Ídem. |
| `costo_usd` | float \| null | `cost_usd` de `usage_log` (`snarf/telemetry/pricing.py`, tarifas reales investigadas, nunca estimadas al voleo) | `null` cuando el vendor no tiene tarifa por uso conocida (ej. ElevenLabs TTS por plan, ver `usage_tracker.record_elevenlabs_tts_call`) — **`null` significa "no se sabe", nunca se muestra como `$0.00`**, para no mentir un costo real de cero donde en realidad es desconocido. |
| `latencia_ms` | float \| null | `duration_ms` de `activity_log` (ya medido con `time.monotonic()` alrededor de cada dispatch) | Hoy solo existe para eventos de `activity_log`. Los eventos de vendor puro (`usage_log`) no miden latencia todavía — gap real, a cerrar en Fase 1 si se quiere latencia por llamada LLM/STT/TTS, no inventar un valor mientras tanto. |
| `estado` | enum: `completo` \| `truncado` \| `error` | Ver sección siguiente | `completo` es el default cuando no hay señal de error ni de truncado. |
| `conversation_id` | string \| null | `snarf/telemetry/context.py` (`threading.local()`, seteado por `Orchestrator.handle()` al entrar a un turno, limpiado en un `finally`) | **Agregado en Fase 3** (no estaba en la lista original de esta fase) — necesario para agregar costo "por sesión". `null` en eventos que no ocurren dentro de un turno de conversación real (digest de Gmail en background, resumen de proyecto, etc.) — nunca inventado. |
| `detalle` | string \| null | `snarf/telemetry/detail.py` (tools, vía `tool_input`/`result` reales en `Orchestrator._handle_tool`) o texto real ya en scope en cada capability de vendor (transcript de STT, texto de TTS, texto generado por el LLM) o `payload.text`/`file.filename` reales en los endpoints de `app.py` que llaman `input_log.record()` | **Agregado en ADR 0089** ("globos contextuales" del dock HUD). A diferencia de `skill` (identificador del tool/vendor), esto es el CONTENIDO real de qué se hizo — a quién se le mandó un mail, qué documento se creó, qué se buscó, qué se transcribió. Recortado mecánicamente a `DETAIL_MAX_CHARS` (100 caracteres), nunca generado por un LLM. `null` cuando el tool/evento genuinamente no tiene contenido legible que mostrar (ej. `drive_move_file` solo tiene IDs en su input) o cuando el extractor no encuentra el campo esperado — nunca se inventa. Cobertura: cada uno de los 60 tools reales del Orchestrator tiene una entrada en `snarf/telemetry/detail.py::DETAIL_EXTRACTORS` (`test_detail_extractors_cover_every_orchestrator_tool` lo garantiza), aunque para varios (solo-ID) el resultado sea honestamente genérico. |
| `preview` | `{title, link, snippet}` \| null | `snarf/telemetry/detail.py::extract_preview`, vía `tool_input`/`result` reales de tools que tocan un documento concreto (Drive/Notion, ver `PREVIEW_EXTRACTORS`) | **Agregado en ADR 0092** (globos de previsualización de documento del dashboard HUD). A diferencia de `detalle` (siempre texto plano), esto queda estructurado para que el frontend arme una tarjeta clickeable en vez de una línea. `link` es siempre una URL real (el `webViewLink`/`url` que devuelve la API de Drive/Notion, o una URL pública y estable construida a partir del `file_id`/`page_id` real con el formato documentado de Google/Notion — nunca inventado). `title` solo está presente cuando viaja gratis en el `tool_input` (ej. al crear un documento) — a propósito **no** se agrega una llamada de red nueva solo para conseguir el título de un archivo que se está leyendo/actualizando (ver comentario en `detail.py`), así que puede ser `null` incluso con `link`/`snippet` presentes. `snippet` es contenido real ya extraído (texto del documento/página), recortado a `PREVIEW_MAX_CHARS` (160 caracteres). A diferencia de `DETAIL_EXTRACTORS`, `PREVIEW_EXTRACTORS` es deliberadamente parcial — la mayoría de los tools no toca ningún documento, así que no hay garantía de cobertura total, solo que toda entrada referencie un tool real (`test_preview_extractors_only_reference_real_tools`). |

## El campo `estado`

Tres valores, todos con una señal real ya presente en el código — ninguno se
infiere sin evidencia:

- **`error`** — ya existe tal cual: `activity_log` registra `status="error"`
  (excepción real durante el dispatch) y `status="unknown_tool"` (el modelo
  invocó un tool_name inexistente). Fase 1 mapea ambos a `estado="error"` en
  el evento unificado (`unknown_tool` es un error del propio Orchestrator, no
  de una Capacidad — ya se distingue así en `brain.py`, que lo dirige al nodo
  `orchestrator`).
- **`truncado`** — señal real ya existe, pero **hoy no se registra en ningún
  log**: `snarf/capabilities/anthropic_llm.py:202` detecta
  `response.stop_reason == "max_tokens"` y le agrega una nota al texto de
  respuesta, sin emitir ningún evento de telemetría. Fase 1 tiene que pasar
  ese `stop_reason` hasta `usage_tracker.record_anthropic_call` (o
  equivalente) para poder marcar `estado="truncado"` con honestidad. Hasta
  que eso exista, ningún evento debe reportar `truncado` — se reporta
  `completo` por default, nunca se adivina.
- **`completo`** — default cuando no aplica ninguno de los dos anteriores.

## Tabla de mapeo acción → verbo temático

Determinística, por `nodo` (o por `agente` como fallback si un nodo nuevo
todavía no tiene entrada propia) — **nunca generada por el LLM**, vive como
una constante en código (Fase 1 la implementa en
`snarf/telemetry/verbs.py` o similar, un dict plano). El registro sigue
CHARACTER.md: ingenio seco, nunca frívolo — el verbo temático es una versión
más precisa o levemente irónica de la acción literal, nunca un chiste gratuito.

| `nodo` (o `agente` de fallback) | Acción literal | Verbo temático |
|---|---|---|
| `orchestrator` | despachando | **orquestando** |
| `llm` | razonando | **pontificando** |
| `specialist_gmail` | interpretando la bandeja | **curando** |
| `specialist_projects_manage` | administrando el proyecto | **archivando** |
| `specialist_projects_tasks` | gestionando tareas/notas | **anotando** |
| `specialist_projects_conversations` | asociando conversación | **enlazando** |
| `memory` | buscando en el historial | **rebobinando** |
| `drive` | operando sobre archivos | **hojeando** |
| `knowledge` | buscando en lo indexado | **rastreando** |
| `documents` | creando un documento | **redactando** |
| `gmail_read` | leyendo correo | **espiando el buzón** |
| `gmail_manage` | organizando etiquetas | **ordenando** |
| `gmail_send` | enviando correo | **despachando el correo** |
| `calendar_view` | consultando la agenda | **consultando la agenda** |
| `calendar_edit` | editando la agenda | **reagendando** |
| `youtube` | consultando YouTube | **hojeando el feed** |
| `notion` | operando sobre Notion | **hojeando Notion** |
| `personality` | ajustando configuración | **calibrándose** |
| `utility` | resolviendo un dato menor | **verificando el dato** |
| `stt` | transcribiendo audio | **escuchando** |
| `tts` | sintetizando voz | **hablando** |
| `input_text` | recibiendo texto | **tomando nota** |
| `input_voice` | recibiendo audio | **prestando oído** |
| `input_file` | recibiendo un archivo | **recibiendo el archivo** |

Modificador por `estado` (se antepone o reemplaza el verbo, a definir en
Fase 1/2 según cómo luzca en el feed real):

| `estado` | Modificador |
|---|---|
| `error` | **tropezando con** |
| `truncado` | **conteniéndose en** |
| `completo` | (sin modificador — el verbo temático solo) |

Cualquier `nodo` nuevo que aparezca en `brain.py` sin entrada acá cae al
verbo genérico de su `agente` (`"operando"` para `capability`, `"delegando"`
para `specialist`) hasta que se le agregue una entrada propia — mismo
protocolo de crecimiento que `brain.py` (ver comentario al inicio del
archivo y ADR 0054): un nodo nuevo real evoluciona esta tabla en el mismo
cambio, no después.

## Relación entre `detalle` y el "resumen" de la Vista HUD (Fase 4-b)

El campo `detalle` (ADR 0089, arriba) es el contenido real persistido en el
evento mismo. `/dashboard/telemetry_feed` (`app.py`) sigue derivando además
un `resumen` on-the-fly (recorte mecánico de `skill`, el identificador del
tool) — quedan ambos: `resumen` identifica QUÉ tool corrió, `detalle`
describe QUÉ CONTENIDO manejó. Los globos contextuales del dock HUD (ADR
0089) usan `detalle`; el feed de texto minimizado (una sola fila visible)
sigue usando `verbo`+`resumen`, sin cambios.

## Resumen truncado de input/output (Fase 4-b)

La Vista HUD del cerebro (Fase 4) va a mostrar, por evento, un resumen corto
de input/output truncado a N caracteres. Ese resumen **no es un campo nuevo
que el LLM tenga que generar** — sale de recortar (no resumir con IA) el
texto que ya existe en el evento real: el `label` que `brain.py` ya arma por
evento (ej. `tool_name`, o `f"{vendor}:{model}"`), o el input/output real ya
guardado en `EpisodicMemory` para eventos de conversación. Ese recorte
mecánico (slice de string) se define en Fase 1/4, no acá — este documento
solo deja registrado que la fuente es texto real ya emitido, nunca una
llamada adicional al modelo (cumple el pedido explícito de la Fase 1: "sin
agregar llamadas extra al modelo").

## Gaps honestos que Fase 1 tiene que resolver (no Fase 0)

1. `latencia_ms` no existe hoy para llamadas de vendor puro (`usage_log`).
2. `estado="truncado"` no se emite en ningún lado todavía — requiere pasar
   `stop_reason` desde `anthropic_llm.py` hasta el punto de registro.
3. Los tres logs actuales no comparten un `event_id` — si Fase 1 decide unir
   eventos de `activity_log` y `usage_log` que corresponden al mismo turno
   (ej. un tool call que internamente llama al LLM), va a necesitar un
   identificador de correlación que hoy no existe. Documentado para que Fase
   1 lo decida con el código real delante, no en abstracto acá.
