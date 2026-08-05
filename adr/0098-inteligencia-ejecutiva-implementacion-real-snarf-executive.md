# ADR 0098 — Inteligencia Ejecutiva: implementación real (`snarf/executive/`)

**Fecha:** 2026-08-04
**Estado:** Aceptado

## Contexto

Fase E del plan de expansión "Inteligencia Ejecutiva". ADR 0094 ya fijó el modelo de autoridad
(cero autoridad inherente, allowlist estructural vía MCP, disciplina de honestidad obligatoria);
ADR 0093/0097 ya construyeron el transporte (servidor MCP real, allowlist por rol en
`snarf/mcp/tools.py::ROLE_TOOL_SUBSETS`). Esta ADR es la implementación real de los 7 roles en sí.

## Decisión

1. **Arquitectura de proceso real, no in-process.** `snarf/executive/process.py::consult_role()`
   levanta `mcp_server.py` como subproceso stdio por cada consulta a un rol — es la razón concreta
   por la que se reabrió MCP (ADR 0093): sin esto, ese trabajo no tendría ningún consumidor real.
   `AnthropicLLM.generate()` es síncrono y llama a `tool_handler()` síncronamente desde dentro de su
   propio loop de rondas, pero una sesión de cliente MCP real (`stdio_client`/`ClientSession`) es
   asincrónica de punta a punta — `_MCPToolBridge` resuelve el cruce corriendo la sesión en un hilo
   propio con su loop de asyncio activo (`run_forever`) y exponiendo un `call_tool()` síncrono que
   bloquea vía `run_coroutine_threadsafe` hasta el resultado real.
2. **7 roles, una clase, N configs** (`snarf/executive/roles.py::ExecutiveRoleConfig`, mismo
   precedente que `llm_routing.PROVIDER_PRESETS`): cada rol reusa, sin duplicar, el
   `mcp_tool_subset` ya definido en `ROLE_TOOL_SUBSETS` (ADR 0097) — una sola fuente de verdad de
   qué puede leer cada rol.
3. **Disciplina de honestidad verificada en código, no confiada al self-report del modelo**
   (`snarf/executive/opinion.py::parse_opinions`): cada rol responde en un formato fijo
   (`HEADLINE:` + líneas `CLAIM: ... | BASIS: ... | FUENTE: ...`). Una línea que se autodeclara
   `BASIS='hecho'` pero cuya `FUENTE` no es el nombre EXACTO de un tool realmente invocado en ese
   turno (rastreado por `consult_role` vía el propio `tool_handler`) se degrada mecánicamente a
   `inferencia` antes de devolverse — mismo criterio que `DashboardCuratorSpecialist` ya usa con sus
   `node_id` reales.
4. **7 roles corren en paralelo, sin visibilidad entre sí**
   (`snarf/executive/specialist.py::ExecutiveBoardSpecialist.consult`, `ThreadPoolExecutor`) — un rol
   que falla (proveedor caído, excepción real) nunca tira abajo a los demás; postura de gobernanza
   (Art. IV, ningún rol se ancla al framing de otro), no solo de latencia.
5. **`build_resilient_llm` en vez de `build_llm`** para el ruteo de cada rol
   (`llm_factory_for_role=lambda role: llm_routing.build_resilient_llm(f"executive_{role}")`,
   `orchestrator.py`) — reusa el mecanismo de fallback automático entre proveedores que ya está
   integrándose al resto del wiring real de Snarf en esta misma ronda, en vez de que Inteligencia
   Ejecutiva quede como el único wiring nuevo sin esa resiliencia.
6. **Tool nuevo del Orchestrator, `executive_board_consult(question, roles=None)`** — no lleva el
   protocolo de confirmación en dos pasos (ADR 0015): es de solo lectura/asesoría, ningún rol puede
   mutar nada (garantía estructural de la Fase D, no solo de prompt). `roles=None` consulta a los 7;
   SYSTEM_PREFIX instruye a Snarf a acotar a los roles relevantes y a nunca llamarla por cuenta
   propia.
7. **Cache-first + persistencia, mismo patrón que `GmailDigestSpecialist`/`DashboardCuratorSpecialist`**:
   cada `consult()` real persiste en `data/executive_board/<user_id>.json`. Widget nuevo
   `GET /dashboard/widgets/executive_board` sirve ese cache sin disparar una consulta nueva en cada
   poll; `POST /dashboard/widgets/executive_board/consult` la dispara de verdad.

## Verificado

- 33 tests nuevos (`tests/test_executive_opinion.py`, `tests/test_executive_roles.py`,
  `tests/test_executive_process.py`, `tests/test_executive_specialist.py`, más 3 del widget en
  `tests/test_app.py`): degradación honesta hecho→inferencia sin fuente real; matching de fuente
  exacto (no substring); paralelismo real vía `ThreadPoolExecutor`; un rol fallando no afecta a los
  demás; `_MCPToolBridge` reemplazado por un fake en tests unitarios (nunca levanta un subproceso
  real ahí); cobertura automática de `TOOL_TO_NODE`/`VERB_BY_SKILL`/`DETAIL_EXTRACTORS` para
  `executive_board_consult` (mismos tests de protocolo de crecimiento de ADR 0054).
- **Smoke test real de punta a punta, fuera de la suite automatizada** (mismo criterio que el de
  ADR 0097: gasta tokens reales, no se corre en cada `pytest`): `Orchestrator.executive_board.consult()`
  real, rol `cto`, subproceso `mcp_server.py` real, sesión MCP real, llamada real a
  `knowledge_index_status`. El rol respondió honestamente que el dominio `code` de la Knowledge
  Layer todavía no tiene nada indexado (nunca se corrió `knowledge_index_start` en producción) en
  vez de fabricar una evaluación — la disciplina de honestidad funcionó de punta a punta con datos
  reales, no solo en un test con fixtures.
- 790/790 tests de la suite completa.

## Consecuencias

- Primer Especialista Cognitivo real que corre fuera del proceso del Orchestrator — todo el resto
  de este repo sigue siendo in-process; este patrón (`_MCPToolBridge`) queda como el único lugar que
  necesita el cruce síncrono/asíncrono, no se generaliza a nada más sin una razón nueva igual de
  concreta.
- `executive_board_consult` queda deliberadamente fuera de `MCP_EXPOSED_TOOLS` — ningún rol puede
  convocar al board (incluso a sí mismo), evita cualquier forma de recursión o de un rol
  "hablando" a través de otro.
- CFO/CMO/Chief Creative Officer siguen con datos reales delgados (ver ADR 0097) hasta que las
  ramas Finance/Community/Content (Fase I) estén construidas — consecuencia honesta y ya prevista,
  no una limitación nueva de esta ADR.
