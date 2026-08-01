# ADR 0074 — Edición de Google Docs existentes (`drive_update_document`)

**Fecha:** 2026-08-01
**Estado:** Aceptado

## Contexto

Snarf solo podía crear archivos nuevos en Drive (`drive_create_document`/`_spreadsheet`/`_presentation`) — nunca modificar uno ya existente. El fundador lo pidió explícitamente para poder mantener un backlog "vivo" y otros documentos actualizables in-place, sin tener que crear una copia nueva cada vez.

Punto de fricción marcado y resuelto con el fundador antes de codear (no autobloqueado): modificar un documento real y existente es una acción de alto impacto según el Art. VII de la Constitución (irreversible sobre contenido real). Preguntado explícitamente qué nivel de confirmación quería, eligió: **confirmación una vez por documento, por conversación** — no en cada edición individual, pero tampoco confirmación implícita para siempre.

Alcance de esta ronda: **solo Google Docs** (texto). Sheets y Slides quedan afuera — editar celdas de una hoja o slides de una presentación es una superficie de API distinta (Sheets API / Slides API, con semántica de rango/objeto en vez de texto plano) y una decisión de diseño separada, no una extensión trivial de esto.

## Decisión

### `GoogleDrive.read_document_text` / `GoogleDrive.replace_document_body`

Dos métodos nuevos en `snarf/capabilities/google_drive.py`, usando la API de Google Docs (`docs.googleapis.com`, vía `googleapiclient`) contra el mismo scope OAuth `https://www.googleapis.com/auth/drive` ya presente en `SCOPES` (`google_auth.py`) — no hace falta pedirle al fundador que reautorice nada.

- `read_document_text(file_id)`: concatena todo el texto plano real del documento (recorre `body.content[].paragraph.elements[].textRun.content`) — se usa para la vista previa antes de confirmar.
- `replace_document_body(file_id, new_text)`: `batchUpdate` con `deleteContentRange` (todo el rango actual, si no está vacío) seguido de `insertText` en el índice 1 — reemplazo total del cuerpo, no edición incremental por ahora.
- `_docs_client()` construye el cliente de la API de Docs sin cachear (a diferencia de `self._service` de Drive) — es una acción puntual y de alto impacto, no de alta frecuencia; no vale la pena sumar un segundo cache thread-local en paralelo al de Drive.

### Tool `drive_update_document`

Nueva en `snarf/core/orchestrator.py`: `{file_id, new_content, confirmed}`. Mismo protocolo de tres pasos que `gmail_send_message`/`drive_delete_file` (confirmed=false → preview con el contenido actual → confirmed=true), **con una excepción explícita documentada en `SYSTEM_PREFIX`**: una vez que el fundador confirmó la edición de un documento puntual en la conversación, ediciones siguientes a ESE MISMO documento más adelante en la misma conversación no vuelven a pedir confirmación — un documento distinto, o la misma edición en una conversación nueva, sí la piden desde cero. Mapeada al nodo `documents` del cerebro (mismo nodo que la creación de archivos — el fundador reconocería "documentos" como una sola subcapacidad, crear vs. editar es la misma familia).

## Verificado

- `.venv/bin/python -m pytest -q` — 534 passed (13 tests de `google_drive.py`, incluyendo 4 nuevos para `read_document_text`/`replace_document_body`, con fakes de la API de Docs siguiendo el mismo patrón que los fakes de Drive ya existentes en `tests/test_google_drive.py`).
- No se agregaron tests a nivel Orchestrator para el handler `_tool_drive_update_document`: siguiendo la convención ya establecida en el repo, `test_orchestrator.py` no cubre los handlers `_tool_*` de acciones de alto impacto individualmente (ni `drive_share_file` ni `drive_delete_file` lo tienen) — esa cobertura vive en la Capacidad subyacente, ya cubierta arriba.

## Consecuencias

- Sheets y Slides quedan como trabajo futuro explícito, no una promesa implícita de esta ronda — si se construyen, es una decisión de diseño nueva (Sheets API opera sobre rangos de celdas, Slides API sobre objetos de página, ninguna de las dos es "texto plano completo" como Docs).
- `replace_document_body` reemplaza TODO el contenido — no hay edición incremental (insertar/reemplazar solo una sección) todavía. Si en el futuro se necesita editar solo una parte de un documento largo, es una extensión real de este ADR, no algo ya cubierto.
