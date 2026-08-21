# ADR 0193 — Gap de `child_database` en el indexado

**Fecha:** 2026-08-20
**Estado:** Aceptado

## Contexto

Fase A6 del plan Second Brain (`ROADMAP_SECOND_BRAIN_NOTION.md`, ver ADR 0179), última fase pendiente de
Track A. Límite conocido desde ADR 0173: `/search` de Notion no devuelve databases incrustadas dentro de
una página (`child_database`) — `NotionSource.iter_items()` solo recorría `iter_all_databases()` (que
usa `/search` por debajo), así que cualquier database que el fundador tenga embebida dentro de una página
(en vez de suelta como página propia) queda invisible para el indexado semántico, sin ningún aviso.

## Decisión

**`Notion.find_child_databases(page_id)` (nuevo, capability)**: recorre recursivamente los bloques reales
de una página (`GET /blocks/{id}/children`, mismo mecanismo de recursión sobre `has_children` que
`_iter_page_blocks` ya usa para toggles/transcripciones) buscando bloques `child_database` — a propósito
NO recursa dentro de la database encontrada como si fuera un bloque más (una database real se consulta con
`query_database`, no tiene sentido "bajar" por sus bloques). Devuelve `[{id, title}]` por cada una.

**`NotionSource.iter_items()` extendido**: para cada página ya iterada, llama a `find_child_databases()` y
procesa sus filas igual que cualquier database (extraído a `_iter_database_rows_as_items()`, reusado
también para las databases sueltas de siempre — evita duplicar la lógica de construir `KnowledgeItem` por
fila). `seen_database_ids` evita procesar dos veces la misma database si además aparece suelta en
`iter_all_databases()`.

## Verificado

- `.venv/bin/python -m pytest -q` — 1631/1631 (1625 previos + 6 nuevos: 4 en `tests/test_notion.py` para
  `find_child_databases` — sin databases embebidas, una embebida directa, recursión real dentro de un
  toggle, y confirmado que NUNCA hace un request de más tratando de "entrar" a la database encontrada — y
  2 en `tests/test_notion_source.py` — una database embebida se indexa igual que una suelta, y nunca se
  procesa dos veces la misma database si aparece por los dos caminos.

## Consecuencias

- **Track A queda cerrado** (A1, A2, A3, A5, A6, A7 — A4 sigue pendiente, bloqueada para verificación en
  vivo por el mismo paso manual del fundador que B1, aunque su código puede escribirse).
- La próxima corrida real de `notion_index_start` contra el Notion del fundador va a indexar por primera
  vez cualquier database que tenga embebida dentro de una página — sin este cambio, quedaba invisible sin
  ningún aviso, ahora el indexado es fiel a lo que realmente existe en su workspace.
