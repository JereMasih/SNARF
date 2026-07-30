# ADR 0066 — Fix: el botón "reintentar" quedaba visible siempre

**Fecha:** 2026-07-30
**Estado:** Aceptado

## Contexto

El fundador reportó que, tras el ADR 0065 (reintentar una nota de voz fallida), el botón "↻ reintentar" quedó visible permanentemente en todos los chats, sin importar si había algo real para reintentar, y clickearlo no hacía nada.

## Decisión

Mismo bug exacto ya documentado en ADR 0059 para `.text-row .icon-btn`: `.retry-btn { display: flex; ... }` (regla de autor) le ganaba al `[hidden]` del navegador (regla de user-agent) — el atributo `hidden` se seguía poniendo/sacando correctamente desde JS (`setRetry`/`clearRetry`), pero visualmente no tenía ningún efecto, así que el botón se veía siempre. Como `pendingRetry` en ese estado siempre era `null` (nunca hubo un error real que lo poblara), clickearlo no hacía nada — el guard `if (fn) fn()` correctamente no ejecutaba nada. Fix: `.retry-btn[hidden] { display: none; }`.

De paso, se corrigió un segundo problema real (no reportado explícitamente pero visible en el mismo síntoma): `pendingRetry` es un estado global único, no por-conversación — cambiar de conversación sin que hubiera ocurrido ningún error todavía no lo afectaba, pero SI había un reintento pendiente de una conversación y el fundador navegaba a otra antes de resolverlo, el botón seguía mostrándose ahí y un click hubiera reintentado contra la conversación equivocada. `loadConversation()` y `startNewConversation()` ahora llaman `clearRetry()` al entrar.

## Verificado

- 475/475 tests (sin cambios de backend).
- Playwright: `getComputedStyle(retryBtn).display === "none"` tanto al cargar la página como después de un envío de texto exitoso — confirma que ya no queda visible sin una falla real.

## Consecuencias

Ninguna — fix acotado, mismo patrón ya conocido del repo.
