# ADR 0141 — Fase 6: Prompt Registry

**Fecha:** 2026-08-10
**Estado:** Aceptado

## Contexto

`ROADMAP_OBSERVABILIDAD_MULTIUSUARIO_N8N.md` (ver ADR 0140 para cómo se recuperó ese documento) fija la
Fase 6: *"Migra los ~11 prompts hardcodeados (`SYSTEM_PREFIX` en `orchestrator.py` + system prompt
propio de cada Specialist) a almacenamiento versionado bajo `data/prompts/`... con: versión activa,
historial, rollback. El texto actual se migra como v1 — nada cambia de comportamiento el día del
corte."* Es el prerequisito técnico explícito de dos casos de uso ya prometidos y todavía bloqueados: el
"n8n edita un agente existente" de ADR 0139 y la comparación de versiones de Langfuse en la Fase 8
futura.

**Alcance real encontrado, más amplio que "~11"**: auditando el código (no asumiendo desde el plan) se
encontraron 20 constantes de prompt hardcodeadas — el conteo de "~11" del plan corresponde a Specialists
como unidad (10 clases + `SYSTEM_PREFIX`), pero varias tienen más de un prompt propio interno
(`morning_routine` clasifica y sintetiza por separado, `project_manager` sugiere subcarpetas y resume
por separado, `research`/`content` tienen 3 modos cada uno). Se migraron los 20 textos reales, no solo
11, para que cada uno sea versionable de forma independiente.

**Fuera de esta ADR, con motivo:** el `_prompt()` de los 7 roles del board de Inteligencia Ejecutiva
(`snarf/executive/roles.py`) es una función compartida con parámetros, no un texto suelto — migrarla
cambia su forma, no solo su almacenamiento; queda para una ronda futura si hace falta. El
`_build_prompt()` de Skill Factory se reconstruye por invocación (branch/nombre/descripción variables),
no es un "system prompt" fijo. `CommunityPulseSpecialist` es determinístico, sin LLM. Ninguno de los tres
encaja en el patrón "texto fijo con versión activa".

## Decisión

**`snarf/runtime/prompt_registry.py` (nuevo)** — mismo estilo "JSON-por-entidad" que
`llm_routing.py`/`data/llm_routing.json`: un solo archivo (`data/prompts.json`), clave = `prompt_id`,
valor = historial completo + versión activa. Cuatro funciones: `get_active_text(id, default)` (el
default hardcodeado si nunca se guardó nada — "nada cambia el día del corte", literal),
`save_new_version(id, text, default)` (siembra v1=default antes de agregar v2, nunca pierde el texto
original), `rollback(id, version, default)` (activa una versión ya existente, nunca borra), `history(id,
default)` (v1 implícito si nunca se tocó). `PROMPT_IDS`: allowlist positivo de los 20 ids reales, mismo
criterio que `MCP_EXPOSED_TOOLS`.

**Descubrimiento real a mitad de la implementación — violación de un boundary de arquitectura ya
test-enforced**: la primera versión de este cambio hacía que cada Specialist importara
`snarf.runtime.prompt_registry` directo. `tests/test_architecture_boundaries.py` (ADR 0026) lo
rechazó: *"Capacidades y Especialistas deben poder usarse desde un proyecto/agente futuro sin arrastrar
a Snarf entero... reciben sus dependencias por inyección en el constructor, no las buscan ellos
mismos"* — el mismo criterio ya vigente para `llm_factory`. Se corrigió: cada Specialist/Capacidad de la
capa reusable (`snarf/specialists/`, `snarf/knowledge/`) recibe un `system_prompt_provider` (callable
sin argumentos, mismo patrón exacto que `llm_factory`) inyectado por quien lo construye. Quien construye
—`Orchestrator.__init__` para 9 Specialists, `app.py` para `DashboardCuratorSpecialist`, ambos ya en
`snarf.core`/nivel de aplicación, con permiso real de importar `snarf.runtime`— es quien conecta el
provider a `prompt_registry.get_active_text(id, DEFAULT_CONSTANT)`. El default de cada Specialist sigue
siendo el texto hardcodeado de siempre (`system_prompt_provider or (lambda: SYSTEM_PROMPT)`) — construir
uno sin el parámetro nuevo (cualquier test existente, un consumidor externo futuro) sigue funcionando
exactamente igual. Esto también preserva la propiedad de "vivo sin reiniciar": el provider es un
callable, releído en cada llamada real, igual que `llm_factory`.

