# ADR 0176 — Edición real de celdas de tabla en Notion (`update_table_cell`)

**Fecha:** 2026-08-19
**Estado:** Aceptado

## Contexto

ADR 0175 (misma ronda) dejó anotado como límite conocido, no resuelto: `notion_update_block` no cubre
filas de tabla (`table_row`) reales. El fundador pidió explícitamente cerrar ese límite — quiere poder
editar celdas de tabla desde Snarf, y que Snarf las edite por su cuenta cuando una tarea real lo requiera,
no solo cuando se lo pidan letra por letra.

## Diagnóstico

La razón real por la que `update_block` no sirve para esto: la API de Notion representa un bloque de
texto normal (paragraph, heading, etc.) con un campo `rich_text` único, pero una fila de tabla lo guarda
distinto — un array `cells`, una lista por columna, cada una con su propio `rich_text`. `update_block`
manda siempre `{tipo: {"rich_text": [...]}}`, que la API rechaza para `table_row` (el campo real ahí es
`cells`, no `rich_text`). Además, la API exige mandar **todas** las columnas de la fila en cada PATCH —
no hay forma de tocar una sola celda "suelta"; sin traer primero la fila completa, un update pisaría y
borraría el resto de las columnas.

## Decisión

**`get_table_row(block_id)`** (nuevo, `snarf/capabilities/notion.py`): trae una fila de tabla completa,
con el texto real de cada columna por separado (a diferencia de `get_block`/`list_blocks`, que la
aplanan a un solo string `"Col A | Col B"` para lectura general).

**`update_table_cell(block_id, column_index, content)`** (nuevo): trae la fila real primero, reemplaza
solo la celda del `column_index` pedido (0-based, mismo orden que ya muestra el texto aplanado de
`read_page_text`/`list_blocks`), y manda las demás columnas sin tocar. Si `column_index` no existe en esa
fila, falla con un `ValueError` real — nunca intenta adivinar o crear una columna que no está.

Tool nueva `notion_update_table_cell` (alto impacto, mismo protocolo de `confirmed` que
`notion_update_block` — una vez por bloque tocado por conversación, no en cada llamada repetida al mismo
bloque). Mapeada al nodo `notion` en `snarf/telemetry/brain.py`, con sus entradas correspondientes en
`verbs.py`/`detail.py` (ambos con test de cobertura total sobre `TOOLS`, mismo protocolo que ADR 0175).

## Verificado

- Contra la tabla real de la nota de Sócrates (misma nota de ADR 0175): 5 filas reales leídas con
  `list_blocks`, `get_table_row` confirmado devolviendo cada columna por separado (`{'cells': ['Concepto',
  'Fórmula/Clave']}` para la fila de encabezado). No se ejecutó ningún `update_table_cell` real contra
  contenido del fundador sin que lo pidiera explícitamente — la escritura queda cubierta por tests
  unitarios sobre el mismo mecanismo PATCH ya verificado en vivo con `update_block` (ADR 0175).
- `.venv/bin/python -m pytest -q` — 1502/1502 (1497 previos + 5 nuevos: `get_table_row`,
  `update_table_cell` reemplaza solo la columna pedida, rechazo de columna fuera de rango, protocolo de
  `confirmed` de la tool nueva).

## Consecuencias

- Cierra el límite conocido que había quedado anotado en ADR 0175 — Snarf ahora puede editar/leer
  cualquier fragmento real del cuerpo de una nota de Notion, incluidas celdas de tabla.
- El bloque `transcription` en sí (generado por Notion, no documentado como editable vía su API pública)
  sigue sin ser editable directamente — no es un límite de esta implementación, es de la API de Notion.
