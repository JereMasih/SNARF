# ADR 0152 — Fase 11: `system_introspect` como tool real, expuesto por MCP

**Fecha:** 2026-08-11
**Estado:** Aceptado

## Contexto

Fase 11 del roadmap (`ROADMAP_OBSERVABILIDAD_MULTIUSUARIO_N8N.md`): *"El servidor MCP ya existe y ya
expone un allowlist a un segundo consumidor real. Sumar tools de introspección de solo lectura (Fase 5)
a `MCP_EXPOSED_TOOLS`, evaluando un subset de rol propio para Claude Code — siempre delegando a
`Orchestrator._handle_tool()`."*

**Corrección real encontrada al investigar** (cambia el diseño, no solo lo confirma): la Fase 5
(`adr/0140-*`) nunca creó un tool real de introspección — creó tres funciones puras en
`snarf/runtime/introspection.py` (`agents_snapshot`/`tools_snapshot`/`executive_board_snapshot`/
`system_snapshot`) consumidas SOLO por `GET /n8n/introspect`, un endpoint HTTP aparte, nunca por
`Orchestrator._handle_tool()`. No había "tools de introspección" ya existentes para sumar al
allowlist — había que crear el tool primero.

## Decisión

**Nuevo tool real `system_introspect`** (`snarf/core/orchestrator.py`, `TOOLS` + dispatch dict): sin
parámetros, delega a `introspection.system_snapshot()` — mismo dato real que ya usa `GET
/n8n/introspect`, nunca una segunda implementación.

**Rotura de un ciclo de import real**: `introspection.py` importaba `TOOLS`/`HIGH_IMPACT_TOOLS`/
`BULK_READ_GATED_TOOLS` directo de `snarf.core.orchestrator` — agregar un tool DENTRO de
`orchestrator.py` que llame a `introspection.system_snapshot()` habría creado
`orchestrator.py → introspection.py → orchestrator.py`. Se resolvió pasando `tools`/`safe_tool_names`
como parámetros (mismo criterio ya usado por `active_user_sessions`, y por `ops_health.system_health()`:
este módulo nunca sale a buscar sus propias señales). `app.py::/n8n/introspect` ahora arma esos dos
parámetros con sus propios imports de `orchestrator.py`/`snarf.mcp.tools`, sin cambiar su contrato HTTP
externo.

**`active_user_sessions` pasa a ser opcional (`None` por default)**: un consumidor MCP de sesión única
(Claude Code u otro cliente externo) no tiene forma real de saber cuántas sesiones web activas hay —
`None` es la respuesta honesta, nunca un cero inventado. `GET /n8n/introspect` lo sigue calculando real
(cuenta `_orchestrators` bajo lock) y pasándolo explícito, sin cambios de comportamiento ahí.

**`system_introspect` sumado a `MCP_EXPOSED_TOOLS`** (`snarf/mcp/tools.py`) — ya queda expuesto por
`snarf/mcp/server.py::build_server()` a cualquier consumidor MCP conectado, sin código nuevo ahí.

**Protocolo de crecimiento del cerebro, aplicado de verdad**: sumado a `TOOL_TO_NODE`
(`snarf/telemetry/brain.py`, tier `utility`, junto a `telemetry_cost_summary`/`get_current_datetime`).
Al correr la suite completa aparecieron dos regresiones reales más allá del cerebro —
`DETAIL_EXTRACTORS` (`snarf/telemetry/detail.py`) y `VERB_BY_SKILL` (`snarf/telemetry/verbs.py`) tienen
el MISMO tipo de test de cobertura total sobre `orchestrator.TOOLS` que `brain.py`, y ambos fallaron
hasta sumar las entradas correspondientes — evidencia real de que el protocolo de "toda tool nueva se
integra en el mismo cambio" no es solo sobre el cerebro visual, son 3 registros reales que hay que
mantener sincronizados cada vez.

**Decisión explícita: NO se creó un subset `ROLE_TOOL_SUBSETS["claude_code"]`.** Investigando el
mecanismo real (`snarf/executive/process.py::_MCPToolBridge`), la restricción por rol
(`role_config.mcp_tool_subset`) se aplica del lado del CLIENTE (`_async_start` filtra
`session.list_tools()` localmente) — es un mecanismo interno de cómo la Inteligencia Ejecutiva usa su
propio bridge, no algo que el SERVIDOR (`build_server()`) aplique por identidad de consumidor.
`build_server()` expone el mismo allowlist completo (`MCP_EXPOSED_TOOLS - HIGH_IMPACT_TOOLS -
BULK_READ_GATED_TOOLS`) a CUALQUIER cliente conectado, sin distinguir quién es. Inventar un
`ROLE_TOOL_SUBSETS["claude_code"]` sin ningún punto real de aplicación sería scaffolding decorativo —
si en el futuro aparece una razón real para restringir qué ve Claude Code específicamente, hace falta
primero un mecanismo real de identidad de consumidor del lado del servidor (no construido acá, sin
evidencia de necesidad todavía).

**Fuera de alcance, a propósito**: registrar `mcp_server.py` como servidor MCP de ESTE repo para que
Claude Code (esta misma sesión) se conecte de verdad (`.mcp.json` o config equivalente) es una decisión
distinta, ya cubierta por la política "Skills vs. MCP" de `CLAUDE.md` — que dice explícitamente que hoy
no hay ningún candidato real identificado para eso. No se creó acá.

## Verificado

- 3 tests nuevos: `tests/test_orchestrator.py` (dispatch real de `system_introspect`, `active_user_sessions
  is None` por el camino normal del Orchestrator), `tests/test_introspection.py` (`system_snapshot` sin
  `active_user_sessions` explícito → `None`). Los tests existentes de `tools_snapshot`/`system_snapshot`
  actualizados a la nueva firma (`tools`, `safe_tool_names` como parámetros).
- `tests/test_mcp_server.py`/`tests/test_brain.py` (cobertura genérica, sin cambios de código) confirman
  automáticamente: `system_introspect` expuesto por `build_server()`, nunca gateado, con nodo real en el
  cerebro.
- 1290/1290 tests de la suite completa (1288 previos + 2 nuevos — el tercero reemplazó un assert dentro
  de un test ya existente de `test_introspection.py`).
