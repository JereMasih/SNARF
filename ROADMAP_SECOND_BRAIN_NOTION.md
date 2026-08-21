# Snarf Second Brain (Notion) + Confiabilidad del Orchestrator

> **Por qué este documento vive acá y no solo en un plan de Claude Code:** un plan guardado por
> `ExitPlanMode` queda en `~/.claude/plans/`, fuera del repo — una sesión nueva de Claude Code no tiene
> garantía de poder leerlo (ver `ROADMAP_OBSERVABILIDAD_MULTIUSUARIO_N8N.md` para el precedente real de
> por qué se adoptó esta convención). Este archivo es la copia autoritativa, versionada en git, que
> cualquier sesión futura puede leer siempre — indexado desde `CLAUDE.md` y `MASTER_MAP.md`.

## Estado actual (retomar una sesión nueva desde acá)

**Última actualización:** 2026-08-21.

**Hecho:**
- Fase D1 — Evolución de `MASTER_MAP.md`/`COGNITION.md` (ADR 0179). Documental: describe el Second Brain
  de Notion en el dominio Knowledge, documenta la colisión de nombre "Área" con claridad, activa el slot
  `FOUNDER_MODEL`, agrega la sección "Equipos de agentes" en COGNITION.md, y crea este mismo archivo.
- Fase A1 — Gaps de capability en `snarf/capabilities/notion.py` (ADR 0180). 8 métodos nuevos (mover
  página, crear database, cover/icon x2, archivar/restaurar) + batching real de escritura con reintento
  en `create_page`/`append_to_page`. 8 tools nuevas en el Orchestrator, 3 de alto impacto. De paso,
  corregido un hallazgo real de hermeticidad de tests (`NOTION_API_KEY` sin limpiar en `conftest.py`).
  1549/1549 tests.
- Fase C1 — Decisión de UX del árbol de drilldown (ADR 0181). Documental: progressive disclosure de un
  nivel a la vez, migaja de pan de 2 niveles, carga lazy por nivel, componente único reparentado. Detalle
  completo en la sección "Fase C1" más abajo.
- Fase A2 — Modelo Área/Proyecto/Recursos/Archivo (ADR 0182). `SecondBrainManager` nuevo
  (`snarf/specialists/second_brain.py`), lee Notion en vivo, namespaced por usuario desde el día uno,
  `database_map.json` con `property_map` para relaciones. 7 tools de solo lectura + nodo nuevo del
  cerebro. `Notion.get_page` nuevo. 1569/1569 tests.
- Fase B2 — Namespacing de `PROJECTS_DIR` legado (ADR 0183). Corrección honesta al alcance original:
  `conversation_projects.json` ya estaba namespaced desde ADR 0137, el bug real era solo `PROJECTS_DIR`.
  `ProjectManager` gana `projects_dir`. 1570/1570 tests.
- Fase A3 — Espejo Proyecto Snarf↔Notion (ADR 0184), backend completo: `notion_project_page_id`,
  `second_brain_link_project`, `ProjectManager.create()` crea la fila real en Notion cuando corresponde.
  El link "Ver en Notion" en la UI queda diferido a propósito a Fase C4. 1579/1579 tests.
- Fase A7 — Home de Área: rollup + reporte (ADR 0185). `get_area_home`/`generate_area_report`/
  `cached_area_report`. Ajustes honestos: rollup sin notas/tareas (no modeladas todavía), reporte sin
  indexar en Knowledge todavía (pendiente real). 1587/1587 tests.
