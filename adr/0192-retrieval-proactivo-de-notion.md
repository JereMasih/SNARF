# ADR 0192 — Retrieval proactivo de Notion

**Fecha:** 2026-08-20
**Estado:** Aceptado

## Contexto

Fase A5 del plan Second Brain (`ROADMAP_SECOND_BRAIN_NOTION.md`, ver ADR 0179). Hoy `knowledge_search`
es una tool que Snarf decide llamar — "proactivo" significa que, en una conversación de un Proyecto ya
vinculado a Notion, el conocimiento real indexado se sume solo, sin que el fundador tenga que pedirlo,
mismo mecanismo que ya inyecta el prompt del proyecto en cada turno (ADR 0047).

**Ajuste honesto al diseño original del roadmap, encontrado real al implementar**: el plan proponía
filtrar `knowledge_search(source="notion", where={"project_id": ...})`. Verificado contra el schema real:
`NotionSource` (ADR 0173) etiqueta cada ítem indexado solo con `location: "notion"` y `notion_url` — nunca
con un `project_id`, porque el indexado de Notion no sabe nada de los Proyectos de Snarf. Filtrar por una
key que no existe en ningún metadato real devolvería siempre una lista vacía, en silencio — exactamente
el tipo de resultado fabricado que el Principio VI prohíbe. La implementación real busca sobre TODO lo
indexado de Notion, acotado por relevancia semántica (embeddings + Chroma), no por un filtro exacto de
proyecto que no es construible con los datos que existen hoy.

## Decisión

`Orchestrator._proactive_notion_context(query)` (nuevo): si el Proyecto activo de la conversación tiene
`notion_project_page_id` (vínculo real de A3) Y hay contenido real ya indexado
(`self._notion_indexer.manifest_summary()["indexed"] > 0` — nunca corre el pipeline si no hay nada que
buscar), busca los `NOTION_RETRIEVAL_TOP_K = 3` fragmentos más relevantes al último mensaje del fundador y
los suma al system prompt del turno. Cacheado en memoria por `(query normalizada) → (timestamp,
resultado)` con `NOTION_RETRIEVAL_CACHE_TTL_SECONDS = 120` — evita repetir el pipeline de
embeddings+Chroma si el fundador escribe varios mensajes seguidos sobre lo mismo. Cualquier fallo (Notion
no indexado, error de embeddings/red) degrada a `None` en silencio, nunca rompe el turno — mismo criterio
defensivo que ya usa la inyección del prompt de proyecto justo arriba en el código.

Inyectado en `Orchestrator.handle()` inmediatamente después del prompt propio del proyecto (ADR 0047),
mismo bloque `if project_id:`, mismo criterio de "nunca romper si el proyecto no existe o no tiene datos".

## Verificado

- `.venv/bin/python -m pytest -q` — 1625/1625 (1620 previos + 5 nuevos en `tests/test_orchestrator.py`:
  contexto real inyectado en el system prompt cuando el proyecto está vinculado y hay contenido indexado;
  nunca llama a `search()` sin nada indexado; nunca llama a `search()` si el proyecto no está vinculado a
  Notion; cache real dentro del TTL (una sola llamada real a `search()` para dos consultas idénticas
  seguidas); degradación real a `None` ante un error de búsqueda.

## Consecuencias

- Fase A6 (gap de `child_database` en el indexado) es independiente, no depende de este cambio.
- Si en el futuro se quiere de verdad acotar el retrieval a SOLO el contenido de un Proyecto puntual (no
  todo Notion), hace falta primero una fase nueva que etiquete cada ítem indexado con el/los Proyecto(s)
  reales a los que pertenece en el momento de indexar — no es parte de este cambio, y no se puede resolver
  solo del lado de la búsqueda.
