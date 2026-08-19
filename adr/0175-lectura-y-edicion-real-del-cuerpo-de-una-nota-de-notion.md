# ADR 0175 — Lectura y edición real del cuerpo de una nota de Notion (bloques anidados y transcripción de reuniones)

**Fecha:** 2026-08-19
**Estado:** Aceptado

## Contexto

El fundador pidió verificar en vivo que Snarf encuentra y entiende bien su Notion real: buscar una nota
sobre Sócrates dentro del proyecto "Mente Filosófica" (base de datos "Notas", relacionada por la
property `Proyecto`). Snarf la encontró (indexado y `notion_search`/`notion_read_page` funcionan), pero
resumió mal el contenido — dijo que la nota estaba "casi vacía, solo el título".

Investigando contra la API real de Notion (no solo el código) se confirmó que la nota tiene contenido
real y extenso: 4 secciones tipo `toggle` (acordeón) en el cuerpo, una de ellas un ensayo completo con
títulos, tabla de contenido y varias secciones desarrolladas, y otra el bloque especial `transcription`
que arma el transcriptor de reuniones de Notion — con tres pestañas reales (Resumen/Notas/Transcripción)
adentro. Confirmado con requests HTTP crudos que la API de Notion expone todo esto sin restricción; el
problema era 100% del lado de Snarf.

`read_page_text` (`snarf/capabilities/notion.py`, sin tocar desde su versión original) solo leía el
`rich_text` de los bloques de **primer nivel** de una página, ignorando cualquier bloque con
`has_children=True` — exactamente el caso de un toggle o del bloque `transcription`. Este límite ya
estaba anotado como conocido en ADR 0173 ("toggles, tablas... sin recorrer"), pero recién con este pedido
real del fundador tuvo un ejemplo concreto y una razón para resolverse.

Además, el fundador pidió explícitamente poder **editar y borrar** contenido ya existente del cuerpo de
una nota, no solo agregar al final (única escritura real que existía, `append_to_page`).

## Decisión

**Lectura recursiva real, con un caso especial para el bloque `transcription`.**
`Notion._iter_page_blocks()` (nuevo, privado) recorre cualquier bloque con `has_children=True` — cubre
toggles, tablas y listas anidadas sin código especial para cada tipo. El bloque `transcription` es la
única excepción real: no tiene `rich_text` propio, su contenido vive en tres bloques hijo referenciados
por id (`transcription.children.summary_block_id/notes_block_id/transcript_block_id`) — confirmado en
vivo que la API los expone igual que cualquier otro bloque vía `GET /blocks/{id}/children`, solo que el
mapa de ids no está documentado como "children" normales. `_iter_page_blocks` los recorre por separado,
etiquetados `[Resumen]`/`[Notas]`/`[Transcripción]` en el texto final, y omite la etiqueta si esa sección
está vacía (ej. "Notas" suele estarlo).

`read_page_text` (misma firma pública, sin romper a `NotionSource` que ya la consume para indexar —
ADR 0173) queda como un `"\n\n".join(...)` sobre este recorrido — mismo resultado de siempre para
contenido simple, contenido real completo para notas armadas con toggles/transcripciones. El indexado
semántico de Notion se beneficia automáticamente, sin tocar `notion_source.py`.

**`list_blocks`/`get_block` nuevos: mismo recorrido, sin aplanar.** Cada fragmento con texto real
conserva su `block_id` y su `type` — necesario para poder decirle a la API de Notion *cuál* bloque tocar.
Los fragmentos sintéticos (etiquetas de sección de una transcripción) llevan `id=None`, marcando que no
son bloques editables de verdad.

**Escritura real de bloques existentes — control total, a pedido explícito del fundador** (edición +
borrado, no solo lectura ni solo "agregar"): `update_block(block_id, block_type, content)` hace
`PATCH /blocks/{id}` con el tipo real como key del body (la API de Notion lo exige tal cual, no lo
adivina); `delete_block(block_id)` hace `DELETE /blocks/{id}` (los manda a la papelera de Notion,
recuperables ahí — mismo criterio de reversibilidad que `drive_delete_file`). Solo cubre tipos con
`rich_text` propio (paragraph, heading_1/2/3, quote, callout, bulleted_list_item, numbered_list_item,
to_do, toggle) — filas de tabla y el bloque `transcription` en sí no son editables por esta vía; si se
intenta, la API de Notion lo rechaza con un error real, sin intento de adivinar un payload que no
corresponde.

**Protocolo de confirmed, dos niveles de severidad distintos:** `notion_update_block` sigue el mismo
criterio que `drive_update_document` — confirmación obligatoria la primera vez que se toca CADA bloque en
una conversación, no en cada llamada repetida al mismo bloque. `notion_delete_block` sigue el criterio
más estricto de `drive_delete_file`/`calendar_delete_event` — confirmación obligatoria SIEMPRE, cada vez,
nunca asumida de una edición anterior en la misma nota. Ambas entran a `HIGH_IMPACT_TOOLS`
(`snarf/core/orchestrator.py`).

**Integradas al cerebro en el mismo cambio** (regla permanente, ver CLAUDE.md): `notion_list_blocks`,
`notion_update_block` y `notion_delete_block` mapeadas al nodo `notion` en
`snarf/telemetry/brain.py::TOOL_TO_NODE` — sin esto, `spans.start_tool` no genera un `event_id` real y el
protocolo de `confirmed` deja de emitir sus eventos `APPROVAL_REQUESTED`/`APPROVAL_GRANTED` en silencio
(encontrado por un test que empezó a fallar, no por inspección). También se sumaron entradas en
`snarf/telemetry/verbs.py` y `snarf/telemetry/detail.py` (ambos con test de cobertura total sobre
`TOOLS`).

## Verificado

- Contra el Notion real del fundador (no solo mocks): `read_page_text` sobre la nota de Sócrates pasó de
  un resumen casi vacío a **64.192 caracteres reales** (ensayo completo, transcripción, resumen) en
  **212 fragmentos** con `block_id` propio vía `list_blocks`.
- `.venv/bin/python -m pytest -q` — 1497/1497 (1486 previos + 11 nuevos: recursión en toggles,
  transcripción con sección vacía omitida, celdas de tabla, `list_blocks`/`get_block`/`update_block`/
  `delete_block`, protocolo de `confirmed` de las dos tools nuevas).

## Consecuencias

- El indexado semántico de Notion (ADR 0173) ahora vectoriza el contenido real de notas armadas con
  toggles o con el transcriptor de reuniones — antes esas notas quedaban casi vacías en `knowledge_search`
  también, sin que hubiera ningún indicio de que faltaba algo.
- Límite conocido, no resuelto en esta ronda: `update_block` no cubre filas de tabla (`table_row`, que
  usa `cells` en vez de `rich_text` — payload de la API distinto) ni el bloque `transcription` en sí
  (generado por Notion, no documentado como editable vía API pública). Si el fundador necesita editar una
  celda de tabla real, es una extensión aparte.
- El server real de producción (puerto 8002) sigue corriendo el código anterior a este ADR hasta que se
  reinicie — confirmar con el fundador antes de reiniciarlo (ver CLAUDE.md).