- Fase B1 — OAuth de Notion por usuario (ADR 0186). Código completo y testeado; verificación en vivo
  bloqueada por el registro manual del fundador en el panel de developers de Notion (ver "Bloqueos reales
  conocidos" arriba). Sin botón "Conectar Notion" en la UI a propósito — se construye en A4. 1604/1604 tests.
- Fase C2 — Tab "Second Brain" con jerarquía Área→Proyecto (ADR 0187). Tab renombrado con ícono nuevo,
  drilldown de 3 niveles con degradación elegante (sin Second Brain conectado, comportamiento idéntico al
  de siempre). 3 endpoints REST nuevos. Verificado con Playwright real (mobile+desktop, cero errores de
  consola) contra un server de prueba. 1610/1610 tests.
- Fase C3 — Reparentado desktop + pulido (ADR 0188). Reparentado ya heredado sin cambios; skeleton de
  carga real nuevo (`showProjectPanelLoading`). Transiciones CSS diferidas a propósito. Verificado con
  Playwright real. 1610/1610 tests.
- Fase C5 — Home de Área en la UI (ADR 0189). `renderAreaHome` + 2 endpoints REST. Primer camino
  "conectado" ejercitado de punta a punta con Playwright real (route interception). 1614/1614 tests.
- Fase C4 — Home de proyecto enriquecido + Playwright de cierre (ADR 0191). Link/vínculo a Notion,
  Recursos reales. **Track C cerrado (C1-C5)**, todo verificado con Playwright real. 1620/1620 tests.
- Fase A5 — Retrieval proactivo (ADR 0192). Ajuste honesto: no filtra por `project_id` (esa etiqueta no
  existe en el indexado real), busca sobre todo lo indexado de Notion por relevancia semántica. 1625/1625.
- Fase A6 — Gap de `child_database` (ADR 0193). **Track A cerrado.** 1631/1631.
- Fase A4 — Onboarding auto-build + mapeo (ADR 0190). Código completo, sin UI (mismo criterio que B1: sin
  precedente real de pantalla de conexión en este repo) y sin verificar contra la API real de Notion
  (mismo bloqueo manual). **Track A completo de código (A1-A7).** 1637/1637.
- Fase D2 — Supervisores periódicos: financiero y de ánimo (ADR 0197). `FinanceSupervisor`/`FounderMood`
  nuevos, 2 loops periódicos, primer trabajo real de Track D. 1652/1652.
- Fase D3 — Mecanismo de equipo multi-agente (ADR 0198). `TeamSession` nuevo (`snarf/executive/team.py`):
  itera con crítica cruzada real sobre un borrador (reusa `consult_role` de los 7 roles existentes para
  criticar), rol de ruteo nuevo dedicado (`executive_team_writer`) para redactar/revisar, tope real de
  rondas, aprobación interna o "aprobado por agotamiento" declarado explícito. Pregunta abierta #2
  resuelta sin confirmar con el fundador: los 7 roles existentes solo critican, nunca redactan — la
  redacción usa el rol nuevo dedicado, no ninguno de los 7. Nunca ejecuta tools mutantes. Tool
  `executive_team_run`, nodo del cerebro propio, excluida de MCP por diseño del allowlist, sin
  confirmación de Art. VII. 1665/1665.
- Fase D4 — Escritura confiable de documentos largos (ADR 0199). `DocumentWriter` nuevo
  (`snarf/specialists/document_writer.py`): genera y escribe una sección de Notion por llamada, con
  contexto acotado (nunca el documento entero) y verificación real releyendo la página antes de avanzar.
  Decisión clave: si el `append` real ya sucedió pero la verificación falla, nunca se reintenta el append
  (evita duplicar contenido real) — queda `unverified`, declarado honesto. Desviación del plan original:
  no se construyó la generalización "por destino", diferida a un segundo caso de uso real. 1679/1679.
- Fase D5 — Integración capstone (ADR 0200). **Cierra Track D (D1-D5) y el plan completo de 22 fases.**
  Sin componentes nuevos grandes, según diseño: guía nueva en el system prompt (`SYSTEM_PREFIX`) para que
  `executive_team_run` planee un documento como un PLAN de secciones (no redactado entero, evita
  reintroducir el límite de tokens) y sume supervisores como contexto; test de integración real
  (`tests/test_document_capstone_integration.py`) que confirma que el artefacto de D3 alimenta
  directamente D4 de punta a punta. Gap real encontrado: `TeamSession` devuelve texto libre,
  `document_write_start` espera secciones estructuradas — decisión explícita de NO construir un parser de
  código nuevo, el propio Orchestrator (LLM) hace ese puente, mismo criterio que ya usa para encadenar
  cualquier otro par de tools. 1681/1681.

**Plan completo (22 fases) cerrado de código.** Queda pendiente Track E (widgets Jarvis del HUD,
ADR 0194-0196), bloqueado desde su primera tarea real (E1 necesita inspeccionar el Notion real del
fundador). El bloqueo de fondo que atraviesa TODO el plan sigue siendo el mismo desde B1: nada de esto se
verificó en vivo contra un Notion real — falta el registro manual del fundador de la integración pública
de Snarf en el panel de developers de Notion.

**Bloqueos reales conocidos:**
- Pregunta abierta #1 (sistema de billing de $10, no hay evidencia de que exista) sigue sin respuesta del
  fundador — no bloquea el resto del código, sí bloquea B1 en su encuadre de negocio.
- Fase B1 (OAuth de Notion) tiene el código completo y testeado, pero requiere que el fundador registre la
  integración de Snarf como pública en el panel de developers de Notion (`NOTION_OAUTH_CLIENT_ID`/
  `NOTION_OAUTH_CLIENT_SECRET` reales) antes de poder verificarse en vivo — no automatizable desde código.
  Ver ADR 0186.

**Decisiones ad-hoc tomadas durante la ejecución que no estaban en el diseño original:** ninguna todavía.

**Numeración de ADR asignada (verificar `ls adr/ | tail -5` al arrancar cada fase — si otra sesión sumó ADRs
intermedios por trabajo no relacionado, correr la numeración de acá, nunca pisar un número ya usado):**

| Fase | ADR |
|------|-----|
| D1 | 0179 (hecho) |
| A1 | 0180 |
| C1 | 0181 |
| A2 | 0182 |
| B2 | 0183 |
| A3 | 0184 |
| A7 | 0185 |
| B1 | 0186 |
| C2 | 0187 |
| C3 | 0188 |
| C5 | 0189 |
| A4 | 0190 |
| C4 | 0191 |
| A5 | 0192 |
| A6 | 0193 |
| E1 | 0194 |
| E2 | 0195 |
| E3 | 0196 |
| D2 | 0197 |
| D3 | 0198 |
| D4 | 0199 |
| D5 | 0200 |

## Protocolo de cierre de sesión (seguir siempre antes de terminar)

Toda sesión que trabaje en este plan, antes de cerrar, debe:
1. Marcar qué fase(s) quedaron completas en la sección "Estado actual" arriba, con el ADR real y el
   conteo de tests real (ej. "1560/1560").
2. Si una fase quedó a medias, describir el estado exacto — qué archivo, qué falta, qué error si lo hay —
   nunca dejar "en progreso" sin ese detalle recuperable.
3. Actualizar "Siguiente fase recomendada".
4. Si se tomó una decisión de diseño no prevista en el plan original, registrarla en "Decisiones ad-hoc"
   con el motivo — mismo criterio de honestidad que ya usa `ROADMAP_OBSERVABILIDAD_MULTIUSUARIO_N8N.md`
   con sus incidentes reales.
5. Si algo de este plan quedó invalidado por lo aprendido durante la fase (ej. una API de Notion se
   comporta distinto a lo asumido acá), corregir esa sección del plan en el momento, no dejarlo para
   después.

## Contexto

El fundador usa Notion como su lugar único de notas, documentos y recursos de referencia por proyecto,
organizado con databases propias al estilo PARA (Áreas/Proyectos/Recursos/Archivo). Snarf ya puede leer y
editar partes de ese Notion (bloques, celdas de tabla, properties) y tiene indexado semántico real
funcionando (ADR 0173), pero:

- No puede mover páginas entre databases, crear databases nuevas, cambiar cover/icon, ni archivar — el
  CRUD está incompleto.
- El indexado es on-demand, nunca proactivo: Snarf solo consulta Notion si se le pide explícitamente.
- Los "Proyectos" de Snarf y los "Proyectos" de Notion son dos mundos sin ningún vínculo.
- No existe ninguna jerarquía de Área en la UI de Snarf — Proyectos es una pestaña plana.
- Notion es una integración global (una sola cuenta), no por usuario — pero el fundador quiere ofrecer
  "conectá tu Notion" como parte de un plan pago, lo cual exige multi-usuario real.

Separado de esto pero en el mismo plan (decisión explícita del fundador, ver ADR 0179): el fundador quiere
usar este trabajo como terreno de prueba para resolver un problema más profundo de confiabilidad del
Orchestrator — supervisores periódicos, un equipo multi-agente que itere/apruebe internamente, y escritura
de documentos largos sin cortes por límites de tokens/RAM/fallas de API.

Tres decisiones de alcance ya las tomó el fundador y no se reabren (ver ADR 0179 para el detalle completo):
1. Un solo plan, ambos frentes van juntos.
2. "Área" se reusa para el nivel superior de la jerarquía de Notion, colisión aceptada y documentada.
3. Multi-usuario desde el diseño, no como migración posterior.

## Convenciones transversales (aplican a las 22 fases)

- Un ADR real por decisión (`adr/01NN-slug-en-español.md`), entrada correlativa en `CHANGELOG.md` con
  conteo de tests real.
- `.venv/bin/python -m pytest -q` completo antes de cerrar cualquier fase. Nunca reduce cobertura.
- Playwright real (login, la interacción nueva, cero errores de consola) para toda fase que toque
  `web/index.html` — no alcanza con que compile.
- Ninguna fase de Track D que introduzca un concepto nuevo se escribe en código antes de que su lugar
  exista en `MASTER_MAP.md`/`COGNITION.md` (Regla de crecimiento del propio mapa) — por eso Track D
  empieza con D1, ya hecha.
- `snarf/capabilities/`, `snarf/specialists/`, `snarf/knowledge/` nunca importan `snarf.core`/
  `snarf.runtime`/`app.py` (ya garantizado por `tests/test_architecture_boundaries.py`).
- Cada Capacidad/Especialista/tool nueva evalúa en el mismo cambio si merece nodo propio en el cerebro
  (`snarf/telemetry/brain.py`, regla de ADR 0054).
- Toda tool nueva mutante e irreversible-en-la-práctica se evalúa contra `POLICY_HIGH_IMPACT_ACTIONS.md`
  y, si corresponde, entra a `HIGH_IMPACT_TOOLS` con protocolo `confirmed`.

---

## TRACK D (parte 1) — Fase conceptual previa

### [x] Fase D1 — Evolución de MASTER_MAP.md / COGNITION.md (ADR 0179) — HECHA 2026-08-20

Documental, sin código. `MASTER_MAP.md` (dominio Knowledge: Second Brain de Notion + colisión de "Área"
documentada; dominio Capabilities: nota de escritura confiable futura; dominio Roadmaps: este archivo
indexado). `COGNITION.md` (slot `FOUNDER_MODEL` activado, sección "Equipos de agentes" nueva). Este archivo
creado. Ver ADR 0179 para el detalle completo.

---

## TRACK A — Notion Second Brain

### [x] Fase A1 — Gaps de capability en `snarf/capabilities/notion.py` (ADR 0180) — HECHA 2026-08-20

Agregar a `class Notion(Capability)`:
1. `move_page(page_id, new_parent_database_id)` — `PATCH /v1/pages/{id}` con `parent: {database_id}`.
   Notion descarta silenciosamente properties que no matchean en la database destino — documentar esto
   explícito en el ADR.
2. `create_database(parent_page_id, title, properties)` — `POST /v1/databases`, no existe hoy. Necesario
   para A4.
3. `update_page_cover`/`update_page_icon` y sus equivalentes de database — `PATCH` con `cover`/`icon`.
4. `archive_page`/`restore_page` — `PATCH` con `archived: true/false`.
5. Batching real de escritura (prerequisito de D4): `create_page`/`append_to_page` en tandas de ≤100
   `children` + reintento con backoff (reusar criterio de retry de `GoogleDrive`, ADR 0041).

Alto impacto: `move_page`, `create_database`, `archive_page` → `HIGH_IMPACT_TOOLS` con `confirmed`.
`update_page_cover`/`icon`/`restore_page` reversibles, sin gate.

Archivos: `snarf/capabilities/notion.py`, `snarf/core/orchestrator.py`, `snarf/telemetry/brain.py`/
`verbs.py`/`detail.py`, `web/index.html` (espejo JS de verbos si aplica).

Tests: extender `tests/test_notion.py`, tests de protocolo `confirmed` para las 3 tools de alto impacto.

### [x] Fase A2 — Modelo Área/Proyecto/Recursos/Archivo en el backend (ADR 0182) — HECHA 2026-08-20

Nueva clase `SecondBrainManager` en `snarf/specialists/second_brain.py`: `list_areas()`, `get_area()`,
`list_projects(area_id=None)`, `list_resources(project_id)`, `list_archive(project_id)`, leído en vivo de
Notion. Mapeo por usuario en `data/second_brain/<user_id>/database_map.json` — no asumir esquema fijo.
Namespacing desde el día uno (contraste explícito con el bug real de `PROJECTS_DIR` global, ver B2).

Archivos: `snarf/specialists/second_brain.py` (nuevo), `snarf/core/orchestrator.py`, `snarf/telemetry/brain.py`.

Tests: `tests/test_second_brain.py` nuevo.

### [x] Fase B2 — Namespacing de `PROJECTS_DIR` legado (ADR 0183) — HECHA 2026-08-20

**Corrección al alcance original**: `conversation_projects.json` YA estaba namespaced desde ADR 0137 — la
exploración que armó este roadmap se equivocó en ese punto. El único bug real era `PROJECTS_DIR`.
`ProjectManager` gana `projects_dir` — `DEFAULT_USER_ID` sigue en `data/projects/`, otros usuarios a
`data/users/<user_id>/projects/`. Ver ADR 0183 para el detalle completo (incluye el fix de 3 tests que
monkeypencheaban la constante de módulo vieja, ya sin efecto real tras este cambio).

Archivos: `snarf/specialists/project_manager.py`, `snarf/core/orchestrator.py`, `tests/test_project_manager.py`, `tests/test_app.py`.

### [x] Fase A3 — Espejo Proyecto Snarf ↔ Proyecto Notion (ADR 0184) — HECHA 2026-08-20 (backend)

Campo `notion_project_page_id` en Proyecto de Snarf. `second_brain_link_project()` para vincular uno
existente (valida vía `SecondBrainManager.get_project`); `ProjectManager.create()` extendido con
`SecondBrainManager.create_project_row()` para crear la fila real en Notion si hay Second Brain conectado
(resuelve la property de título real, nunca asumida). Las Áreas NO se importan como entidad propia con
JSON — Snarf las refleja en vivo, Notion es la única fuente de verdad.

**Diferido a propósito a Fase C4**: el link "Ver en Notion" en `renderProjectHome` (`web/index.html`) — el
backend ya está completo y testeado, la superficie visual se agrega junto con la pasada de Playwright de
cierre de Track C, para no abrir un navegador real dos veces por el mismo tipo de cambio chico.

Archivos: `snarf/specialists/project_manager.py`, `snarf/specialists/second_brain.py`,
`snarf/core/orchestrator.py`.

Tests: `tests/test_project_manager.py`, `tests/test_second_brain.py`. 1579/1579.

### [x] Fase A7 — Home de Área: rollup + análisis/reporte (ADR 0185) — HECHA 2026-08-20

`get_area_home(area_id)` (proyectos + agregado de Recursos/Archivo de todos sus proyectos, con flags
`resources_mapped`/`archive_mapped` para distinguir "cero real" de "no mapeado todavía") y
`generate_area_report(area_id)`/`cached_area_report(area_id)` (análisis LLM cacheado, mismo criterio que
`ProjectManager.generate_summary()` — nunca inventa datos, Principio VI). Nuevo rol de ruteo
`second_brain_report`. Split de nodo del cerebro (`specialist_second_brain_reports`, techo de 8 tools por
nodo ya alcanzado).

**Ajustes honestos al alcance original:**
- El rollup NO cubre "notas/tareas" — esas no tienen database mapeada en el modelo de A2 (solo
  áreas/proyectos/recursos/archivo); inventar el mapeo hubiera violado el Principio VI. Cubre
  Proyectos+Recursos+Archivo, que sí están modelados.
- El reporte NO se indexa todavía en Knowledge (el plan original lo preveía) — decidir bien cómo un ítem
  "generado por Snarf" encaja en un pipeline pensado para contenido real de Notion merece su propia
  decisión, no algo resuelto de apuro acá. Pendiente real.

Archivos: `snarf/specialists/second_brain.py`, `snarf/core/orchestrator.py`, `snarf/telemetry/brain.py`/
`verbs.py`/`detail.py`, `snarf/runtime/llm_routing.py`.

Tests: `tests/test_second_brain.py`. 1587/1587.

### [x] Fase B1 — OAuth de Notion por usuario (ADR 0186) — HECHA 2026-08-20 (código; verificación en vivo pendiente)

Espejar ADR 0137 (Google). `snarf/capabilities/notion_auth.py` (nuevo), intercambio directo (sin SDK,
Basic Auth). `Notion` gana `notion_auth` opcional — prioriza el token OAuth real, cae de vuelta a
`NOTION_API_KEY` global (`DEFAULT_USER_ID` sin cambios de comportamiento). Endpoints
`GET /auth/notion/start`/`GET /auth/notion/callback`.

**Bloqueo real, no resuelto acá**: requiere que el fundador registre la integración de Snarf como pública
en el panel de developers de Notion (`NOTION_OAUTH_CLIENT_ID`/`NOTION_OAUTH_CLIENT_SECRET` reales +
redirect URI dado de alta) — paso manual, no automatizable. El código está completo y testeado con mocks,
pero no ejercitado en vivo todavía.

**Ajuste al alcance original**: sin botón "Conectar Notion" en la UI — investigado antes de construirlo,
el equivalente de Google (`GET /google/connect`) tampoco tiene ninguno en `web/index.html` hoy. Se
construye en Fase A4 (onboarding), su lugar natural.

Archivos: `snarf/capabilities/notion_auth.py` (nuevo), `snarf/capabilities/notion.py`,
`snarf/core/orchestrator.py`, `app.py`, `.env.example`, `tests/conftest.py` (hermeticidad de los 2 env
vars nuevos).

Tests: `tests/test_notion_auth.py` (nuevo), `tests/test_notion.py`, `tests/test_app.py`. 1604/1604.

### [x] Fase A4 — Onboarding y auto-construcción de databases (ADR 0190) — HECHA 2026-08-20 (código; sin UI, sin verificación en vivo)

`auto_build_workspace`/`suggest_mapping` nuevos. Ajuste al alcance original: mapeo por keyword real, no
similaridad semántica vía LLM. 3 tools nuevas, la de auto-build de alto impacto. Guía en el prompt: enseñar
PARA antes de construir/mapear.

**Sin UI todavía** (mismo criterio que B1: ni el flujo de Google tiene pantalla dedicada hoy) y **sin
verificar contra la API real de Notion** (mismo bloqueo manual que B1) — el shape exacto de `relation` en
`create_database` queda sin confirmar contra un workspace real.

**Track A completo de código** (A1-A7).

Archivos: `snarf/specialists/second_brain.py`, `snarf/core/orchestrator.py`. 1637/1637.

Tests: `tests/test_second_brain.py`. Playwright: flujo completo con Notion mockeado.

### [x] Fase A5 — Retrieval proactivo (ADR 0192) — HECHA 2026-08-20

`Orchestrator._proactive_notion_context()`: en una conversación de Proyecto vinculado con contenido real
indexado, suma automáticamente al system prompt los fragmentos más relevantes. Cacheado 120s por consulta.

**Ajuste honesto al alcance original**: NO filtra por `project_id` — los ítems indexados de Notion no
llevan esa etiqueta (solo `location`/`notion_url`, ver ADR 0173), filtrar por una key inexistente hubiera
devuelto siempre vacío en silencio. Busca sobre todo lo indexado de Notion, acotado por relevancia
semántica real — acotar por Proyecto puntual requeriría etiquetar en el momento de indexar, trabajo
pendiente real no resuelto acá.

Archivos: `snarf/core/orchestrator.py`. Tests: `tests/test_orchestrator.py`, 5 nuevos. 1625/1625.

### [x] Fase A6 — Gap de `child_database` en indexado (ADR 0193) — HECHA 2026-08-20

`Notion.find_child_databases()` nuevo + `NotionSource.iter_items()` extendido, sin duplicar si la misma
database aparece por los dos caminos. **Track A cerrado** (A1/A2/A3/A5/A6/A7 — A4 pendiente).

Archivos: `snarf/knowledge/notion_source.py`, `snarf/capabilities/notion.py`. 1631/1631.

Tests: `tests/test_notion_source.py`.

---

## TRACK C — UI Second Brain

### [x] Fase C1 — Decisión de UX del árbol de drilldown (ADR 0181) — HECHA 2026-08-20

**Decisión de UX: progressive disclosure de un solo nivel expandido a la vez, in-place, nunca un árbol
multi-expandido con indentación.**

Patrón elegido, con su justificación:

1. **Un nivel visible a la vez, reemplazando la lista anterior (no anidando).** Precedente real ya en el
   repo: `enterProject(id)` (`web/index.html:3956`) no dibuja los proyectos indentados debajo de la lista
   de conversaciones — reemplaza la lista completa por el contenido del nivel siguiente. Es la práctica
   correcta acá: en mobile (viewport angosto) un árbol Área→Proyecto→Conversaciones con indentación real
   degrada mal a partir del segundo nivel (texto truncado, difícil de tocar); reemplazar la lista visible
   evita ese problema sin inventar un componente nuevo.
   - Second Brain agrega un nivel más que Proyectos (Área, por encima), pero el mismo patrón escala: nivel
     1 = lista de Áreas → tocar una entra a nivel 2 = lista de Proyectos de esa Área (reusa
     `renderProjectListInto` tal cual, ver C2) → tocar un Proyecto entra a nivel 3 = conversaciones + home
     (reusa `enterProject`/`renderProjectHome` sin cambios).
2. **Migaja de pan siempre visible.** Ya existe un precedente parcial: `renderProjectPanelHeaderInto` (ver
   `web/index.html`) ya muestra un botón "← todos" cuando se está dentro de un Proyecto. Second Brain
   extiende esto a 2 niveles de "atrás" en vez de 1 — el header muestra "Áreas" en nivel 1, "‹ Áreas /
   [Nombre del Área]" en nivel 2, "‹ [Nombre del Área] / [Nombre del Proyecto]" en nivel 3 — cada segmento
   de la migaja es clicable y vuelve directo a ese nivel (no solo "un paso atrás").
3. **Carga lazy por nivel, nunca la jerarquía completa de una sola vez.** Áreas se traen al abrir el tab
   (`second_brain_list_areas`, liviano). Los Proyectos de un Área recién se piden al expandirla
   (`second_brain_list_projects(area_id)`). Conversaciones + home de un Proyecto recién al entrar (mismo
   mecanismo que ya usa `enterProject` hoy). Mismo criterio de costo que ya rige el resto del repo (ADR
   0067: nunca traer de más sin necesidad real) — evita pedir todo el Second Brain del fundador (que puede
   tener decenas de Proyectos con cientos de recursos) en un solo request al abrir el tab.
4. **Mismo componente para mobile y desktop, reparentado — nunca dos implementaciones paralelas.** Sigue
   el patrón ya establecido (`appendChild` sobre el nodo vivo, ADR 0035/0048/0178) — la lista de Áreas/
   Proyectos vive en un único DOM que se reparentea entre `#sidebar` (mobile/tab) y `#dashHistoryParked`
   (desktop), nunca se reconstruye por HTML aparte para cada superficie.

**Por qué NO un árbol multi-expandido (ej. accordion con varias ramas abiertas a la vez):** con
profundidad real de hasta 3 niveles y contenido potencialmente numeroso en cada uno (varios Proyectos por
Área, varias Conversaciones por Proyecto), un árbol que permite tener múltiples ramas abiertas
simultáneamente crece verticalmente sin límite y pierde la ventaja de "una sola pantalla, una sola
decisión" que ya funciona bien para Proyectos hoy. La profundidad de este dominio (≤3 niveles fijos, no
arbitraria) hace que el drilldown secuencial sea estrictamente más simple de implementar y de usar que un
árbol genérico, sin perder ninguna capacidad real que el fundador haya pedido.

