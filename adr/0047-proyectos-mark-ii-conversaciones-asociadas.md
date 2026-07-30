# ADR 0047 — Proyectos Mark II: conversaciones formalmente asociadas a un proyecto

**Fecha:** 2026-07-29
**Estado:** Aceptado

## Contexto

El fundador pidió una spec detallada para que una conversación pueda pertenecer formalmente a un Proyecto (`project_id` nullable, máximo un proyecto a la vez), con el prompt propio de ese proyecto aplicándose automáticamente en **todos** los turnos de esa conversación mientras dure la asociación — no solo cuando se lo menciona explícitamente. Pidió tools de asignar/desasignar/listar, y una interfaz completa para gestionarlo.

Esto completa y reemplaza el trabajo pausado "Proyectos Mark I.5" (nunca tuvo ADR propio): mismo objetivo de fondo (estadísticas reales, resumen, conversaciones asociadas al proyecto), pero con un modelo de datos más sólido. El enfoque de Mark I.5 — `project_id` viajando como parámetro por mensaje en `/send` — no alcanzaba para lo que pide esta spec: una conversación recién creada sin mensajes todavía no tiene nada que taggear, y reasignar una conversación existente no tenía dónde guardar "cuál es su proyecto actual".

Confirmado con el fundador antes de implementar:
- **Sin reescritura retroactiva de historial**: reasignar A→B solo cambia el comportamiento de los turnos que vengan después; el historial ya generado bajo el prompt de A queda intacto.
- **Migración**: sin script de backfill — ausencia de entrada en el store nuevo equivale a `project_id` null, mismo patrón que `dashboard_prefs.py`/`personality_prefs.py`.
- **Interfaz**: entrar a un proyecto desde la barra lateral escala esa misma barra (muestra solo las conversaciones de ese proyecto, con vuelta a la lista general) y reemplaza — no complementa — el modal chico que existía antes, mostrando un "home" del proyecto dentro del área de chat mientras no haya ninguna conversación cargada.

## Decisión

### 1. Fuente de verdad nueva — `snarf/memory/episodic.py`

`EpisodicMemory` suma `data/conversation_projects.json` (`{conversation_id: {"project_id", "assigned_at"}}`), separado del tag histórico `project_id` por-entrada que ya existía (Mark I.5) — ese tag sigue existiendo tal cual y pasa a ser puramente auditoría (qué proyecto estaba vigente cuando se escribió CADA mensaje), nunca la fuente de verdad de "cuál es el proyecto actual". Métodos nuevos: `assign_conversation()`/`unassign_conversation()` (devuelven `{conversation_id, from_project_id, to_project_id}` para trazabilidad), `get_conversation_project()`. `list_conversations()` deja de filtrar por el tag histórico y pasa a filtrar por este mapeo; además incluye conversaciones recién asignadas sin ningún mensaje todavía (placeholder `"(nueva conversación)"`), y suma `unassigned_only` para la lista general de la barra lateral.

### 2. `Orchestrator` — de parámetro por mensaje a lookup por conversación

`handle()` pierde el parámetro `project_id` (código muerto de Mark I.5, ningún frontend real lo usaba) — se resuelve internamente vía `self._memory.get_conversation_project(conversation_id)`, calculado antes del `if` para estar disponible también en modo eco. `app.py`: `SendRequest` pierde `project_id`; `/send` vuelve a llamar `handle()` solo con `conversation_id`.

### 3. Tools nuevas (no gateadas)

`project_assign_conversation`, `project_unassign_conversation`, `project_list_conversations` — confirmado con el fundador que no requieren el protocolo de confirmación en dos pasos (reversibles al instante, no tocan datos de terceros ni archivos). Mapeadas en `snarf/telemetry/brain.py` a `specialist_projects`.

### 4. REST — `app.py`