**`snarf/core/orchestrator.py`** usa `prompt_registry` directo (vive en `snarf.core`, no en la capa
reusable) para sus 3 prompts propios (`orchestrator_system_prefix`, `conversation_title`,
`history_compaction`) y para construir los `system_prompt_provider` de los 9 Specialists que instancia.

**Ningún endpoint HTTP nuevo en esta ADR.** Escribir una versión desde n8n/el cockpit del fundador es
Fase 9.3 del roadmap (*"abrir el prompt/config activo de un agente, editarlo, y activar la nueva
versión, con historial y rollback"*) — todavía sin construir. Hoy `save_new_version()`/`rollback()`
solo se llaman desde tests; están listas para que Fase 9.3 las use, pero exponerlas por HTTP es decisión
de esa fase, no de esta.

## Mapeo completo prompt_id → origen

| `prompt_id` | Constante original | Módulo |
|---|---|---|
| `orchestrator_system_prefix` | `SYSTEM_PREFIX` | `orchestrator.py` |
| `conversation_title` | `CONVERSATION_TITLE_SYSTEM_PROMPT` | `orchestrator.py` |
| `history_compaction` | `HISTORY_COMPACTION_SYSTEM_PROMPT` | `orchestrator.py` |
| `drive_vision` | `VISION_SYSTEM_PROMPT` | `knowledge/extraction.py` |
| `gmail_digest` | `SYSTEM_PROMPT` | `specialists/gmail_digest.py` |
| `dashboard_curator` | `DASHBOARD_CURATOR_SYSTEM_PROMPT` | `specialists/dashboard_curator.py` |
| `project_manager_subfolder_suggestion` | `SUBFOLDER_SUGGESTION_SYSTEM_PROMPT` | `specialists/project_manager.py` |
| `project_manager_summary` | `SUMMARY_SYSTEM_PROMPT` | `specialists/project_manager.py` |
| `calendar_brief` | `SYSTEM_PROMPT` | `specialists/productivity/calendar_brief.py` |
| `morning_routine_classify` | `CLASSIFY_SYSTEM_PROMPT` | `specialists/productivity/morning_routine.py` |
| `morning_routine_synthesize` | `SYNTHESIZE_SYSTEM_PROMPT` | `specialists/productivity/morning_routine.py` |
| `research_deep_research` | `DEEP_RESEARCH_CONFIG.system_prompt` | `specialists/research/mode.py` |
| `research_trend_scan` | `TREND_SCAN_CONFIG.system_prompt` | `specialists/research/mode.py` |
| `research_competitor_watch` | `COMPETITOR_WATCH_CONFIG.system_prompt` | `specialists/research/mode.py` |
| `content_blog_post` | `BLOG_POST_CONFIG.system_prompt` | `specialists/content/mode.py` |
| `content_social_post` | `SOCIAL_POST_CONFIG.system_prompt` | `specialists/content/mode.py` |
| `content_newsletter` | `NEWSLETTER_CONFIG.system_prompt` | `specialists/content/mode.py` |
| `client_status` | `SYSTEM_PROMPT` | `specialists/agency/client_status.py` |
| `books_categorize` | `SYSTEM_PROMPT` | `specialists/finance/books_categorize.py` |
| `sponsor_inbox_triage` | `SYSTEM_PROMPT` | `specialists/sales/sponsor_inbox_triage.py` |

## Verificado

- 7 tests nuevos en `tests/test_prompt_registry.py`: default sin override, `save_new_version` siembra
  v1 real antes de v2, override vivo sin reiniciar, `rollback` reactiva sin borrar, rollback a versión
  inexistente rechazado, historial implícito de v1, dos prompts guardados nunca se pisan entre sí.
- 5 tests nuevos de wiring extremo a extremo (uno representativo por patrón estructural distinto, no los
  20 completos): `test_orchestrator.py` (`orchestrator_system_prefix` vía `handle()` real,
  `history_compaction` vía `_capped_for_replay()` real), `test_gmail_digest.py` (Specialist simple),
  `test_research_specialist.py` (Specialist basado en config de modo, mismo patrón que Content),
  `test_extraction.py` (Capacidad de `snarf/knowledge/`, patrón distinto a Specialist).
- `tests/test_architecture_boundaries.py` sigue en verde — ningún Specialist/Capacidad de la capa
  reusable importa `snarf.runtime`.
- 1233/1233 tests de la suite completa (`.venv/bin/python -m pytest -q`), 1221 previos (post Fase 5) +
  12 nuevos.
