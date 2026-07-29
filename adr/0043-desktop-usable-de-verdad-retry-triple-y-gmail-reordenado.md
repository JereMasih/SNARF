# ADR 0043 — Desktop usable de verdad: reintento triple, widgets que no se cortan, Gmail reordenado

**Fecha:** 2026-07-29
**Estado:** Aceptado

## Contexto

Verificando en vivo el trabajo de ADR 0041, aparecieron regresiones y bugs reales adicionales, algunos preexistentes a esta sesión:

1. El widget de Gmail seguía mostrando `[SSL] record layer failure` incluso con el reintento único de ADR 0041 — confirmado con Playwright contra el server real: el mismo error puede pegarle tanto al intento original como al reintento (es una falla de red genuinamente intermitente, no una conexión rota de una vez para siempre).
2. Al achicar un widget arrastrando su esquina, el título y subtítulo podían recortarse junto con el contenido — `.dash-widget-head`/`.dash-widget-sub` no tenían `flex-shrink: 0`, así que en un contenedor flex-column angosto se comprimían en vez de quedar fijos mientras solo el cuerpo scrollea.
3. El widget de Gmail mostraba primero la lista de mensajes y, bien abajo, la interpretación — al revés de lo que el fundador quiere leer primero.
4. **Bug real preexistente, no de esta sesión**: en modo desktop (`body.jarvis-mode`), `.menu-btn` (el botón hamburguesa que abre el cajón lateral con el menú de usuario — configuración del dashboard y cerrar sesión) estaba día directamente `display: none`, sin ningún reemplazo. El historial de conversaciones ya es un bloque siempre visible de la grilla en desktop, pero **la configuración y el cierre de sesión no tenían ningún otro camino** — quedaban completamente inalcanzables en escritorio.
5. El toggle de modo Toque/Teclado (`#modeFab`) seguía visible en desktop, donde no aporta nada: el modo Toque es el orbe a pantalla completa, y en desktop la caja de texto ya tiene su propio botón de micrófono al lado.

Verificado también, no como bug sino como estado esperado: los widgets de "costo" y "uso real de APIs" mostraban `$0.00`/`0 caracteres` — consecuencia directa y honesta del incidente documentado en ADR 0042 (pérdida real de `usage_log.jsonl`), no un bug nuevo. El cupo real de ElevenLabs sí se mostraba correctamente (50.036/65.000), confirmando que esa parte funciona.

## Decisión

### 1. Reintento triple, no único

`retry_once_with_fresh_client` (ADR 0041) pasa a `retry_with_fresh_client`, con `MAX_ATTEMPTS = 3` (intento original + 2 reintentos) y una pausa corta (`RETRY_DELAY_SECONDS = 0.4`) entre cada intento fallido, dándole tiempo real a la falla transitoria de resolverse. Sigue sin ocultar un fallo persistente: agotados los 3 intentos, se propaga igual que antes.

### 2. `flex-shrink: 0` en título y subtítulo de cada widget

Solo `.dash-widget-body` (que ya tenía `overflow-y: auto`) absorbe la reducción de tamaño al achicar un widget — título y subtítulo quedan con su altura natural siempre, nunca comprimidos.

### 3. Gmail: interpretación primero, lista después

`gmailBodyHTML()` invierte el orden: `.dash-gmail-digest` (botón "interpretar bandeja" + contenido) va primero; `.dash-gmail-list` (selector de cantidad + mensajes) va debajo, con el borde separador que antes tenía el digest.

### 4. Acceso a perfil/configuración restaurado en desktop

Se elimina el `display: none` de `.menu-btn` en `body.jarvis-mode` — el botón hamburguesa vuelve a estar visible también en escritorio, en la franja superior fija (por encima de la grilla, sin superponerse a ningún widget). Abre el mismo cajón lateral de siempre (`#sidebar`), que ya funcionaba de forma independiente del modo Jarvis — ahí vive el menú de usuario con configuración del dashboard y cerrar sesión.

### 5. Toggle Toque/Teclado oculto en desktop

`body.jarvis-mode .mode-fab { display: none; }`. Desktop arranca siempre en modo Teclado (`let mode = "text"`, sin persistencia en `localStorage`), así que ocultar el toggle no deja a nadie atascado en modo Toque sin salida.

## Verificado

- 305/305 tests (todos los cambios de este ADR son de frontend o de una constante de reintentos ya cubierta por `tests/test_google_retry.py`, actualizado para 3 intentos).
- Playwright contra una copia aislada del repo: `menuBtn` visible y funcional en desktop (abre el cajón, `#settingsBtn` visible y funcional, abre el panel de configuración de verdad); `modeFab` oculto; al achicar un widget a su tamaño mínimo, título y subtítulo mantienen su altura completa (no se recortan).
- Playwright contra el server real (solo lectura, sin tocar datos): confirmado el error SSL real en el widget de Gmail antes de este fix.

## Consecuencias

- El botón hamburguesa ahora es el único camino a "configuración del dashboard" y "cerrar sesión" en desktop — si en el futuro se agrega otro punto de entrada más directo (ej. un ícono de perfil dedicado en la grilla), hay que decidir si el hamburguesa se mantiene como respaldo o se retira.
- El reintento triple agrega hasta ~0.8s de latencia extra en el peor caso (2 fallos + 2 pausas) antes de mostrar un error real — aceptable para un widget que se refresca en segundo plano, no para una acción disparada por click directo del usuario que espera respuesta inmediata.
