# ADR 0028 — Vectorización de Google Drive y panel de costo de API

**Fecha:** 2026-07-28
**Estado:** Aceptado

## Contexto

Retomando el roadmap (ver "Planificado" en `MASTER_MAP.md`, Capabilities), el fundador pidió tres cosas en la misma ronda: (1) visibilidad en tiempo real de cuánto gasta Snarf en APIs, dado que hoy paga Claude Pro (suscripción de chat, separada) y tiene $10 de crédito cargados en la API de Anthropic más ~$10/mes de Google Drive (almacenamiento, no relacionado con esto); (2) construir la extracción de contenido por tipo de archivo (PDF, imagen, audio, video) para poder vectorizar Drive completo, pendiente desde ADR 0013/0014; (3) evaluar si conviene ya una infraestructura multi-usuario para esto. Antes de construir, se hizo un análisis de costo real (Voyage AI, ElevenLabs, Anthropic, con tarifas verificadas 2026-07-28) para elegir proveedor y modelo priorizando costo y escalabilidad — resumen en `MEMORY.md`/conversación, cifras exactas en `snarf/telemetry/pricing.py`. El Drive real del fundador ronda 700GB, cantidad de archivos desconocida — descarta cualquier diseño que asuma indexar todo en una sola llamada síncrona.

## Decisión

### 1. Telemetría de costo (`snarf/telemetry/`)

Paquete nuevo, sibling de `snarf/memory/` — no es Capacidad ni Especialista, es un utilitario de bajo nivel que las Capacidades pueden importar (no está en la lista prohibida de `tests/test_architecture_boundaries.py`, a diferencia de `snarf.core`/`snarf.runtime`).

- `pricing.py`: tarifas públicas verificadas (Anthropic Sonnet 5/Haiku 4.5/Opus 5 por millón de tokens con descuento de cache; ElevenLabs Scribe por hora; Voyage por millón de tokens con los 200M gratis por cuenta). Son estimaciones basadas en tarifa publicada, **no el saldo real de ninguna cuenta**.
- `usage_tracker.py`: registro append-only (`data/usage_log.jsonl`, mismo patrón que `episodic_memory.jsonl`) de cada llamada real, con costo estimado. `AnthropicLLM.generate()`, `ElevenLabsSTT.transcribe()` y `ElevenLabsTTS.synthesize()` quedaron instrumentadas para registrar cada llamada real. TTS registra caracteres sin inventar un costo en USD (depende del plan contratado, no es pago por uso plano como Scribe) — Principio VI de Foundation: nunca presentar como cierto lo que no se puede justificar.
- Nuevo widget de dashboard "Costo de API" (`cost`, séptimo en `WIDGET_IDS`), alimentado por `GET /dashboard/summary` → `usage_tracker.summarize()`: total estimado (todo el tiempo / hoy / últimos 7 días), desglose por proveedor, y una nota explícita de que es una estimación, no el saldo real de cada cuenta.

### 2. Extracción de contenido por tipo (Capacidades nuevas)

- `PdfExtractor` (`pypdf`) para PDF.
- Imágenes: sin Capacidad nueva — reusa `AnthropicLLM`, pero instanciada con `claude-haiku-4-5` (`DRIVE_VISION_MODEL`), no el modelo principal de Snarf — mismo criterio que `GMAIL_DIGEST_MODEL` (ADR 0025/0026): describir una imagen es una tarea acotada y mecánica.
- Audio: reusa `ElevenLabsSTT` ya existente.
- Video: `FfmpegAudioExtractor` (subprocess a `ffmpeg`, binario de sistema — no es un paquete de pip, se documenta en `.env.example`) extrae la pista de audio, que luego pasa por `ElevenLabsSTT`.
- `GoogleDrive` gana `read_file_bytes()` (bytes crudos, sin decodificar como texto — necesario para PDF/imagen/audio/video) y paginación real: `list_files_page()` + `iter_all_files()` (generador que recorre todas las páginas). `list_files()` no cambió de firma — nada que ya lo use se rompió.

### 3. Pipeline de indexación (`snarf/knowledge/`, nuevo paquete reusable)

