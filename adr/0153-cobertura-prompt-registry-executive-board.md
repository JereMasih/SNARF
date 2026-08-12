# ADR 0153 — Extensión de cobertura del Prompt Registry: los 7 roles del Executive Board

**Fecha:** 2026-08-11/12
**Estado:** Aceptado

## Contexto

Al diseñar el "mapa navegable de Snarf en n8n" (Fase 13 del roadmap de observabilidad/multi-usuario/n8n),
se encontró un gap real: el Prompt Registry (Fase 6, ADR 0141) cubre 20 `prompt_id`, pero los 7 roles del
Executive Board (ADR 0094: cto/coo/research/ceo/cfo/cmo/creative) no estaban entre ellos — su texto vivía
inline, generado en `snarf/executive/roles.py::_prompt()` al importar el módulo, sin pasar nunca por
`prompt_registry`. No eran editables vía `/n8n/prompts/{id}` pese a que el fundador pidió explícitamente
poder "editar cada nodo" del mapa.

Se evaluó también sumar `community_pulse`, `monthly_pnl` y el meta-prompt de Skill Factory a esta misma
ronda — descartado por motivos distintos en cada caso (ver "Decisión", punto 3).

## Decisión

1. **7 `prompt_id` nuevos** en `snarf/runtime/prompt_registry.py::PROMPT_IDS`:
   `executive_board_{cto,coo,research,ceo,cfo,cmo,creative}`.
2. **`PROMPT_DEFAULTS`** (`snarf/core/orchestrator.py`) suma esos 7, tomando `ROLE_CONFIGS[role]
   .system_prompt` de `snarf.executive.roles` como default real — mismo texto que corría antes de esta
   ADR, "nada cambia de comportamiento el día del corte" (mismo criterio que ADR 0141).
3. **`snarf/executive/process.py::consult_role`** ahora lee la versión activa real vía
   `prompt_registry.get_active_text(f"executive_board_{role}", role_config.system_prompt)` antes de
   llamar al LLM del rol — nunca cacheado a nivel de import, una edición/rollback vía `/n8n/prompts` o
   `/prompts` queda vivo de inmediato, sin reiniciar nada (mismo patrón que los otros 20). Verificado que
   `snarf/executive/` no está sujeto al límite de `test_architecture_boundaries.py` (ese test solo escanea
   `snarf/capabilities`, `snarf/specialists`, `snarf/knowledge`), así que importar `snarf.runtime
   .prompt_registry` ahí no viola ningún límite de arquitectura existente.
4. **`community_pulse`/`monthly_pnl`: NO sumados.** Ambos son determinísticos, sin llamada a LLM — no
   existe ningún texto de prompt que editar.
5. **Meta-prompt de Skill Factory (`SkillFactorySpecialist._build_prompt`): NO sumado, a propósito.**
   A diferencia de los 27 prompts de arriba (system prompts de LLM planos, seguros de reescribir libre),
   este es una plantilla con interpolación de variables (`branch`/`skill_name`/`description`/
   `clarifying_answers`) y guardrails de seguridad reales embebidos (la lista explícita de archivos que
   Skill Factory puede tocar, el límite de nunca editar FOUNDATION/CONSTITUTION/CHARACTER/COGNITION/
   MASTER_MAP). Exponerlo a edición de texto libre sin ninguna validación de estructura sería un foot-gun
   real — alguien podría borrar sin querer el guardrail de alcance y ampliar sin darse cuenta lo que
   Skill Factory puede tocar. Queda documentado como decisión explícita, no como un gap accidental.

## Verificado

- 2 tests nuevos en `tests/test_executive_process.py`: `consult_role` usa el texto activo real del
  registro cuando se editó (`prompt_registry.save_new_version`), y cae al default hardcodeado cuando
  nunca se tocó.
- Coverage test ya existente (`tests/test_orchestrator.py`, `assert set(PROMPT_DEFAULTS.keys()) ==
  set(PROMPT_IDS)`) sigue verde sin modificarse — ambos conjuntos crecieron en paralelo.
- Suite completa: ver CHANGELOG.

## Consecuencias

- Los 7 roles del Executive Board ya son editables desde `/prompts` (founder) y `/n8n/prompts` (n8n) —
  desbloquea el mapa navegable de la Fase 13 para cubrir esa rama también, no solo los Specialists de
  `snarf/specialists/`.
- `n8n_workflows/snarf_editar_prompt.json` actualizado con los 7 `prompt_id` nuevos en el dropdown.
- Si en el futuro `community_pulse`/`monthly_pnl` suman una llamada real a LLM, o si se decide construir
  una validación de estructura para el meta-prompt de Skill Factory (placeholders obligatorios + guardrail
  no removible), esta ADR queda como el precedente de cuándo sí/no conviene sumar algo al Prompt Registry.
