# ADR 0115 — Notion: soporte de databases (query, crear registro, actualizar properties)

**Fecha:** 2026-08-05
**Estado:** Aceptado

## Contexto

La Capability de Notion (ADR 0075, 2026-08-01) solo cubría páginas sueltas: `search`, `create_page`,
`append_to_page`, `read_page_text` — cero soporte de databases ni properties tipadas. El fundador
necesita que Snarf se conecte a databases reales que ya tiene, las llene (cree registros) y les
cambie propiedades (select, multi-select, date, number, checkbox, relation, etc.) — casos de uso
completamente fuera del alcance de ADR 0075, que ni siquiera los mencionaba como pospuestos.

## Decisión

Cuatro métodos nuevos en `snarf/capabilities/notion.py`, mismo estilo (`requests` directo, sin SDK,
versión fija `2022-06-28`) que los cuatro existentes:

- `get_database(database_id)` → `GET /v1/databases/{id}`, devuelve nombre + `properties` (dict
  `{nombre: tipo}`) — pensado para llamarse SIEMPRE antes de crear/actualizar un registro, así el
  modelo sabe qué properties existen y de qué tipo es cada una sin inventarlas.
- `query_database(database_id, filter=None, sorts=None, page_size=100)` →
  `POST /v1/databases/{id}/query`, `filter`/`sorts` en el formato real de la API de Notion.
- `create_database_item(database_id, properties)` → `POST /v1/pages` con
  `parent: {database_id: ...}` — `properties` va tal cual llega, ya tipada.
- `update_page_properties(page_id, properties)` → `PATCH /v1/pages/{id}`.

Cuatro tools nuevas registradas en `snarf/core/orchestrator.py`
(`notion_get_database`/`notion_query_database`/`notion_create_database_item`/
`notion_update_page_properties`), mismo patrón de dispatch simple que las cuatro existentes.
Instrucción explícita en el system prompt: llamar `notion_get_database` antes de crear/actualizar,
nunca inventar nombres o tipos de properties (Principio VI de FOUNDATION.md).

Registradas también en `snarf/telemetry/brain.py` (mismo nodo `notion` — CRUD sobre el mismo recurso,
no una subcapacidad distinta, ver protocolo de crecimiento del cerebro), `verbs.py` y `detail.py`.

## Verificado

- 13 tests en `tests/test_notion.py` (7 existentes + 6 nuevos, `requests` mockeado).
- `NOTION_API_KEY` confirmada configurada en `.env` — a diferencia de ADR 0075 (donde la Capability
  quedaba construida pero inactiva por falta de credencial), esta extensión puede verificarse contra
  la API real de Notion cuando el fundador la use.
- 946/946 tests de la suite completa.

## Consecuencias

- Queda pendiente, sin construir: manejo de errores específicos de Notion para properties mal tipadas
  (hoy simplemente propaga el error real de la API) — se evalúa si hace falta según uso real.
