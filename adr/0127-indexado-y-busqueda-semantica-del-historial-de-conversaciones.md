# ADR 0127 — Indexado y búsqueda semántica del historial de conversaciones (dominio `conversations`)

**Fecha:** 2026-08-06
**Estado:** Aceptado

## Contexto

Pedido explícito: que Snarf pueda acceder a su propio historial de conversaciones y proyectos de forma
eficiente, en vez de depender de que el usuario recuerde en qué conversación pasó algo. El patrón
`KnowledgeSource`/`KnowledgeIndexer`/`VectorStore` (ADR 0096) ya resuelve exactamente este problema para
el dominio `code` — costo cero más allá de embeddings, sin llamada de red para leer contenido, reindexado
incremental vía `modified_marker` comparado contra un manifiesto. Este dominio nuevo (`conversations`)
reusa el mismo motor genérico sin tocarlo.

## Decisión

- **`EpisodicConversationSource(KnowledgeSource)`** (`snarf/knowledge/episodic_conversation_source.py`),
  `domain = "conversations"`. Una conversación ENTERA es el ítem indexable (no un chunk por mensaje):
  `modified_marker` es su `last_activity` real, así que una conversación que sigue creciendo se reindexa
  sola en el próximo ciclo sin código nuevo — `KnowledgeIndexer` ya compara el marker contra el manifiesto.
  `read_item()` arma el texto con el título, el `project_id` si está asignado, y cada turno real
  usuario/Snarf.
- `project_id` viaja como metadata real (nunca inventado) para poder filtrar la búsqueda por proyecto.
  Se **omite la clave por completo** cuando la conversación no tiene proyecto asignado, en vez de guardar
  `None` — ver Hallazgo abajo.
- `KnowledgeIndexer.search()` extendido con un parámetro `where: dict | None`, pasado tal cual hasta
  `VectorStore.search()` (que ya lo soportaba) — genérico, `KnowledgeIndexer` no conoce `conversations` en
  particular.
- `Orchestrator`: nuevo `self._conversations_indexer`, mismo patrón exacto que `self._code_indexer`,
  colección chroma separada (`conversations`) bajo `KNOWLEDGE_DATA_DIR/{user_id}/conversations/`. Tool
  nueva `conversations_search(query, project_id=None, top_k=5)` — si viene `project_id`, se traduce a
  `where={"project_id": project_id}`. `knowledge_search`/`knowledge_index_start`/`knowledge_index_status`
  extienden su enum de dominio a `conversations`.
- Telemetría: entradas nuevas en las tres tablas paralelas del protocolo de crecimiento —
  `verbs.py::VERB_BY_SKILL`, `brain.py::TOOL_TO_NODE`, `detail.py::DETAIL_EXTRACTORS` — para
  `conversations_search`.

## Hallazgo (smoke test real, no detectado por los tests unitarios): chromadb rechaza `None` en metadata

Los tests con `FakeVectorStore` (fakes en memoria) pasaron limpio, pero un smoke test real contra las 180
conversaciones reales de producción (leyendo `data/episodic_memory.jsonl`, indexando en un directorio
chroma temporal — sin tocar el índice real) reveló:

```
TypeError: argument 'metadatas': Cannot convert Python object to MetadataValue
```

Causa: `extra_metadata={"project_id": self._memory.get_conversation_project(conversation_id), ...}` ponía
`None` como valor cuando la conversación no tenía proyecto — la mayoría de las 180 reales. El binding Rust
de chromadb (`MetadataValue`) no acepta `None` como tipo válido de metadata (solo str/int/float/bool). El
fake usado en los tests unitarios no replica esta validación real del backend, así que el bug era invisible
sin probar contra el vector store real.

**Fix**: en `iter_items()`, la clave `project_id` se agrega a `extra_metadata` solo si `project_id` es
verdadero — se omite entera cuando no hay proyecto asignado, en vez de guardar `None`. Efecto colateral
correcto: un filtro `where={"project_id": X}` sobre conversaciones sin esa clave las excluye de forma
natural, que es exactamente el comportamiento esperado (una conversación no asignada a ningún proyecto no
debería aparecer en una búsqueda acotada a un proyecto específico).

## Verificado

- `.venv/bin/python -m pytest -q` — 1009 passed (30 tests nuevos: `test_episodic_conversation_source.py`
  completo, extensiones en `test_knowledge_indexer.py` y `test_orchestrator.py` para `where`/dominio
  `conversations`).
- Smoke test real end-to-end (post-fix) contra datos reales de producción: 180 conversaciones reales
  encontradas vía `EpisodicMemory()` sin override de path; 2 conversaciones reales indexadas en un
  directorio chroma temporal (nunca el índice real) sin error; búsqueda semántica real
  (`VoyageEmbeddings` real) devolvió 3 resultados reales relevantes al texto indexado.

## Consecuencias

- Cualquier fuente de conocimiento futura que use `KnowledgeSource`/`extra_metadata` con un valor
  potencialmente ausente (no solo `project_id`) debe omitir la clave en vez de pasar `None` — chromadb es
  el backend real de `VectorStore`, esta restricción no es específica de `conversations`.
- `conversations_search` queda disponible como tool real del Orchestrator, mismo nivel que
  `knowledge_search(domain="code")` — cubre "proyectos" como filtro (`project_id`) sobre el mismo dominio,
  no como dominio aparte.
