# ADR 0185 — Home de Área: rollup + análisis/reporte

**Fecha:** 2026-08-20
**Estado:** Aceptado

## Contexto

Fase A7 del plan Second Brain (`ROADMAP_SECOND_BRAIN_NOTION.md`, ver ADR 0179). El fundador pidió
explícitamente que cada Área tenga, igual que ya tiene un Proyecto, un panorama agregado real —
proyectos, notas, tareas, recursos, archivo — más un análisis generado automáticamente, expuesto
eventualmente como widgets en el HUD (Track E).

**Ajuste honesto de alcance respecto al plan original**: el plan mencionaba agregar "notas/tareas" de
Notion al rollup. `SecondBrainManager` (ADR 0182) solo modela 4 databases reales
(`areas`/`proyectos`/`recursos`/`archivo`) — no hay ninguna clave de mapeo para "notas" o "tareas" como
databases separadas de Notion, porque no se sabe todavía si el fundador las tiene como databases propias o
como properties dentro de Recursos/Proyectos. Inventar una clave de mapeo para una database que no se
confirmó que existe violaría el Principio VI (Foundation) — se prefiere no rellenar. El rollup real de esta
fase cubre **Proyectos + Recursos + Archivo**, que sí están modelados; "notas"/"tareas" quedan para cuando
la Fase E1 inspeccione el esquema real del fundador con las tools ya construidas.

## Decisión

**`SecondBrainManager.get_area_home(area_id)`** (nuevo): Área + sus Proyectos + Recursos y Archivo
agregados de TODOS esos Proyectos. Nunca muestra un cero como si fuera un dato real cuando en realidad es
desconocido: `resources_mapped`/`archive_mapped` (booleanos) distinguen "cero recursos reales" de "no se
puede saber, falta mapear la property de relación en `database_map`" — la agregación ni siquiera se
intenta si no está mapeado, para no levantar el `ValueError` que `list_resources`/`list_archive` ya tiran
en ese caso (ADR 0182).

**`SecondBrainManager.generate_area_report(area_id)`/`cached_area_report(area_id)`** (nuevos, mismo patrón
que `ProjectManager.generate_summary()`/`cached_summary()`, ADR 0047): análisis generado por LLM sobre el
`get_area_home()` real — nunca inventa proyectos ni actividad, y cuando Recursos/Archivo no están
mapeados se lo dice explícito al LLM en el contexto ("sin mapear todavía... no se puede saber") en vez de
omitirlo en silencio, para que el reporte generado tampoco lo omita. Cacheado en
`data/second_brain/<user_id>/area_reports/<area_id>.json` con `report`/`report_generated_at`.
`SecondBrainManager` gana `llm_factory` opcional (mismo criterio de inyección que `ProjectManager`/
`GmailDigestSpecialist`, ADR 0026) — nuevo rol de ruteo `second_brain_report`
(`snarf/runtime/llm_routing.py`), barato por default (`mlx_local_fast`), igual que `project_summary`.

**Split de nodo del cerebro**: `specialist_second_brain` ya tenía 7 tools desde A2/A3 — sumar estas 2
lo hubiera llevado a 9, por encima del techo real de 8 (`test_no_specialist_node_absorbs_too_many_tools`,
ADR 0054). Nodo nuevo `specialist_second_brain_reports` para `second_brain_get_area_home`/
`second_brain_area_report_refresh` — distinto por naturaleza (genera un análisis con LLM, no CRUD crudo de
lectura), mismo criterio que ya separó `specialist_projects_manage`/`_tasks`/`_conversations`.

**Orchestrator**: `second_brain_get_area_home` (usa el reporte cacheado, lo genera la primera vez —
mismo patrón que `project_get`) y `second_brain_area_report_refresh` (fuerza uno nuevo, ignorando el
cache — pedido explícito del fundador, mismo espíritu que el botón "actualizar" de Proyecto, aunque acá
por ahora solo expuesto como tool conversacional, no como endpoint REST — el botón real en la UI llega en
Fase C5).

## Verificado

- `.venv/bin/python -m pytest -q` — 1587/1587 (1579 previos + 8 nuevos en `tests/test_second_brain.py`:
  `get_area_home` con Área inexistente, con Recursos/Archivo sin mapear (flags en `false`, listas vacías,
  nunca un `ValueError` propagado), agregando de verdad across 2 Proyectos; `generate_area_report` sin
  LLM disponible, con LLM real (contenido del mensaje verificado — nombres de Proyectos reales, aviso
  explícito de "sin mapear todavía"), degradación ante error del LLM; `cached_area_report` genera una
  sola vez y reusa cache en la segunda llamada, `None` para Área inexistente.
- `tests/test_llm_routing.py`, `tests/test_verbs.py`, `tests/test_telemetry_detail.py`, `tests/test_brain.py`:
  cobertura total del rol `second_brain_report` y de las 2 tools nuevas, techo de tools por nodo respetado.

## Consecuencias

- Fase C5 (Home de Área en la UI) consume `second_brain_get_area_home` directo — ya tiene todo lo que
  necesita mostrar (Área, Proyectos, agregados con sus flags de "mapeado", reporte cacheado).
- Fase E1 (widgets Jarvis) puede reusar el mismo rollup para el widget de reporte de Área — mismos datos,
  otra superficie.
- Pendiente real, sin resolver acá: si el fundador tiene databases separadas de "Notas"/"Tareas" en su
  Second Brain real, no hay todavía forma de mapearlas ni de agregarlas al rollup — requiere ampliar
  `DATABASE_MAP_KEYS` (ADR 0182) cuando se confirme el esquema real (Fase E1).
- **Diferido, no implementado en esta fase**: el plan original preveía que el reporte generado se indexara
  también en la Knowledge Layer (reusando el pipeline de `NotionSource`/`KnowledgeIndexer`, ADR 0173), para
  que el análisis mismo retroalimente el RAG. No se construyó acá — integrarlo bien exige decidir cómo un
  ítem "generado por Snarf" (no una página/fila real de Notion) encaja en un pipeline pensado para indexar
  contenido de Notion tal cual, sin inventar una fuente híbrida a las apuradas. Queda como trabajo real
  pendiente, a retomar cuando el patrón de retrieval proactivo de Fase A5 esté construido y se pueda
  decidir con más contexto si conviene el mismo mecanismo o uno separado.