Ver Fase C2 para la implementación concreta de este patrón.

### [x] Fase C2 — Tab "Second Brain" con jerarquía Área→Proyecto (ADR 0187) — HECHA 2026-08-20

Tab renombrado (no reemplazado — degradación elegante: sin Second Brain conectado, muestra exactamente la
lista plana de Proyectos de siempre). Ícono "2 + cerebro" (SVG monolínea). `renderAreaListInto`/
`renderAreaProjectsInto`/`enterArea`/`exitArea` nuevos, `enterProject(id)` sin cambios pero ya no limpia
`currentAreaId` (breadcrumb real de 3 niveles). 3 endpoints REST nuevos
(`/second-brain/status`/`areas`/`areas/{id}/projects`), `ProjectManager.find_by_notion_page_id()`.

Archivos: `web/index.html`, `app.py`, `snarf/specialists/project_manager.py`,
`snarf/core/orchestrator.py`.

Tests: `tests/test_project_manager.py`, `tests/test_app.py`. **Playwright real verificado** (mobile +
desktop, server de prueba puerto 8000, cero errores de consola) — camino "no conectado" (el real hoy).
Camino "conectado" (Áreas reales) sin verificar en vivo, solo con tests mockeados. 1610/1610.

### [x] Fase C3 — Reparentado desktop + pulido (ADR 0188) — HECHA 2026-08-20