`PUT`/`DELETE /conversations/{id}/project`, `GET /projects/{id}/conversations`. `GET /conversations` (lista general) pasa a `list_conversations(unassigned_only=True)` — las conversaciones con proyecto viven en la lista propia de ese proyecto. `GET /projects/{id}` se enriquece con `file_count`, `pending_task_count`, `conversations`, y usa `cached_summary()` (genera el resumen la primera vez que se pide, mismo patrón que `GmailDigestSpecialist`). Nuevo `POST /projects/{id}/summary/refresh`.

### 5. `ProjectManager` — completar lo pausado de Mark I.5

`file_count()`: cuenta real vía `iter_all_files`, **excluyendo subcarpetas** (bug real encontrado con Playwright: las subcarpetas sugeridas por el LLM también son "files" para la API de Drive — sin el filtro, un proyecto recién creado ya mostraba archivos que en realidad eran sus propias subcarpetas vacías). `generate_summary()`/`cached_summary()`: mismo patrón que `GmailDigestSpecialist`, nunca inventa datos fuera de prompt/tareas/notas/archivos reales. `PROJECT_PROMPT_MAX_LENGTH = 4000`, truncado defensivo en `set_prompt()` y en `_normalize()` (disco).

### 6. Frontend — `web/index.html`

Se retira el modal `#projectPanel`/`#projectOverlay` (y su z-index 16/17 de la ronda anterior, ya obsoleto). Nueva vista "home" del proyecto dentro del área de chat (`renderProjectHome`, reusa `.project-field`/`.project-section`/`.project-item-row` ya existentes): estadísticas reales, resumen con botón actualizar, prompt con contador de caracteres en vivo, tareas, notas, y lista de conversaciones del proyecto. La barra lateral drilldownea: clickear un proyecto muestra sus conversaciones en el mismo lugar de la lista, con "← todos los proyectos" para volver — sin cerrar la barra (bug real encontrado y corregido: la primera versión reusaba `startNewConversation()`, que cierra la barra de golpe). "+ nueva conversación de este proyecto" asigna antes del primer mensaje; si el usuario tipea directo sobre el home sin usar ese botón, `sendText()` asigna recién en ese momento (evita conversaciones fantasma solo por mirar un proyecto). Desde la lista general, un botón 📁 por conversación abre un `<select>` real con los proyectos existentes para asignarla.

## Verificado

- 398/398 tests.
- Playwright de punta a punta contra una instancia real aislada (puerto 8001, credenciales de Drive compartidas vía symlink pero `data/` propio y vacío — mismo criterio que ADR 0045): crear proyecto real, ver estadísticas/resumen generados contra Drive/LLM reales, editar prompt con contador, agregar tarea (con `pending_task_count` correcto tras refrescar), crear una conversación nueva del proyecto y mandar un mensaje real, confirmar que aparece en la lista del proyecto y NO en la lista general, volver a la lista de proyectos sin que se cierre la barra, reabrir el proyecto y confirmar que las estadísticas persisten, mover una conversación general a un proyecto vía el selector — cero errores de consola en todo el flujo. Limpiado después: carpetas reales de Drive y registros locales de prueba borrados, nada quedó en producción.
- Dos bugs reales encontrados y corregidos durante esta verificación (no en la revisión de código): `file_count()` contaba las subcarpetas propias como archivos; "← todos los proyectos" cerraba la barra lateral en vez de solo volver a la lista.

## Consecuencias

- El botón 📁 de "mover a proyecto" en la lista general es la versión más simple que satisface la letra de la spec (un selector real, no un `prompt()` de texto) — si en el futuro hace falta reasignar entre proyectos desde DENTRO de la vista de un proyecto (no solo desde la lista general), es la misma pieza a extender.
- `PROJECT_PROMPT_MAX_LENGTH = 4000` es una estimación razonable, no una cifra pedida por el fundador — señalado como ajustable si en el uso real resulta corta o larga.
- El resumen del proyecto se genera automáticamente en el primer `GET /projects/{id}` tras la creación (antes vacío) — esto significa que abrir un proyecto por primera vez siempre dispara una llamada real al LLM; aceptable dado el mismo patrón ya usado por el digest de Gmail.
