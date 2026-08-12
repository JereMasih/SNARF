# ADR 0157 — Agent/Capability Registry: tool_subset, conexiones, y versionado de routing

**Fecha:** 2026-08-12
**Estado:** Aceptado

## Contexto

ADR 0156 (Fase 15) autorizó que el fundador, confirmando en vivo desde n8n, pueda reconfigurar cualquier
eje de la construcción de un agente del Executive Board — no solo el texto del prompt (ya versionado desde
ADR 0141/0153 vía `snarf/runtime/prompt_registry.py`), también qué herramientas MCP tiene, qué modelo/
ruteo usa, y cómo se conecta/secuencia con otros roles. Verificado en código antes de diseñar: el ruteo de
modelo (`llm_routing_role`) ya era editable en runtime (`PUT /llm-routing`, `app.py:1024`) pero sin
historial ni rollback; `mcp_tool_subset` (`ROLE_TOOL_SUBSETS`, `snarf/mcp/tools.py:39`) no era editable en
absoluto — constante Python leída client-side en `snarf/executive/process.py`; y ningún concepto de
conexión/secuencia entre roles existía en ningún lado — `ExecutiveBoardSpecialist.consult()`
(`snarf/executive/specialist.py:74`) es 100% fan-out paralelo.

Esta ADR construye el registro que cierra esas tres brechas — el "estado versionado" que ADR 0156 exige
como intermediario obligatorio entre cualquier escritura (n8n confirmado, cockpit del founder, o el propio
Orchestrator) y lo que corre en runtime. Sin código de motor de ejecución todavía (eso es Fase 17, ADR
0158) ni de superficie n8n (Fase 18/19) — solo el registro y su validación.

## Decisión

Tres módulos nuevos en `snarf/runtime/`, mismo shape "JSON-por-entidad" (versionado, historial, rollback,
"nada cambia el día del corte") ya probado por `prompt_registry.py`, más una extensión aditiva de
`llm_routing.py`:

1. **`tool_subset_registry.py`** (`data/tool_subsets.json`) — versiona `tool_subset` por rol.
   `get_active_subset(role, default)` devuelve `ROLE_TOOL_SUBSETS[role]` (comportamiento actual) si nunca
   se guardó nada. `save_new_version()` valida que el subset nuevo sea subconjunto de `MCP_EXPOSED_TOOLS`
   (`snarf/mcp/tools.py`) — rechazo temprano, no la superficie de seguridad real: el gate autoritativo
   sigue siendo `snarf/mcp/server.py::build_server()` (`MCP_EXPOSED_TOOLS - HIGH_IMPACT_TOOLS -
   BULK_READ_GATED_TOOLS`), y `_MCPToolBridge.start()` ya filtra lo que el server realmente sirve por este
   subset — un nombre guardado acá que el server no sirve nunca llega a exponerse. Deliberadamente **no
   importa `snarf.core.orchestrator`** (donde viven `HIGH_IMPACT_TOOLS`/`BULK_READ_GATED_TOOLS`): ese
   import crearía un ciclo real, porque `orchestrator.py` ya importa `snarf.executive.specialist`, que en
   Fase 17 pasa a importar este módulo.
2. **`agent_graph_registry.py`** (`data/agent_graph.json`) — versiona las "stages" de ejecución del board:
   una lista de listas de roles (`[["cto","coo"], ["ceo"]]` = paralelo primero, secuencial después).
   Default sin overrides: una sola stage con los 7 roles (el fan-out actual, cero regresión). Valida que
   cada rol exista en `ROLE_CONFIGS`, que ninguna stage esté vacía, y que ningún rol se repita entre
   stages — no hace falta detección de ciclos genérica, es una lista ordenada, no un grafo arbitrario.
3. **Extensión de `llm_routing.py`**: `routing_history()`/`save_routing_versioned()`/`rollback_routing()`
   nuevos, respaldados por un archivo paralelo (`data/llm_routing_history.json`) — **aditivo**, nunca toca
   el shape plano de `data/llm_routing.json` que `build_llm()`/`_ResilientLLM` ya leen en caliente cada
   turno. El fallback automático (`attempt_fallback`/`maybe_revert_expired_fallback`) sigue llamando a
   `save_routing()` directo, sin versionar — versionar reintentos automáticos ensuciaría el historial que
   el founder/n8n necesitan para saber qué fue una elección real. Solo escrituras reales (cockpit,
   n8n confirmado) deben pasar por `save_routing_versioned()`.
4. **`agent_registry.py`** — módulo de composición sin storage propio. `get_agent_recipe(agent_id)` junta
   los cuatro ejes (prompt + tools + routing + stages) de un rol del board, cada uno con su valor activo y
   su historial. Es el único punto de lectura que deben usar las Fases 17 (motor de stages), 18 (generador
   n8n) y 19 (endpoints `propose`/`apply`) — nunca leer los cuatro registros sueltos por su cuenta, mismo
   principio de chokepoint único que ya rige `Orchestrator._handle_tool()`.

**Alcance honesto, explícito en el ADR:** `tool_subset` y `stages` son ejes específicos del Executive
Board — el único patrón MCP-multi-proceso que existe hoy en el repo. Los demás Specialists
(`snarf/specialists/*`) no tienen ningún concepto de "MCP tool subset" propio ni participan de ninguna
secuencia entre agentes; forzarles esos dos ejes sería inventar una capacidad que el código no sostiene
(Principio VI, FOUNDATION.md — nunca presentar como real algo que no lo es). `get_agent_recipe()` por eso
solo resuelve los 7 roles del board por ahora; generalizarlo queda para cuando un consumidor real (Fase 18
u otro) lo necesite, no antes.

## Riesgo real, explícito

Mismo riesgo ya identificado en ADR 0156 para la categoría "fundador confirmado": un `tool_subset` mal
configurado podría dejar a un rol sin ninguna herramienta útil, o unas stages mal pensadas podrían generar
una secuencia que tarda mucho sin aportar valor. Mitigado acá con validación dura en cada `save_new_version()`
(nunca confiar en que la UI de n8n por sí sola previno un estado inválido) — nada de esto puede dejar el
sistema en un estado roto de forma silenciosa, solo potencialmente subóptimo, siempre reversible por
rollback.

## Verificado

- 26 tests nuevos: `tests/test_tool_subset_registry.py` (9), `tests/test_agent_graph_registry.py` (8),
  `tests/test_agent_registry.py` (4), extensión de `tests/test_llm_routing.py` (5) — cubren: comportamiento
  idéntico al hardcodeado sin overrides, historial/rollback real en los cuatro ejes, rechazo de un
  `tool_subset` fuera de `MCP_EXPOSED_TOOLS`, rechazo de un rol desconocido o repetido en las stages, y que
  el fallback automático de `llm_routing` nunca ensucia el historial versionado.
- 1336/1336 tests de la suite completa (`.venv/bin/python -m pytest -q`), 1310 previos (post ADR 0155) +
  26 nuevos.
