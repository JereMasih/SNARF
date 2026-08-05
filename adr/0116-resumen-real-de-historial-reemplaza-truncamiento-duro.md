# ADR 0116 — Resumen real de historial reemplaza el truncamiento duro por caracteres

**Fecha:** 2026-08-05
**Estado:** Aceptado

## Contexto

`_capped_for_replay()` (ADR previo, motivado por un incidente real de 523.869 tokens re-cacheados)
cortaba a lo bruto cualquier entrada de historial de más de `HISTORY_REPLAY_MAX_CHARS = 8000`
caracteres al reconstruir la conversación para el LLM, dejando una nota de "contenido omitido" —
perdía contenido en silencio en vez de condensarlo. El pedido del fundador de "optimizar el contexto
entregado" apuntaba directo a este mecanismo: el resto del pipeline (qué Capacidad/Especialista
invocar) ya lo decide el propio modelo vía tool-calling dentro del loop existente — un router de
reglas fijas antes del LLM sería estrictamente peor que dejarlo razonar.

## Decisión

- Nuevo rol de ruteo `history_compaction` en `snarf/runtime/llm_routing.py` (default
  `claude-haiku-4-5`, mismo criterio de costo que el resto de roles secundarios).
- `Orchestrator._capped_for_replay()` (ahora método, antes función módulo): si una entrada supera el
  tope, llama a `_summarize_history_entry()`, que usa `llm_routing.build_resilient_llm("history_compaction")`
  para condensarla fielmente (`HISTORY_COMPACTION_SYSTEM_PROMPT`: conservar datos concretos, nunca
  inventar — Principio VI). Si el resumen falla por cualquier motivo (LLM no disponible, error de
  red), cae a `_hard_cut_for_replay()` — el mismo corte duro de siempre, nunca rompe el turno.
- `self._history_summary_cache` (dict en memoria, por `Orchestrator`, keyed por hash del contenido):
  evita re-resumir la misma entrada vieja en cada turno mientras siga dentro de la ventana de últimas
  10 entradas — no persistida entre reinicios, barata de reconstruir.

## Verificado

- `tests/test_orchestrator.py`: fallback al corte duro cuando `history_compaction` no está disponible
  (caso real en todos los tests, ver `conftest.py` que limpia `ANTHROPIC_API_KEY`), y resumen real +
  cacheo (una entrada repetida no dispara una segunda llamada al LLM) con un summarizer fake.
- 946/946 tests de la suite completa.

## Consecuencias

- Costo adicional real: una llamada a Haiku por entrada de historial larga nueva (no cacheada) — bajo
  dado que Haiku es el modelo más barato del sistema y el cacheo en memoria evita repetirla.
- No se tocó el mecanismo de invocación de tools/Especialistas — sigue siendo 100% decisión del modelo
  principal, como estaba diseñado.
