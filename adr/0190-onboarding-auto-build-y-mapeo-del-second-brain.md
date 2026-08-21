# ADR 0190 — Onboarding: auto-build y mapeo del Second Brain

**Fecha:** 2026-08-20
**Estado:** Aceptado

## Contexto

Fase A4 del plan Second Brain (`ROADMAP_SECOND_BRAIN_NOTION.md`, ver ADR 0179), última fase de Track A.
Con B1 (OAuth) ya con el código completo, falta el camino real para que un usuario nuevo (o el fundador
mismo) termine de conectar su Second Brain: crear la estructura desde cero, o mapear la que ya tiene.
Pedido explícito del fundador: que Snarf explique la metodología PARA antes de construir nada, nunca en
silencio.

## Decisión

**`SecondBrainManager.auto_build_workspace(parent_page_id)` (nuevo)**: crea una página raíz "Snarf Second
Brain" bajo `parent_page_id` (una página que el usuario ya compartió con la integración — Notion no
permite crear una página en la raíz absoluta del workspace, solo como hija de algo ya accesible) + 4
databases reales (Área/Proyecto/Recursos/Archivo) con relaciones reales entre ellas (Proyecto→Área,
Recursos/Archivo→Proyecto, usando los ids reales devueltos por cada `create_database` anterior, nunca
inventados), y completa `database_map.json` con esos ids y el `property_map` de las relaciones.

**`SecondBrainManager.suggest_mapping()` (nuevo)**: para el fundador que ya tiene su propia estructura,
busca databases existentes por coincidencia real de palabras clave en el título ("área"/"proyecto"/
"recurso"/"archivo" y sus variantes en inglés) — determinístico, sin LLM. **Ajuste al alcance original**:
el plan hablaba de "similaridad semántica"; se implementó con keywords simples en vez de una llamada a
embeddings/LLM — más barato, más predecible, y suficiente para el caso real (el fundador nombra sus
databases con palabras reconocibles, no hace falta un modelo para eso). Nunca guarda nada por su cuenta.

**Orchestrator**: 3 tools nuevas — `second_brain_onboarding_auto_build` (alto impacto, `confirmed`
obligatorio siempre: crea estructura real y permanente), `second_brain_onboarding_suggest_mapping` (solo
lectura), `second_brain_onboarding_apply_mapping` (guarda `save_database_map`, reversible, sin gate —
mismo criterio que "solo escribe JSON local" ya usado en A3 para `second_brain_link_project`). Guía nueva
en el system prompt: explicar la jerarquía PARA antes de ofrecer construir/mapear, nunca en silencio —
pedido explícito del fundador. Nodo nuevo `specialist_second_brain_onboarding` (mismo criterio de split
que A7 — `specialist_second_brain` ya estaba en el techo de tools).

**Diferido, no implementado en esta fase**: la superficie de UI de onboarding en `web/index.html`.
Investigado antes de construirla (mismo criterio que B1): no hay ningún precedente real de un wizard de
conexión en este repo — ni siquiera el flujo de Google (`/google/connect`) tiene una UI dedicada. Construir
una pantalla completa de onboarding (explicar PARA, elegir auto-build vs. mapear, pedir el
`parent_page_id`) sin poder probarla en vivo (B1 sigue bloqueado por el registro manual del fundador en
Notion) sería trabajo no verificable — se prioriza el código real y testeado del backend, la UI se
construye cuando haya algo real contra qué probarla.

## Verificado

- `.venv/bin/python -m pytest -q` — 1637/1637 (1631 previos + 6 nuevos en `tests/test_second_brain.py` —
  `auto_build_workspace` crea la página raíz + las 4 databases en el orden correcto, con las relaciones
  apuntando a los ids reales devueltos por la database anterior (nunca inventados), guarda un
  `database_map` completo; `suggest_mapping` matchea por keyword real y nunca persiste nada por su
  cuenta — más la entrada nueva en el `HIGH_IMPACT_TOOLS` parametrizado de `test_orchestrator.py`).
- `tests/test_verbs.py`/`tests/test_telemetry_detail.py`/`tests/test_brain.py`: cobertura total de las 3
  tools nuevas, techo de tools por nodo respetado con el nuevo split.
- **No verificado en vivo contra la API real de Notion** — mismo bloqueo real que B1 (falta el registro
  manual del fundador de la integración pública). El shape exacto de la property `relation` en
  `create_database` (`{"database_id": ..., "single_property": {}}`) sigue sin confirmar contra un
  workspace real; si la API real exige un shape distinto, es lo primero a corregir cuando se pueda probar.

## Consecuencias

- **Track A queda completo de código** (A1-A7) — el único bloqueo real restante en todo Track A/B es de
  verificación en vivo (B1/A4), no de código faltante.
- Cuando el fundador complete el registro manual de la integración pública de Notion, el primer paso real
  debería ser ejercitar `second_brain_onboarding_auto_build` contra una página de prueba chica (nunca
  contra el workspace real sin avisar) para confirmar el shape real de `relation` antes de ofrecerlo a
  un usuario real.
