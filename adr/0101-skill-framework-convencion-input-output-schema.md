# ADR 0101 — Skill Framework: convención `INPUT_SCHEMA`/`OUTPUT_SCHEMA`

**Fecha:** 2026-08-04
**Estado:** Aceptado

## Contexto

Fase G del plan de expansión "Inteligencia Ejecutiva". La propuesta original del fundador (~13
archivos por skill: README/skill.md/prompts separados/config.yaml/checklist.md/tests.md/etc.) ya se
había reconciliado en el diseño del plan contra la convención real de hoy (2 archivos: el módulo del
Specialist + su test) — la mayoría de esos archivos se rechazaron por redundantes con lo que ya
existe (docstring, ADR+CHANGELOG, `llm_routing.ROLES`). Lo único que sobrevivió como genuinamente
nuevo: un dict `INPUT_SCHEMA`/`OUTPUT_SCHEMA` a nivel de módulo, con la misma forma JSON-Schema que
`orchestrator.TOOLS[i]["input_schema"]` — justificado porque la Skill Factory (Fase H) va a necesitar
algo generable y validable por máquina, no porque un humano leyendo un archivo de ~80 líneas lo
necesite.

## Decisión

1. **Convención documentada en `snarf/specialists/base.py`** (docstring de módulo, nuevo): cada
   módulo que define una subclase real de `Specialist` declara `INPUT_SCHEMA`/`OUTPUT_SCHEMA` a nivel
   de módulo. El registro real de un Skill-Specialist sigue siendo el de siempre — tools nuevos en
   `orchestrator.TOOLS`/`_tool_handlers` + nodo nuevo en `brain.py` — nunca `REGISTRY`/`register()`
   (ya definidos en `base.py`, nunca usados en el repo real): un dict a nivel de módulo no sostiene
   más de una instancia por proceso, y varios tests reales instancian más de un `Orchestrator` en el
   mismo proceso — resucitarlo reintroduciría ese problema real, no lo resuelve. Se documenta
   explícitamente por qué sigue sin usarse, para que una sesión futura no lo revincule por error.
2. **Convención retrofiteada en los 3 Specialist reales de hoy**: `GmailDigestSpecialist`,
   `DashboardCuratorSpecialist`, `ExecutiveBoardSpecialist` (Fase E) — cada uno suma su
   `INPUT_SCHEMA`/`OUTPUT_SCHEMA` real, reflejando su firma/resultado reales, no inventados.
   `ProjectManager` queda fuera a propósito: no hereda de `Specialist` (ya no lo hacía antes de esta
   ADR, no es un cambio de esta ronda) — sus 14 tools no comparten una sola forma de
   entrada/salida, por eso nunca implementó `handle()`.
3. **Test de cobertura nuevo**, `tests/test_specialist_schema_coverage.py`, mismo protocolo de
   crecimiento que `TOOL_TO_NODE`/`VERB_BY_SKILL` (ADR 0054): itera sobre `Specialist.__subclasses__()`
   real (nunca una lista mantenida a mano aparte) y falla si una subclase no declara ambos dicts.
4. **Explícitamente NO se restructura `snarf/specialists/` en sub-paquetes por rama todavía** —el
   plan lo nombraba como "el único cambio estructural real" de esta fase, pensado para cuando existan
   decenas de skills reales agrupables por rama (Memory/Productivity/Research/...). Hoy hay 3
   Specialists reales, ninguno todavía asignado a una de las 9 ramas de la Fase I (que no existen
   todavía) — mover archivos existentes ahora sería puramente especulativo, y además de alto riesgo
   real en este momento puntual: dos de los tres módulos (`gmail_digest.py`, `dashboard_curator.py`)
   están siendo editados activamente por otra sesión en paralelo (trabajo de fallback automático
   entre proveedores de LLM, ver ADR 0099) al momento de escribir esta ADR — un rename/move ahora
   arriesgaría perder o pisar ese trabajo. Se hace la restructuración real recién en la Fase I, cuando
   el primer skill nuevo de una rama necesite un lugar real donde vivir — mismo criterio anti-
   anticipación que ya usó la Fase F para no construir validación automática sin un caso de uso real.

## Verificado

- 1 test nuevo (`tests/test_specialist_schema_coverage.py`), cobertura automática de las 3
  subclases reales de `Specialist`.
- 795/795 tests de la suite completa.

## Consecuencias

- Un Specialist nuevo (incluidos los de la Fase I) que herede de `Specialist` sin declarar sus dos
  dicts hace fallar la suite — mismo tipo de red de seguridad que ya protege `TOOL_TO_NODE`.
- La restructuración en sub-paquetes por rama queda como trabajo real y esperado de la Fase I, no
  una decisión pendiente sin dueño — se ejecuta ahí, con el primer skill real que la necesite.
