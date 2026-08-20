# ADR 0178 — Protocolo de reporte de bugs con contexto real + clasificación automática, y baja de conversación continua

**Fecha:** 2026-08-19
**Estado:** Aceptado

## Contexto

Tras el incidente real de ADR 0177 (carta a la abuela), el fundador pidió un protocolo real para
reportar problemas sin perder el hilo: un botón accesible desde desktop y mobile que capture contexto
automáticamente, una vista de "mis reportes" con su estado, y un agente que clasifique y ayude a
resolverlos — con ejecución automática para severidad baja/media y confirmación explícita para críticos
(decisión tomada junto al fundador). De paso, pidió inhabilitar el botón de "Conversación continua (manos
libres)" del input — no funciona bien hoy, se retoma más adelante.

Mejores prácticas de 2026 investigadas (Sources: [Gleap — In-App Bug Reporting Guide](https://www.gleap.io/blog/in-app-bug-reporting-guide),
[bugpilot.io — Automated Bug Triage](https://bugpilot.io/2026/01/28/automated-bug-triage-ai-prioritization-reporting-guide/)):
capturar contexto automático en vez de pedirle todo al usuario, y mantener human-in-the-loop para casos
ambiguos/críticos — coincide con el protocolo de `confirmed` que este proyecto ya usa (Constitution
Art. VII).

## Decisión

**Fase 1 (esta ronda): reporte + contexto + clasificación automática. La ejecución de un fix en sí queda
para una ronda aparte** (ver "Consecuencias") — diseñar bien el sandboxing de código desatendido merece
su propia verificación en vivo, no algo empaquetado a último momento en una tanda ya grande.

**Backend — `snarf/specialists/bug_reports.py` (nuevo), mismo patrón que `project_manager.py`:** un JSON
por reporte (`data/bug_reports/{id}.json`). `create()` captura en silencio, vía `memory_provider` (no una
instancia fija — mismo criterio que `llm_factory` en `ProjectManager`, evita quedar con una referencia
vieja si `orchestrator._memory` se reemplaza después de construir, como pasa en tests reales de
`test_app.py`), el `conversation_id` y las últimas 4 turnos reales de esa conversación — esto es lo que le
permite a Snarf, en cualquier conversación futura, reconstruir "de qué se trataba" sin que el fundador lo
repita.

**Cuatro tools nuevas** (`bug_report_create/list/get/update_status`, `snarf/core/orchestrator.py`) —
reversibles, sin protocolo de `confirmed`. `bug_report_get` es la que usa Snarf cuando el fundador
pregunta por un reporte viejo, trayendo el contexto original real en vez de asumir que se acuerda solo.
Integradas al cerebro en el mismo cambio (regla de CLAUDE.md, aprendida en carne propia en ADR 0175):
nodo nuevo `specialist_bug_reports` en `snarf/telemetry/brain.py`/`verbs.py`/`detail.py` (los tres con
test de cobertura total) y en los espejos JS de `web/index.html`/`web/arquitectura.html`.

**Endpoint REST directo, no vía `/send`** (`POST /bug_reports`, `GET /bug_reports`, `GET /bug_reports/{id}`,
`PATCH /bug_reports/{id}/status`, `app.py`): reportar tiene que ser instantáneo y no depender de un turno
de LLM — la contextvar `snarf.telemetry.context` solo existe DENTRO de un turno real de
`Orchestrator.handle()`, así que el frontend manda `conversation_id` explícito en el body.

**Clasificación automática, nuevo loop periódico** (`_periodic_bug_triage_loop`, `app.py`, mismo patrón
que `_periodic_dashboard_curation_loop`, cada 15 min): un rol de ruteo nuevo `bug_triage`
(`snarf/runtime/llm_routing.py`, barato por default como `project_summary`/`dashboard_curator`) clasifica
cada reporte `nuevo` en `category`/`severity`/`plan` corto, y lo mueve a `planificado`. Nunca ejecuta un
fix por sí sola.

**Frontend (`web/index.html`):** botón 🐞 nuevo en tres lugares — toolbar del chat-dock desktop
(`#chatDockReportBugBtn`), barra superior de la vista clásica desktop (`#topChromeReportBugBtn`), y mobile
inmediatamente a la derecha de `#dashBtn` (`#bugReportBtn`, `right:16px` — `.project-home-btn` se corrió a
`right:100px` para no superponerse cuando ambos están visibles, decisión explícita del fundador). Los tres
abren el mismo modal liviano (textarea + "Enviar reporte"), que captura `conversationId`/`currentView` ya
trackeados por el propio frontend, sin pedirle nada más al fundador. Nueva pestaña "Mis reportes" en el
panel de conversaciones/proyectos (`#sidebar` y `#dashHistoryParked`, las dos instancias reales que ya
existían para Conversaciones/Proyectos).

**Conversación continua inhabilitada**: `#continuousModeBtn` (fila de entrada) queda con el atributo
`hidden` — no se borró el botón ni el bloque de soporte de ADR 0151 (~170 líneas de JS), mismo criterio
que `RunAtLoad` en los LaunchAgents (CLAUDE.md): instalado pero inerte, fácil de reactivar quitando
`hidden` cuando se retome.

**Por qué NO se tocó el protocolo de `confirmed` en sí**: las cuatro tools de reportes son reversibles por
diseño (crear/listar/leer/cambiar estado, nunca una acción de alto impacto), así que no lo necesitan —
ADR 0177 ya había señalado que el protocolo en sí no era la causa de la fricción real.

## Verificado

- `.venv/bin/python -m pytest -q` — 1531/1531 (1505 previos + 26 nuevos: `bug_reports.py` CRUD/
  normalización, las 4 tools vía `_handle_tool` incluida la captura real de `conversation_id` desde
  `context`, los 4 endpoints REST, `_classify_bug_report` con LLM real mockeado y con JSON malformado).
- Playwright real contra un server de prueba (puerto 8000, nunca el de producción): mobile (`bugReportBtn`
  visible, modal abre, reporte se envía, aparece en "Mis reportes" con estado `nuevo`) y desktop
  (`continuousModeBtn` ya no visible, `topChromeReportBugBtn` aparece al hover de la franja superior,
  igual que el resto de esa barra) — cero errores de consola en ambas pasadas. Datos de prueba borrados
  después de verificar.

## Consecuencias

- **Fase 2, pendiente, ronda aparte:** ejecución automática real de un fix (que un bug de severidad
  baja/media pase de `planificado` a resuelto sin que el fundador lo pida) — implica spawnear una sesión
  de Claude Code headless contra este repo, con guardrails reales (nunca `git push` ni reiniciar el server
  de producción sin confirmación explícita, solo investigar/corregir/testear/commitear local, mismo flujo
  ya probado en ADR 0173-0177 de esta sesión).
- El drawer de "Mis reportes" hoy solo lista (sin acciones de cambiar estado desde la UI) — el
  `PATCH /bug_reports/{id}/status` ya existe en el backend, listo para cuando se agregue esa interacción.
