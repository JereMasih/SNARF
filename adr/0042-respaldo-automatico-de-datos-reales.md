# ADR 0042 — Respaldo automático de `data/`

**Fecha:** 2026-07-29
**Estado:** Aceptado

## Contexto

Durante esta misma sesión, al verificar en vivo el widget de "uso real de APIs" (ADR 0041), Claude Code escribió por error datos de prueba directo en el archivo real `data/usage_log.jsonl` en vez de en un archivo aislado de test. Al intentar revertir ese error con `head -n -4 archivo.jsonl` (sintaxis de GNU coreutils, no soportada por el `head` de macOS/BSD), el comando falló silenciosamente y produjo un archivo vacío — que luego se movió por encima del original sin verificar su contenido antes. Resultado real: **se perdieron las 4304 líneas de historial real de uso de Anthropic/ElevenLabs/Voyage acumuladas durante toda la vida del proyecto.** No fue recuperable: el archivo está en `.gitignore` a propósito (es telemetría runtime), no había snapshot local de APFS ni Time Machine configurado, y ningún proceso lo tenía abierto por file descriptor.

El fundador pidió una solución de dos partes: que este tipo de error no vuelva a pasar, y que si pasa igual, siempre se pueda volver a una versión funcional viva.

Es importante ser honesto sobre el alcance real de este ADR: no impide que Claude Code (u otro proceso) vuelva a escribir o borrar datos reales por error — esa es una cuestión de disciplina operativa (probar siempre contra un path de test aislado, nunca contra `data/` real, verificar el contenido de un archivo intermedio antes de sobreescribir el original). Lo que sí puede garantizar el código es que, si algo así vuelve a pasar, exista una versión reciente para restaurar.

## Decisión

Nuevo módulo `snarf/runtime/data_backup.py`:

- `backup_now()`: copia una lista explícita de targets reales e irremplazables (`activity_log.jsonl`, `episodic_memory.jsonl`, `input_log.jsonl`, `manual_verification_log.jsonl`, `usage_log.jsonl`, `dashboard_prefs/`, `gmail_digest/`, `local_files/`) a un snapshot nuevo con timestamp bajo `data_backups/` (fuera de `data/`, gitignored). Poda los snapshots más viejos, dejando los últimos 14.
- Se excluye a propósito `data/drive_index/` (el caché de vectores de Google Drive, ~550MB): es regenerable desde la fuente real (el propio Drive), respaldarlo sería caro y redundante — la fuente de verdad ya vive en otro lado.
- `restore_latest()`: restaura el snapshot más reciente sobre `data/`, sin borrar targets que ese snapshot no tenga.
- `list_backups()`: lista los snapshots disponibles, más nuevo primero.

Disparado automáticamente en `app.py`: un backup al arrancar el server (`@app.on_event("startup")`), y uno cada 6 horas mientras corre (`asyncio` en segundo plano) — así un proceso de larga vida (días sin reiniciar) igual queda cubierto, no solo en cada restart. Ambos se saltan durante los tests (`PYTEST_CURRENT_TEST`, que pytest ya setea solo) para que la suite no dispare cientos de backups reales ni deje tareas de fondo colgadas entre tests.

## Verificado

- 305/305 tests, incluye `tests/test_data_backup.py` (copia archivos y directorios, saltea targets inexistentes, poda snapshots viejos respetando `keep_last_n`, restaura el snapshot más reciente sobre datos corrompidos, y los casos vacíos de ambas funciones).
- Confirmado que la suite completa no crea `data_backups/` en el repo real (el guard de `PYTEST_CURRENT_TEST` funciona).
- Probado en un server real (puerto de prueba descartable): el snapshot se crea de verdad al arrancar, con la estructura esperada.

## Consecuencias

- `data_backups/` puede crecer hasta 14 snapshots — para los archivos respaldados (unos pocos MB en total, sin `drive_index/`) esto es insignificante en disco.
- Si se agrega un nuevo archivo de estado real e irremplazable a `data/` en el futuro, hay que sumarlo a `BACKUP_TARGETS` a mano — no hay descubrimiento automático, a propósito (evita respaldar por accidente algo pesado o regenerable como `drive_index/`).
- Esto no reemplaza la disciplina real: seguir probando siempre contra un path de test aislado (`monkeypatch`, o una copia del repo aparte como se hizo para verificar este mismo ADR) en vez de tocar `data/` real.