Reparentado a desktop confirmado sin cambios de código nuevos (hereda el mecanismo genérico ya real de
`reparentHistoryIntoDashboard()`, verificado durante C2). `showProjectPanelLoading()` nuevo: skeleton
"cargando…" al cambiar de nivel sin nada cacheado todavía. Estados vacíos ya resueltos en C2. Transiciones
CSS de expand/collapse diferidas a propósito (pulido visual sin verificación funcional real posible).

Archivos: `web/index.html`. Playwright real: skeleton visible al entrar sin cache, navegación de ida y
vuelta sin errores de consola. 1610/1610 (sin cambios de backend).

### [x] Fase C5 — Home de Área en la UI (ADR 0189) — HECHA 2026-08-20

`renderAreaHome(home)` análoga a `renderProjectHome`. 2 endpoints REST nuevos
(`GET /second-brain/areas/{id}`, `POST .../report/refresh`). `enterArea()` carga lista+home juntos
(patrón dual de `enterProject`), `exitArea()` gana `clearChat()`.

Archivos: `web/index.html`, `app.py`. **Primer camino "conectado" ejercitado de punta a punta con
Playwright real** (route interception con datos de prueba, ya que el Second Brain real no está conectado
todavía) — navegación completa Áreas→Proyecto→home, cero errores de consola, captura guardada. 1614/1614.

