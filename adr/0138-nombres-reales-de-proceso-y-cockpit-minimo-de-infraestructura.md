# ADR 0138 — Nombres reales de proceso + primera pieza real del cockpit de infraestructura

**Fecha:** 2026-08-10
**Estado:** Aceptado

## Contexto

Al llegar a la Fase 4 del plan (levantar n8n), el fundador pidió primero resolver algo más urgente:
poder distinguir con nombre correcto los procesos reales de Snarf en su Mac, saber dónde viven, y
tener una forma de verlos/abrirlos/cerrarlos — disparado por ver "22.71GB de RAM usados" en Activity
Monitor y no poder explicarse a qué correspondía, pese a estar usando (según su entendimiento) solo el
modelo local rápido.

**Diagnóstico real, no supuesto**, con `ps`/`launchctl`/`vm_stat` reales antes de tocar nada:

- Los 22.71GB no son de Snarf. Los procesos reales de Snarf (server principal + MLX rápido + Kokoro
  TTS, los únicos tres corriendo en el momento del diagnóstico) sumaban ~350MB combinados recién
  arrancados — el modelo rápido, una vez con los pesos cargados tras un reinicio real, sube a ~2.5GB
  (medido en vivo). El uso real de memoria del sistema está dominado por Chrome (10+ procesos
  renderer, cientos de MB cada uno), VS Code, Spotify y Claude Code — apps normales del día a día,
  no algo que Snarf esté haciendo mal.
- `com.snarf.mlx-heavy` y `com.snarf.mlx-mid` (los otros dos servers MLX documentados en CLAUDE.md)
  **no estaban cargados** en el momento del diagnóstico — solo `mlx-fast` corría. La cifra de "3
  servers 24/7" de rondas anteriores ya no reflejaba el estado real.
