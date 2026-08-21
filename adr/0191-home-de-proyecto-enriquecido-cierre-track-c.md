# ADR 0191 — Home de proyecto enriquecido, cierre de Track C

**Fecha:** 2026-08-20
**Estado:** Aceptado

## Contexto

Fase C4 del plan Second Brain (`ROADMAP_SECOND_BRAIN_NOTION.md`, ver ADR 0179), cierre de Track C. A3
había diferido a propósito el link "Ver en Notion" en el home de proyecto para esta fase (ver ADR 0184).
El plan original también pedía: notas reales (no solo conteo — **ya resuelto desde ADR 0047, código
existente sin tocar**, `renderProjectHomeNotes` ya lista el texto real de cada nota), recursos reales de
Notion, botón "vincular a Notion" para proyectos viejos, y un badge de "conocimiento indexado: N ítems".

## Decisión

**Backend REST nuevo** (`app.py`):
- `PUT /projects/{project_id}/notion-link` (`ProjectNotionLinkRequest`): valida la página real vía
  `orch.second_brain.get_project()` antes de guardar (mismo criterio que la tool
  `second_brain_link_project`, ADR 0184) — nunca guarda un id inventado.
- `GET /projects/{project_id}/notion-resources`: `{resources: [...], mapped: bool}` — `mapped=false`
  (nunca una lista vacía sin explicar) si el proyecto no está vinculado o la relación Recursos↔Proyecto
  todavía no está mapeada en el Second Brain (mismo criterio honesto de `resources_mapped` ya usado en A7).

**Frontend (`renderProjectHome`)**:
- `notionPageUrl(pageId)` (nuevo, mismo formato que `_notion_page_link` de `snarf/telemetry/detail.py`):
  link real "ver en Notion ↗" si `project.notion_project_page_id` existe; si no, botón "vincular a
  Notion" que pide el id o link completo (extrae el id real con una regex simple, acepta ambos formatos)
  y llama al PUT nuevo.
- Sección "Recursos (Notion)" — solo se renderiza si el proyecto está vinculado, se carga aparte (fetch
  propio después del render inicial, nunca bloquea la apertura del home) para no pegarle a Notion en cada
  apertura de un proyecto sin vínculo.

**Diferido, no implementado en esta fase**: el badge "conocimiento indexado: N ítems". Investigado antes
de construirlo: `KnowledgeIndexer.manifest_summary()` (ya real) cuenta el TOTAL de ítems indexados de todo
el dominio, no filtrado por proyecto — obtener un conteo real por proyecto requeriría un método nuevo del
vector store (contar con filtro `where`, distinto de la búsqueda top-k que ya existe vía
`search_within`/`orch.projects.search_within`). Se prefiere no construir esa pieza nueva a las apuradas al
cierre de una fase ya grande — queda como trabajo real pendiente, sin ticket propio todavía.

## Verificado

- `.venv/bin/python -m pytest -q` — 1620/1620 (1614 previos + 6 nuevos: vínculo válido/inválido/proyecto
  inexistente, recursos sin vincular/vinculados/con relación sin mapear).
- **Playwright real, mobile y desktop, contra un server de prueba real (puerto 8000)** — sobre proyectos
  REALES del fundador (verificado explícitamente después de la corrida que ningún archivo real en
  `data/projects/` quedó mutado: las llamadas de escritura sensibles se interceptaron client-side con
  `page.route()`, nunca llegaron al server real):
  - Botón "vincular a Notion" visible en un proyecto real sin vínculo, en mobile y desktop.
  - Tras vincular (mockeado), el link "ver en Notion ↗" aparece con la URL real correcta
    (`https://www.notion.so/<id-sin-guiones>`).
  - Sección de Recursos carga y muestra un recurso real (mockeado) como link clicable.
  - Navegación completa ida y vuelta (botón "← volver", reabriendo el menú que se cierra en mobile al
    entrar a un proyecto — comportamiento preexistente).
  - **Cero errores de consola** en las 4 pasadas de esta fase (mobile linking, desktop linking, ambas con
    y sin route interception).

## Consecuencias

- **Track C queda cerrado**: C1 (decisión de UX), C2 (tab + drilldown), C3 (skeleton), C5 (home de Área),
  C4 (home de proyecto enriquecido) — los 5 verificados con Playwright real, sin dejar ningún dato real
  del fundador mutado por accidente durante la verificación.
- El badge de conocimiento indexado por proyecto queda como mejora futura real, ya investigada — el
  bloqueo concreto (falta un método de conteo filtrado en el vector store) queda documentado acá para
  cuando se retome.
