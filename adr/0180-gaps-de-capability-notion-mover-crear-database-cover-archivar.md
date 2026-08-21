# ADR 0180 — Gaps de capability en Notion: mover página, crear database, cover/icon, archivar

**Fecha:** 2026-08-20
**Estado:** Aceptado

## Contexto

Fase A1 del plan Second Brain (`ROADMAP_SECOND_BRAIN_NOTION.md`, ver ADR 0179 para el contexto completo).
`snarf/capabilities/notion.py` ya soportaba leer/editar bloques, celdas de tabla, properties y crear
registros dentro de una database existente (ADR 0075/0115/0173/0175/0176), pero cuatro operaciones
seguían sin existir: mover una página entre databases, crear una database nueva, cambiar cover/icon de
página o database, y archivar/restaurar una página. Sin ellas, el Second Brain no puede reorganizar
contenido real del fundador ni construir su propia estructura en el onboarding (Fase A4).

Además, `create_page`/`append_to_page` mandaban todos los bloques en una sola llamada HTTP, sin respetar
el límite real de la API de Notion (100 `children` por request) ni reintentar ante una falla transitoria
— un documento largo generado por Snarf (pedido explícito del fundador para la confiabilidad del
Orchestrator, Track D) fallaría a mitad de camino apenas superara ese límite.

## Decisión

**Ocho métodos nuevos en `Notion` (`snarf/capabilities/notion.py`):** `move_page`, `create_database`,
`update_page_cover`/`update_page_icon` (y sus equivalentes `update_database_cover`/`update_database_icon`),
`archive_page`/`restore_page`. `move_page` documenta explícito en su docstring que Notion descarta en
silencio cualquier property que no matchee en la database destino — quien lo use debe advertir eso antes
de pedir confirmación. `create_database` recibe `properties` tal cual (mismo criterio que
`create_database_item`, sin reinterpretar el formato tipado de Notion). Cover/icon aceptan `None` para
quitar la portada/ícono existente.

**Batching real de escritura**: `create_page`/`append_to_page` ahora troceran en tandas de
`MAX_CHILDREN_PER_REQUEST = 100`, con reintento (`_request_with_retry`, hasta `NOTION_MAX_ATTEMPTS = 3`
con pausa de `NOTION_RETRY_DELAY_SECONDS = 0.4` entre intentos) ante un 429 o 5xx transitorio — mismo
criterio de 3 intentos que `google_retry.retry_with_fresh_client` (ADR 0041), adaptado a un cliente HTTP
sin estado (no hay ningún "service" cacheado que resetear, solo reintentar la misma llamada). Un error
real (4xx que no sea rate limit) se propaga en el primer intento, sin reintentar en vano.

**Orchestrator**: 8 tools nuevas (`notion_move_page`, `notion_create_database`,
`notion_update_page_cover`, `notion_update_page_icon`, `notion_update_database_cover`,
`notion_update_database_icon`, `notion_archive_page`, `notion_restore_page`). `notion_move_page`,
`notion_create_database` y `notion_archive_page` entran a `HIGH_IMPACT_TOOLS` con protocolo `confirmed`
obligatorio siempre — mismo criterio que `drive_delete_file`/`project_delete`. El preview de
`notion_move_page` intenta traer el schema de la database destino (`get_database`, best-effort, nunca
bloquea el preview si falla) para mostrar qué properties existen ahí antes de confirmar. Las 5 tools
restantes (cover/icon x2, restore) son reversibles desde el propio Notion, sin gate. Las 8 rutean al nodo
`notion` ya existente del cerebro (`snarf/telemetry/brain.py`) — mismo criterio de CRUD sobre un mismo
recurso ya usado para el resto de las tools de Notion, ninguna amerita nodo propio.

**`POLICY_HIGH_IMPACT_ACTIONS.md`**: nueva tabla con las 5 acciones de esta fase y su justificación,
siguiendo el protocolo propio del documento ("cada categoría nueva... se suma a la tabla de arriba").

**Hallazgo real de hermeticidad de tests, corregido en el mismo cambio**: `NOTION_API_KEY` era la única
credencial de vendor que `tests/conftest.py::_no_real_credentials` no limpiaba. Al correr la suite
completa, `test_app.py` importa `app.py`, que llama `load_dotenv()` a nivel de módulo — dejando el
`.env` real cargado en `os.environ` para el resto de la sesión de pytest. Los handlers de preview de
alto impacto que llaman a un método NO mockeado de `self._notion` (`get_block` en
`_tool_notion_update_block`/`_tool_notion_delete_block`, ya existentes desde ADR 0175; `get_database` en
el nuevo `_tool_notion_move_page`) hubieran podido disparar una llamada HTTP real a la API de Notion en
medio de un test. Corregido agregando `NOTION_API_KEY` al mismo `delenv` que ya protege
Anthropic/ElevenLabs/Voyage/Gemini/OpenAI/xAI/Groq.

## Verificado

- `.venv/bin/python -m pytest -q` — 1549/1549 (1531 previos + 18 nuevos: 15 en `tests/test_notion.py`
  para los 8 métodos nuevos, batching de `create_page`/`append_to_page` sobre 100+ bloques, y retry
  real ante 503/429 con reintento agotado; 3 entradas nuevas en el `HIGH_IMPACT_TOOLS` parametrizado de
  `tests/test_orchestrator.py`, cubiertas por los dos tests genéricos ya existentes — sin
  confirmación nunca llama a la capacidad real, con `confirmed=True` la llama exactamente una vez, y
  emite `APPROVAL_REQUESTED`/`APPROVAL_GRANTED` reales).
- `tests/test_verbs.py`/`tests/test_telemetry_detail.py`/`tests/test_brain.py`: las 3 tests de cobertura
  total ("toda tool real de `TOOLS` tiene verbo/detalle/nodo") siguen en verde con las 8 tools nuevas.
- No se probó contra el Notion real del fundador en esta fase — los métodos nuevos son capability pura,
  verificados con mocks de `requests`; la primera vez que se ejerciten en vivo va a ser en fases
  posteriores del roadmap (A4 onboarding, o a pedido explícito del fundador).

## Consecuencias

- Fase A2 (modelo Área/Proyecto/Recursos/Archivo) ya puede apoyarse en `create_database` para el
  onboarding de Fase A4.
- El batching de `create_page`/`append_to_page` es prerrequisito directo de Fase D4 (escritura confiable
  de documentos largos) — ya resuelve el límite de 100 children por request, D4 todavía tiene que agregar
  la capa de generación por sección + verificación + estado reanudable.
- Ningún cambio en `web/index.html` — no hay lista hardcodeada de tools de alto impacto ni de nodos por
  tool en el frontend, el mecanismo ya es genérico (confirmado vía el campo `pending`/`confirmed` que
  ya maneja cualquier tool).
