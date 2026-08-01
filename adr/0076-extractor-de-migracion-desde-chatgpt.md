# ADR 0076 — Extractor de migración desde el export completo de ChatGPT

**Fecha:** 2026-08-01
**Estado:** Aceptado

## Contexto

El fundador tiene dos Projects reales en ChatGPT ("Alimentación y Workout" y "High Value Men") que quiere migrar a Proyectos de Snarf. Ya existía en el backlog el flujo manual (el fundador pega texto/copia conversaciones a mano) documentado como disponible hoy; esta ronda pidió específicamente construir el extractor automático que parsea el export completo, no solo dejar registrada la idea.

Limitación real de la plataforma, no de Snarf: ChatGPT no expone una API pública para leer un Project puntual, solo exportación completa de cuenta (ZIP con `conversations.json`, mezclando todo el historial sin discriminar por Project). El export tampoco documenta, hasta donde se pudo confirmar sin tener un ZIP real en mano, ningún campo que identifique el Project de origen de cada conversación.

El fundador todavía no pidió el export (Settings → Data Controls → Export en su cuenta de ChatGPT) — así que este extractor se construyó y probó contra el **formato documentado** de `conversations.json` (fixtures con la forma real del árbol `mapping`), no contra datos reales de su cuenta.

## Decisión

### `snarf/migration/chatgpt_export.py`

Módulo nuevo, package `snarf.migration` (distinto de `snarf.capabilities` — no es una integración en vivo con una API externa durante la conversación, es una herramienta de migración offline sobre un archivo que el fundador provee):

- `load_export_zip(zip_path)`: abre el ZIP real, falla fuerte si no encuentra `conversations.json` (señal de que no es un export real).
- `parse_conversations(conversations_json)`: convierte la lista cruda en `ChatGPTConversation`/`ChatGPTMessage` tipados. El punto no trivial: los mensajes de ChatGPT no están en una lista plana, viven en un árbol `mapping` (nodo → padre/hijos) — `_linearize` camina ese árbol desde `current_node` hasta la raíz para reconstruir el orden cronológico real, en vez de confiar en el orden de inserción del dict (no garantizado).
- `filter_by_title_keyword(conversations, keyword)`: heurístico de texto sobre el título — **no** una lectura de un campo real de "Project", porque ese campo no existe de forma documentada en este export. Declarado así explícitamente en el docstring del módulo para que nadie lo trate como más confiable de lo que es.
- `conversation_to_markdown(conversation)`: prepara texto plano legible, listo para pasar a `project_add_note`/`drive_create_document` de Snarf — no reimplementa el guardado, solo el parseo.

## Verificado

- `.venv/bin/python -m pytest -q` — 547 passed, incluye 6 tests nuevos (`tests/test_chatgpt_export.py`): linearización cronológica de un árbol de 3 nodos, exclusión de mensajes de sistema/vacíos, fallback sin `current_node`, filtro de título case-insensitive, render a Markdown, y lectura de un ZIP real armado en el propio test (`tmp_path` + `zipfile`).
- **No verificado contra un export real de ChatGPT** — el fundador todavía no lo generó. Antes de confiar en `filter_by_title_keyword` para algo importante, hay que correr `load_export_zip` contra el ZIP real y confirmar si existe algún campo adicional (`gizmo_id`, `conversation_template_id` o similar) que identifique el Project de origen con más precisión que el título.

## Consecuencias

- El flujo manual ya documentado en el backlog (`project_set_prompt`/`project_add_note`/`project_search`) sigue siendo el camino disponible hoy para migrar contenido puntual — este extractor no lo reemplaza todavía, es un parser de bajo nivel que alguien (Claude Code, en una sesión futura) tiene que orquestar contra el ZIP real del fundador cuando lo tenga.
- Si el ZIP real revela un campo de Project explícito, `filter_by_title_keyword` debería reemplazarse (o complementarse) por un filtro exacto sobre ese campo — extensión real de este ADR, no algo ya cubierto.
