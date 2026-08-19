# ADR 0173 — Indexado semántico real de Notion (`NotionSource`)

**Fecha:** 2026-08-18
**Estado:** Aceptado

## Contexto

El fundador pidió que "todo lo de Notion" quedara resuelto en una misma ronda: poder ver y editar
databases dentro de páginas, y que el contenido quedara indexado semánticamente/vectorizado, listo para
usarse desde `knowledge_search` — no solo el token cargado.

Investigando el código real se encontró que ver/editar databases **ya estaba construido** —
`snarf/capabilities/notion.py` ya tenía `get_database`, `query_database`, `create_database_item`,
`update_page_properties`, expuestos como tools reales del Orchestrator desde antes de esta ronda. Lo que
no existía era el indexado: `KNOWLEDGE.md` describía una `NotionKnowledgeSource` que vectorizaría Notion
igual que Drive, pero no había ningún código real detrás de esa mención — ninguna clase, ningún indexador,
nada en `snarf/knowledge/`. `.env` ya tenía `NOTION_API_KEY` cargada desde el 2026-08-14, sin haberse
usado nunca contra datos reales.

## Decisión

**Reusar el motor genérico ya existente, no construir uno nuevo.** `snarf/knowledge/indexer.py`
(`KnowledgeIndexer`) y el contrato `KnowledgeSource` (`snarf/knowledge/source.py`) ya estaban pensados
exactamente para este caso — "fuentes sin la complejidad de extracción por mimetype que Drive sí tiene"
(docstring de `KnowledgeIndexer`). El único código nuevo real es `NotionSource`
(`snarf/knowledge/notion_source.py`), que implementa `iter_items()`/`read_item()` sobre la Capacidad
`Notion` ya existente.

**Cada fila de una database es su propio ítem indexado, no solo cada página.** El contenido real del
fundador (áreas, proyectos, notas, tareas) vive mayormente en filas de databases, no en cuerpos de página
— indexar solo páginas hubiera dejado ese contenido invisible para `knowledge_search`. Las properties
tipadas de cada fila (`select`, `multi_select`, `date`, `checkbox`, `relation`, etc.) se convierten a texto
plano legible con `format_properties_text` (nuevo, en `snarf/capabilities/notion.py`) antes de chunkear —
sin esto no había ningún texto indexable en una fila, solo datos tipados sin forma de embeber.

**Notion comparte el mismo dominio `personal` que Drive — misma colección física, no una nueva.**
`self._notion_indexer` (nuevo, en `Orchestrator.__init__`) usa `KnowledgeIndexer` apuntado al mismo
`persist_directory` que `self._drive_indexer`, con manifiesto propio (`notion_manifest.json`, separado del
de Drive para que el tracking de qué ya se indexó no se pise entre las dos fuentes). Como los chunks de
Notion viven en la misma colección, `domain="personal"` ya los encuentra sin ningún cambio en el motor.

**Bug real encontrado y corregido en la misma ronda, verificando contra una conversación real del
fundador:** `KNOWLEDGE.md` documentaba la key de metadata para sub-acotar dentro de `personal` como
`source: "drive"|"notion"|"upload"`, pero el código real de `DriveIndexer` nunca usó esa key — usa
`location` (`"drive"`/`"local"`), documentación desactualizada desde antes de esta ronda. `NotionSource`
se escribió originalmente copiando la key equivocada de la documentación (`source`) en vez de verificar
contra el código real de `DriveIndexer` — dos keys de metadata distintas que nunca se cruzaban, así que
ningún filtro por fuente funcionaba. Corregido: `NotionSource` ahora escribe `location: "notion"`, y
`knowledge_search` gana un parámetro `source` (`"drive"`/`"notion"`) que arma el `where={"location": ...}`
real pasado a `self._drive_indexer.search()`. `KNOWLEDGE.md` corregido para documentar `location`, no
`source`.

**Dos tools nuevas, mismo patrón que Drive:** `notion_index_start`/`notion_index_status`, mapeadas al
mismo nodo `"knowledge"` del cerebro que `drive_index_start`/`drive_index_status` (no al nodo `"notion"`,
donde ya viven las tools de interacción con contenido) — son tools de indexación, categoría distinta.

**Se agregó paginación real a la Capacidad `Notion`**, ausente hasta ahora porque nunca hizo falta:
`iter_all_pages()`/`iter_all_databases()` (recorren `/search` con `start_cursor`/`has_more` hasta agotar
resultados, a diferencia de `search()`, pensada para un pedido puntual del LLM con tope de 20) e
`iter_database_rows()` (mismo criterio sobre `/databases/{id}/query`, sin el tope fijo de `query_database`).

## Consecuencias

- `KNOWLEDGE.md` queda corregido para reflejar código real, no una mención sin implementación detrás.
- Límite conocido, no resuelto en esta ronda: si una database del fundador está incrustada como bloque
  (`child_database`) dentro de una página en vez de ser una database de página completa, `/search` no la
  encuentra — quedaría fuera del indexado hasta que se agregue recorrido de bloques anidados, trabajo
  aparte si la verificación real lo confirma necesario.
- `read_page_text` (capacidad ya existente, sin tocar) sigue sin recorrer bloques anidados (toggles,
  tablas) — mismo alcance que ya tenía el resto de la Knowledge Layer, no una regresión de esta ronda.
- 1483/1483 tests. Pendiente de verificación real: el fundador todavía tiene que compartir sus páginas de
  Notion con la integración antes de que `notion_index_start` encuentre contenido real.