- `extraction.py`: `ContentExtractor`, dispatcher por `mimeType` (vía `categorize_mime`) hacia el extractor correspondiente. Todo dentro de un `try/except`: un tipo no soportado o un fallo real nunca tira la corrida entera, queda registrado con su razón (Principio VI: nunca descartar en silencio).
- `chunking.py`: función pura, chunks de tamaño fijo con solapamiento.
- `vector_store.py`: wrapper sobre `chromadb` en modo persistente local (sin servidor) — gratis, coherente con que todo en Snarf persiste a `data/` local. El cliente se arma recién en el primer uso real (mismo criterio que `GoogleDrive._client()`), para que construir la clase no toque disco.
- `manifest.py` (`IndexManifest`): progreso por archivo en `data/drive_index/<user_id>/manifest.json` — `modifiedTime` visto, estado (`indexed`/`skipped_unsupported`/`error`), cantidad de chunks. Permite reanudar un job interrumpido y re-indexar barato (saltea archivos sin cambios).
- `drive_indexer.py` (`DriveIndexer`): orquesta todo. Corre en un `threading.Thread` de background, arrancado siempre explícitamente — nunca automático, mismo criterio de gobernanza que ADR 0026 fijó para el refresco de Gmail. Expone `scan()` (solo lectura, cuenta archivos/bytes por categoría, sin gastar nada), `start()`/`stop()`/`status()`, y `search()` (embebe la consulta y busca en el vector store).
- `snarf/knowledge/` quedó sujeto a la misma garantía de reusabilidad que ADR 0026 fijó para `capabilities/`/`specialists/` — `tests/test_architecture_boundaries.py` ahora también lo cubre.

### 4. Herramientas nuevas para Snarf (`orchestrator.py`)

`drive_index_scan`, `drive_index_start`, `drive_index_status`, `drive_index_stop`, `drive_search_knowledge`. Ninguna es de alto impacto en el sentido de ADR 0015 (nada se borra ni se manda afuera de forma irreversible), así que no llevan el protocolo `confirmed=true`. Pero dado el costo real en dólares y tiempo de indexar 700GB, `SYSTEM_PREFIX` instruye a Snarf a: nunca llamar `drive_index_start` por su cuenta, solo cuando el fundador lo pida explícitamente, y mostrar siempre primero un `drive_index_scan` en la conversación para que decida el alcance (todo el Drive o una carpeta puntual vía `query`) con números reales, no una proyección.

### 5. Proveedores elegidos, priorizando costo y escalabilidad

- **Embeddings: Voyage AI, `voyage-4-lite`** ($0.02/M tokens, 200M tokens gratis por cuenta — la pieza más cara del pipeline en teoría es, con altísima probabilidad, gratis en la práctica). Recomendado oficialmente por Anthropic para usar con Claude.
- **Transcripción: ElevenLabs Scribe** (ya integrado, más barato que la alternativa obvia de OpenAI Whisper).
- **Visión: Claude Haiku 4.5** (no Sonnet 5 — ver punto 2).
- **Vector store: chromadb local** ($0, sin servicio hosteado).

Cero vendors nuevos innecesarios: de las piezas nuevas, solo Voyage es un vendor genuinamente nuevo (`VOYAGE_API_KEY`); el resto reusa lo que ya existía pago e integrado, o es gratis y local.

### 6. Infraestructura multi-usuario: evaluada y pospuesta (no construida)

El fundador preguntó si conviene ya una infraestructura/interfaz para que cada usuario nuevo vectorice su propio Drive. Se decidió **no construirla ahora**: no existe todavía un segundo usuario real (MASTER_MAP.md ya lista login con Google y "flujo real de un segundo usuario" como Planificado, sin fecha, exactamente por esto), y construir multi-tenencia genérica sin un segundo consumidor real sería la misma anticipación que ADR 0019/0022/0026 ya se prohibieron. Lo que sí se hizo — el único trabajo real que la extensión futura necesita — es namespacing por `user_id` desde el día uno: `data/drive_index/<user_id>/manifest.json` y `.../chroma/`, exactamente el mismo patrón que `credentials/tokens/<user_id>.json` (ADR 0021), `data/dashboard_prefs/<user_id>.json` y `data/gmail_digest/<user_id>.json`. Agregar un segundo usuario real, cuando exista, es pasar otro `user_id` — no rediseñar esta pieza.

### 7. Adenda (misma jornada): catálogo de "other", alias `free_tier`, y un bug real de reintento

Tras ver el resultado del scan real (37.479 archivos, ~820GB — más cerca de la estimación corregida del fundador que de la original), el fundador pidió: dejar video para el final, investigar qué son los 9.854 archivos de la categoría "other" (~230GB) antes de decidir, y arrancar por lo que sale gratis.

