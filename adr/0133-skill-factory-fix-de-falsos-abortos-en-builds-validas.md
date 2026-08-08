# ADR 0133 — Skill Factory: fix de falsos abortos en construcciones válidas

**Fecha:** 2026-08-08
**Estado:** Aceptado

## Contexto

Tres intentos reales de construir la skill `drive_incremental_indexer` (rama `knowledge`) con
`skill_factory_build` terminaron en `status='failed'` (`data/skill_proposals/index.json`). Dos
fallaron por falta de crédito real de la API de Anthropic (motivo ajeno a esta ADR, ya cubierto por
ADR 0131). El tercero (`drive_incremental_indexer-b4320396`) reveló dos bugs reales en el propio
Skill Framework, ninguno relacionado con el perímetro de seguridad en sí — el motor **nunca llegó a
tocar** ningún archivo fuera de alcance (`diff_files` del manifest: solo
`snarf/specialists/knowledge/` y `tests/test_drive_incremental_indexer.py`, ambos dentro de lo
esperado).

**Bug A — deadlock real de autocorrección.** `LocalCodeWriter.run()` escribió el módulo del
Specialist con `write_file`, pero el módulo tenía un error de sintaxis real (un string sin
triple-comilla con saltos de línea literales adentro, en la constante `SYSTEM_PROMPT` del propio
Specialist — nunca el system prompt principal de Snarf, pese a lo confuso del nombre compartido).
Al intentar corregirlo, el modelo local leyó la descripción real de `write_file` ("nunca para tocar
un archivo que ya existe") y la de `edit_file` (rechazado, esos 4 paths de wiring no incluyen el
Specialist nuevo), concluyó honestamente que no tenía ninguna herramienta autorizada para
corregir su propio archivo, y abandonó con `NO PUDE`. La restricción real (`_write_file` en
`local_code_writer.py`) nunca impidió reescribir un path ya presente en `allowed_write_paths` — el
bloqueo era enteramente de redacción de las tools, no del gateo real.

**Bug B — falso positivo del chequeo de perímetro por diff de git.** `_default_git_dirty_files()`
corría `git status --porcelain` sin `--untracked-files=all`. Cuando una construcción es la primera
skill de una rama que todavía no existe como directorio (como `knowledge/`), git colapsa el
directorio nuevo entero en una sola línea `?? snarf/specialists/knowledge/` en vez de listar cada
archivo. `_expected_files()` compara contra paths de archivo exactos, así que esa línea colapsada
nunca matchea nada — cualquier build exitosa que estrena una rama nueva se habría abortado sola con
un falso "tocó archivo fuera del alcance autorizado", sin que el motor hubiera hecho nada mal.
Confirmado reproduciendo el comportamiento de git en un repo de prueba antes del fix.

**Bug C — sin validación de `branch`/`skill_name` de entrada.** Ninguno de los dos venía sanitizado
antes de construir los paths de escritura. Como el gateo de `_write_file` es por membresía exacta
de set (`rel not in allowed_write_paths`), y ese set se construye con los mismos strings sin
validar, un `skill_name` con `../` definiría su propio path de escape del repo — nunca explotado en
los intentos reales, pero un gap real que había que cerrar antes de que este motor corra sin
supervisión directa.

## Decisión

1. **`_validate_identifier()` nueva en `skill_factory.py`**, snake_case estricto
   (`^[a-z][a-z0-9_]*$`) para `branch` y `skill_name`, verificada al principio de `build_skill()`
   — antes de crear manifest, antes de tocar git, antes de invocar el motor. Un identificador
   inválido devuelve `status='rejected'` sin ningún efecto secundario (nunca se guarda proposal,
   nunca se llama a `LocalCodeWriter`).
2. **`_default_git_dirty_files()` ahora usa `git status --porcelain --untracked-files=all`** —
   siempre lista archivos individuales, nunca colapsa un directorio nuevo.
3. **Redacción de `write_file`/`SYSTEM_PROMPT` en `local_code_writer.py` corregida**: ahora dice
   explícitamente que puede llamarse más de una vez sobre el mismo path para autocorregirse (dentro
   del propio alcance de escritura no hay diferencia real entre "crear" y "corregir"), y que
   `edit_file` es exclusivamente para los 4 archivos de wiring preexistentes. El gateo real
   (`_write_file`) no cambió — ya permitía reescribir un path de `allowed_write_paths` sin importar
   si existía; el bug era solo de instrucciones.
4. **`_build_prompt()` en `skill_factory.py`** ahora indica el mismo criterio en el paso 4 (correr
   tests): si el error está en el Specialist/test propio, corregirlo con `write_file` sobre el
   mismo path, nunca tocar otro archivo.

## Alcance de autoridad — sin cambios respecto de ADR 0095/0130

El perímetro estricto (nunca FOUNDATION/CONSTITUTION/CHARACTER/COGNITION/MASTER_MAP, alcance nombrado
de archivos nuevos + 4 de wiring, verificación de diff independiente, suite completa obligatoria)
sigue exactamente como ADR 0095 lo fijó. Ningún cambio de esta ronda amplía lo que el motor puede
tocar — el fix es que deje de fallar solo por reportar mal un path ya válido, y que pueda
corregirse a sí mismo dentro del mismo archivo que ya estaba autorizado a escribir.

## Verificado

- 7 tests nuevos: `tests/test_skill_factory.py` (rechazo de `skill_name`/`branch` con `../` o fuera
  de snake_case sin invocar el motor; build válido con identificadores snake_case; reproducción real
  con un repo git de prueba de que `_default_git_dirty_files` ya no colapsa un directorio nuevo) y
  `tests/test_local_code_writer.py` (`write_file` reescribiendo el mismo path dos veces para
  autocorregirse).
- Restos rotos del intento fallido (`snarf/specialists/knowledge/drive_incremental_indexer.py`,
  `tests/test_drive_incremental_indexer.py` — nunca trackeados en git, `status='failed'` en el
  manifest) eliminados con confirmación explícita del fundador.
- 1094/1094 tests de la suite completa.

## Consecuencias

- Una construcción que estrena una rama nueva (primera skill de un dominio) ya no aborta sola por el
  falso positivo del diff de git.
- El motor local puede iterar sobre su propio error de sintaxis/lógica sin quedar bloqueado por una
  descripción de tool ambigua — se espera una tasa de éxito real más alta para el mismo tipo de bug
  que frenó `drive_incremental_indexer`.
- `branch`/`skill_name` fuera de snake_case (incluida cualquier forma de path traversal) se rechazan
  de entrada, sin gastar ni una ronda del motor local.
