# ADR 0122 — Paginación de conversaciones desde el mensaje más reciente, y botón "ir al final"

**Fecha:** 2026-08-05
**Estado:** Aceptado

## Contexto

`GET /conversations/{id}` devolvía siempre la conversación completa en una sola respuesta —
`EpisodicMemory.get_conversation()` no tenía paginación, ni en el backend ni en el frontend
(`loadConversation()` en `web/index.html`). El fundador pidió explícitamente que el chat cargue "desde
el mensaje más recientehacia atrás" en vez de la conversación entera de una, y un botón que lleve al
último mensaje — investigación de esta ronda encontró además que esto es un contribuyente real y
plausible a la lentitud reportada en móvil (una conversación larga sin paginar significa un payload cada
vez más grande en cada apertura).

## Decisión

**Backend** (`snarf/memory/episodic.py`, `app.py`): `EpisodicMemory.get_conversation()` gana `limit` y
`before_timestamp` opcionales — sin argumentos sigue devolviendo todo (comportamiento sin cambios para
`generate_conversation_title`/la tool conversacional `get_conversation`, que necesitan la conversación
entera). `GET /conversations/{id}` ahora acepta `limit`/`before` como query params y responde
`{"entries": [...], "has_more": bool}` — pide un elemento de más (`limit + 1`) para saber si queda más
historial antes del tramo sin un segundo query.

**Frontend**: `loadConversation()` pide solo el último tramo (`CONVERSATION_PAGE_SIZE = 30`). Un listener
de scroll en `#chat` dispara `loadOlderMessages()` cerca del tope, que antepone el tramo anterior
compensando el alto insertado (`chat.scrollTop = previousScrollTop + (nuevo alto - alto anterior)`) para
que la posición de lectura del fundador no salte. `addMessage()` gana un parámetro final opcional
`insertBeforeNode` — con él, inserta en su lugar en vez de aplicar el `appendChild` + auto-scroll normal,
reusado sin duplicar la lógica de construcción de cada burbuja.

Nuevo botón flotante `#jumpToBottomBtn`, posicionado absoluto dentro de `.chat` justo arriba del
micrófono, visible solo cuando el chat no está scrolleado al fondo (`isChatScrolledNearBottom()`).

## Verificado

- `.venv/bin/python -m pytest -q` — tests nuevos en `test_episodic_memory.py` (paginación por `limit`,
  por `before_timestamp`, sin argumentos sigue devolviendo todo) y `test_app.py` (paginación real del
  endpoint HTTP, `has_more` correcto en los tres casos).
- Verificación en navegador (Playwright) pendiente antes de dar la fase por completamente cerrada —
  requerida por convención del repo para cualquier cambio de `web/index.html`.

## Consecuencias

- `GET /conversations/{id}` cambia de forma (antes devolvía una lista cruda, ahora
  `{entries, has_more}`) — el único consumidor real es el propio frontend, actualizado en el mismo
  cambio; no hay otro cliente HTTP de esta ruta hoy.
- Cinco lugares distintos en `web/index.html` que abren una conversación nueva (vacía) necesitaron
  resetear el estado de paginación (`resetConversationPagination()`) para no arrastrar el cursor de la
  conversación anterior — nueva función chica para no repetir esas 3 líneas cinco veces.