- Motivo real de la confusión de nombres: todos estos procesos corren sobre el mismo binario
  (`Python.framework`'s launcher `Python.app`), así que Activity Monitor/`ps`/`top` los mostraban
  genéricamente como "Python" — indistinguibles entre sí y de cualquier otro script Python de la Mac.

## Decisión

### 1. Nombres de proceso reales

Se probó primero `exec -a <nombre>` desde el shell del propio LaunchAgent (patrón estándar Unix) —
**no funcionó, con evidencia real**: el build de Python usado (Homebrew Python.framework con el
launcher "Python.app") resetea el argv[0] que `exec -a` deja seteado, en algún punto de su propio
arranque, antes de que la app corra — confirmado comparando contra `/bin/sleep` (donde `exec -a` sí
sobrevive) vs. contra `python -m mlx_lm` (donde no).

**Fix real que sí funciona**: `setproctitle.setproctitle(...)`, llamado DESDE ADENTRO del proceso
Python ya vivo (después de que ese reseteo ya pasó) — confirmado en vivo, sobrevive.

- `app.py` llama `setproctitle.setproctitle(f"snarf-server (PID {os.getpid()})")` al importarse —
  opcional (`try/except ImportError`), el server sigue arrancando igual sin el paquete instalado.
- `snarf/runtime/timestamp_lines.py` (el filtro de logs con timestamp que ya corre en pipe detrás de
  `com.snarf.server`) hace lo mismo (`snarf-server-logs`).
- `snarf/runtime/proctitle_exec.py` (nuevo): wrapper genérico `python -m
  snarf.runtime.proctitle_exec <nombre> <módulo> [args...]` — para procesos de TERCEROS (`mlx_lm`)
  donde no se puede agregar `setproctitle` por dentro sin parchear una dependencia. Reusable para
  `mlx-heavy`/`mlx-mid` el día que vuelvan a cargarse.
- `com.snarf.mlx-fast.plist` pasa a invocar `mlx_lm` a través de ese wrapper (`snarf-mlx-fast`).
- `com.snarf.kokoro-tts.plist` (repo separado, `kokoro-fastapi` — no se le agregó ningún archivo
  nuevo, solo `setproctitle` a su propio venv vía `uv pip install`) usa un `-c` inline equivalente
  (`snarf-kokoro-tts`).
- Los tres LaunchAgents afectados se recargaron de verdad (`launchctl bootout`/`bootstrap`,
  `com.snarf.server` con `kickstart -k`) y se verificó cada uno: `ps -o comm` muestra el nombre real,
  y cada server responde su healthcheck real (`/status` en 8002, `/v1/models` en 8991,
  `/v1/audio/voices` en 8880) — cero downtime más allá del segundo real de cada restart, cero cambios
  en `data/` (`git status data/` limpio antes y después).

### 2. Primera pieza real del cockpit de infraestructura (adelanto de Fase 9.1 del plan)

En vez de una vista nueva de dashboard (que hubiera necesitado verificación real en navegador antes de
poder darla por terminada), la primera versión vive donde Snarf ya tiene una interfaz real y probada:
el chat. Dos tools nuevas, **solo para el fundador** (`self._user_id == DEFAULT_USER_ID`, cualquier
otro usuario recibe un error — nunca expuestas a un usuario de prueba, y nunca al allowlist de MCP por
estar `ops_process_restart` en `HIGH_IMPACT_TOOLS`):

- `ops_process_status` (lectura, sin confirmación): estado real (`running`/`pid`/`rss_mb`) de cada
  LaunchAgent conocido de Snarf — allowlist positivo explícito (`snarf/runtime/process_control.py`,
  mismo criterio que `snarf/mcp/tools.py::MCP_EXPOSED_TOOLS`), nunca un label arbitrario de
  `launchctl`.
- `ops_process_restart` (alto impacto, protocolo de confirmación en dos pasos): reinicia real
  (`launchctl kickstart -k`) uno de los servers locales. **`com.snarf.server` queda explícitamente
  excluido** — reiniciarse a sí mismo desde dentro del propio request que está respondiendo lo mataría
  a mitad de camino; sigue siendo manual por terminal, como ya documentaba CLAUDE.md.

## Riesgos / lo que queda pendiente

1. **El PID que `launchctl list` reporta para `com.snarf.server` es el del `/bin/sh` que envuelve el
   pipe hacia `timestamp_lines`, no el proceso real de uvicorn** (que corre con más RAM real) —
   `ops_process_status` reporta ese dato tal cual lo da `launchctl` (nunca inventa uno mejor), así que
   por ahora subestima la RAM real de ese proceso puntual. Documentado, no resuelto en esta ronda.
2. **Todavía no hay UI de dashboard para esto** — la interfaz real hoy es el chat (pedirle a Snarf
   "mostrame el estado de tus procesos"). Una vista visual dedicada queda para cuando le toque el
   turno a la Fase 9 completa del plan.
3. **Notion/VPS**: análisis y recomendación de VPS, tratados por separado (ver conversación) — esta
   ADR es específicamente sobre nombres de proceso + control básico, no sobre dónde debería correr
   Snarf a futuro.

## Verificado

- 10 tests nuevos: `tests/test_proctitle_exec.py` (3), `tests/test_process_control.py` (7: estado
  real/detenido/con pid "-", exclusión de `com.snarf.server` de reinicio, rechazo de un label
  desconocido, llamada real a `launchctl kickstart` con un label válido). Extensión de
  `tests/test_orchestrator.py` (+6: las dos tools nuevas vía `_handle_tool`, gateo real a
  no-fundador para ambas, protocolo de confirmación de `ops_process_restart`, rechazo explícito de
  reiniciar el server principal).
- 1195/1195 tests de la suite completa (`.venv/bin/python -m pytest -q`), incluidos los tests de
  cobertura del "protocolo de crecimiento" (`test_tool_to_node_covers_every_orchestrator_tool`,
  `test_verb_by_skill_covers_every_orchestrator_tool`,
  `test_detail_extractors_cover_every_orchestrator_tool`) — las dos tools nuevas están registradas en
  las tres tablas paralelas, no solo en `TOOLS`.
- Verificado en vivo (no solo en tests) contra los LaunchAgents reales de esta Mac: los tres procesos
  reiniciados responden con nombre real en `ps -o comm` y healthcheck en verde; `ops_process_status`
  corrido de verdad devuelve el estado real de los 6 LaunchAgents conocidos, incluidos los dos
  (`mlx-heavy`/`mlx-mid`) hoy descargados, reportados honestamente como `running: false` en vez de
  fallar o inventar un estado.