### [x] Fase C4 — Home de proyecto enriquecido + Playwright de cierre (ADR 0191) — HECHA 2026-08-20

`renderProjectHome` extendido: link "ver en Notion ↗" o botón "vincular a Notion", sección de Recursos de
Notion real. Notas ya eran reales desde ADR 0047. Badge de conocimiento indexado diferido (requiere un
método de conteo filtrado en el vector store que no existe todavía).

**Track C cerrado** — 5 fases (C1-C5), todas verificadas con Playwright real en mobile y desktop, sobre
proyectos reales del fundador, confirmado que ningún dato real quedó mutado durante la verificación
(llamadas sensibles interceptadas client-side). Cero errores de consola en todas las pasadas.

Archivos: `web/index.html`, `app.py`. 1620/1620.

---

## TRACK E — Widgets "Jarvis" para el HUD

**Nota honesta:** el catálogo de estas 3 fases se diseñó sin acceso real a la API de Notion desde la
sesión de planificación (esa capacidad vive en el runtime de Snarf, no en Claude Code) — es un punto de
partida razonable, no una inspección real del Notion del fundador. **La primera tarea real de E1 es
inspeccionar contenido real con las tools ya construidas en A1/A2 antes de fijar el schema.** Corrección
real encontrada durante la planificación: no existe hoy ningún reproductor de video embebido en
`web/index.html` — solo audio (`sharedAudio`) para la voz de Snarf. El widget de video se construye nuevo.

