# ADR 0030 — Snarf puede crear, recibir y vectorizar archivos reales

**Fecha:** 2026-07-28
**Estado:** Aceptado

## Contexto

Ítem 3 de la Fundación técnica acordada con el fundador (ver MASTER_MAP.md, Roadmaps): antes de sumar Capacidades nuevas, Snarf tiene que poder crear y recibir archivos reales, no solo leer los que ya existen en Drive. El pedido concreto: generar Google Docs, Sheets, PDF, PowerPoint y Markdown con un link de descarga; recibir archivos subidos en el chat; y que una imagen subida se analice y quede vectorizada sola, para que Snarf la recuerde en conversaciones futuras — el mismo criterio se extiende a cualquier archivo subido, no solo imágenes.

## Decisión

### 1. Generar documentos (`DocumentBuilder`, `snarf/capabilities/document_builder.py`)

Capacidad nueva, sin credenciales, todo local: `build_markdown`, `build_pdf` (`fpdf2`, nueva dependencia liviana), `build_pptx` (`python-pptx`, ya instalado para lectura, ahora también escribe), `build_xlsx` (`openpyxl`, ídem). No genera Google Docs/Sheets/Slides directamente — eso lo resuelve la conversión de Drive al subir (punto 2).

### 2. Subir y convertir (`GoogleDrive.upload_file` + `get_or_create_folder`)

`GoogleDrive` gana `upload_file(name, content, mime_type, parent_id, convert_to)`: sube bytes reales con `MediaIoBaseUpload`, y si `convert_to` es un mimeType nativo de Google, Drive convierte el contenido subido al formato editable nativo — **no hizo falta integrar la API de Google Docs por separado**. Para un Google Doc, se sube texto plano con `convert_to=application/vnd.google-apps.document`; para Sheets/Slides, se sube el xlsx/pptx generado por `DocumentBuilder` con el `convert_to` correspondiente. Verificado en vivo: los tres casos (markdown tal cual, Google Doc por conversión, xlsx tal cual) generaron archivos reales y abribles en el Drive del fundador.

`get_or_create_folder(name, parent_id)` — todo lo que Snarf crea o recibe vive en una carpeta fija, `Snarf - Archivos`, resuelta una sola vez y cacheada.

### 3. Orquestación (`DocumentPublisher`, `snarf/knowledge/document_publisher.py`)

Junta `DocumentBuilder` + `GoogleDrive` + `DriveIndexer`: genera los bytes según el formato pedido, sube a la carpeta fija, e indexa el archivo de inmediato (ver punto 4) — sin esperar a la próxima corrida completa de indexación. Si la indexación falla, el archivo igual quedó creado y se informa `indexed: false` en vez de perder el resultado real por un problema aparte.

Tres herramientas nuevas para Snarf: `drive_create_document` (markdown/pdf/google_doc), `drive_create_spreadsheet` (xlsx/google_sheet), `drive_create_presentation` (pptx/google_slide). Todas devuelven el `webViewLink` real de Drive — ese es el "link de descarga" pedido.

### 4. Indexar un archivo suelto, sin esperar al background (`DriveIndexer.index_file`)

Refactor mínimo: la lógica de `_process_file` (ya existía para la corrida en background) ahora también se puede invocar para un único archivo conocido, fuera de cualquier corrida — necesario tanto para lo que Snarf crea como para lo que el fundador sube. `DriveIndexer.get_indexed_text(file_id)` (vía `VectorStore.get_by_file_id`, nuevo) recupera el texto ya indexado de un archivo puntual — para poder devolver la descripción de una imagen recién subida sin pagar la extracción dos veces.

### 5. Recibir archivos (`POST /files/upload`)

Nuevo endpoint: sube el archivo a `Snarf - Archivos`, lo indexa con `index_file`, y si es una imagen devuelve además el texto de la descripción que generó la visión al indexarla — visible de inmediato en el chat, sin esperar una búsqueda aparte. Nuevo botón de adjuntar (ícono de clip) en `web/index.html`, junto al campo de texto.

### 6. Adenda (misma jornada): destino explícito Drive vs. local, sin duplicar nunca el archivo original

El fundador preguntó cómo evitar que lo que Snarf crea/recibe termine duplicado (el archivo real en Drive, y otra copia ocupando espacio en el futuro VPS). La respuesta, aclarada y confirmada con el fundador: **nunca hubo duplicación** — `DocumentBuilder` genera bytes en memoria, `GoogleDrive.upload_file` los sube directo a Drive sin pasar por disco, y lo único que vive local es el índice vectorial (texto extraído, cortado y embebido — órdenes de magnitud más chico que el archivo original, nunca el archivo en sí). Lo que sí faltaba, y que el fundador pidió: una opción real de **no** subir a Drive.

