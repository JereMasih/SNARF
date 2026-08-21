# ADR 0182 — Modelo Área/Proyecto/Recursos/Archivo: `SecondBrainManager`

**Fecha:** 2026-08-20
**Estado:** Aceptado

## Contexto

Fase A2 del plan Second Brain (`ROADMAP_SECOND_BRAIN_NOTION.md`, ver ADR 0179). Con los gaps de capability
de A1 resueltos, hace falta un modelo real en el backend de Snarf que refleje la jerarquía Área→Proyecto→
Recursos/Archivo que el fundador ya mantiene en su Notion (método PARA), sin asumir un esquema fijo —
cada fundador nombra sus databases y sus properties como quiera.

## Decisión

**`SecondBrainManager` (`snarf/specialists/second_brain.py`, nuevo).** Mismo patrón que `ProjectManager`:
compone la Capacidad `Notion`, no importa `snarf.core`/`snarf.runtime` (ADR 0026), vive en
`snarf/specialists/` aunque no sea un Specialist de un solo `handle()`.

**Notion es la única fuente de verdad — nunca se duplica contenido en un JSON propio.** A diferencia de
`ProjectManager` (que persiste el registro completo de cada Proyecto), `SecondBrainManager` lee Áreas/
Proyectos/Recursos/Archivo en vivo (`query_database`/`get_page`, ambos ya reales) cada vez que se piden.
Lo único que persiste localmente es el **mapeo** de qué database real corresponde a cada rol
(`data/second_brain/<user_id>/database_map.json`: `{areas, proyectos, recursos, archivo, property_map}`)
— el fundador ya tiene sus propias databases con sus propios nombres de columna, nunca se asume un
esquema fijo. `property_map` guarda el nombre real de las properties de relación necesarias para filtrar
(ej. `proyecto_area_relation`, `recurso_proyecto_relation`, `archivo_proyecto_relation`) — sin ese mapeo,
`list_projects(area_id=...)`/`list_resources(project_id)`/`list_archive(project_id)` levantan un
`ValueError` explícito en vez de devolver un filtro adivinado o vacío sin explicación (Principio VI,
Foundation: nunca fabricar un resultado sin base real).

**Namespacing desde el día uno**, en contraste directo con el bug real de `PROJECTS_DIR` global que
`ProjectManager` todavía arrastra (ver Fase B2, pendiente): `data/second_brain/<user_id>/`, nunca una
carpeta compartida entre usuarios — acá no hay nada viejo que migrar, nace bien desde el principio.

**Capability nueva necesaria en el camino**: `Notion.get_page(page_id)` (`GET /pages/{id}`) — no existía
ningún método para traer un registro puntual por id sin recorrer toda una database; `get_area`/
`get_project` lo necesitan. De paso, se hizo pública `extract_title()` (antes `_extract_title`, privada) —
mismo criterio ya usado con `format_properties_text`, reusable desde `second_brain.py` sin duplicar la
lógica de extraer el título de una fila.

**Orchestrator**: `self._second_brain = SecondBrainManager(self._notion, user_id)`, 7 tools nuevas de solo
lectura (`second_brain_status`, `second_brain_list_areas`, `second_brain_get_area`,
`second_brain_list_projects`, `second_brain_get_project`, `second_brain_list_resources`,
`second_brain_list_archive`) — ninguna gateada, todas lectura. `second_brain_status` expone
`is_connected()` para que Snarf pueda decir honestamente "todavía no está conectado" en vez de mostrar
listas vacías sin explicar por qué. Nuevo nodo `specialist_second_brain` en el cerebro (mismo criterio de
CRUD acotado que `specialist_bug_reports`/`specialist_skill_factory` — un solo nodo, sin split).

## Verificado

- `.venv/bin/python -m pytest -q` — 1569/1569 (1549 previos + 20 nuevos: 19 en
  `tests/test_second_brain.py` — namespacing real por `user_id`, defaults/roundtrip del `database_map`,
  `is_connected`, listado de Áreas/Proyectos/Recursos/Archivo con y sin filtro, `ValueError` explícito sin
  `property_map`, `get_area`/`get_project` con página no encontrada/archivada — y 2 en `tests/test_notion.py`
  para `get_page`.
- `tests/test_verbs.py`/`tests/test_telemetry_detail.py`/`tests/test_brain.py`: cobertura total de las 7
  tools nuevas.

## Consecuencias

- Fase A3 (espejo Proyecto Snarf↔Notion) puede apoyarse en `get_project`/`get_area` para validar que un
  `notion_page_id` real existe antes de guardarlo.
- Fase A4 (onboarding) va a ser quien complete `database_map.json` por primera vez — `SecondBrainManager`
  hoy no tiene ningún método de escritura del mapeo expuesto como tool todavía (`save_database_map` existe
  en la clase, pero no está registrado como tool del Orchestrator) — se registra recién cuando A4 lo
  necesite, para no exponer una superficie de configuración sin flujo real que la use.
- El diseño de `property_map` (nombres de relación por clave conceptual) es una apuesta razonable pero no
  verificada contra el Notion real del fundador todavía — la primera vez que se ejercite en vivo (Fase E1
  o antes, si el fundador pide probar el Second Brain) puede requerir ajustes si su esquema real no calza
  con lo asumido acá (ej. relaciones con nombre distinto por Área vs. por Proyecto).