- **`DriveIndexer.catalog_unsupported()`**: recorre el Drive y registra, por cada archivo sin extractor, su `mimeType` real y nombre — sin extraer contenido, sin costo. Persiste un catálogo completo (`data/drive_index/<user_id>/unsupported_catalog.json`) y devuelve un resumen agrupado por `mimeType` con ejemplos. Nueva herramienta `drive_index_catalog_unsupported`.
- **Alias `query='free_tier'`**: acota `scan`/`start`/`catalog_unsupported` a Google Docs/Sheets/Slides + PDF + texto plano — lo que hoy se extrae localmente o se lee directo de Drive, sin ningún costo real de API más allá de embeddings (que con altísima probabilidad quedan dentro del tier gratuito de Voyage).
- **Bug real encontrado y corregido**: `IndexManifest.needs_processing` consideraba "ya resuelto" a un archivo marcado `error` con el mismo `modifiedTime`, así que un fallo transitorio (por ejemplo, `VOYAGE_API_KEY` todavía no configurada) lo dejaba descartado para siempre, incluso después de arreglar la causa. Corregido: un archivo en estado `error` siempre se reintenta en la próxima corrida, a diferencia de `indexed` o `skipped_unsupported`, que sí son resultados estables.
- **Resultado real del catálogo**: de los ~230GB de "other", ~195GB son 23 archivos ZIP grandes (instaladores de software, plugins de WordPress, `Jere Masih Trader (ISO LOGO).zip`) y ~17GB son `octet-stream` (mayormente artefactos de un proyecto Unity: crash dumps, `.dll`, configuración) — ninguno de los dos es contenido personal indexable. El hallazgo genuinamente valioso: 128 archivos `.zip`/`.rar` (~11GB) que sí son robots e indicadores de trading reales (`PATREX PRO ROBOTS`, `KD + RT`, `Jere Trading System`), más binarios de indicadores sueltos (`Murrey_Math_v1_12.dll`, `TFL_Intraday_Pivots.dll`) — no extraíbles como texto sin decompilar, pero identificables por nombre. Y, sin buscarlo, apareció una categoría de documentos personales genuinamente valiosos que hoy caen en "other" solo porque no existe extractor: 95 `.docx`, 41 `.epub` (libros reales), 7 `.pptx`, 7 `.xlsx`, 14 `.doc`, 6 `.xls`, 3 `.pages`, 1 `.numbers` — candidatos naturales a sumar al tier gratuito en una próxima ronda.

## Verificado

- 165 tests (todos los anteriores + nuevos: `pricing`/`usage_tracker`, instrumentación de las 3 Capacidades de voz/LLM, `chunking`, `extraction` (los 4 tipos + casos de error/no-soportado), `manifest` (incluido el reintento de `error`), `vector_store` (chromadb real contra directorio temporal), `drive_indexer` (incluyendo `stop()` real sobre un thread en curso, el catálogo de "other" y el alias `free_tier`), `pdf_extractor`, `ffmpeg_audio`, `voyage_embeddings`, paginación de `GoogleDrive`, y las 6 herramientas nuevas del Orchestrator).
- `tests/test_architecture_boundaries.py` extendido a `snarf/knowledge/`: sigue en verde.
- Encontrado y corregido durante la construcción: `DriveIndexer._process_file` no envolvía la llamada a `extractor.extract()` en el mismo `try/except` que el resto — una excepción ahí (no un `ExtractionResult` con `skipped_reason`, sino una excepción real) tiraba abajo el thread de background entero en silencio, sin registrar nada. Corregido antes de mergear; test de regresión (`test_start_marks_extraction_errors_without_crashing_the_run`) lo cubre.
- `drive_index_scan` corrido en vivo contra el Drive real del fundador (ver CHANGELOG.md para el resultado concreto).

## Consecuencias

- Vectorizar Drive completo tiene costo real (Voyage probablemente gratis, pero ElevenLabs y Claude Vision no) y toma tiempo — por diseño, nunca arranca solo. El primer paso real sigue siendo un piloto acotado a una carpeta chica, no las 700GB completas de una vez.
- El manifest reescribe el archivo entero por cada archivo procesado (no incremental) — aceptable para un Drive de escala de un solo founder (miles de archivos, no millones); si el volumen crece órdenes de magnitud, esto es lo primero que habría que optimizar.
- La próxima Capacidad que necesite registrar costo (por ejemplo, si se agrega un proveedor de LLM nuevo) tiene el precedente de `usage_tracker.py` para copiar: instrumentar la llamada real, nunca inventar un costo que no se pueda justificar con la tarifa publicada.