### [ ] Fase E1 — Backend: datos agregados para widgets de contenido (ADR 0194)

Endpoints `/dashboard/widgets/second_brain/*` (mismo patrón que `/dashboard/widgets/gmail` etc.):
area_report, project_report, tasks_matrix (urgente/importante, **solo si hay properties reales de
prioridad/fecha en Notion** — nunca inventar clasificación sin base real), resources.

Archivos: `app.py`, `snarf/specialists/second_brain.py`.

### [ ] Fase E2 — Frontend: renderer de widgets por tipo de contenido (ADR 0195)

Widget de video (nuevo), texto largo con scroll, matriz de tareas, galería de recursos, reporte de
Área/Proyecto — reusando la grilla de 12 columnas y `wrapExistingAsBlock`/`appendChild` (ADR 0035).

Archivos: `web/index.html`. Playwright: cada tipo de widget.

### [ ] Fase E3 — Widgets de gráficos/analítica (ADR 0196)

Gráficos SVG livianos hechos a mano siguiendo la skill `dataviz` — sin librería de charting ni servicio
externo nuevo (mismo criterio de Skills vs. MCP de `CLAUDE.md`).

Archivos: `web/index.html`.

---

## TRACK D (parte 2) — Confiabilidad del Orchestrator

### [x] Fase D2 — Supervisores periódicos: financiero y de ánimo (ADR 0197) — HECHA 2026-08-20

