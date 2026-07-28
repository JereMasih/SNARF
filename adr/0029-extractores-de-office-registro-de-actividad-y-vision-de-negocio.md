# ADR 0029 — Extractores de Office, registro real de actividad, y registro de la visión ampliada de negocio

**Fecha:** 2026-07-28
**Estado:** Aceptado

## Contexto

Tras el catálogo real de "other" (ADR 0028, adenda), aparecieron 95 `.docx`, 41 `.epub` y otros documentos personales genuinamente valiosos sin extractor. El fundador pidió, en el mismo intercambio: dejar video para el final, sumar `.docx`/`.pptx`/`.xlsx` al tier gratuito, y — en un mensaje aparte, mucho más amplio — una visión de negocio completa para Snarf (dashboard de costos/ingresos/mercados/campañas, visualización tipo "cerebro Jarvis", reemplazo de sus chatbots externos con migración de "Proyectos" de ChatGPT, arquitectura de Especialistas por dominio, creación/exportación de documentos, onboarding). Ese pedido es, en los hechos, la hoja de ruta de una empresa, no una tarea — se decidió no construirlo de una, registrarlo completo en `MASTER_MAP.md` (Regla de crecimiento de ese mapa) y acordar con el fundador un orden de ejecución antes de tocar código en las piezas grandes.

## Decisión

### 1. Extractores de Office (`.docx`/`.pptx`/`.xlsx`)

`DocxExtractor` (`python-docx`), `PptxExtractor` (`python-pptx`), `XlsxExtractor` (`openpyxl`) — mismo patrón que `PdfExtractor`: Capacidad chica, sin credenciales, `available` siempre `True`. `ContentExtractor` (`snarf/knowledge/extraction.py`) pasa de un `if/elif` a un diccionario `mimeType → extractor` para los tipos binarios (PDF/DOCX/PPTX/XLSX), y `categorize_mime` suma las categorías `docx`/`pptx`/`xlsx`. `FREE_TIER_DRIVE_QUERY` (ADR 0028) se amplía para incluir estos tres mimeTypes — siguen siendo extracción 100% local, sin costo de API.

### 2. Registro real de actividad del Orchestrator (`snarf/telemetry/activity_log.py`)

Prerrequisito explícito para la visualización "cerebro de Snarf" (MASTER_MAP.md, Fase 3 de Roadmaps): hoy `episodic_memory.jsonl` solo guarda input/response, nunca qué herramienta se ejecutó. `Orchestrator._handle_tool` (el único punto de despacho de las ~28 herramientas) ahora registra cada llamada — nombre, estado (`ok`/`error`/`unknown_tool`), duración, error si lo hay — en `data/activity_log.jsonl`, append-only, mismo patrón que `episodic_memory.jsonl` y `usage_log.jsonl`. Nuevo endpoint de solo lectura `GET /dashboard/activity` (stats + últimas 50 entradas). **No se construyó ningún widget visual todavía** — es deliberadamente solo el dato real; la visualización es la siguiente pieza, sobre datos reales en vez de inventados.

### 3. Visión ampliada de negocio: registrada, no construida

Ver `MASTER_MAP.md` (sección Roadmaps) para el pedido completo y el orden acordado con el fundador ("el más eficiente posible"): (1) tier gratuito de Drive + registro de actividad [esta ADR], (2) creación/exportación de documentos, (3) datos de mercado, (4) migración de ChatGPT + arquitectura de Especialistas/Proyectos, (5) visualización Jarvis sobre el registro real, (6) fuente de datos de costos/ingresos de negocio (conversación pendiente, no código), (7) interfaz de configuración/onboarding. Multi-usuario sigue explícitamente pospuesto — el fundador ratificó la decisión de ADR 0028 cuando se le preguntó directamente si quería reabrirla.

**Por qué no se construyó nada de esto todavía:** varias piezas requieren una fuente de datos real que hoy no existe (costos de negocio, ingresos, campañas — mostrar cualquiera de estos sin una integración real violaría el Principio VI de Foundation, honestidad intelectual, que este mismo dashboard ya viene respetando estrictamente desde ADR 0022) o un vendor todavía no elegido (datos de mercado). Construir sin ese fundamento habría significado inventar datos o adivinar una decisión de vendor que le corresponde al fundador — exactamente lo que la "Colaboración crítica" de `PROJECT_CONTEXT.md` pide evitar.

## Verificado

- 183 tests (todos los anteriores + `DocxExtractor`/`PptxExtractor`/`XlsxExtractor` con archivos reales generados por las mismas librerías, dispatch de `ContentExtractor` para los tres tipos nuevos, `activity_log` (record/recent/stats) e instrumentación de `Orchestrator._handle_tool` para los tres casos: éxito, error, herramienta desconocida).

## Consecuencias

- El tier gratuito de Drive ahora cubre Google Docs/Sheets/Slides, PDF, DOCX/PPTX/XLSX y texto plano — el resto de "other" (software, robots de trading en zip/rar/dll, epub, doc/xls/ppt legacy, pages/numbers) queda catalogado (ADR 0028) pero todavía sin extractor.
- `data/activity_log.jsonl` empieza a acumular datos reales desde hoy — para cuando se construya la visualización Jarvis, ya va a haber historial real que mostrar, no una tabla vacía.
- La visión de negocio completa queda como documento vivo en `MASTER_MAP.md`, no como trabajo comprometido — el fundador puede reordenarla en cualquier momento sin que se pierda contexto.
