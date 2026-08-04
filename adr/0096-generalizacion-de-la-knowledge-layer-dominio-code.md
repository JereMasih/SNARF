# ADR 0096 — Generalización de la Knowledge Layer: contrato `KnowledgeSource` y dominio `code`

**Fecha:** 2026-08-04
**Estado:** Aceptado

## Contexto

Fase C del plan de expansión "Inteligencia Ejecutiva" (ver ADR 0093/0094/0095, KNOWLEDGE.md). MASTER_MAP.md ya planificaba, sin construir, una "interfaz genérica de fuente de conocimiento" para que Drive no sea el único camino de vectorización (Roadmaps, Fase 2). Dos consumidores reales necesitan esto ahora: el rol CTO de Inteligencia Ejecutiva (ADR 0094) necesita una fuente de dato 100% real desde el día uno, y el propio repositorio de Snarf (código + ADRs + tests + docs de raíz) es exactamente esa fuente — nunca antes indexada.

## Decisión

1. **Contrato nuevo `KnowledgeSource`** (`snarf/knowledge/source.py`): `KnowledgeItem` (dataclass: id/name/mime_type/modified_marker/extra_metadata) + `KnowledgeSource` (ABC: `iter_items()`/`read_item()`). Mismo espíritu que `Capability`/`Specialist` — sin identidad propia, inyectado por constructor.
2. **`LocalRepoKnowledgeSource`** (`snarf/knowledge/local_repo_source.py`, domain=`code`): recorre `snarf/**/*.py`, `tests/**/*.py`, `adr/*.md` y los documentos reales de la raíz (FOUNDATION/CONSTITUTION/CHARACTER/COGNITION/KNOWLEDGE/MASTER_MAP/POLICY_HIGH_IMPACT_ACTIONS/CLAUDE/CHANGELOG). Costo cero más allá de embeddings — a diferencia de Drive, no hay extracción por mimetype ni llamada de red para leer.
3. **`KnowledgeIndexer`** (`snarf/knowledge/indexer.py`): motor de indexación genérico y agnóstico de fuente — mismo pipeline real que `DriveIndexer` (chunking → embeddings → vector store, progreso reanudable por manifiesto, mismo locking y mismo patrón de thread de background), pero contra cualquier `KnowledgeSource`. **No reemplaza a `DriveIndexer`** — sigue siendo el motor real del dominio `personal`, sin tocar, aditivo puro (mismo criterio que ADR 0090 usó para el frontend).
4. **Namespacing real**: `collection_name` de Chroma = dominio (`code` para lo nuevo, `drive` sin cambios para lo existente); el filtro `where` sigue siendo el mecanismo de sub-alcance dentro de un dominio (mismo patrón que `project_id` ya usa, ADR 0045) — dos primitivas reales de Chroma, cada una con su trabajo, no confundidas entre sí.
5. **Cuatro tools nuevos, aditivos**: `codebase_search` (wrapper fino, domain-locked a `code`, el tool principal del rol CTO), `knowledge_search(query, domain, top_k)` (router explícito — `personal` delega a `self._drive_indexer`, `code` a `self._code_indexer`, cualquier otro dominio devuelve un error explícito en vez de inventar resultados, Principio VI), `knowledge_index_start(domain)` y `knowledge_index_status(domain)` (hoy solo `domain='code'` real; `personal` sigue usando `drive_index_start`, sin duplicar ese camino).
6. **Cerebro/telemetría**: los 4 tools nuevos se mapean al nodo `knowledge` ya existente (`brain.py`) — es la misma capacidad real (buscar/indexar sobre conocimiento) sirviendo una fuente nueva, no una subcapacidad que un usuario reconocería como distinta (criterio del protocolo de ADR 0054). Mismo criterio aplicado a `verbs.py`/`detail.py` (ADR 0083/0089) — cobertura completa, sin dejar tools nuevos invisibles.

## Verificado

- `LocalRepoKnowledgeSource` corrido en vivo contra el repositorio real: 242 ítems reales (138 `.py`, 104 `.md`), lectura de contenido confirmada — sin ninguna llamada a Voyage (operación gratis, análoga a `drive_index_scan`).
- 732/732 tests (25 nuevos: `test_local_repo_source.py`, `test_knowledge_indexer.py`, y la rama nueva de `test_orchestrator.py` para el router `knowledge_search`/`knowledge_index_start`/`knowledge_index_status`).

## Consecuencias

- El dominio `code` de KNOWLEDGE.md pasa de reservado a real. `personal` sin cambios. `business`/`trading`/`marketing`/`finance` siguen reservados — `knowledge_search` lo declara explícito en cada llamada en vez de fallar en silencio o inventar.
- Indexar el dominio `code` por primera vez (`knowledge_index_start(domain='code')`) tiene costo real de Voyage (embeddings) — mismo criterio de "usalo solo cuando el fundador lo pida" que ya rige a `drive_index_start`, ahora explícito también en SYSTEM_PREFIX.
