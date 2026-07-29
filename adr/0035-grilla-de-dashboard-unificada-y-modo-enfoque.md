# ADR 0035 — Grilla de dashboard unificada y redimensionable, modo enfoque

**Fecha:** 2026-07-29
**Estado:** Aceptado

## Contexto

Con la visualización del cerebro terminada por hoy, el fundador pidió cerrar tres bugs de UI reales (texto redundante en modo teclado, la app abriendo el teclado nativo solo en mobile al arrancar, y "escuchar" a veces sin generar audio) y, antes de migrar a un VPS, estandarizar el dashboard de escritorio: hoy el historial de conversaciones y el chat con Snarf viven fuera del sistema de widgets — fijos, sin poder moverse ni cambiar de tamaño — mientras el resto de los widgets solo se pueden reordenar, nunca redimensionar.

Dos decisiones tomadas explícitamente con el fundador antes de construir: (1) grilla con flujo automático (cada bloque controla su ancho/alto, el arrastre decide su posición en el flujo) en vez de posicionamiento libre x/y con colisión — evita construir un motor de colisión/empuje que no existe hoy; (2) chat e historial se pueden mover/redimensionar como cualquier bloque pero nunca se pueden ocultar. El fundador también pidió, en la misma ronda, un modo enfoque (chat a pantalla completa con una barra lateral de historial/nueva conversación/usuario) y confirmó explícitamente posponer "Proyectos" (prompt + archivos por proyecto + organización en Drive — una Capacidad nueva entera, del tamaño de "Modo Capacidades" en `MASTER_MAP.md`) para un ciclo de planificación aparte.

## Decisión

### 1. Tres bugs de UI reales, corregidos

- Texto redundante ("escribí tu mensaje") eliminado del modo teclado — el placeholder de la caja ("Escribile a Snarf...") ya decía lo mismo.
- La app arranca siempre en modo texto (sin cambios), pero `textInput.focus()` ya no se dispara al cargar — antes abría el teclado nativo en mobile sin que el usuario tocara nada. `setMode()` gana un segundo parámetro `autoFocus` (default `true`, `false` solo en el arranque).
- **Bug real de audio, encontrado y corregido**: `sharedAudio.play().catch(() => {})` tragaba en silencio cualquier fallo de reproducción (política de autoplay del navegador, o una carga interrumpida por otro click de "escuchar" mientras cargaba) — el reproductor flotante igual se mostraba como si estuviera sonando. Ahora `playAudio()` propaga el error y `fetchAndPlay()` lo muestra ("error, probá de nuevo") en vez de fallar en silencio.

### 2. Grilla unificada de 12 columnas (solo desktop, ≥900px)

Reemplaza las tres zonas fijas de antes (arriba/izquierda/derecha, con columnas de ancho fijo) por un solo `#dashGridDesktop`: `grid-template-columns: repeat(12, 1fr); grid-auto-rows: 28px; grid-auto-flow: row` (disperso, no `dense`, para que el orden visual siempre coincida con el orden de arrastre). Cada bloque —incluidos "historial" y "chat", nuevos en el sistema de widgets— tiene su propio `col_span`/`row_span`, con valores por defecto pensados para que la primera carga se parezca a la proporción de antes.

`snarf/runtime/dashboard_prefs.py`: `WIDGET_IDS` unificado (agrega `"history"` y `"chat"`), nuevo `ALWAYS_VISIBLE_WIDGET_IDS = {"chat", "history"}` forzado en `_normalize()` — no se pueden ocultar ni con un payload directo a la API. **Bug real corregido de paso**: `_normalize()` reconstruía `widget_options` a mano, hardcodeado solo a la clave `"gmail"` — cualquier otro widget se descartaba en silencio. Se generalizó a un loop sobre todos los `WIDGET_IDS`, con validación real (excluyendo `bool`, que en Python es subclase de `int`) y clamping (`col_span` 1-12, `row_span` 3-30).

**Chat e historial se reparentan, nunca se reconstruyen**: son nodos vivos con listeners atados (grabación, textarea, audio, refresco de conversaciones) — `reparentChatIntoDashboard()`/`reparentHistoryIntoDashboard()` los mueven (`appendChild`, nunca clonar) a un wrapper `.dash-widget` nuevo, una sola vez al arrancar en desktop. El resto de los widgets se siguen reconstruyendo por HTML en cada refresh, igual que antes.

**Reordenamiento, de 1D a 2D**: `makeReorderable()` comparaba solo `clientY` contra el punto medio vertical de cada hermano — funcionaba con una sola columna, pero con bloques de ancho variable en una grilla real necesitaba comparar también X. Cambio quirúrgico al predicado de colisión, mismo mecanismo general. De paso, se corrigió un bug latente en `reorderWithinSubset` (un id oculto en el subset podía terminar asignado `undefined`) — mucho más probable de dispararse ahora que casi todo comparte un solo scope de reordenamiento.