- **`LocalFileStore`** (`snarf/capabilities/local_file_store.py`): guarda bytes en disco, en `data/local_files/<user_id>/` — gitignorado, mismo criterio que `data/drive_index/`.
- **`DriveIndexer.index_local_text`**: indexa texto que no viene de un archivo de Drive — como ya se conoce el texto de origen (es el mismo que se usó para generar el documento), no hace falta re-extraerlo de los bytes generados.
- **`DocumentPublisher` gana `destination: "drive" | "local"`** en sus tres métodos de creación. Con `"local"`, nunca se llama a ningún método de `GoogleDrive` — ni `upload_file` ni `get_or_create_folder`. Los formatos nativos de Google (`google_doc`/`google_sheet`/`google_slide`) no existen en local — son, por definición, resultado de la conversión de Drive al subir — y piden `ValueError` si se combinan con `destination="local"`.
- Toda entrada del vector store, sea de Drive o local, queda con un campo `location` (`"drive"` o `"local"`) en sus metadatos — permite distinguir el origen en cualquier búsqueda futura sin necesitar una segunda base de datos.
- `SYSTEM_PREFIX` instruye a Snarf a preguntarle al fundador qué destino prefiere antes de crear un archivo, salvo que ya lo haya dicho explícitamente en el intercambio — mismo criterio de "pedir antes de asumir" que el resto del prompt ya aplica a otras herramientas.

### 7. Segunda adenda (misma jornada): tres destinos — Drive, dispositivo, servidor — y el servidor solo para el fundador

Tras la adenda anterior (destino local vs. Drive), el fundador pidió una distinción más precisa: además de Drive, quiere poder mandar un archivo directo a **su propio dispositivo** (con el diálogo nativo de guardar del sistema operativo que esté usando) y, por separado, reservarse **a él únicamente** la opción de usar el disco del propio servidor de Snarf como carpeta de trabajo — no algo que un futuro segundo usuario deba tener disponible.

- **`destination` pasa a tener tres valores**: `"drive"` (sin cambios), `"device"` y `"server"`. Los dos últimos comparten mecánica (`LocalFileStore`, mismo `data/local_files/<user_id>/`), pero difieren en dos cosas: `"device"` devuelve un `download_url` real (`GET /files/local/<user_id>/<archivo>`, nuevo endpoint en `app.py`) que el navegador resuelve con su propio diálogo de "Guardar como" — nativo del sistema operativo de quien lo use, sin que Snarf construya nada específico por plataforma; `"server"` no devuelve link, pensado como carpeta de trabajo persistente.
- **`allow_server_storage`**: `DocumentPublisher` recibe este flag en el constructor. El `Orchestrator` lo calcula una sola vez, comparando el `user_id` de la sesión contra `DEFAULT_USER_ID` ("fundador"). Pedir `destination="server"` sin el flag activo lanza `ValueError` — el archivo nunca se llega a crear. `SYSTEM_PREFIX` además instruye a Snarf a ni ofrecer ese destino como opción si quien habla no es el fundador — dos capas, prompt y código, mismo patrón que el resto de la gobernanza del proyecto.
- El endpoint de descarga valida que el `user_id` de la sesión coincida con el dueño del archivo, y descarta cualquier componente de directorio del nombre de archivo (`Path(filename).name`) antes de tocar el filesystem — sin eso, un nombre como `../../.env` habría podido leer archivos fuera de la carpeta del usuario.

## Verificado

- 235 tests (52 nuevos en total sobre esta ADR: `DocumentBuilder` con roundtrip real a través de los extractores existentes — PdfExtractor/PptxExtractor/XlsxExtractor validan el contenido que el propio builder generó; `GoogleDrive.upload_file`/`get_or_create_folder`; `DriveIndexer.index_file`/`get_indexed_text`/`index_local_text`; `VectorStore.get_by_file_id`; `LocalFileStore`; `DocumentPublisher` completo con fakes, incluidos los tres destinos y el rechazo de `server` sin permiso; las 3 herramientas nuevas del Orchestrator con `destination`; el endpoint `/files/upload`, incluida la degradación cuando Drive falla; el endpoint `/files/local/<user_id>/<archivo>`, incluido el rechazo cruzado entre usuarios y el path traversal).
- Verificación en vivo contra el Drive real del fundador: un Markdown, un Google Doc (por conversión real, no simulada) y un Excel con `destination="drive"` — los tres creados, indexados, y recuperables con una búsqueda semántica real inmediatamente después. Con `destination="device"`: un Markdown que quedó en `data/local_files/fundador/` (confirmado en disco) con su `download_url` real, indexado, sin ninguna llamada a Drive. Con `destination="server"`: mismo resultado, permitido para el fundador.

## Consecuencias

- La carpeta `Snarf - Archivos` se vuelve el lugar fijo donde vive todo lo que Snarf produce o recibe — cuando exista la migración a documentos legacy `.doc`/`.xls`/`.ppt` o formatos de Apple (`.pages`/`.numbers`, catalogados en ADR 0028 como "other"), este mismo patrón de conversión-al-subir es el primer lugar donde evaluar si Drive los puede convertir también.
- `index_file` y `get_indexed_text` quedan como piezas reusables para el resto de la Fundación — en particular, la migración a VPS (ítem 4) no cambia nada de esto, y un futuro segundo usuario (ítem 5) reusa exactamente el mismo `DocumentPublisher` con su propio `user_id`.
