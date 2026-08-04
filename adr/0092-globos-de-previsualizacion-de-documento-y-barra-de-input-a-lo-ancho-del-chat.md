# ADR 0092 — Globos de previsualización de documento, y barra de input a lo ancho del chat

**Fecha:** 2026-08-04
**Estado:** Aceptado

## Contexto

El fundador señaló, con un ejemplo real (pedido de analizar el plan del
canal de deporte de Tommy en Drive), el límite de fondo de los globos de
contexto del dashboard HUD (ADR 0089): un globo que dice "leyendo plan de
contenido... canal de edits de fútbol" y corta el texto ahí "no se vuelve
útil" — no muestra nada del documento real que se está analizando, ni deja
llegar a él. Pidió globos de previsualización real: título del documento,
un resumen corto o el inicio del contenido, y eventualmente una miniatura
visual (primera página si es un doc, una tabla si es una sheet, etc.),
clickeable hasta el archivo real — estandarizado para Drive/Notion y
extensible a futuras fuentes (markdown, mp3, video, zip). También pidió que
la barra de input del chat-dock (conversaciones/proyectos, modo enfoque,
adjuntar, texto, mic) sea coherente en ancho con el resto del chat, no un
bloque angosto y descentrado.

Investigando el pipeline real de telemetría (`snarf/telemetry/detail.py`,
`google_drive.py`, `document_publisher.py`, `notion.py`) se confirmó qué
dato ya existe hoy y cuál falta desde cero:

- **Ya existe:** snippet real de contenido en `drive_read_file` (texto
  extraído) y `notion_read_page`; título real en el `tool_input` al crear
  un documento/página (`drive_create_document/spreadsheet/presentation`,
  `notion_create_page`); `webViewLink`/`url` reales en el `result` de esas
  mismas creaciones — pero **descartados en el camino** al armar `detalle`
  (que solo guarda un string, nunca metadata estructurada).
- **Falta de verdad:** el nombre real de un archivo que se está
  leyendo/actualizando (`drive_read_file`/`drive_update_document` solo
  reciben `file_id` en su input — ni el LLM se lo puede pasar, ni el
  handler se lo pide hoy a Drive) y cualquier miniatura visual
  (`thumbnailLink` de la API de Drive nunca se pidió, no hay infraestructura
  de proxy/cacheo/servido de imágenes en todo el backend — el único
  precedente de servir binarios cacheados es el audio de TTS,
  `GET /audio/{id}`).

## Decisión

### 1. Campo nuevo `preview` en el evento unificado, paralelo a `detalle`

`snarf/telemetry/detail.py`: `PREVIEW_EXTRACTORS` + `extract_preview()`,
paralelo a `DETAIL_EXTRACTORS`/`extract()` pero **deliberadamente parcial**
— a diferencia de `detalle`, la mayoría de los 60 tools no toca ningún
documento real, así que no hay (ni tiene sentido que haya) un test de
cobertura total; solo se exige que toda entrada referencie un tool real
(`test_preview_extractors_only_reference_real_tools`). Cada entrada
devuelve `{"title", "link", "snippet"}` (cualquiera puede ser `None`) para:
`drive_read_file`, `drive_update_document`, `drive_create_document`,
`drive_create_spreadsheet`, `drive_create_presentation`,
`notion_create_page`, `notion_read_page`.

`link` es siempre una URL real: el `webViewLink`/`url` que ya devuelve la
API de Drive/Notion cuando está disponible (creación de documentos), o una
URL pública y **estable, documentada por Google/Notion** construida a
partir del `file_id`/`page_id` real (`docs.google.com/document/d/{id}/edit`
según `mime_type`, `drive.google.com/file/d/{id}/view` genérico,
`notion.so/{page_id sin guiones}`) — nunca inventada, nunca requiere una
llamada de red nueva.

**Decisión explícita de alcance — sin título para lectura/actualización:**
`drive_read_file`/`drive_update_document` solo reciben `file_id` en su
input real; conseguir el nombre del archivo requeriría una llamada nueva a
la API de Drive (`files().get(fields="name")`) en el camino caliente de
cada lectura/escritura de documento, agregando latencia real al turno del
usuario solo para enriquecer un globo. Se prefirió honestidad sobre
completitud: esos dos previews tienen `title: None` (el `link`/`snippet`
alcanzan para que el globo sea útil), en vez de pagar latencia oculta o
acoplar `detail.py` (hoy puramente una transformación sin I/O) a las
capabilities de red.

Wiring en cascada, mismo patrón que `detalle` (ADR 0089):
`Orchestrator._handle_tool` (rama `"ok"`) → `activity_log.record(...,
preview=...)` → `events.record_tool_event(..., preview=...)` →
`events._event(...)` → persistido en `data/telemetry_events.jsonl`.
`widget_summary.summarize_node` gana `last_preview` (el evento reciente con
preview real, independiente de `last_detalle`) y cada `recent_items[]` su
propio `preview`. Documentado en `TELEMETRY_SCHEMA.md`.

### 2. Tarjeta de preview en el frontend — reemplaza el texto plano, nunca un slot nuevo

