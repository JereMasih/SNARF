# ADR 0034 — `drive_read_file` extrae de verdad; el cerebro gana partículas, resplandor y cámara; `/send` degrada con gracia

**Fecha:** 2026-07-29
**Estado:** Aceptado

## Contexto

Tras ADR 0032 (PDF vía PyMuPDF), el fundador probó en vivo con un PDF real (`Peso_16-07-2026.pdf`, un reporte de composición corporal con fuentes Type3) y Snarf seguía devolviendo bytes crudos. La causa no era el fix de `PdfExtractor` — era que `drive_read_file`, la herramienta que Snarf usa para "leer" un archivo en el chat, nunca pasó por `ContentExtractor`/`PdfExtractor`: llamaba directo a `GoogleDrive.read_file_text()`, que decodifica cualquier binario como UTF-8 a lo bruto. Dos caminos de código hacían "extraer texto de un archivo de Drive" — uno (el de indexación) se arregló en ADR 0032, el otro (el de lectura en vivo) quedó exactamente igual que antes.

En la misma ronda, con la instancia real del fundador (puerto 8002) reiniciada para verificar el fix, pidió una cuarta vuelta sobre el cerebro: más luz, partículas, sensación de flotar en el espacio digital, y una cámara que se acerque a un proceso en primer plano cuando corresponda — con el cerebro de Ultron/Jarvis en *Avengers: Age of Ultron* como referencia explícita.

Al cerrar la jornada, `/send` tiró un HTTP 500 real contra la instancia del fundador: su cuenta de la API de Anthropic (separada de la suscripción de Claude Pro) se quedó sin crédito. No es un bug de código, pero expuso uno real: `Orchestrator.handle()` no envolvía la llamada al LLM en ningún `try/except`, a diferencia de `/transcribe`, que ya degrada con gracia ante un fallo de STT.

## Decisión

### 1. `drive_read_file` reusa `ContentExtractor`, no `GoogleDrive.read_file_text()`

`Orchestrator._read_drive_file(file_id, mime_type)` ahora llama a `self._content_extractor.extract({"id": file_id, "mimeType": mime_type})` — el mismo pipeline que ya usa la indexación de Drive (PDF/Word/PowerPoint/Excel extraídos de verdad, con el fallback de OCR de ADR 0032; imagen por visión; audio/video por transcripción; texto/Google Docs sin cambios). Un solo camino de verdad para "extraer contenido de un archivo de Drive", en vez de dos que pueden desalinearse. Si la extracción falla, se devuelve `{"error": ...}` en vez de silenciarlo. `Orchestrator` guarda una referencia a `content_extractor` (ya se construía, solo faltaba exponerla).

**Verificado en vivo contra el archivo real del fundador**: `Peso_16-07-2026.pdf` ahora extrae el análisis de composición corporal completo y legible (agua corporal, proteína, minerales, masa grasa, con sus rangos de referencia) — antes devolvía glifos ilegibles.

**Instancia real reiniciada**: el proceso de producción del fundador (puerto 8002) corría desde el lunes con el código viejo en memoria — Python no recarga solo. Reiniciado con `nohup`/`disown` (mismo patrón ya validado para el indexado), confirmado en el mismo entorno virtual donde se instalaron `pymupdf`/`pytesseract`.

### 2. Cerebro de Snarf: capa de partículas + resplandor real + cámara de foco

Nueva capa `<canvas>` (`#brainParticles`), la primera vez que este proyecto usa canvas — todo lo anterior (nodos/edges/colores/latido, ADR 0031-0033) sigue siendo SVG+CSS sin cambios; el canvas es pura atmósfera encima, nunca reemplaza la lógica de datos ya construida.

- **Partículas ambiente**: ~90 (desktop) / 45 (mobile) motas de polvo de luz, colores tomados de la misma paleta real (`--brain-*`), con profundidad simulada (más lejos = más chicas/tenues/lentas) — deriva continua, nunca estáticas.
- **Resplandor real, no un blur simulado**: `globalCompositeOperation = "lighter"` (blending aditivo real de canvas) — las partículas se iluminan entre sí donde se superponen, igual que luces reales.
- **Estallido de partículas por evento real**: cada vez que llega un evento real (el mismo que ya dispara el pulso puntual por el edge, ADR 0031), estalla un grupo de partículas en el nodo de origen, coloreadas según el color real de ese nodo (o rojo si fue un error) — incluye al Orchestrator para los `unknown_tool`, que antes no tenían ninguna reacción visual.
- **Cámara que se acerca a un nodo activo**: `#brainGraphInner` (SVG + canvas juntos, siempre con el mismo transform — nunca se desalinean) hace zoom hacia el nodo que acaba de recibir un evento real (~1.55x, ~2.4s) y vuelve solo a la vista general. Disparado por el mismo evento real que ya dispara el pulso, nunca simulado.
- **Sensación de flotar**: una deriva y un "respiro" de zoom sutil y constante, incluso en reposo — nunca una imagen del todo estática.

Todo el sistema (partículas + cámara) corre en un solo loop de `requestAnimationFrame`, con la misma disciplina de gobernanza que el resto del cerebro (ADR 0026/0031): arranca solo al abrir la pantalla completa, se frena al cerrar o cuando la pestaña se oculta — nunca corre en segundo plano sin uso real.

### 3. `Orchestrator.handle()` degrada con gracia si el LLM falla

La llamada a `self._llm.generate(...)` queda envuelta en `try/except` — un fallo real (crédito agotado, rate limit, red) ahora produce una respuesta explícita (`"[error real del LLM, no pude responder: {exc}]"`, guardada igual en la memoria episódica) en vez de un HTTP 500 crudo hasta `/send`. Mismo criterio que ya usaba `/transcribe` para fallos de STT.

## Verificado

- 276 tests (todos los anteriores + 3 nuevos: `_read_drive_file` delega en `ContentExtractor` en vez de bytes crudos y reporta explícito cuando la extracción falla; `Orchestrator.handle()` degrada con gracia cuando `_llm.generate` lanza una excepción real).
- Verificado en vivo contra el archivo real del fundador (ver arriba) y contra la instancia real reiniciada (dos veces en la misma jornada: una para el fix de `drive_read_file`, otra para la degradación de `/send`).
- Verificación en vivo con Playwright de la capa de partículas: partículas ambiente renderizando con resplandor real en desktop y mobile; cámara confirmada en zoom real (`scale(1.55)` durante el foco, vuelta a `scale(1.0)` después) inyectando un evento controlado; loop de animación confirmado apagado (`brainAnimFrameId === null`) tras cerrar la pantalla completa — sin fugas de rendimiento.

## Consecuencias

- Cualquier futura Capacidad nueva que extraiga contenido de un archivo de Drive tiene un solo lugar para hacerlo bien (`ContentExtractor`) — `drive_read_file` y la indexación ya comparten ese único camino, no hay un tercero que se pueda volver a desalinear.
- El canvas es la primera pieza de este proyecto que no es SVG/CSS puro — aceptado a propósito para lograr partículas y resplandor con calidad real; el resto de la interfaz (dashboard, chat) no se ve afectada.
- Reiniciar un proceso real en producción (aunque sea de un solo usuario) es una acción que se pidió confirmación antes de ejecutar — la memoria episódica persiste en disco, así que nada se perdió.
