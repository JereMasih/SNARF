# ADR 0197 — Supervisores periódicos: financiero y de ánimo

**Fecha:** 2026-08-20
**Estado:** Aceptado

## Contexto

Fase D2 del plan Second Brain (`ROADMAP_SECOND_BRAIN_NOTION.md`, ver ADR 0179), primera fase real de
Track D (confiabilidad del Orchestrator). El fundador pidió que el Orchestrator reciba contexto de
supervisores periódicos — uno de estado financiero, uno de estado de ánimo — antes de convocar al futuro
equipo multi-agente (Fase D3). Investigado antes de construir: no existía ningún supervisor periódico
sobre el usuario en todo el repo; el precedente arquitectónico más cercano es `_periodic_bug_triage_loop`
(ADR 0178).

**Gap real encontrado al diseñar, no anticipado por el plan original**: `finance_books_categorize` (ADR
0107) recibe `file_id` por llamada — no hay ningún concepto de "la" Google Sheet de finanzas del fundador
guardado en ningún lado. Un loop verdaderamente automático no tiene de dónde leer sin que alguien le diga
antes cuál es esa Sheet. Se resuelve con una configuración nueva, explícita y persistida
(`finance_supervisor_set_sheet`), no asumida.

## Decisión

**`FinanceSupervisor` (`snarf/specialists/finance_supervisor.py`, nuevo)**: compone
`BooksCategorizeSpecialist`+`MonthlyPnLSpecialist` ya reales (ADR 0107) — ningún cálculo ni categorización
nueva, solo una interpretación corta por LLM encima del P&L determinístico ya calculado. `refresh()`
devuelve `None` (nunca inventa un snapshot) si el usuario no configuró ninguna Sheet con
`set_sheet_file_id()`. Loop diario (`FINANCE_SUPERVISOR_INTERVAL_SECONDS`).

**`FounderMood` (`snarf/specialists/founder_mood.py`, nuevo, ancla en el slot `FOUNDER_MODEL` activado en
ADR 0179)**: única fuente honesta — la memoria episódica reciente (`EpisodicMemory.recent()`). Sin
mensajes reales todavía, dice "sin señales claras" en vez de forzar una lectura — ni siquiera llama al
LLM en ese caso. El system prompt exige la misma disciplina de `basis` (`hecho`/`inferencia`/`hipótesis`)
que la Inteligencia Ejecutiva (ADR 0094), más estricta acá que en cualquier otro Especialista: es fácil
que un LLM invente un estado de ánimo sin evidencia real (Principio VI). Loop cada 6 horas
(`FOUNDER_MOOD_INTERVAL_SECONDS`).

**Cadencias — default propio, no confirmado con el fundador** (pregunta abierta #8 del roadmap, sigue sin
responder): diaria para financiero (la señal no cambia más rápido que el ritmo con que el fundador
actualiza su Sheet), cada 6 horas para ánimo (la memoria episódica sí puede cambiar varias veces en un día
real de conversación). Ajustable después sin tocar el diseño — son solo dos constantes en `app.py`.

**Orchestrator**: `self._finance_supervisor`/`self._founder_mood`, propiedades públicas
`orchestrator.finance_supervisor`/`orchestrator.founder_mood` (para que los loops de `app.py` los
alcancen, mismo patrón que `orchestrator.second_brain`). 3 tools nuevas
(`finance_supervisor_get_snapshot`, `finance_supervisor_set_sheet`, `founder_mood_get_snapshot`) — ninguna
gateada (lectura o configuración local, nunca acción mutante real). 2 nodos nuevos del cerebro
(`specialist_finance_supervisor`, `specialist_founder_mood` — separados porque son dos dominios sin
relación entre sí, no CRUD del mismo recurso). 2 roles de ruteo nuevos (`finance_supervisor`,
`founder_mood_supervisor`), baratos por default.

**`app.py`**: `_periodic_finance_supervision_loop`/`_periodic_founder_mood_loop`, mismo criterio de guard
`PYTEST_CURRENT_TEST` que los otros 4 loops ya reales. Ninguno de los dos ejecuta jamás una acción
mutante — solo leen (Drive/memoria) y guardan una interpretación local.

## Verificado

- `.venv/bin/python -m pytest -q` — 1652/1652 (1637 previos + 15 nuevos: 8 en
  `tests/test_finance_supervisor.py` — namespacing por usuario, `refresh()` sin Sheet configurada
  devuelve `None`, P&L real + interpretación real, degradación honesta sin LLM/ante error — y 7 en
  `tests/test_founder_mood.py` — sin mensajes reales nunca llama al LLM, envía solo texto real del
  fundador, namespacing por usuario, degradación honesta) — más la cobertura total en
  `tests/test_brain.py`/`tests/test_verbs.py`/`tests/test_telemetry_detail.py`/`tests/test_llm_routing.py`.
  Un fallo real encontrado durante la verificación (`test_send_returns_the_deliverable_field...`) resultó
  ser un flake preexistente sin relación con este cambio — pasa solo, pasa en la suite completa en una
  segunda corrida, no reproducido de forma consistente.
- No verificado en vivo contra una Google Sheet real del fundador ni contra memoria episódica real de
  producción — ambos supervisores son nuevos, sin uso real todavía.

## Consecuencias

- Fase D3 (mecanismo de equipo) puede consumir `finance_supervisor_get_snapshot`/
  `founder_mood_get_snapshot` como contexto real disponible para el futuro "equipo de marketing" —
  siempre que el fundador haya configurado su Sheet real primero.
- Pendiente real, sin resolver acá: ninguna superficie de UI para configurar la Sheet de finanzas ni para
  ver los snapshots (solo tools conversacionales por ahora) — mismo criterio de "construir la UI cuando
  haya algo real y probable en vivo contra qué construirla" ya aplicado en B1/A4.