`web/index.html`: `dashHudPreviewCardHTML(preview)` — título (si hay),
snippet en cursiva (si hay), link "abrir archivo →" (si hay), acento ámbar
(mismo color que ya usa `data-family="document"`). Se integra en los slots
de texto existentes (`body`, `list`, `timeline`, `wall`) en vez de un slot
nuevo: cuando el widget/item trae `preview` real, la tarjeta reemplaza el
texto plano de `detalle` — funciona automáticamente en cualquiera de las 24
plantillas ya existentes, sin tener que reasignarle una plantilla nueva a
ningún nodo. El link real navega al archivo (`target="_blank"`); el click
listener del dock distingue explícitamente un click en `.dash-hud-preview-link`
del resto de la tarjeta (que sigue abriendo el panel de detalle del nodo,
mismo criterio que ya se usó para sacar el botón de pin).

### 3. Explícitamente diferido: miniatura visual (thumbnail)

La previsualización visual (primera página de un doc, tabla de una sheet,
slide de una presentación) pedida por el fundador **no se construye en este
ciclo** — requiere infraestructura real nueva y no trivial: pedir
`thumbnailLink` a la API de Drive (nunca solicitado hoy), un proxy/cacheo
en el backend (las URLs de `thumbnailLink` requieren la sesión autenticada
de Drive, no son públicas — mismo tipo de necesidad que ya resuelve el
cacheo de audio de TTS, pero para imágenes) y un endpoint que las sirva. Se
prioriza el título/snippet/link real (entrega valor inmediato, cero
llamadas de red nuevas) como v1; la miniatura queda como iniciativa aparte,
a construir si el fundador confirma que la quiere ahora que ve la v1 en
producción.

### 4. Barra de input a lo ancho del chat-dock

`.text-row` traía un `max-width: 480px` global (pensado para la vista de
chat angosta de siempre) — dentro del chat-dock (`min(760px, 92vw)`, mucho
más ancho) quedaba como un bloque chico y descentrado en vez de ocupar el
ancho real de la conversación. `#chatDock .text-row { max-width: none; }`
— scopeado a la Vista HUD a propósito, la vista de chat clásica y el modo
enfoque no pidieron este cambio.

## Bug real encontrado y corregido verificando con Playwright

`dashHudTransformFor(pos, opts)` leía `pos.ring` **antes** de chequear
`opts.exitToCenter` — cuando un widget deja de ser relevante y sale de
pantalla, se lo llama a propósito con `pos = null` (ver el loop de
`hiddenIds` en `renderDashboardHudWidgets`), y esa lectura tiraba
`TypeError: Cannot read properties of null` sin capturar, interrumpiendo el
resto del `forEach` de ese ciclo de render (los widgets siguientes en la
misma pasada quedaban sin actualizar su posición). Nunca se había
manifestado visiblemente en sesiones anteriores porque requiere que un
widget activo deje de serlo entre dos polls — se encontró recién al
inyectar un set de widgets sintéticos distinto al ya renderizado para
verificar la tarjeta de preview. Corregido: el chequeo de `exitToCenter`
ahora va primero, siempre.

## Verificado

- `.venv/bin/python -m pytest -q` — 707/707 passed (18 tests nuevos:
  `extract_preview` en `tests/test_telemetry_detail.py`, propagación en
  `tests/test_activity_log.py`, `last_preview`/`recent_items[].preview` en
  `tests/test_widget_summary.py`).
- Playwright contra el servidor real de producción (puerto 8002), sin
  disparar ninguna llamada real a Drive/Notion/LLM (se habría facturado sin
  necesidad): widgets sintéticos inyectados solo en el estado del
  navegador, nunca escritos a `data/telemetry_events.jsonl`. Confirmado en
  vivo: tarjeta con título+snippet+link real y clickeable; tarjeta sin
  título cuando el preview no lo trae (nunca un placeholder inventado);
  orbe central nunca tapado (ADR anterior) con los widgets nuevos
  intercalados; barra de input ocupando el ancho real del chat-dock; cero
  errores de consola. Preferencia de vista restaurada a como estaba.

## Consecuencias

- **El cambio de backend (`preview`) requiere reiniciar el servidor real de
  producción** para entrar en vigencia — a diferencia del CSS/JS del punto
  2/4 (100% frontend, alcanza con recargar la pestaña), ningún tool call
  real va a llevar `preview` hasta que el proceso de `com.snarf.server` se
  relance con este código. Confirmar con el fundador antes de reiniciar
  (convención ya establecida en CLAUDE.md).
- Miniatura visual (thumbnails) queda pendiente como iniciativa aparte (ver
  punto 3) — no construir sin antes confirmar que vale la latencia/
  infraestructura nueva (proxy + cacheo de imágenes autenticadas).
- Cobertura de fuentes hoy: Drive + Notion. Markdown/mp3/video/zip
  (mencionados por el fundador) ya tienen categorización de mimeType en
  `snarf/knowledge/extraction.py::categorize_mime` pero no forman parte de
  ningún tool con preview propio todavía — agregarlos es, por diseño,
  una entrada nueva en `PREVIEW_EXTRACTORS` cuando exista un tool real que
  los toque, sin tocar el resto del pipeline.
