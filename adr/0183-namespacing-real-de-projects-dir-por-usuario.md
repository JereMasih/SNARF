# ADR 0183 — Namespacing real de `PROJECTS_DIR` por usuario

**Fecha:** 2026-08-20
**Estado:** Aceptado

## Contexto

Fase B2 del plan Second Brain (`ROADMAP_SECOND_BRAIN_NOTION.md`, ver ADR 0179). El plan original asumía,
a partir de una exploración previa, que tanto `PROJECTS_DIR` (`snarf/specialists/project_manager.py`)
como `data/conversation_projects.json` (`snarf/memory/episodic.py`) estaban globales, sin namespacing por
`user_id` — deuda a resolver antes de que Fase A3 construyera más superficie encima.

**Corrección real encontrada al ejecutar esta fase**: `data/conversation_projects.json` YA está
namespaced correctamente desde ADR 0137 — `Orchestrator.__init__` (línea ~2197) ya construye
`EpisodicMemory` pasando `project_links_path=user_memory_dir / "conversation_projects.json"` para
cualquier `user_id` distinto de `DEFAULT_USER_ID`. La exploración previa que alimentó el plan original
estaba equivocada en ese punto específico — se corrige acá en vez de dejarlo pasar (Principio VI,
Foundation). El único bug real confirmado era `PROJECTS_DIR`: `ProjectManager` recibía `user_id` en su
constructor desde siempre, pero nunca lo usaba para la ruta de almacenamiento — `_path()`/`_save()`/
`list_projects()` apuntaban siempre a la constante de módulo fija `Path("data/projects")`, sin importar
qué usuario construyera el `ProjectManager`.

## Decisión

Mismo patrón que ADR 0137 ya aplicó a `EpisodicMemory`: `ProjectManager.__init__` gana un parámetro
`projects_dir: Path = PROJECTS_DIR` — `_path()`, `_save()` y `list_projects()` pasan a usar
`self._projects_dir` en vez de la constante de módulo. `Orchestrator` pasa explícito
`projects_dir=PROJECTS_DIR if user_id == DEFAULT_USER_ID else MEMORY_DATA_DIR / user_id / "projects"` —
`DEFAULT_USER_ID` (el fundador) sigue en `data/projects/` sin ninguna migración (cero riesgo para datos
reales ya en disco); cualquier otro usuario recibe su propia carpeta bajo `data/users/<user_id>/projects/`.

**Hallazgo real de test hermético, corregido en el mismo cambio**: tres tests (`tests/test_project_manager.py`
x2, `tests/test_app.py` x2) monkeypencheaban la constante de módulo `PROJECTS_DIR` esperando que
`ProjectManager()` (sin `projects_dir=` explícito) la recogiera — pero el valor default de un parámetro se
fija en Python al momento de definir la función, no en cada llamada, así que ese monkeypatch dejó de tener
efecto con este cambio. Los tests de `test_project_manager.py` se corrigieron pasando `projects_dir=`
explícito al construir `ProjectManager`. Los de `test_app.py` (que usan el singleton `app_module.orchestrator`
ya construido antes de que el test corra) se corrigieron tocando directamente el atributo de instancia
real (`app_module.orchestrator.projects._projects_dir = tmp_path / "projects"`) en vez de la constante de
módulo, que ya no tiene ningún efecto sobre un objeto ya construido.

## Verificado

- `.venv/bin/python -m pytest -q` — 1570/1570 (1569 previos + 1 test nuevo de namespacing real en
  `tests/test_project_manager.py`: dos `ProjectManager` de dos `user_id` distintos, proyectos
  completamente aislados, cada uno con su propio archivo real en disco — mismo criterio ya exigido a
  `SecondBrainManager` en ADR 0182).
- Los 4 tests que monkeypencheaban `PROJECTS_DIR` (2 en `test_project_manager.py`, 2 en `test_app.py`)
  siguen en verde con la corrección aplicada — verificados explícitamente que siguen aislados de
  `data/projects/` real (nunca tocan el directorio real del repo).

## Consecuencias

- Fase A3 (espejo Proyecto Snarf↔Notion) puede construirse ahora sobre un `ProjectManager` ya namespaced
  sin arrastrar esta deuda.
- `ROADMAP_SECOND_BRAIN_NOTION.md` corregido: la mención de `data/conversation_projects.json` como
  pendiente de namespacing se retira — ya estaba resuelta desde ADR 0137, la fase B2 original quedó
  reducida solo a `PROJECTS_DIR`.
