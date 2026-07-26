# ADR 0012 — Audio bajo demanda, selector de modo segmentado y arranque en conversación nueva

**Fecha:** 2026-07-25
**Estado:** Aceptado

## Contexto

Tres pedidos del fundador tras usar la interfaz: (a) el audio se reproducía automáticamente; quería control explícito de cuándo escucharlo, con velocidad ajustable y opción de cortarlo antes de que termine; (b) el selector de modo (click/mantener/texto) era demasiado chico y estaba demasiado cerca del orbe — tocarlo frecuentemente disparaba grabación por error; (c) la app arrancaba retomando la última conversación, y el fundador prefiere que siempre arranque en una nueva, yendo a buscar una anterior solo si la necesita.

## Decisión

1. **Audio bajo demanda.** Se eliminó la reproducción automática al llegar la respuesta. Cada mensaje de Snarf con audio disponible muestra un botón "▶ escuchar". Al tocarlo aparece una ventana flotante fija (arriba de la pantalla) con indicador de reproducción, un botón de velocidad que cicla 1x/1.25x/1.5x/1.75x/2x/0.75x, y un botón de cierre que corta el audio inmediatamente. Se sigue reutilizando el elemento `<audio>` compartido (necesario para el desbloqueo de audio en iOS, ADR 0009) — ahora la reproducción ocurre directamente dentro del gesto de tocar "escuchar", así que además es más confiable en iOS que el intento anterior de reproducir automáticamente después de una espera asíncrona.
2. **Selector de modo como control segmentado.** Reemplaza al botón de texto chico por tres botones (Mantener / Toque / Texto) con ícono, etiqueta y área de toque generosa, agrupados en una barra con el modo activo resaltado — sin ambigüedad sobre cuál está seleccionado, y con separación suficiente del orbe para no disparar grabación por error.
3. **Arranque siempre en conversación nueva.** Se quitó `resumeLatestOrNew()`. El id de conversación se genera nuevo en cada carga de la página; retomar una anterior es siempre una acción explícita desde la barra lateral.

## Consecuencias

- Los mensajes recuperados desde el historial de una conversación pasada (barra lateral) no tienen botón de audio — nunca se guardó el audio en sí, solo el texto; escuchar una respuesta vieja hoy no está soportado y no se intentó regenerarla (evitar gasto de API innecesario por una funcionalidad no pedida).
- Verificado por lectura de código y por servidor (HTML actualizado, sin referencias residuales al selector viejo). No verificado visualmente por el fundador todavía.
