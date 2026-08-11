# ADR 0140 — Fase 5: API de introspección real (agentes, tools, board ejecutivo)

**Fecha:** 2026-08-10
**Estado:** Aceptado

## Contexto

ADR 0139 (Fase 4, n8n self-hosted) dejó `GET /n8n/status` deliberadamente mínimo — reusa
`ops_health.system_health()`/`process_control.status()` tal cual, sin ninguna implementación nueva,
y dice explícitamente: *"una API de introspección real y más completa es trabajo de la Fase 5, no de
esta"*. Esta ADR cierra esa Fase 5 del plan de 12 fases aprobado con el fundador (observabilidad +
n8n + multi-usuario + cockpit, ver ADR 0135).

**Nota de honestidad real sobre esta ronda**: el texto exacto de qué debía cubrir la Fase 5 no quedó
guardado como documento en el repo — el plan de 12 fases se aprobó en una sesión anterior cuyo
historial de conversación ya no está disponible en esta. El alcance de esta ADR se reconstruyó desde
la evidencia real más fuerte que sí quedó escrita: la propia cita de ADR 0139 arriba, más el hallazgo
en ADR 0139/CHANGELOG de que el caso de uso "n8n edita un agente existente" queda bloqueado por las
Fases 5/6 (introspección real, Prompt Registry) — es decir, Fase 5 es la introspección de **qué
agentes/tools/roles existen realmente**, previa y necesaria para que Fase 6 (Prompt Registry, todavía
sin construir) pueda editarlos.

## Decisión

**`snarf/runtime/introspection.py` (nuevo), tres funciones puras + un agregador — cero
implementación nueva de ningún dato, solo agregación de lo que ya existe:**

- `agents_snapshot()`: ruteo real (proveedor/modelo) de cada uno de los roles de `llm_routing.ROLES`,
  leído de `llm_routing.load_routing()` — el mismo dato que ya alimenta `GET /llm_routing` para la
  Configuración del fundador. Cada entrada se etiqueta con su rol real del board de Inteligencia
  Ejecutiva si corresponde (`executive_board_role`, cruzado contra `ExecutiveRoleConfig.
  llm_routing_role`).
- `tools_snapshot()`: nombre + descripción real de cada tool del Orchestrator, filtrado por el mismo
  cálculo que ya usa `snarf/mcp/server.py::build_server()` (`MCP_EXPOSED_TOOLS - HIGH_IMPACT_TOOLS -
  BULK_READ_GATED_TOOLS`) — nunca un segundo allowlist. Deliberadamente sin `input_schema`:
  introspección es "qué puede hacer Snarf", no una superficie de invocación remota nueva — n8n
  observa y propone, nunca ejecuta tools directo (principio ya fijado en ADR 0139).
- `executive_board_snapshot()`: los 7 roles reales del board (`snarf/executive/roles.py::ROLE_CONFIGS`
  — rol, nombre visible, dominio), ya público en la propia UI de Configuración.
- `system_snapshot(*, active_user_sessions: int)`: agrega las tres anteriores. Recibe
  `active_user_sessions` como parámetro del llamador en vez de importar `app.py` — mismo criterio ya
  usado por `ops_health.system_health()` (recibe `llm_available`/`google_available`/`recent_activity`
  como parámetros, nunca va a buscarlos él mismo), evita un import circular real (`app.py` ya importa
  `snarf.runtime.introspection`).

**`GET /n8n/introspect` (nuevo, `app.py`)**: mismo `require_n8n_token` que `/n8n/status` (header
`X-Snarf-Token`, `N8N_CONTROL_TOKEN`) — nunca la cookie de sesión del founder, mismo criterio de ADR
0139. `active_user_sessions` se calcula contando el registro real `_orchestrators` (Fase 3, ADR 0137)
bajo su lock existente, sin ninguna instrumentación nueva.

**Por qué un endpoint nuevo y no extender `/n8n/status`**: responsabilidades distintas — `/n8n/status`
es un chequeo de salud (¿está Snarf vivo, qué procesos corren?), `/n8n/introspect` es un catálogo
(¿qué agentes/tools/roles existen, con qué modelo corre cada uno?) — un workflow de n8n que arma un
dashboard de estado no necesita descargar el catálogo completo en cada poll, y viceversa.

## Alcance explícitamente fuera de esta ADR

- **Editar** cualquier agente/prompt/ruteo desde n8n — eso sigue siendo Fase 6 (Prompt Registry), no
  construida. Esta ADR es puramente de lectura, mismo principio "n8n observa y propone" de ADR 0139.
- Exponer el `system_prompt` real de cada Specialist/rol ejecutivo — son potencialmente largos y su
  edición es justamente el problema que resuelve Fase 6; esta ADR expone solo metadata (qué rol, qué
  modelo, qué dominio), nunca el contenido del prompt.
- Estado de ejecución en vivo más allá del conteo de sesiones activas (spans en curso, último turno
  por usuario) — no se encontró evidencia de que estuviera en el alcance real de la Fase 5 tal como se
  la puede reconstruir hoy; se deja para si el fundador lo pide explícitamente, en vez de inventarlo.

## Verificado

- 10 tests nuevos: `tests/test_introspection.py` (6 — ruteo real por rol, etiquetado de roles del
  board ejecutivo, `tools_snapshot()` nunca expone un `HIGH_IMPACT_TOOLS` ni un nombre fuera del
  allowlist de MCP, descripciones reales idénticas a `orchestrator.TOOLS`, los 7 roles del board,
  agregación completa). `tests/test_app.py` (+3 — `GET /n8n/introspect`: 401 sin token, 503 sin
  configurar, 200 con agentes/tools/board/sesiones activas reales).
- 1221/1221 tests de la suite completa (`.venv/bin/python -m pytest -q`), 1211 previos + 10 nuevos.
