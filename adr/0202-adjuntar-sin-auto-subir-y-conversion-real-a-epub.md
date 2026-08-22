# ADR 0202 — Adjuntar sin auto-subir + capacidad real de conversión a EPUB en el Orchestrator

**Fecha:** 2026-08-22
**Estado:** Aceptado

## Contexto

El fundador reportó, probando la interfaz real de Snarf (no Claude Code), dos problemas
mientras intentaba convertir un PDF ("Monólogo Lili") a EPUB:

1. Adjuntar un archivo en el chat lo subía y procesaba a Drive inmediatamente al
   seleccionarlo — antes de que el usuario dijera qué hacer con él en texto o audio.
2. El Orchestrator respondió que no tenía ninguna skill/herramienta para convertir a EPUB.

Investigado antes de tocar código: en `web/index.html`, el listener `change` de
`#fileInput` llamaba a `uploadAttachedFile()` de forma inmediata (`POST /files/upload` sin
esperar nada) — el texto que el usuario tipeaba después viajaba en un POST completamente
aparte a `/send`, sin ninguna relación con el archivo ya subido.

El Orchestrator de Snarf no tiene ningún concepto de "skill" al estilo Claude Code — todas
sus capacidades son tools Python registradas a mano en `snarf/core/orchestrator.py`
(`TOOLS` + `self._tool_handlers`). Un grep de "epub" en todo `snarf/` no encontró ningún
handler: el Orchestrator dijo la verdad, no tenía esa capacidad. Confirmado además en
`data/episodic_memory.jsonl` (conversación real de hoy, 2026-08-22T11:41): *"no existe
ninguna skill (nueva o vieja) para convertir PDFs a ePub en mi repertorio de
herramientas"*. La skill `pdf-to-epub` de Claude Code (instalada y probada en esta misma
sesión, en `.claude/skills/pdf-to-epub/`) es un sistema completamente separado — el
Orchestrator no puede invocarla en tiempo de ejecución.

## Decisión

**Frontend**: el archivo elegido ya no se sube al seleccionarlo. Queda "adjunto
pendiente" en un chip nuevo del composer (`#pendingAttachment`, mismo patrón visual que
`#replyContext` — reusa el ícono de clip y el botón `✕` ya existentes, sin íconos
nuevos) hasta que el usuario efectivamente envía el mensaje. Los 4 caminos de envío (texto
+ Enter, voz manos-libres, voz con revisión, modo continuo) convergen todos en la misma
`sendText()` — ahí, y solo ahí, se sube el archivo (`POST /files/upload`) junto con la
instrucción real, y su `file_id` viaja en el mismo `POST /send` (`attachment_file_id`/
`attachment_name`/`attachment_mime_type`, nuevos en `SendRequest`). Si la subida falla, el
chip y el borrador de texto se restauran — nunca se pierde el archivo ni lo escrito.

**Backend**: nueva capacidad `snarf/capabilities/epub_builder.py` (`EpubBuilder`), con la
misma lógica de detección de estructura ya probada en la skill `pdf-to-epub` (diálogo con
escenas, capítulos, o texto corrido/flow), portada a memoria (bytes in/out, sin tocar el
filesystem — más apto para un server concurrente que el script original basado en
directorio temporal). Nueva tool `convert_to_epub`: descarga el archivo fuente de Drive
(`GoogleDrive.read_file_bytes`), lo convierte, sube el `.epub` resultante a la carpeta
`Snarf/Archivos` y lo indexa (mismo patrón que `/files/upload`). **Sin gate de
confirmación**: crea contenido nuevo en el Drive del propio fundador a partir de un archivo
que ya le pertenece, mismo criterio ya establecido para `drive_create_document`/
`document_write_start` (ninguno de esos exige `confirmed` — ese gate es para
borrar/sobreescribir/compartir/publicar afuera, no para crear).

`Orchestrator.handle()` ahora recibe los 3 campos de adjunto y, cuando hay uno, agrega una
nota corta al `system` prompt con el `file_id` real ya utilizable — es lo que le permite al
modelo llamar `convert_to_epub`/`drive_read_file` en el mismo turno según lo que el usuario
pida, en vez de decir "no hay ningún PDF adjunto" como pasó hoy.

**Protocolo de crecimiento** (mismo cambio, no aparte): `convert_to_epub` mapeado al nodo
`documents` en `snarf/telemetry/brain.py` (reusa el nodo existente, junto a
`drive_create_document`), y agregado también a los otros dos registros de cobertura que el
propio protocolo no documentaba explícitamente pero que la suite exige por construcción
(descubierto recién al correr los tests, no en la investigación previa):
`snarf/telemetry/verbs.py::VERB_BY_SKILL` y `snarf/telemetry/detail.py::DETAIL_EXTRACTORS`
— ambos con tests de cobertura idénticos al de `brain.py` (`test_verb_by_skill_covers_every_orchestrator_tool`,
`test_detail_extractors_cover_every_orchestrator_tool`). `snarf/runtime/areas.py` no se
tocó — ese mapeo cubre solo los 7 dominios de Specialists de Fase I, las tools de capacidad
cruda quedan afuera a propósito.

## Verificado

- `.venv/bin/python -m pytest -q` — 1692/1692 (7 tests nuevos en
  `tests/test_epub_builder.py`: detección de modo dialogue/chapters/flow, conversión real
  desde bytes de un PDF armado con `fitz`, EPUB resultante validado como zip bien formado
  con `mimetype` primera entrada sin comprimir y XHTML bien formado; 2 tests nuevos en
  `tests/test_orchestrator.py` para el tool `convert_to_epub` — camino feliz y el caso
  `ValueError` sin contenido extraíble; 3 tests nuevos/extendidos en `tests/test_app.py`
  para los campos de adjunto en `/send` y el `mimeType` nuevo en `/files/upload`).
- Playwright real contra un server de prueba (puerto 8000, nunca el 8002 de producción):
  adjuntar un archivo no dispara `/files/upload` hasta enviar el mensaje; el botón "✕" del
  chip cancela el adjunto; al enviar, exactamente un `/files/upload` se dispara y la
  burbuja del usuario muestra el nombre del archivo; punta a punta con un PDF real
  pidiéndole a Snarf que lo convierta a EPUB, `convert_to_epub` se ejecuta y devuelve un
  link real a un `.epub` nuevo en Drive.

## Consecuencias

- `pdfplumber` (agregado a `requirements.txt` en esta misma sesión para la skill de Claude
  Code) queda ahora también como dependencia real de producción, usada por `EpubBuilder`.
  `ContentExtractor` sigue usando PyMuPDF sin cambios — son dos extractores de PDF
  distintos, cada uno con su propio consumidor, no hay conflicto ni duplicación de
  responsabilidad.
- La skill `pdf-to-epub` de Claude Code y la capacidad `convert_to_epub` del Orchestrator
  comparten la misma lógica de detección/armado por diseño (una portada de la otra), pero
  son dos implementaciones independientes en dos sistemas separados — un fix futuro a la
  heurística de detección tiene que aplicarse en los dos lugares si se quiere mantener la
  paridad.
- `convert_to_epub` no soporta PDFs escaneados (sin texto seleccionable) — mismo límite ya
  documentado en la skill original; ahí hay que pasar primero por OCR (`pdf_extractor` con
  Tesseract) y convertir el texto resultante.
