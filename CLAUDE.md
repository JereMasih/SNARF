# CLAUDE.md

Índice para sesiones de Claude Code en este repo. No repite contenido — apunta a dónde mirar.

## Antes de tocar código

- `MASTER_MAP.md` es el plano maestro del ecosistema — leelo primero para ubicar en qué Dominio cae el pedido (Identity, Governance, Cognition, Knowledge, Architecture, Capabilities, Business, Infrastructure, Roadmaps). Su "Regla de crecimiento": si algo nuevo no encaja en el mapa, primero evoluciona el mapa.
- `FOUNDATION.md` / `CONSTITUTION.md` / `CHARACTER.md` / `COGNITION.md`: identidad y gobernanza del proyecto. Principio VI de FOUNDATION.md (Honestidad Intelectual) rige también el propio trabajo de Claude en este repo: nunca presentar datos inventados como reales — construir el cerebro de Snarf, por ejemplo, se hizo estrictamente desde telemetría real (`activity_log`, `usage_log`, `input_log`), nunca con datos de relleno.
- `adr/` tiene una decisión por archivo, numeradas; `CHANGELOG.md` tiene una entrada por ADR con conteo de tests. Todo cambio de arquitectura real (no un fix trivial) se documenta en ambos.
- `ROADMAP_OBSERVABILIDAD_MULTIUSUARIO_N8N.md` es el plan vivo en curso (observabilidad, multi-usuario, n8n, memoria semántica) — tiene su propia sección "Estado actual" al tope para retomar sin preguntar de nuevo qué falta. Vive en el repo (no en `~/.claude/plans/`) a propósito: un plan de `ExitPlanMode` no es fiable entre sesiones — pasó de verdad que una sesión nueva no pudo leerlo y tuvo que reconstruir alcance desde un ADR. Cualquier plan multi-sesión futuro de este tipo debería vivir acá también, no solo en el plan mode.

## Convenciones de este repo

- Tests con `.venv/bin/python -m pytest -q` (54 archivos en `tests/`, suite completa corre en segundos). Correr la suite completa antes de dar por terminado cualquier cambio de backend.
- Cambios de frontend (`web/index.html`, un solo archivo grande): no alcanza con que compile — verificar en un navegador real (Playwright) antes de reportar terminado, especialmente drag/resize/reparentado de DOM vivo.
- DOM con estado (chat, historial de conversaciones, sidebar de mobile): reparentar (`appendChild` sobre el nodo existente) en vez de reconstruir por HTML — reconstruir pierde listeners y estado.
- Gotcha real de Python ya mordido una vez: `bool` es subclase de `int` — cualquier validación de `isinstance(x, int)` sobre un valor que puede venir de un payload externo necesita excluir `bool` explícitamente (ver `snarf/runtime/dashboard_prefs.py`).
- Mensajes de commit: en español, breves, sin firma manual del asistente salvo el trailer `Co-Authored-By` ya estándar de Claude Code. Ver `git log` para el tono real.
- Server real de producción corre en el puerto 8002 gestionado por un LaunchAgent de macOS (`~/Library/LaunchAgents/com.snarf.server.plist`, `RunAtLoad`+`KeepAlive`, 2026-08-04) — sobrevive reposo/logout y se relanza solo si el proceso muere por cualquier motivo; reemplazó al viejo `nohup`+`disown` (ya no alcanza con un `kill` simple: hay que `launchctl bootout gui/501/com.snarf.server` para pararlo de verdad, y `launchctl bootstrap gui/501 <plist>` para levantarlo). No confundir con instancias de prueba en 8000/8001. Si hace falta reiniciarlo, confirmar con el fundador primero.
- Gotcha real ya mordido con ese LaunchAgent: procesos lanzados por `launchd` (a diferencia de los lanzados desde una Terminal interactiva) no heredan acceso a carpetas protegidas por TCC (Documents/Desktop/Downloads) — hace falta otorgar Acceso Total al Disco al binario real de Python (`Ajustes → Privacidad y Seguridad`) para que pueda ni siquiera hacer `chdir` a este repo. Y aun con ese permiso otorgado, `StandardOutPath`/`StandardErrorPath` del plist **no pueden apuntar dentro de Documents** — `launchd` abre esos archivos con su propia identidad antes del exec, no con la del binario ya autorizado, y falla con `exit 78 (EX_CONFIG)` sin loguear nada. Por eso el log real vive en `~/Library/Logs/snarf/server_8002.log` (fuera de Documents) con un symlink `server_8002.log` en la raíz del repo apuntando ahí, para no romper el hábito de `tail server_8002.log`.

## Skills vs. MCP en este repo

Política acordada con el fundador (2026-07-29), para cómo equipamos a Claude Code en este proyecto — no es una decisión de arquitectura de Snarf-producto (ver más abajo):

- **Default: Skill**, no MCP. Una Skill es solo una carpeta (`.claude/skills/<nombre>/SKILL.md` + scripts opcionales) versionable en git, con divulgación progresiva real (metadatos → instrucciones → recursos/scripts, cada nivel se carga solo si hace falta). Hoy no hay ninguna Skill ni servidor MCP configurado, ni acá ni globalmente — está todo por construir.
- **MCP solo cuando es la única puerta de entrada real** a una fuente externa (no cuando ya existe un SDK/API directa como Google/Anthropic/ElevenLabs/Voyage, que es el caso de todas las integraciones de Snarf). Ningún candidato real identificado todavía para este repo.
- Candidatos concretos de Skill para este repo, todavía sin construir: la convención exacta de ADR+CHANGELOG+MASTER_MAP (hoy se re-deriva leyendo ADRs viejos cada sesión); el smoke-check de Playwright (login, dashboard, cero errores de consola); la receta de reinicio del server real (LaunchAgent `com.snarf.server`, puerto 8002 — ver Convenciones arriba).
- **Por qué Snarf-el-producto en general tampoco usa MCP para la mayoría de sus herramientas** (pregunta distinta, sobre la arquitectura del `Orchestrator`, no sobre cómo trabaja Claude Code acá): MCP resuelve "un mismo set de herramientas reusado por múltiples clientes distintos" — para el propio Orchestrator, Snarf tiene un solo consumidor de sus herramientas, así que meter un proceso servidor/protocolo/transporte de por medio no compra nada ahí. Tool-use nativo de Anthropic (`_tool_handlers`) sigue siendo la versión más simple posible de esa integración. Ver ADR 0037.
- **Reapertura acotada (2026-08-04, ver ADR 0093):** con la Inteligencia Ejecutiva (board asesor de 7 roles, corren como procesos separados del Orchestrator — ver COGNITION.md/ADR 0094) apareció el primer segundo consumidor real de las herramientas de Snarf. Ahí sí se usa MCP — transporte stdio, allowlist de solo lectura, delega siempre a `Orchestrator._handle_tool()` (nunca una segunda implementación de la lógica de un tool). Sigue sin usarse MCP para el Orchestrator principal ni para nada con un solo consumidor real.

## Costo/tokens de esta sesión

- `snarf/capabilities/anthropic_llm.py` ya cachea system+tools (breakpoint fijo) y el último mensaje de cada llamada/ronda del loop de herramientas (breakpoint móvil, TTL de 1h). Si se toca ese archivo, no romper ninguno de los dos breakpoints — hay tests dedicados en `tests/test_anthropic_llm.py`.
- Preferencia del fundador: sesiones largas y continuas están bien, pero al cerrar una tanda grande de features (varios ADRs seguidos) es buen momento para `/clear` antes de arrancar la siguiente, en vez de seguir acumulando contexto indefinidamente.
