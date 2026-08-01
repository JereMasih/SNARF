# ADR 0075 — Integración con Notion (búsqueda, lectura y escritura de páginas)

**Fecha:** 2026-08-01
**Estado:** Aceptado

## Contexto

El fundador pidió explícitamente conectar Snarf con su Notion: buscar, leer y crear/editar páginas. Ya existía una nota de backlog marcando esto como diferido (ver memoria `snarf_roadmap_legion_and_notion_deferred_items`) — en esta ronda el fundador confirmó que quiere avanzar igual.

Punto de fricción marcado y resuelto explícitamente con el fundador, no autobloqueado: MASTER_MAP.md pausa Capabilities nuevas hasta cerrar el checklist de "Fundación técnica", salvo excepción acotada y logueada. El fundador confirmó avanzar; este ADR ES esa excepción logueada.

Alcance real de esta ronda, acotado a propósito: el fundador todavía no tiene el token de integración de Notion a mano (`notion.so/my-integrations`) — la Capability queda construida y probada con fakes, pero **inactiva** hasta que exista `NOTION_API_KEY` real en el entorno (mismo patrón de degradación que `VoyageEmbeddings`/`ElevenLabsTTS`: `available=False` sin token, error explícito al llamar una tool sin lanzar nada en silencio). El extractor de transcripción de YouTube→nota y la integración con el pipeline de `drive_search_knowledge` mencionados en el pedido original quedan fuera de este ADR — son piezas más grandes (STT/transcripción de video ya existe para Drive, pero conectarla a un flujo Notion-específico y sumar Notion como fuente indexable es una extensión real, no algo trivial de sumar acá).

## Decisión

### `snarf/capabilities/notion.py`

Capability nueva, usando `requests` directo contra la API REST de Notion (`api.notion.com/v1`, versión fija `2022-06-28`) — sin SDK de terceros, mismo criterio que `ElevenLabsTTS`/`ElevenLabsSTT` (CLAUDE.md: Skill/API directa preferida sobre MCP cuando ya hay una API real). Token en `NOTION_API_KEY` (`.env.example`), patrón `available` idéntico al resto de las Capacidades opcionales.

Métodos: `search(query)`, `read_page_text(page_id)`, `create_page(parent_page_id, title, content)`, `append_to_page(page_id, content)`. `content` es texto plano con párrafos separados por línea en blanco, convertido a bloques `paragraph` de Notion (`_paragraph_blocks`) — a propósito NO es un parser de Markdown completo (sin negrita/listas/encabezados); alcanza para que texto real llegue legible, una conversión más rica queda para cuando haga falta de verdad.

### Tools nuevas

`notion_search`, `notion_read_page`, `notion_create_page`, `notion_append_to_page` (`snarf/core/orchestrator.py`). Clasificadas como reversibles (se pueden deshacer desde el propio Notion) — mismo criterio que `drive_create_folder`/`gmail_create_label`, sin protocolo de `confirmed` en dos pasos. Mapeadas a un nodo `notion` nuevo del cerebro (protocolo de ADR 0054) — un usuario que mira el grafo reconocería "Notion" como una subcapacidad propia y distinta, no una operación más de Drive/Knowledge.

## Verificado

- `.venv/bin/python -m pytest -q` — 541 passed, incluye 7 tests nuevos de `tests/test_notion.py` (disponibilidad sin token, cada método con `requests` mockeado siguiendo el mismo patrón que `tests/test_elevenlabs_tts.py`).
- No se pudo verificar contra la API real de Notion todavía — no hay token (`NOTION_API_KEY`) configurado en este entorno. Cuando el fundador genere la integración en `notion.so/my-integrations`, pegue el token en `.env` y comparta manualmente las páginas relevantes desde Notion (una integración nueva no ve nada hasta que se comparte explícitamente), corresponde una verificación en vivo antes de dar esto por completamente probado — señalado acá para no perder el pendiente.

## Consecuencias

- Sin token real, esta Capability es código muerto verificable solo por test — aceptado a propósito (mismo patrón que `VoyageEmbeddings` antes de tener `VOYAGE_API_KEY`, no es un precedente nuevo).
- El extractor YouTube→Notion y la indexación de Notion en `drive_search_knowledge` quedan como extensiones futuras explícitas, no una promesa implícita de este ADR.
