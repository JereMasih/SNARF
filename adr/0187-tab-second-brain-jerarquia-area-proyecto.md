# ADR 0187 — Tab "Second Brain" con jerarquía Área→Proyecto

**Fecha:** 2026-08-20
**Estado:** Aceptado

## Contexto

Fase C2 del plan Second Brain (`ROADMAP_SECOND_BRAIN_NOTION.md`, ver ADR 0179). Con A2/A3/A7 (modelo,
espejo, reportes) y C1 (decisión de UX) ya resueltos, hace falta la superficie real en `web/index.html`:
el pedido explícito del fundador de un ícono "2 + cerebrito" en una columna que reemplace la de Proyectos,
con drilldown Área→Proyecto→Conversaciones.

**Decisión de diseño real, no resuelta explícitamente por el fundador (pregunta abierta #6 del plan):**
¿el tab reemplaza del todo a "Proyectos", dejando huérfanos los proyectos sin vínculo a Notion? Se
resuelve acá con **degradación elegante**: el mismo tab (renombrado "Second Brain") muestra la jerarquía
de Áreas SI el Second Brain está conectado; si no (el estado real hoy, sin B1 completado en vivo ni A4
construido todavía), muestra exactamente la lista plana de Proyectos de siempre, sin ninguna pérdida de
funcionalidad. Nada queda huérfano nunca — es la misma superficie, el nivel de Área es un agregado
opcional encima.

## Decisión

**Backend nuevo, REST (`app.py`)**, necesario porque el Home de Área/lista de Proyectos ya construidos en
A2/A7 son tools conversacionales, no endpoints — la UI necesita HTTP directo (mismo criterio que
`GET /projects`):
- `GET /second-brain/status` → `{connected}`.
- `GET /second-brain/areas` → lista de Áreas reales.
- `GET /second-brain/areas/{area_id}/projects` → Proyectos reales de Notion de esa Área, cada uno
  enriquecido con `snarf_project_id` (el Proyecto de Snarf vinculado, si ya existe uno — nuevo
  `ProjectManager.find_by_notion_page_id()`) para que la UI pueda entrar directo a sus conversaciones sin
  inventar un segundo flujo. `orchestrator.second_brain` nueva propiedad pública (mismo patrón que
  `orchestrator.projects`).

**Frontend (`web/index.html`)**:
- Tab renombrado "Proyectos" → "Second Brain", con ícono nuevo "2 + cerebrito" (SVG monolínea, mismo
  lenguaje visual del resto de `ICONS` — dígito "2" + 3 nodos conectados). `data-tab="projects"` sin
  cambios (identificador interno, bajo riesgo tocarlo).
- `renderProjectPanelHeaderInto` refactorizado: `showBack: boolean` fijo → `backLabel`/`onBack`
  parametrizables, y el botón "+ nuevo" pasa a ser opcional — necesario para los 3 niveles reales con
  breadcrumb dinámico (antes solo existían 2: lista/detalle).
- `renderAreaListInto` (nivel 1, si conectado) y `renderAreaProjectsInto` (nivel 2) nuevas, mismo esqueleto
  que `renderProjectListInto` ya existente. `enterArea`/`exitArea` nuevas.
- `currentAreaId`/`currentAreaName` nuevo estado — a propósito **`enterProject()` no lo toca**: si se
  entra a un Proyecto desde dentro de un Área, `currentAreaId` sigue seteado mientras se mira ese
  Proyecto, así el botón "← volver" de las conversaciones cae de vuelta en la lista de Proyectos de ESA
  Área (breadcrumb real de 3 niveles), no siempre al nivel superior. Los 3 lugares que sí representan una
  salida completa del drilldown (conversación suelta sin proyecto, "+ nueva conversación") sí limpian
  `currentAreaId`.
- `refreshProjectList()` extendido a 3 ramas (antes 2): conversaciones de un Proyecto (sin cambios) /
  Proyectos de un Área / nivel superior — que a su vez chequea `second_brain_status` (cacheado en memoria
  por sesión, `secondBrainConnectedCache`) para decidir Áreas vs. la lista plana de siempre.

## Verificado

- `.venv/bin/python -m pytest -q` — 1610/1610 (1604 previos + 6 nuevos: `find_by_notion_page_id` en
  `tests/test_project_manager.py`, 4 tests de los 3 endpoints REST nuevos en `tests/test_app.py` — estado
  reflejado, Áreas reales, `snarf_project_id` marcado correctamente, 409 real cuando falta el mapeo de
  relación).
- **Playwright real contra un server de prueba (puerto 8000, nunca producción)**, mobile (420×900) y
  desktop (1400×900, con el bloque ya reparentado a la grilla — confirmado que pierde su `id` original al
  reparentearse, comportamiento preexistente de ADR 0035, no un bug): tab con ícono real visible, click
  activa el panel, cae correctamente en la lista plana de Proyectos reales del fundador (Second Brain no
  conectado todavía, estado real), **cero errores de consola** en ambas pasadas. Captura real guardada
  como evidencia del render en desktop.
- No se pudo verificar en vivo el camino "conectado" (Áreas reales) — el Second Brain del fundador no está
  conectado todavía (B1 pendiente del paso manual, A4 sin construir). Verificado por revisión de código y
  por los tests de los endpoints REST con datos mockeados.

## Consecuencias

- Fase C3 (reparentado desktop + pulido) continúa directo desde acá — el tab ya se reparenta
  correctamente hoy (mismo mecanismo genérico de `#dashHistoryParked`), C3 es sobre transiciones/estados
  de carga, no sobre esto.
- Fase C5 (Home de Área en la UI) consume `enterArea`/`GET /second-brain/areas/{id}` — la lista ya
  navega ahí, falta el home real con el reporte (hoy `enterArea` solo entra al nivel de lista de
  Proyectos).
- Limitación real conocida, no resuelta acá: "+ nuevo proyecto" dentro de una Área sigue creando un
  Proyecto de Snarf plano (vía `createProject()`, sin cambios) — no lo asocia automáticamente a esa Área
  en Notion. Vincularlo requiere que el fundador use `second_brain_link_project` desde el chat, o una
  mejora de UI futura.
