# ADR 0045 — Capacidad "Proyectos" (Mark I)

**Fecha:** 2026-07-29
**Estado:** Aceptado

## Contexto

"Proyectos" estaba registrado desde ADR 0035 como una Capacidad nueva entera, pospuesta explícitamente a su propio ciclo de diseño — nunca se había construido. El fundador la retomó hoy como el primer frente de un plan de cuatro (Proyectos → Finanzas → Notion → Newsletter de trading), y definió el alcance en dos respuestas directas: un Proyecto es carpeta de Drive + prompt propio + tareas/notas (no solo carpeta+prompt), y esta primera versión no necesita reconciliarse todavía con Notion (eso queda para esa fase).

En la misma ronda, el fundador pidió además: unificar "Snarf - Archivos" y la nueva carpeta de Proyectos bajo una sola carpeta raíz "Snarf" en Drive, separada de sus carpetas manuales; y que Snarf pueda de verdad "gestionar archivos" (ya movía/creaba/borraba, pero no podía renombrar ni compartir). Ambos se resolvieron dentro de este mismo ADR por ser prerrequisito directo de Proyectos (la carpeta raíz) o una extensión mínima y acotada de la Capacidad de Drive ya existente.

Quedó explícitamente fuera de esta ronda, registrado en memoria para las fases correspondientes: los subagentes de marketing de la futura Legión deben basarse en los manuales de funciones reales que el fundador escribió para su equipo en Global Next Trade (Drive); un agente "secretario" que lleve su agenda personal; y que Notion+Drive funcionen como insumos combinados y bidireccionales.

## Decisión

### 1. Carpeta raíz "Snarf" en Drive

Migración real, una sola vez: "Snarf - Archivos" (carpeta ya existente, con archivos reales) se movió para quedar dentro de una nueva carpeta raíz "Snarf", y se renombró a "Archivos" — mismos archivos, mismos ids, solo cambió el padre. `DocumentPublisher.folder_id()` resuelve ahora "Snarf" → "Archivos" (anidado) en vez de la carpeta suelta de antes; para una instalación nueva sin nada creado todavía, el get-or-create anidado la arma bien desde cero.

### 2. `GoogleDrive` suma `rename_file` y `share_file`

`rename_file(file_id, new_name)`: bajo riesgo, no gateado. `share_file(file_id, role, email=None)`: dado un `email`, permiso a esa persona puntual; sin él, `type="anyone"` (link público) — cambia acceso real de terceros, gateado por confirmación en el Orchestrator igual que `drive_delete_file`.

### 3. `snarf/specialists/project_manager.py` — `ProjectManager`

Cada Proyecto es un JSON en `data/projects/{id}.json` (`{name, prompt, drive_folder_id, subfolders, tasks, notes}`), con la misma disciplina defensiva de `dashboard_prefs.py` al leer (nunca confía en lo que hay en disco). `create()` arma una carpeta de Drive dentro de "Snarf/Proyectos" — nombrada `"{name} ({short_id})"`, no `name` a secas, para que dos proyectos con el mismo nombre visible (ej. borrado y recreado) nunca colisionen en la misma carpeta real — y le pide a un modelo barato (mismo criterio que `GmailDigestSpecialist`) 2-4 nombres de subcarpeta apropiados, con fallback a `["Archivos"]` si el LLM no está disponible o falla. `delete()` borra solo el registro local — nunca la carpeta/archivos reales de Drive, a propósito, para no repetir el incidente de datos reales de esta misma sesión (ADR 0042).

### 4. Búsqueda semántica acotada a un Proyecto

`drive_indexer.py`/`vector_store.py` suman un parámetro `where` opcional a `search()`, y `index_file()`/`index_local_text()` ya soportaban (o ahora soportan) `extra_metadata` por chunk. `POST /files/upload` acepta un `project_id` opcional: si viene, sube a la carpeta de ESE proyecto y etiqueta el índice con `{"project_id": ...}` — sin esto, `project_search`/`search_within` devolvería vacío para siempre, ya que nada tagearía los archivos como pertenecientes a un proyecto.

