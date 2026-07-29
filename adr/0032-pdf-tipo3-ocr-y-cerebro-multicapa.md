# ADR 0032 — PDF con fuentes Type3 + fallback OCR, y cerebro de Snarf multi-capa

**Fecha:** 2026-07-29
**Estado:** Aceptado

## Contexto

Dos pedidos del fundador en la misma ronda, tras ver el "cerebro de Snarf" recién construido (ADR 0031):

1. Un bug real encontrado en uso: ciertos PDFs (exportados desde apps móviles o navegadores, ej. reportes de composición corporal) usan fuentes Type3 embebidas — cada glifo es un programa de dibujo propio, no un glifo estándar. El texto es seleccionable/copiable en visores reales (tienen CMap/ToUnicode embebido), pero `PdfExtractor` (basado en `pypdf`) no lo resolvía y devolvía texto vacío o basura, que además se indexaba en silencio como si hubiera funcionado.
2. Con capturas de referencia del HUD de Jarvis (Iron Man): el cerebro necesita "pulsos de luz que recorren los flujos", latido distinto para nodos activos vs en espera, y todos los nodos que se puedan agregar de forma honesta.

## Decisión

### 1. `PdfExtractor` reescrito sobre PyMuPDF (`fitz`), con fallback de OCR

Reemplaza `pypdf` por completo (`snarf/capabilities/pdf_extractor.py`). `page.get_text()` de PyMuPDF resuelve el CMap/ToUnicode de fuentes Type3 de forma nativa — arregla el bug reportado sin necesitar OCR para esos archivos. Cascada de estrategia, con una heurística simple (menos de ~20 caracteres reales por página sugiere "sin capa de texto", no un documento corto real):

1. Extracción nativa vía PyMuPDF.
2. Si el texto nativo no parece real y `tesseract` está instalado en el sistema (`shutil.which`, mismo patrón que `FfmpegAudioExtractor`): rasteriza cada página con la misma librería (`page.get_pixmap()`, sin dependencia extra de conversión) y corre OCR con `pytesseract` (`lang="spa+eng"`).
3. Si ninguna de las dos estrategias encuentra texto usable, `ContentExtractor.extract()` ahora lo declara explícitamente (`skipped_reason="PDF sin texto extraíble (ni nativo ni OCR)"`) en vez de indexar contenido vacío en silencio — bug relacionado, corregido en el mismo cambio.

**Decisión de licencia, explícita con el fundador**: PyMuPDF es AGPL-v3 (o licencia comercial). Se evaluó la alternativa MIT (`pdfplumber`, soporte a Type3 menos robusto) y el fundador eligió PyMuPDF — sin problema para uso interno; relevante solo si Snarf se ofrece como servicio a terceros por red en el futuro, momento en el que esta decisión debería revisarse.

**Tesseract necesita el paquete de idioma español aparte** de la instalación base de Homebrew (`spa.traineddata`, descargado de `tessdata_fast` a `$(brew --prefix)/share/tessdata/`) — instalado en el entorno de desarrollo del fundador como parte de este trabajo, documentado en `.env.example` junto al mismo patrón ya usado para `ffmpeg`.

### 2. Cerebro de Snarf: arquitectura de dos capas + latido diferenciado + flujo continuo

**Más nodos, todos con respaldo real** (Principio VI — nunca decorativos sin dato detrás):

- `stt`/`tts` reemplazan al nodo único "voz": `usage_tracker` ya registra el modelo real de cada llamada a ElevenLabs (`stt_scribe` vs `tts`), así que separarlos no inventa nada, solo deja de esconder un dato que ya existía.
- `specialist_gmail` se separa de `gmail`: `gmail_summarize_inbox` es el único Especialista Cognitivo real hoy (`GmailDigestSpecialist`, ADR 0025) — una capa arquitectónica distinta de la Capacidad Gmail cruda, ya documentada en COGNITION.md/ADR 0003. El cerebro ahora dibuja un anillo interno para Especialistas Cognitivos y uno externo para Capacidades, reflejando la arquitectura real de tres capas en vez de una lista plana — hoy el anillo interno tiene un solo nodo, pero crece solo a medida que se construyan más Especialistas (ver Roadmaps).
- `snarf/telemetry/brain.py` gana `last_timestamp` por nodo (máximo real entre sus eventos), base de todo lo que sigue.

**Dos latidos distintos, nunca decorativos sin dato real detrás**: un nodo con actividad real en los últimos 60 segundos (`node.last_timestamp`) entra en un latido rápido tipo "lub-dub" (`brain-heartbeat`, más brillante); sin eso, cae a un latido lento de espera (`brain-breathe`, tenue) — nunca completamente apagado, nunca falseando actividad que no ocurrió.

**Flujo de luz continuo sobre edges activos**: además del pulso puntual que ya viajaba por evento nuevo (ADR 0031), un edge cuyo nodo está activo ahora tiene una "corriente" de guiones animados corriendo todo el tiempo que dure esa actividad (`stroke-dasharray` + `stroke-dashoffset`, CSS puro) — la "sinapsis encendida" que pidió el fundador, distinta del pulso puntual de un evento discreto.

## Verificado

- 264 tests (todos los anteriores + 15 nuevos: `PdfExtractor` reescrito completo con PDFs reales construidos con PyMuPDF, incluidos los casos de fallback de OCR con y sin tesseract instalado; `ContentExtractor` con el caso de PDF sin texto usable; `brain.py` con la nueva cobertura de `last_timestamp`, el split `stt`/`tts`, y el ruteo de `gmail_summarize_inbox` al nodo especialista).
- Verificación en vivo con Playwright: los 12 nodos (Orchestrator + 1 Especialista + 10 Capacidades) renderizan sin recorte de etiquetas, en desktop y mobile, sin errores de consola. Estado activo/idle probado inyectando un snapshot controlado (`applyBrainSnapshot`) — confirmado que un nodo con evento a 5s se ve activo con flujo encendido, y uno a 300s se ve en espera sin flujo.

## Consecuencias

- El primer viewBox del SVG del cerebro (`0 0 400 400`, ADR 0031) se quedó chico para dos anillos con etiquetas de texto — corregido a `0 0 500 500` con centro y radios recalculados; si se agregan más nodos a futuro, este es el primer lugar a revisar antes de que las etiquetas se corten de nuevo.
- La lista `TOOL_TO_NODE` sigue cubierta por un test de regresión contra las herramientas reales del Orchestrator — el split de `gmail_summarize_inbox` a su propio nodo no rompe esa garantía, solo cambia el valor mapeado.
- PyMuPDF es la primera dependencia AGPL del proyecto — precedente a tener en cuenta si en el futuro Snarf se ofrece como servicio a terceros por red.
