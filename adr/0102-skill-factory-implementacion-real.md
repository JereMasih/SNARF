# ADR 0102 — Skill Factory: implementación real

**Fecha:** 2026-08-05
**Estado:** Aceptado

## Contexto

Fase H del plan de expansión "Inteligencia Ejecutiva". ADR 0095 ya fijó el modelo de autoridad
(ninguna enmienda de Constitution necesaria — una confirmación explícita, caso por caso, en el
momento, ya es la autoridad directa que Art. VII exige) y el alcance autorizado (construir/activar
una skill nueva siguiendo el Skill Framework de ADR 0101, nunca tocar
FOUNDATION/CONSTITUTION/CHARACTER/COGNITION/MASTER_MAP ni código fuera de ese flujo, cada
construcción quema su propia confirmación). Esta ADR es la implementación real.

## Decisión

1. **`snarf/capabilities/claude_code.py::ClaudeCode`**: invoca el CLI real `claude -p "<prompt>" 
   --output-format json` como subproceso — versión real instalada (2.1.220) inspeccionada campo por
   campo antes de escribir código (`is_error`/`result`/`subtype`/`session_id`/`total_cost_usd`),
   mismo criterio de ADR 0097 con el SDK `mcp`. `--allowedTools` acota a
   `Edit/Write/Read/Glob/Grep/Bash(.venv/bin/python -m pytest*)` — nunca red, nunca
   `git commit`/`git push` (eso lo hace el fundador o una sesión interactiva después, nunca este
   flujo automático); `--disallowedTools` refuerza eso mismo por partida doble.
   `--permission-mode acceptEdits` + timeout real (900s default) como resguardo — sin esto, una
   invocación headless sin TTY que necesite un permiso no cubierto por el allowlist se cuelga
   esperando una respuesta que nunca llega.
2. **`snarf/specialists/skill_factory.py::SkillFactorySpecialist`**: no hereda de `Specialist` —
   mismo motivo que `ProjectManager` (ADR 0101), sus tres operaciones (`build_skill`/`activate`/
   `status`) no comparten una sola forma de entrada/salida.
3. **Verificación de alcance robusta a un working tree ya sucio de otra sesión en paralelo**: en vez
   de comparar contra un working tree limpio (asunción que no es la realidad de este repo hoy,
   donde otra sesión construye el fallback automático entre proveedores de LLM en simultáneo —
   ADR 0099), `build_skill()` toma un snapshot real de `git status --porcelain` ANTES de invocar a
   Claude Code y otro DESPUÉS — solo el delta (`after - before`) se considera "tocado por esta
   construcción". Un archivo ya sucio de otra sesión nunca cuenta como parte del alcance, y nunca
   dispara un abort falso.
4. **Verificación de alcance real**: si el delta incluye cualquiera de
   FOUNDATION/CONSTITUTION/CHARACTER/COGNITION/MASTER_MAP, o cualquier archivo fuera del conjunto
   esperado (`snarf/specialists/<rama>/<skill>.py`, `snarf/specialists/<rama>/__init__.py`,
   `tests/test_<skill>.py`, y la sección aditiva de `orchestrator.py`/`brain.py`/`verbs.py`/
   `detail.py`), la construcción se aborta sola con el motivo real, nunca sigue sola.
5. **Suite completa real** (no solo los tests nuevos) corre después de la construcción — si no pasa
   entera, la construcción queda en `failed`, nunca se ofrece activar algo que no pasa sus propios
   tests.
6. **Dos tools de alto impacto** (`skill_factory_build`, `skill_factory_activate`) suman a
   `HIGH_IMPACT_TOOLS` — mismo protocolo `_pending()`/`confirmed` de dos pasos que ya usan
   `gmail_send_message`/`drive_delete_file` (ADR 0015), reusado tal cual, no reinventado. La
   verificación del framework y de tests corre DENTRO de `skill_factory_build` (confirmación 1);
   `skill_factory_activate` (confirmación 2, separada) es la única que dispara el reinicio real del
   server. Un tool de solo lectura, `skill_factory_status`, no lleva confirmación. Los tres quedan
   automáticamente excluidos del allowlist MCP (ADR 0093/0097): los dos primeros por estar en
   `HIGH_IMPACT_TOOLS`, y ninguno de los tres se agregó a `MCP_EXPOSED_TOOLS` — la Inteligencia
   Ejecutiva (ADR 0094) nunca puede construir ni activar una skill, ni siquiera consultar el estado
   de una construcción, coherente con su cero autoridad de ejecución.
7. **`data/skill_proposals/`** (nuevo): registro de auditoría real (Art. VIII, trazabilidad) de cada
   intento — `index.json` (hasta `MAX_STORED_SKILL_PROPOSALS = 20`) + un `manifest.json` por
   propuesta con estado real (`building`/`built`/`activated`/`aborted`/`failed`), motivo si abortó o
   falló, archivos reales tocados, resultado real de tests, costo real y `session_id` de Claude Code.
   Endpoints nuevos de solo lectura: `GET /skill_proposals`, `GET /skill_proposals/{id}`.
8. **Activación real reinicia el server** (`launchctl bootout`/`bootstrap` sobre el LaunchAgent
   `com.snarf.server`, mismo procedimiento real ya documentado en CLAUDE.md) — nunca queda
   "caliente" sin reiniciar, mismo razonamiento que el plan original: `TOOLS` se arma una sola vez al
   importar `orchestrator.py`, activar en caliente sin reinicio es una superficie de riesgo real y
   nueva que ningún mecanismo de este repo prueba todavía.

## Deliberadamente NO verificado en vivo en esta ronda

A diferencia de las Fases C/D/E (que sí tuvieron un smoke test real de punta a punta), esta ADR
**no** incluye una invocación real del CLI `claude` sobre este mismo repositorio, ni un reinicio real
del server de producción, por dos motivos concretos y puntuales de este momento (no una limitación
permanente del diseño):

- El working tree real tiene, ahora mismo, trabajo genuino y sin commitear de otra sesión en
  paralelo (ADR 0099) — una invocación real de Claude Code (que edita archivos de verdad) corre
  riesgo real de interferir con ese trabajo, sin necesidad.
- Activar de verdad dispara un reinicio real del server de producción del fundador — una acción con
  impacto real fuera de este proceso, que no corresponde disparar como parte de verificar código
  nuevo sin su confirmación puntual para ESO específicamente.

Recomendado: la primera verificación en vivo de punta a punta (pedirle a Snarf que construya una
skill real y chica) debería correr con el working tree limpio y con el fundador presente para la
confirmación de activación real.

## Verificado

- 28 tests nuevos: `tests/test_claude_code.py` (7, CLI real mockeado — nunca invocado de verdad),
  `tests/test_skill_factory.py` (12, incluye el caso explícito de working tree ya sucio de otra
  sesión), `tests/test_orchestrator_skill_factory.py` (6, confirmación en dos pasos real vía
  `Orchestrator._handle_tool`, exclusión de MCP), `tests/test_skill_proposals_endpoint.py` (3).
- 823/823 tests de la suite completa.

## Consecuencias

- Primera vía real por la que Snarf puede modificar su propio código fuente — acotada, auditable,
  y que nunca se activa sin dos confirmaciones explícitas nuevas cada vez.
- `data/skill_proposals/` se vuelve, desde ahora, la fuente real de qué intentos de auto-modificación
  existieron — cualquier revisión futura de esta capacidad debería empezar ahí, no adivinando.