### 5. Wiring del Orchestrator y del cerebro

11 tools nuevas (`project_create`, `project_list`, `project_get`, `project_set_prompt`, `project_add_task`, `project_complete_task`, `project_delete_task`, `project_add_note`, `project_delete_note`, `project_search`, `project_delete`) más `drive_rename_file`/`drive_share_file`. `project_delete` y `drive_share_file` siguen el protocolo de confirmación en dos pasos existente. `snarf/telemetry/brain.py` suma un nodo `specialist_projects` (tier "specialist", mismo nivel que `specialist_gmail`) — las dos tools de Gmail y Proyectos son Especialistas Cognitivos reales, una capa distinta de la Capacidad Drive cruda.

### 6. REST + frontend

`GET/POST /projects`, `GET /projects/{id}`, `PUT .../prompt`, `POST/PATCH/DELETE .../tasks(/{id})`, `POST/DELETE .../notes(/{id})`, `DELETE /projects/{id}?confirmed=true` — mismo criterio que `POST /dashboard/widgets/gmail/digest/refresh`: llaman directo a `ProjectManager`, sin pasar por `_handle_tool` (no generan pulso en el cerebro por ese camino; sí por el conversacional).

En el frontend, la barra lateral (`#sidebar`, ya construida en ADR 0035, reparentada igual en mobile/modo enfoque/hamburguesa-desktop) suma un switcher de dos pestañas (Conversaciones/Proyectos) — comparten el mismo slot flex, nunca montadas ambas a la vez. Un panel de detalle nuevo (mismo patrón overlay que `.settings-panel`/`.brain-panel`) muestra nombre, prompt editable, tareas y notas, y un link real a la carpeta de Drive. Borrar un proyecto entero pide `window.confirm()` real antes de mandar `?confirmed=true` — la API REST no puede replicar el protocolo de vista-previa-en-dos-turnos del camino conversacional.

## Verificado

- 348/348 tests (incluye `tests/test_project_manager.py` nuevo, extensiones a `test_google_drive.py`, `test_drive_indexer.py`, `test_vector_store.py`, `test_orchestrator.py`, `test_brain.py`, `test_data_backup.py`, `test_document_publisher.py`, `test_app.py`).
- Migración de carpeta raíz verificada en vivo contra el Drive real: los mismos 8 archivos de "Archivos", mismos ids, ahora con padre "Snarf".
- Creación real de un proyecto de prueba contra el Drive real: carpeta anidada correctamente en Snarf/Proyectos, subcarpetas sugeridas por el LLM coherentes con el nombre dado, limpiado después (borrado el registro local vía API + la carpeta real de Drive a mano, sin dejar basura).
- Playwright, flujo completo en una copia aislada del repo (con un proyecto sembrado a mano para no depender de credenciales reales de Drive en la verificación de UI): crear, abrir, editar prompt, agregar/tildar/borrar tarea, agregar/borrar nota, borrar el proyecto completo con confirmación real — cero errores de consola en todo el flujo.

## Consecuencias

- `search_within`/`project_search` solo encuentran contenido subido a un proyecto a través de Snarf (con `project_id` explícito) — un archivo que el fundador arrastre a mano a la carpeta de Drive de un proyecto, por fuera de Snarf, no queda taggeado y no aparece en esa búsqueda. Quedó registrado como límite conocido de Mark I, no un bug.
- El botón hamburguesa (restaurado en ADR 0043) es ahora también el único camino de entrada a Proyectos en desktop — si en el futuro se agrega un ícono dedicado, hay que decidir si el hamburguesa se mantiene como respaldo.
- La reconciliación entre las tareas/notas de un Proyecto y la futura integración de Notion queda abierta a propósito — se decide cuando llegue esa fase, con evidencia real de cómo se usó esta primera versión, no antes.
