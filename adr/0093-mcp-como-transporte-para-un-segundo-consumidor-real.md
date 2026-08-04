# ADR 0093 — MCP como transporte para un segundo consumidor real

**Fecha:** 2026-08-04
**Estado:** Aceptado

## Contexto

CLAUDE.md registra, desde ADR 0037, la política de no usar MCP para las herramientas propias de Snarf: "Snarf tiene un solo consumidor de sus propias herramientas (su propio Orchestrator), así que meter un proceso servidor/protocolo/transporte de por medio no compra nada. Tool-use nativo de Anthropic (`_tool_handlers`) ya es la versión más simple posible de esa integración."

Esa premisa deja de sostenerse con la Inteligencia Ejecutiva (ver COGNITION.md, sección "Especialistas de proceso separado", y ADR 0094): un board de 7 roles asesores que corren como procesos separados del Orchestrator principal, no como Especialistas in-process. Esos procesos necesitan tool-calling nativo contra un subconjunto de las herramientas de Snarf sin ser el Orchestrator — son el primer segundo consumidor real que este repo tiene.

## Decisión

1. **Esto no toca el despacho de las 60+ herramientas del Orchestrator.** `TOOLS`, `_tool_handlers` y el tool-use nativo de Anthropic siguen exactamente igual. MCP es aditivo, acotado específicamente a este segundo consumidor nuevo — nunca un reemplazo del camino existente.
2. **Transporte MCP stdio** — sin puerto, sin superficie de autenticación de red, proceso hijo por sesión. Es el transporte con menor superficie de ataque/operación real que satisface el requisito, mismo criterio que ya usó ADR 0015 para elegir el mecanismo más simple posible de confirmación en dos pasos.
3. **Nueva dependencia `mcp` en `requirements.txt`.** Su forma real (`mcp.server.Server` vs. `mcp.server.fastmcp.FastMCP`, firmas exactas) se verifica campo por campo contra el SDK realmente instalado al momento de implementar (Fase D de este plan) — misma disciplina que ADR 0068 ya exigió para los proveedores de LLM alternativos.
4. **Actualiza la sección "Skills vs. MCP" de CLAUDE.md**, sumando el motivo de esta reapertura, sin borrar la política de equipamiento de Claude Code (ese es un tema distinto, sigue vigente sin cambios).
5. **Supersede parcialmente solo la sección MCP de ADR 0037** — el resto de esa ADR (layout del dashboard, malla del cerebro) queda intacto. Conforme al Artículo VIII de Constitution, este registro no edita ADR 0037 en el lugar: lo supera con esta referencia explícita.

## Alcance de la implementación

El servidor MCP en sí (`snarf/mcp/`, allowlist de herramientas expuestas, tests de cobertura) se construye en la Fase D del plan de expansión (`docs/plans/` — ver también el plan de la sesión). Esta ADR fija la decisión de gobernanza; el código llega después, con su propia verificación.

## Consecuencias

- La política de "no MCP" deja de ser absoluta y pasa a ser condicional a la existencia de un segundo consumidor real — documentado explícitamente en vez de dejarlo implícito.
- Cualquier futuro tercer consumidor de las herramientas de Snarf debe evaluarse contra el mismo criterio (¿hace falta un proceso/protocolo/transporte real, o alcanza con una llamada de método in-process?) antes de sumar más superficie MCP.
