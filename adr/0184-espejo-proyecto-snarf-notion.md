# ADR 0184 — Espejo Proyecto Snarf ↔ Proyecto Notion

**Fecha:** 2026-08-20
**Estado:** Aceptado

## Contexto

Fase A3 del plan Second Brain (`ROADMAP_SECOND_BRAIN_NOTION.md`, ver ADR 0179). Con el modelo de A2
(`SecondBrainManager`) y el namespacing de B2 resueltos, hace falta el vínculo real entre un Proyecto de
Snarf y su "hermano" en la database de Proyectos del Notion del fundador — para que una conversación sobre
un Proyecto de Snarf pueda, más adelante (Fase A5, retrieval proactivo), traer automáticamente el
conocimiento real que vive del lado de Notion.

## Decisión

**Campo nuevo `notion_project_page_id: str | None`** en el registro de Proyecto de Snarf
(`ProjectManager._normalize`) — `None` para proyectos viejos o creados sin Second Brain conectado.

**Dos caminos de vinculación:**
1. `ProjectManager.create()` extendido: si se inyectó un `SecondBrainManager` (parámetro opcional
   `second_brain`, `None` por defecto — un Proyecto de Snarf siempre se puede crear sin Notion) y está
   conectado, llama a `SecondBrainManager.create_project_row(name)` (nuevo) para crear la fila real en la
   database de Proyectos y guarda el id devuelto. `create_project_row` resuelve el nombre real de la
   property de título de esa database (`get_database` + buscar `type == "title"`) en vez de asumir
   `"Name"`/`"Nombre"` — cada fundador nombra sus properties como quiera. Nunca levanta: si algo falla
   (sin `property_map`, error de red, sin property de título), el Proyecto de Snarf se crea igual, solo sin
   vínculo — el vínculo es un extra, no un prerrequisito.
2. `second_brain_link_project(project_id, notion_page_id)` (tool nueva, no gateada — reversible, solo
   escribe JSON local): vincula un Proyecto ya existente a una página de Notion ya existente. Reusa
   `SecondBrainManager.get_project()` (ya valida existencia real + no-archivada) para no inventar un
   segundo camino de validación, luego persiste con `ProjectManager.set_notion_link()` (nuevo, mismo
   patrón que `set_prompt`).

**Las Áreas siguen sin importarse como entidad propia** (ya decidido en A2) — este ADR no lo reabre.

**Diferido explícitamente a Fase C4, no parte de este cambio**: el link "Ver en Notion" en el home de
proyecto (`renderProjectHome`, `web/index.html`). El propio roadmap ya preveía esta opción ("si no se
agregó ya en A3") — se difiere a propósito porque C4 es donde de todos modos se hace la pasada completa de
Playwright de cierre de Track C, evitando abrir un navegador real dos veces para el mismo tipo de cambio
chico. El backend (el dato `notion_project_page_id` y la tool de vínculo) ya está completo y testeado; solo
falta la superficie visual.

## Verificado

- `.venv/bin/python -m pytest -q` — 1579/1579 (1570 previos + 9 nuevos: 5 en `tests/test_project_manager.py`
  — `create()` con/sin Second Brain conectado, `set_notion_link` actualiza/devuelve `None` para proyecto
  inexistente, namespacing intacto — y 4 en `tests/test_second_brain.py` para `create_project_row`
  (resuelve la property de título real, `None` sin conexión/sin mapeo/sin property de título).
- `tests/test_verbs.py`/`tests/test_telemetry_detail.py`/`tests/test_brain.py`: cobertura total de
  `second_brain_link_project` (nodo `specialist_projects_manage`, mismo criterio que el resto del CRUD de
  Proyectos).

## Consecuencias

- Fase A7 (Home de Área) y Fase C4 (Home de proyecto enriquecido) ya tienen el dato real
  (`notion_project_page_id`) para mostrar el vínculo cuando exista.
- Fase B1 (OAuth por usuario) es quien va a hacer que `create_project_row`/la validación de
  `second_brain_link_project` funcionen contra el Notion real de un usuario que no sea el fundador — hoy
  siguen apuntando al `NOTION_API_KEY` global, consistente con que B1 todavía no se ejecutó.