**Redimensionar es un gesto nuevo** (`makeResizable()`, mismo estilo que `makeReorderable`): un handle por bloque, arrastre convierte píxeles a columnas/filas leyendo el ancho real de columna vía `getComputedStyle(grid).gridTemplateColumns` (el navegador ya resuelve `repeat(12,1fr)` a píxeles concretos), aplicado en vivo y persistido al soltar.

**Desktop arranca siempre en el Dashboard** (antes: Chat) — con la distribución guardada la última vez. El botón que alternaba Chat/Dashboard se oculta en modo Jarvis (el chat vive siempre dentro de la grilla); el modo enfoque (punto 3) cubre la misma necesidad de ver el chat solo.

**Mobile queda completamente afuera** — misma razón que en ADR anteriores de este dashboard: el swipe horizontal ya usa el mismo espacio de gesto que un resize táctil necesitaría, y "ancho" no tiene sentido en una columna única de teléfono. Confirmado en vivo: cero handles de resize en mobile, mismo stack de siempre.

### 3. Modo enfoque: chat a pantalla completa + barra lateral reusada

El bloque de chat gana un botón "expandir" — abre un overlay a pantalla completa (mismo esqueleto que el del cerebro, ADR 0031) con el chat de un lado y, del otro, la **misma barra lateral que ya existía** para el menú hamburguesa de mobile (`#sidebar`, con historial, "+ nueva conversación" y el menú de usuario/configuración) — reusada, no duplicada, vía una variante CSS `.docked` que la saca de su modo "cajón fuera de pantalla" mientras el modo enfoque está abierto. Al cerrar, vuelve a su lugar de siempre para que el menú hamburguesa de mobile la siga usando igual. Esta misma barra lateral es la que a futuro va a alojar la navegación de "Proyectos" (pospuesto, ver Contexto).

### 4. "Proyectos" registrado, no construido

Igual que otras veces que una visión más grande apareció en el camino: se registra la intención completa (prompt de proyecto, archivos por proyecto con organización propuesta en Drive, capacidades a estilo Claude/ChatGPT Proyectos) sin construir nada todavía — es una Capacidad nueva entera, merece su propio ciclo de diseño.

## Verificado

- 285 tests (todos los anteriores + 10 nuevos: chat/historial siempre visibles y no ocultables ni vía payload directo; span por defecto para todo widget dentro de límites; guardar/clampear spans válidos e inválidos; regresión específica del bug de `widget_options` — gmail y otro widget sobreviven juntos a un mismo guardado; roundtrip de span vía HTTP; la API tampoco puede ocultar chat/historial).
- Verificado en vivo con Playwright contra datos reales ya guardados (no solo fixtures de test): el archivo de preferencias real del fundador (de antes de este cambio, sin `history`/`chat`) se migró sin intervención manual al cargar — chat/historial aparecieron con sus valores por defecto, y las 4 Capacidades de Google que el fundador ya había ocultado manualmente siguieron ocultas, tal cual las había dejado.
- Resize confirmado real: arrastrar el handle de un widget cambia su `grid-column`/`grid-row` en vivo y persiste después de recargar la página.
- Modo enfoque confirmado real: abrir el chat a pantalla completa, enviar un mensaje real y recibir una respuesta real del LLM dentro del overlay, cerrar y confirmar que el chat vuelve a su bloque normal en la grilla — sin perder ningún estado.
- Mobile confirmado sin cambios: mismo stack de un widget por fila, cero handles de resize en toda la página, arranca en Chat como siempre.

## Consecuencias

- El botón que alternaba Chat/Dashboard ya no tiene función en desktop (oculto vía CSS) — si en el futuro hiciera falta una razón distinta para volver a esa alternancia, es la primera pieza a revisar.
- La barra lateral (`#sidebar`) ahora vive en dos contextos posibles (cajón de mobile, panel acoplado del modo enfoque) — cualquier cambio futuro a su contenido (por ejemplo, sumar la navegación de "Proyectos") aparece automáticamente en ambos, sin duplicar código.
- `snarf/runtime/dashboard_prefs.py` queda como la única fuente de verdad de tamaño/posición por bloque — cualquier Capacidad nueva que sume un widget al dashboard debe agregar su entrada a `DEFAULT_SPANS` (backend) y `DEFAULT_SPANS` (frontend, mismo nombre, dos lugares que deben mantenerse en espejo) para tener un tamaño inicial razonable.
