# ADR 0097 — Servidor MCP real: allowlist, `snarf/mcp/`, cuarto punto de entrada

**Fecha:** 2026-08-04
**Estado:** Aceptado

## Contexto

Fase D del plan de expansión "Inteligencia Ejecutiva" (ver ADR 0093, que fijó la decisión de gobernanza de reabrir MCP para este caso puntual). Esta ADR es la implementación real: el paquete `mcp` (SDK oficial, `modelcontextprotocol.io`) no estaba instalado — se instaló y se inspeccionó campo por campo (versión real instalada: **2.0.0**, con una API bastante distinta de lo asumido en el diseño original de ADR 0093, que hablaba de `mcp.server.Server`/`mcp.server.fastmcp.FastMCP`: esta versión usa `mcp.server.mcpserver.MCPServer`, con `add_tool(fn, ...)` que construye el JSON Schema introspeccionando la firma de una función Python, no aceptando un schema crudo directo).

## Decisión

1. **`snarf/core/orchestrator.py` suma dos constantes nombradas**: `HIGH_IMPACT_TOOLS` (los 11 tools reales de confirmación en dos pasos, ADR 0015) y `BULK_READ_GATED_TOOLS` (los 6 tools reales de `_bulk_read_gate`, ADR 0067) — antes conocimiento tribal repartido en los métodos que llaman a `_pending()`/`_bulk_read_gate()`, ahora un hecho chequeable por test.
2. **`snarf/mcp/tools.py`**: `MCP_EXPOSED_TOOLS` — allowlist positivo, explícito, de 17 tools reales (nunca derivado por exclusión). Dos ejes, no solo "solo lectura": se excluye también lectura cruda de contenido personal (`drive_read_file`, `gmail_read_message`, `get_conversation`, `search_memory`) — solo entran resultados ya agregados/filtrados. Suma `telemetry_cost_summary` (tool nuevo, ver punto 4) para que el allowlist tenga algo real que ofrecerle al rol CFO de Inteligencia Ejecutiva (ADR 0094), en vez de dejarlo con cero tools. También `ROLE_TOOL_SUBSETS`: sub-allowlist por rol (7), cada uno subconjunto verificado del allowlist general.
3. **`snarf/mcp/server.py::build_server()`**: dado que el SDK real construye el schema por introspección de función, cada tool expuesto genera dinámicamente un wrapper Python con firma tipada real (a partir del `input_schema` ya existente en `orchestrator.TOOLS` — nunca un schema escrito dos veces a mano) cuyo cuerpo delega, sin excepción, a `Orchestrator._handle_tool()`. Filtra explícitamente `HIGH_IMPACT_TOOLS`/`BULK_READ_GATED_TOOLS` del allowlist como defensa en profundidad, aunque ninguno esté hoy en `MCP_EXPOSED_TOOLS`.
4. **Tool nuevo `telemetry_cost_summary`** (Orchestrator, aditivo): wrapper fino sobre `usage_tracker.summarize()`, ya existente y real — costo real de operar Snarf por vendor, nunca caja/ingresos del negocio del fundador (ese dominio sigue vacío, ver KNOWLEDGE.md). Sin este tool, el rol CFO de Inteligencia Ejecutiva (ADR 0094) hubiera quedado con cero competencia real.
5. **`mcp_server.py`** (raíz): cuarto punto de entrada, hermano de `main.py`/`main.py --voice`/`app.py`, transporte stdio (sin puerto, proceso hijo por sesión — menor superficie real que un server de red).
6. **Nueva dependencia real, pineada**: `mcp==2.0.0` en `requirements.txt`.

## Verificado

- 8 tests nuevos (`tests/test_mcp_server.py`): allowlist ⊆ tools reales del Orchestrator; disjunto de `HIGH_IMPACT_TOOLS`/`BULK_READ_GATED_TOOLS`; cada sub-allowlist de rol ⊆ allowlist general; `list_tools()` devuelve exactamente el allowlist; llamar un tool fuera del allowlist (`drive_delete_file`, real, existe en el Orchestrator) falla antes de tocar `_handle_tool`; el resultado vía MCP coincide con `_handle_tool` directo; parámetros opcionales no provistos nunca se pasan como `None` explícito.
- **Smoke test real de punta a punta**: `mcp_server.py` levantado como subproceso real, conectado con un `ClientSession` real vía stdio (no mockeado) — `list_tools()` devolvió los 17 tools reales, `call_tool("get_current_datetime", {})` devolvió una fecha/hora real vía el camino completo (cliente MCP → subproceso → `Orchestrator._handle_tool` → resultado real).
- 740/740 tests de la suite completa.

## Consecuencias

- Primer y único segundo consumidor real de las herramientas de Snarf. Cualquier tool nuevo que se agregue al Orchestrator queda automáticamente fuera del allowlist MCP hasta que alguien lo sume explícitamente a `MCP_EXPOSED_TOOLS` — nunca expuesto por accidente.
- La API del SDK `mcp` puede seguir cambiando (es un proyecto joven, ya en su segunda versión mayor) — `build_server()` concentra toda la superficie de acoplamiento real al SDK en un solo archivo, para que una futura ruptura de API se resuelva en un lugar, no desperdigada.
