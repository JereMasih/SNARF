# ADR 0198 — Mecanismo de equipo multi-agente

**Fecha:** 2026-08-21
**Estado:** Aceptado

## Contexto

Fase D3 del plan Second Brain (`ROADMAP_SECOND_BRAIN_NOTION.md`, ver ADR 0179), pieza de mayor riesgo y
novedad de todo Track D (confiabilidad del Orchestrator). El fundador quiere que el Orchestrator pueda
convocar al "equipo correcto" de agentes, que ese equipo itere y se autocorrija su propio plan hasta uno
óptimo, con aprobación interna automática, antes de producir un resultado final. El mecanismo existente más
cercano — `ExecutiveBoardSpecialist.consult()` (ADR 0093/0094) — es de una sola ronda, en paralelo, sin
visibilidad entre roles, y nunca produce un artefacto (solo opiniones etiquetadas con `basis`). No alcanza
para lo pedido: hace falta iteración real con crítica cruzada y convergencia a un borrador concreto.

**Pregunta abierta #2 del roadmap, no confirmada por el fundador**: ¿el "equipo de marketing" reusa los 7
roles ya existentes del board (CMO/Chief Creative Officer/Chief Research Officer, etc.) o necesita roles
nuevos, más operativos (ej. un "redactor" que produzca texto en vez de solo opinar)? Decisión tomada acá,
sin bloquear en la pregunta: **ambos, con roles distintos por función**. Los 7 roles existentes de
`ROLE_CONFIGS` (`snarf/executive/roles.py`) siguen siendo los únicos que critican — nunca se les pide que
redacten, sería forzar un rol de asesoría a hacer algo para lo que no está diseñado. La redacción/revisión
del borrador usa un rol de ruteo nuevo y dedicado, `executive_team_writer` (barato por default,
`mlx_local_fast`, mismo criterio que el resto de roles nuevos de esta sesión) — no reusa ninguno de los 7.
Si en el futuro hace falta un "redactor" con personalidad/criterio propio y no solo un LLM genérico
redactando, se revisita como ADR aparte; hoy alcanza con un system prompt dedicado
(`TEAM_DRAFT_SYSTEM_PROMPT`).

## Decisión

**`TeamSession` (`snarf/executive/team.py`, nuevo)** — reusa `consult_role`/`_MCPToolBridge` (mismo
primitivo de proceso separado que ya usa el board, `snarf/executive/process.py`) para la crítica de cada
rol convocado, sin duplicar esa infraestructura. A diferencia del board:

- **Itera con tope real, nunca infinito** (`max_rounds`, default `DEFAULT_MAX_ROUNDS = 3` — mismo criterio
  que `_max_continuations` de `AnthropicLLM`, ADR 0113): ronda 1 genera un borrador; cada ronda siguiente
  pide crítica a cada rol convocado (formato `BLOQUEANTE:`/`SUGERENCIA:`/`SIN OBJECIÓN:`, parseado por
  `_parse_objections`) y, si hay objeciones bloqueantes, regenera el borrador incorporándolas de verdad
  antes de la próxima ronda.
- **Aprobación interna real**: aprobado apenas ninguna objeción sea `BLOQUEANTE` en una ronda. Si se agotan
  las rondas sin resolver todas las bloqueantes, igual se declara `approved=True` pero con
  `approved_by_exhaustion=True` explícito — nunca se presenta un agotamiento de intentos como si fuera
  consenso real logrado (Principio VI, Foundation).
- **Sin autoridad entre roles**: cada `consult_role()` corre en su propio proceso separado, sin visibilidad
  de la crítica de otro rol dentro de la misma ronda — mismo invariante del board (ADR 0094). Solo entre
  rondas, vía la regeneración del borrador, un rol "ve" indirectamente que hubo objeciones (nunca de quién
  específicamente, si eso importara).
- **Nunca ejecuta ninguna tool mutante**: el resultado (`draft`) vuelve a quien llamó como texto, igual que
  cualquier Especialista. Si ese borrador se usa después para escribir algo real (ej. a Notion, ver D4),
  pasa por las tools mutantes normales con su propio gate de alto impacto — el equipo en sí nunca escribe
  directo a ningún sistema externo.
- **Degradación honesta**: sin LLM de borrador configurado, dice explícito "falta configurar el modelo de
  lenguaje" en vez de fallar silenciosamente; ante una excepción real del LLM, "No se pudo generar el
  borrador: {excepción}" — nunca un borrador vacío disfrazado de éxito.

