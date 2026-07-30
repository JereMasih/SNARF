# ADR 0060 — Mini-cerebro clickeable durante "pensando", vuelta automática al chat

**Fecha:** 2026-07-30
**Estado:** Aceptado (versión inicial — ver Consecuencias para lo que queda para una vuelta futura)

## Contexto

El fundador pidió que el indicador de "pensando" (los tres puntitos) sume una mini-animación del cerebro, clickeable, que abra el cerebro completo como si fuera un holograma — y que al llegar la respuesta se vuelva sola al chat, sin que el fundador tenga que cerrarlo a mano.

## Decisión

Se reusa toda la infraestructura ya construida del cerebro en vez de duplicarla: `brainMiniBodyHTML` (el SVG chico + stats del widget del dashboard) se separó en `brainMiniSvgMarkup(data)` (solo el grafo) para poder insertarlo sin las dos líneas de estadísticas, que no hacían falta en un espacio tan chico. `showTyping()` pide `/dashboard/brain` en paralelo (sin bloquear la aparición de los tres puntitos, que siguen apareciendo de inmediato) e inserta esa mini-animación real, clickeable, dentro de la misma burbuja de "pensando". Un click llama a `openBrainFullscreen()` — el mismo mecanismo que ya usa el widget del dashboard, no uno nuevo — y marca `brainOpenedFromThinking = true`. `hideTyping()` (que ya se llama apenas la respuesta real llega) chequea esa marca y cierra el cerebro solo si se había abierto por acá, devolviendo al chat sin que el fundador tenga que hacer nada.

## Verificado

- 445/445 tests (sin cambios de backend — 100% frontend).
- Playwright: la mini-animación aparece durante "pensando" con datos reales de `/dashboard/brain`; el click abre el cerebro completo (`brainPanel.open`); al llegar la respuesta real, se cierra solo — confirmado que `brainPanel` vuelve a no tener la clase `open` apenas el mensaje de Snarf aparece en el chat.

## Consecuencias

- **Simplificación consciente, no lo que se pidió al 100%**: el cerebro se abre con el mismo overlay flotante que ya existe (fondo oscurecido + panel centrado, funciona igual en mobile y desktop) — no se construyó todavía una versión específica de escritorio que quede "contenida dentro de la caja de chat" en vez de un overlay global, que es lo que pidió explícitamente el fundador para esa plataforma. El overlay actual ya cumple el efecto "holograma sobre fondo oscurecido" en cualquier tamaño de pantalla, así que se prioriza tenerlo funcionando ya — la contención específica de escritorio dentro de la caja de chat queda como refinamiento pendiente, a pedido explícito si el fundador lo sigue queriendo después de ver esta versión en uso real.
- El efecto de cámara 3D/perspectiva con paneo por capas (pedido en la misma ronda, confirmado como bien interpretado) sigue sin construir — es la pieza más grande y más creativa, todavía pendiente.
