# ADR 0027 — Panel superior movible y transparencia de paneles/burbujas

**Fecha:** 2026-07-27
**Estado:** Aceptado

## Contexto

Al usar el layout Jarvis ya con ADR 0026 corregido, el fundador notó que todos los paneles se podían arrastrar excepto el de arriba (Conversaciones) — confirmó que la columna izquierda (lista de conversaciones + estado del sistema) está bien que quede fija, pero el panel superior no debería estarlo. También pidió que los paneles y las burbujas de chat dejen de ser un tinte plano y tengan un degradé del centro (más visible) hacia los bordes (más oscuro), coherente con el resto de la estética Jarvis, cuidando que la línea de escaneo de fondo siga pasando por detrás de todo.

## Decisión

1. **Panel superior movible**: `TOP_ZONE` (fijo, un solo widget) y `RIGHT_ZONE` se fusionaron en un solo grupo reordenable, `TOP_AND_RIGHT_ZONE` (los 6 widgets salvo "Estado del sistema", que sigue fijo a la izquierda por decisión explícita del fundador). El primer widget de ese orden combinado ocupa la franja superior (ancho completo); el resto cae en la columna derecha. Arrastrar cualquier widget al principio lo "asciende" a la franja de arriba; arrastrar el que estaba arriba hacia abajo lo "baja" a la columna derecha.
2. **`makeReorderable` generalizada** para operar sobre varios contenedores como si fueran una sola lista (antes solo aceptaba un contenedor): al soltar, se recalculan los ids combinando ambas zonas y se vuelve a renderizar el dashboard completo, que reasigna automáticamente cuál widget va arriba y cuáles a la derecha según el nuevo orden.
3. Las funciones de refresco de Gmail (`checkGmailForNewMail`, `startGmailDigestPolling`) ya no asumen que el widget de Gmail vive en una zona fija — ahora lo buscan por id en todo el documento, porque después de este cambio puede terminar en la franja de arriba o en la columna derecha según cómo el fundador lo haya movido.
4. **Transparencia de paneles y burbujas**: `.dash-widget`, `.msg.user` y `.msg.snarf` pasan de un `background` plano semitransparente a un `radial-gradient` (más tinte/brillo en el centro, oscureciendo hacia el borde) más `backdrop-filter: blur(6px)` para el efecto de vidrio esmerilado ya usado en el sidebar y el panel de configuración. Verificado que la línea de escaneo de fondo (`.scanline`) sigue pasando detrás: ya pintaba por debajo de `#appRoot` desde el fix de stacking de ADR 0024 (`#appRoot` tiene su propio `z-index:2`, mayor al `z-index:1` de `.scanline`) — lo que se veía "por encima" antes era la línea transparentándose a través de un fondo casi 100% translúcido, no un problema real de orden de apilamiento.

## Verificado

- Con Playwright (mouse real): arrastrar el primer widget de la columna derecha hasta la franja superior efectivamente lo promueve, y el que estaba arriba pasa a la columna derecha.
- Suite completa: 93/93 (sin tests nuevos — cambio de CSS y de mecánica de arrastre ya cubierta por el patrón existente).
- Captura de pantalla real confirmando el degradé aplicado y la línea de escaneo pasando por detrás de los paneles.

## Consecuencias

- La zona de cada widget (arriba/izquierda/derecha) ya no es un dato fijo por id — se deriva en cada render de la posición en `panel_order`. Cualquier código que asuma "Gmail siempre está en la columna derecha" (como pasaba antes en las funciones de refresco) queda roto por diseño; ya corregido en este mismo ADR, pero vale tenerlo presente para futuros widgets.

## Adenda (misma jornada) — textura, tipografía y modos de entrada simplificados

El fundador pidió, en la misma ronda: paneles y burbujas con más textura (degradé más marcado del centro al borde, con un leve resplandor cian en el borde interior, no solo transparencia plana); títulos de widget menos "gritados" (de `font-weight: 500` a `400`, tamaño levemente mayor); y una simplificación real del selector de modo de entrada, de tres modos (mantener presionado / toque / texto) a dos (toque, con el orbe ahora más chico para darle protagonismo a la conversación; y teclado, que pasa a ser el modo por defecto tanto en desktop como en mobile). El modo teclado ahora tiene un botón de micrófono embebido junto al campo de texto: un clic empieza a grabar, el siguiente clic detiene, transcribe, y coloca el texto en el campo para revisar antes de enviar — mismo mecanismo de grabación ya existente (`startRecording`/`stopRecording`/`transcribeBlob`), sin una vista previa separada. El botón de enviar pasa de texto a un ícono de flecha hacia arriba.

**Explícitamente pospuesto, no descartado**: el fundador también pidió ancho variable por widget (que cada panel pueda ocupar 1 o más columnas), una zona izquierda tan flexible como la derecha (hoy fija a lista de conversaciones + estado del sistema), y que la posición del propio módulo de chat sea reubicable. Se señaló que esto es, en los hechos, construir un editor de layout tipo grilla genérico (similar a un dashboard de BI) — una inversión de arquitectura real, no un ajuste de CSS — y se dejó pendiente de una ronda dedicada en vez de improvisarlo dentro de esta.

**Verificado**: con Playwright — el modo por defecto es teclado (orbe oculto, fila de texto visible), el selector solo ofrece dos modos, el orbe mide ~133px (antes 180px), y el flujo completo del botón de micrófono (grabar → detener → transcribir → texto en el campo) se probó de punta a punta con un dispositivo de audio falso de Chromium, incluyendo una llamada real a la API de transcripción (no simulada).

## Segunda adenda (misma jornada) — vidrio esmerilado real

El primer intento de degradé (arriba) subía la opacidad de fondo en vez de bajarla, lo que en los hechos volvía los paneles más opacos, no más transparentes — al pedir "vidrio esmerilado" el fundador quería lo contrario: que la línea de escaneo y las partículas de fondo se sigan viendo *a través* del panel, difuminadas, no tapadas. Corregido bajando la opacidad del degradé en toda la curva (antes hasta 0.9 en el borde, ahora hasta ~0.46) y subiendo el `backdrop-filter` de 6-7px a 15px + `saturate(1.3)` — el desenfoque real de vidrio esmerilado depende de cuánto se ve *detrás*, no de cuán oscuro es el tinte. Verificado con capturas de pantalla: la línea de escaneo y las partículas ahora se ven claramente a través de paneles y burbujas, difuminadas, no tapadas.

## Tercera adenda (misma jornada) — más transparencia, menos difuminado

El fundador ajustó el pedido: quería aún más transparencia y *menos* desenfoque, para que el paso de la línea de escaneo por detrás de paneles y burbujas se disfrute con nitidez en vez de perderse en el blur. Se bajó `backdrop-filter` de `blur(15px)` a `blur(4px)` en `.dash-widget`, `.msg.user` y `.msg.snarf`, y se redujo aún más la opacidad del degradé radial en los tres (por ejemplo, en `.dash-widget` de `0.11/0.3/0.46` a `0.07/0.16/0.24`). El borde se mantuvo (incluso levemente más marcado) para que el panel siga siendo legible como forma pese a la mayor transparencia del fondo. Verificado con Playwright contra el servidor real (cookie de sesión generada con `create_session_token`, sin pasar por el login): la línea de escaneo y la grilla de fondo cruzan un globo de chat real con nitidez, no como un borrón difuso.
