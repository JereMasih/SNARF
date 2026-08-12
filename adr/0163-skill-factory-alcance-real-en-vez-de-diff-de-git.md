# ADR 0163 — Skill Factory: alcance real (`files_written`) en vez de diff de git

**Fecha:** 2026-08-12
**Estado:** Aceptado

## Contexto

El fundador pidió construir un skill nuevo (`document_to_reader_optimized`, conversión de documentos a
EPUB) vía la Skill Factory. La construcción abortó con `"Tocó archivo(s) fuera del alcance autorizado"`,
citando archivos que no tenían nada que ver con ese skill —
`.claude/skills/n8n-map-sync/SKILL.md`, `adr/0158-*.md`, `adr/0159-*.md`,
`snarf/runtime/agent_change_proposals.py`, `tests/test_agent_change_proposals.py`. Investigado: esos son
archivos reales de otra sesión de Claude Code (Fases 15-21 de
`ROADMAP_OBSERVABILIDAD_MULTIUSUARIO_N8N.md`) que estaba corriendo **en paralelo, en el mismo working
tree**, exactamente en la ventana de tiempo del build.

**Causa raíz real, confirmada leyendo el código:** `SkillFactorySpecialist.build_skill()` determinaba qué
tocó el motor de escritura comparando dos fotos de `git status --porcelain --untracked-files=all` contra
**todo el repo** (`before`/`after`, `touched = after - before`) — nunca algo scopeado al propio motor. Ya
había un intento previo de tolerar esto ("para tolerar que el working tree ya tenga cambios reales de otra
sesión en paralelo", ver comentario original y `test_build_skill_tolerates_preexisting_dirty_files_from_
another_session`), pero solo cubría archivos sucios **antes** de arrancar el build — cualquier archivo
nuevo que apareciera **durante** la ventana del build (como los de una sesión concurrente activamente
escribiendo) se contaba igual como "tocado por el motor", sin importar quién lo escribió de verdad.

**Hallazgo secundario, más serio:** el código real que el motor local sí llegó a escribir
(`snarf/specialists/productivity_documents/document_to_reader_optimized.py`) resultó ser un placeholder
falso — devolvía un link de Drive inventado (`fake-epub-id`) sin llamar nunca a las capacidades inyectadas,
y dependía de una Capacidad (`document_processor`) que no existe en el repo. El abort (por el motivo
equivocado) evitó sin querer que se activara una tool que le mentiría al fundador sobre haber subido un
EPUB real — viola Principio VI de FOUNDATION.md. Ese código se descartó (nunca estuvo en git, solo
filesystem) — reconstruir el skill de verdad, con una Capacidad real de conversión a EPUB, queda como
pedido aparte.

## Decisión

**`LocalCodeWriterResult` gana un campo nuevo, `files_written: frozenset[str]`** — armado dentro de
`LocalCodeWriter.run()`, en `_write_file()`/`_edit_file()`, exactamente en el momento en que cada
escritura pasa su propio gate contra `allowed_write_paths`/`allowed_edit_paths`. Es estructuralmente
imposible que contenga un path que no pasó ese gate — el gate ya era, desde siempre, la verificación real
y autoritativa; `files_written` simplemente la expone en vez de dejar que `SkillFactorySpecialist` intente
re-derivarla con una señal indirecta (diff de git) que depende de que el working tree esté quieto.

**`SkillFactorySpecialist.build_skill()`** ya no llama a `git status` en absoluto para esta decisión —
`touched = set(result.files_written)`, punto. Se eliminaron `_default_git_dirty_files()` y el parámetro
`git_dirty_files_fn` (sin otro consumidor en el repo, `grep` confirmado). Los chequeos de
`_NEVER_ALLOWED_FILES`/alcance esperado se mantienen sobre `touched` — ahora son, en la práctica,
inalcanzables (el gate de escritura ya garantiza que `touched ⊆ _expected_files()`), pero se dejan como
defensa en profundidad real: si algún día el gate de `local_code_writer.py` tuviera un bug, esto lo sigue
detectando.

## Verificado

- 3 tests nuevos en `tests/test_local_code_writer.py`: `files_written` reporta cada escritura exitosa,
  nunca incluye una escritura rechazada por estar fuera de alcance, incluye ediciones y deduplica
  reescrituras repetidas del mismo path (autocorrección).
- `tests/test_skill_factory.py` reescrito completo: reemplaza la fixture `dirty_files_sequence` (before/
  after simulados) por `files_written` explícito en cada test — más directo, sin indirección. Test nuevo
  clave: `test_build_skill_never_consults_git_or_the_working_tree_for_the_scope_decision` — monkeypatchea
  `subprocess.run` para que cualquier invocación real falle el test, y confirma que `build_skill()` decide
  el alcance correctamente sin necesitar siquiera que `repo_root` sea un repo git real.
- Corriendo la suite completa (no solo los tests nuevos) apareció un test roto más, en un archivo distinto:
  `tests/test_skill_proposals_endpoint.py::test_skill_proposals_reflects_a_real_build` seguía haciendo
  `monkeypatch.setattr(..., "_git_dirty_files_fn", ...)` sobre un atributo que ya no existe — corregido
  (se sacó esa línea, y `_FakeAvailableCodeWriter.run()` ahora devuelve `files_written` real). Mismo
  recordatorio de siempre: un cambio de firma/atributo necesita grep de todos sus usos, no solo el archivo
  de test más obvio.
- 1384/1384 tests de la suite completa (`.venv/bin/python -m pytest -q`), verificado en una corrida real
  después de este último fix, no antes.
- Código placeholder descartado del filesystem (`snarf/specialists/productivity_documents/`,
  `tests/test_document_to_reader_optimized.py`, `data/document_to_reader_optimized/`) — nunca estuvo en
  git, ninguna operación de git involucrada en el descarte.