**Orchestrator**: `self._executive_team = TeamSession(draft_llm_factory=..., role_llm_factory_for_role=...)`
junto a `self._executive_board`. Tool nueva `executive_team_run(objective, roles, max_rounds)` — valida
`roles` contra `ROLE_CONFIGS` y devuelve `{"error": ...}` explícito ante roles desconocidos, lista vacía, o
`max_rounds < 1`, nunca lanza una excepción cruda al loop de herramientas. `_handle_tool()` marca
`context.set_board_consulted(True)` también para `executive_team_run` (mismo criterio ya usado para
`executive_board_consult`: un equipo también es una consulta real a roles de la Inteligencia Ejecutiva,
mismo contexto auditable).

**Cerebro** (`snarf/telemetry/brain.py`): nodo propio `specialist_executive_team`, distinto de
`specialist_executive_board` pese a reusar la misma infraestructura de proceso — mecanismo diferente por
naturaleza (iterativo, con aprobación interna y producción de artefacto, vs. una sola ronda de opiniones),
mismo criterio que ya separó `specialist_second_brain_reports` de `specialist_second_brain`. Verbo
("convocando al equipo") y extractor de detalle (`_executive_team_run`, muestra roles + objetivo truncado)
agregados a `verbs.py`/`detail.py`.

**MCP** (`snarf/mcp/tools.py`): `executive_team_run` queda excluido de `MCP_EXPOSED_TOOLS` por diseño del
propio allowlist (positivo, nunca por exclusión — la tool simplemente no está en la lista). Mismo criterio
que la exclusión ya deliberada de `executive_board_consult`: ningún rol de la Inteligencia Ejecutiva puede
convocar recursivamente a otro equipo/board desde dentro de su propia consulta.

**`POLICY_HIGH_IMPACT_ACTIONS.md`**: nueva fila, `executive_team_run` **no** requiere confirmación de
Art. VII — nunca ejecuta una tool mutante, el artefacto que produce siempre vuelve como texto a quien llamó.
Mismo criterio ya usado para "un rol de Inteligencia Ejecutiva emite una opinión/asesoría".

## Verificado

- `.venv/bin/python -m pytest -q` — 1665/1665 (1652 previos + 13 nuevos en `tests/test_executive_team.py`:
  rechaza roles desconocidos/lista vacía/`max_rounds < 1`, aprueba en la primera ronda sin objeciones
  bloqueantes, revisa el borrador incorporando una objeción bloqueante real y aprueba en la ronda
  siguiente, aprueba por agotamiento cuando las objeciones nunca se resuelven, nunca bloquea por
  `SUGERENCIA` sola, con múltiples roles necesita que todos den luz verde, degrada honesto sin LLM
  disponible y ante error del LLM, ningún rol ve la crítica del otro dentro de la misma ronda,
  `_parse_objections` extrae severidad/texto correctamente y devuelve lista vacía ante texto vacío/`None`)
  — más cobertura completa en `tests/test_brain.py`/`tests/test_verbs.py`/`tests/test_telemetry_detail.py`.
- No verificado en vivo contra el board real de Inteligencia Ejecutiva con roles reales (los 13 tests usan
  `consult_role`/LLMs fake) — sin caso de uso real todavía que lo dispare en producción.

## Consecuencias

- Fase D4 (escritura confiable de documentos largos) y D5 (integración capstone) pueden convocar
  `executive_team_run` para producir un plan de secciones antes de escribirlo, con los supervisores de D2
  disponibles como contexto adicional del objetivo (ej. restricción de presupuesto real para un equipo de
  marketing).
- Pendiente real, sin resolver acá: ninguna superficie de UI para lanzar/ver una corrida de equipo (solo
  tool conversacional por ahora, mismo criterio de "construir la UI cuando haya algo real en vivo contra
  qué construirla" ya aplicado en B1/A4/D2).
- La pregunta abierta #7 del roadmap ("¿el fundador quiere ver siempre el resultado final antes de usarlo
  para algo real, o puede correr completo hasta el paso de escritura?") sigue sin responder — no bloqueó
  esta fase porque `executive_team_run` nunca escribe nada por su cuenta: el gate real sigue siendo el de
  la tool mutante que eventualmente use el borrador.