`FinanceSupervisor`/`FounderMood` nuevos, mismo patrón que `_periodic_bug_triage_loop`. Gap real
encontrado: no había ningún concepto de "la" Sheet de finanzas del fundador guardado — se agregó
`set_sheet_file_id()` explícito. Cadencias default propias (diaria/6h), sin confirmar con el fundador
(pregunta abierta #8 sigue abierta). **Primer trabajo real de Track D.**

Archivos: `snarf/specialists/finance_supervisor.py` (nuevo), `snarf/specialists/founder_mood.py` (nuevo),
`snarf/core/orchestrator.py`, `app.py`, `snarf/runtime/llm_routing.py`. 1652/1652 (flake preexistente sin
relación, descartado).

### [x] Fase D3 — Mecanismo de "equipo" multi-agente (ADR 0198) — HECHA 2026-08-21

`TeamSession` en `snarf/executive/team.py`, reusa `consult_role` para la crítica de cada uno de los 7 roles
existentes. Pregunta abierta #2 resuelta sin confirmar con el fundador: los 7 roles solo critican, la
redacción/revisión del borrador usa un rol de ruteo nuevo dedicado (`executive_team_writer`), nunca uno de
los 7 — evita forzar un rol de asesoría a redactar. Loop de iteración con tope real (`max_rounds`, default
3), aprobación interna apenas no hay objeciones `BLOQUEANTE`, o "aprobado por agotamiento" declarado
explícito si se acaban las rondas sin consenso real. Nunca ejecuta tools mutantes — el borrador vuelve como
texto a quien llamó. Nodo del cerebro propio (`specialist_executive_team`), excluida de
`MCP_EXPOSED_TOOLS` por diseño del propio allowlist, sin confirmación de Art. VII (ver
`POLICY_HIGH_IMPACT_ACTIONS.md`).

Archivos: `snarf/executive/team.py` (nuevo), `snarf/core/orchestrator.py`, `snarf/runtime/llm_routing.py`,
`snarf/telemetry/brain.py`/`verbs.py`/`detail.py`, `POLICY_HIGH_IMPACT_ACTIONS.md`. 1665/1665 tests (13
nuevos en `tests/test_executive_team.py`).

### [x] Fase D4 — Escritura confiable de documentos largos (ADR 0199) — HECHA 2026-08-21

`DocumentWriter` en `snarf/specialists/document_writer.py` (no `snarf/runtime/`, como sugería el plan
original — compone la Capacidad Notion sin importar `snarf.core`/`snarf.runtime`, mismo boundary que
`SecondBrainManager`/`FinanceSupervisor`). Cada llamada avanza como máximo una sección: genera con
contexto acotado (nunca el documento completo acumulado), escribe con `notion_append_to_page` (ya
troceado/reintentado, ADR 0180), y verifica releyendo la página antes de avanzar. Estado persistido en
`data/document_writes/<user_id>/<write_id>.json`, reanudable desde una instancia/proceso totalmente
nuevo. Si el append real ya sucedió pero la verificación falla, nunca se reintenta el append (evita
duplicar contenido real) — queda `unverified`, declarado honesto en vez de "listo". Desviación del plan
original: no se construyó la generalización "por destino" pedida, diferida a un segundo caso de uso real.

Archivos: `snarf/specialists/document_writer.py` (nuevo), `snarf/core/orchestrator.py`,
`snarf/runtime/llm_routing.py`, `snarf/telemetry/brain.py`/`verbs.py`/`detail.py`,
`POLICY_HIGH_IMPACT_ACTIONS.md`. 1679/1679 tests (14 nuevos en `tests/test_document_writer.py`).

### [x] Fase D5 — Integración capstone (ADR 0200) — HECHA 2026-08-21

**Cierra Track D (D1-D5) y el plan completo de 22 fases.** Sin componentes nuevos grandes, como preveía el
diseño original: D3 y D4 ya componen a través del propio loop de herramientas del Orchestrator. Guía nueva
en `SYSTEM_PREFIX` (`executive_team_run` planea un documento como PLAN de secciones, nunca redactado
entero; suma supervisores de D2 como contexto real cuando aplica; `document_write_start/continue/status`
explica el flujo completo, nunca "listo" con `sections_stuck` no vacío). Gap real encontrado al integrar:
`TeamSession.run()` devuelve texto libre, no una lista estructurada — decisión explícita de NO construir
un parser de código nuevo (frágil, sin necesidad real); el propio Orchestrator (la LLM) arma el puente,
mismo criterio que ya usa entre cualquier otro par de tools encadenadas. Test de integración real
(`tests/test_document_capstone_integration.py`) confirma que el plan de secciones de un equipo (fakeado)
alimenta directo una escritura de documento verificada de punta a punta, incluyendo el caso
`approved_by_exhaustion=true` fluyendo sin ocultarse.

**Sin verificación en vivo** — ni contra el Notion real del fundador (Second Brain no conectado, bloqueo
manual de B1 sigue en pie) ni con una corrida real end-to-end (Claude Code no tiene acceso directo a las
tools de producción de Snarf desde este entorno). Queda como primer uso real recomendado una vez resuelto
el bloqueo de OAuth.

Archivos: `snarf/core/orchestrator.py` (`SYSTEM_PREFIX`), `tests/test_document_capstone_integration.py`
(nuevo). 1681/1681 tests (2 nuevos).

---

## Orden de ejecución recomendado

| # | Fase | ADR | Depende de | Por qué acá |
|---|------|-----|------------|-------------|
| 1 | D1 — Evolución del mapa | 0179 (hecho) | — | Documental, desbloquea todo lo conceptual de Track D. |
| 2 | A1 — Gaps de capability Notion | 0180 | — | Backend puro, desbloquea A2-A7 y D4/D5. |
| 3 | C1 — Decisión UX drilldown | 0181 | — | Paralelizable con A1. |
| 4 | A2 — Modelo Área/Proyecto | 0182 | A1 | Necesita `create_database`/mapeo de A1. |
| 5 | B2 — Namespacing legado | 0183 | A2 | Resolver deuda de `PROJECTS_DIR` antes de A3. |
| 6 | A3 — Espejo Snarf↔Notion | 0184 | A2, B2 | Necesita modelo y namespacing resueltos. |
| 7 | A7 — Home de Área (backend) | 0185 | A2, A3 | Rollup necesita modelo y espejo de Proyecto. |
| 8 | B1 — OAuth Notion por usuario | 0186 | A1-A3, A7 | Aísla riesgo OAuth, core ya verificado. |
| 9 | C2 — Tab Second Brain | 0187 | A2, A3, C1 | UI necesita datos reales. |
| 10 | C3 — Reparentado + pulido | 0188 | C2 | Continuación directa. |
| 11 | C5 — Home de Área (UI) | 0189 | A7, C2 | Necesita rollup y tab construidos. |
| 12 | A4 — Onboarding + enseñar PARA | 0190 | A1, B1 | Onboarding es post-OAuth. |
| 13 | C4 — Home de proyecto + Playwright cierre | 0191 | A3, A4, C3, C5 | Cierre de Track C. |
| 14 | A5 — Retrieval proactivo | 0192 | A2, A3 | Requiere Proyecto activo + índice. |
| 15 | A6 — Gap child_database | 0193 | A1 | Baja prioridad, independiente. |
| 16 | E1 — Backend widgets Jarvis | 0194 | A7, A3 | Datos agregados necesitan A7/A3. |
| 17 | E2 — Frontend widgets HUD | 0195 | E1 | Necesita endpoints de E1. |
| 18 | E3 — Widgets de gráficos | 0196 | E1 | Mismos datos agregados. |
| 19 | D2 — Supervisores periódicos | 0197 | D1 | Solo depende del mapa, paralelizable. |
| 20 | D3 — Mecanismo de equipo | 0198 | D1, D2 | Mayor riesgo, después de Track A/C/E sólidos. |
| 21 | D4 — Escritura confiable | 0199 | A1 | Necesita Notion (destino real) de A1. |
| 22 | D5 — Integración capstone | 0200 | D2, D3, D4, A3 | Cierre, escenario real que motivó el pedido. |

D1, A1 y C1 no tienen dependencias entre sí. D2 tampoco depende de Track A/C/E salvo D1.

## Verificación end-to-end

- Backend: `.venv/bin/python -m pytest -q` completo después de cada fase, conteo creciente en CHANGELOG.md.
- Frontend: Playwright real en C2/C3/C4/C5, E2, y B1 (flujo de conexión).
- D5 exige, idealmente, una corrida real contra el Notion del fundador con un documento de prueba chico.

## Preguntas abiertas para el fundador (no resueltas en este plan)

1. ¿Existe ya o hay que construir desde cero el sistema de planes/billing de $10?
2. El "equipo de marketing" de D3: ¿roles existentes del board de 7 o roles nuevos más operativos?
3. ¿Plantilla de databases de onboarding (A4) fija o negociada por conversación?
4. Mapeo de databases existentes con nombres distintos (A4): ¿confirmación por similaridad alcanza, o
   mapeo campo por campo?
5. Al mover una página entre databases (A1), Notion descarta properties que no matchean: ¿advertir con
   detalle antes de `confirmed`, o alcanza el gate genérico?
6. Tab "Second Brain" (C2): ¿reemplaza del todo "Proyectos", o convive un fallback para proyectos sin
   Notion?
7. Aprobación automática del equipo (D3): ¿el fundador quiere ver siempre el resultado final antes de
   usarlo para algo real, o puede correr sin intervención hasta el paso de escritura?
8. Cadencia de los supervisores de D2: ¿diaria para financiero? ¿fuente adicional para ánimo?
9. Matriz urgente/importante (E1): ¿el fundador ya tiene properties de prioridad/fecha reales en Notion?
10. Widgets de Track E: ¿opt-in manual la primera vez, o entran directo a la curación automática?
11. Reproductor de video (E2): ¿alcanza con YouTube embebido, o hay otras plataformas a soportar desde el
    arranque?
