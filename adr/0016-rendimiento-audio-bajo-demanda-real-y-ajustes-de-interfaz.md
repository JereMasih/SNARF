# ADR 0016 — Rendimiento: TTS realmente bajo demanda, calentamiento de conexión

**Fecha:** 2026-07-25
**Estado:** Aceptado

## Contexto

El fundador reportó que la interfaz se sentía demasiado lenta. Investigando, se encontraron dos causas reales, no una sola:

1. ADR 0012 hizo la **reproducción** de audio bajo demanda, pero `/send` seguía **generando** el audio con ElevenLabs en cada respuesta, se fuera a escuchar o no — un trabajo desperdiciado en la mayoría de los turnos.
2. El cliente HTTP hacia la API de Anthropic paga un costo de conexión (TLS/handshake) la primera vez que se usa; medido en aislamiento, la primera llamada tomó 6-7s contra 1.3-1.5s en llamadas posteriores sobre la misma conexión ya establecida.

## Decisión

1. `/send` ya no sintetiza audio. Nuevo endpoint `POST /tts` que recibe el texto y devuelve el audio, llamado por el frontend recién cuando se toca "escuchar" — incluye además una mejora no pedida pero derivada gratis: ahora también se puede escuchar el audio de mensajes de conversaciones pasadas (antes no se podía, porque el audio nunca se guardaba).
2. Se agregó `AnthropicLLM.warmup()` / `Orchestrator.warmup()`, invocado al arrancar `app.py`, que hace una llamada mínima a la API para establecer la conexión antes de que llegue la primera consulta real.
3. Ajustes menores pedidos: velocidad de reproducción por defecto 1.25x (antes 1x), botón "escuchar" siempre en su propia línea dentro del globo de respuesta (antes podía quedar pegado al texto).
4. Corregido además, en la misma revisión: el chat no scrolleaba correctamente en Chrome de escritorio después de una respuesta larga — bug conocido de `flex-direction: column` + `justify-content: flex-end` en contenedores con overflow. Se reemplazó por el patrón robusto (contenedor scrolleable simple + wrapper interno con `margin-top: auto`).

## Verificado

Medido directamente, no supuesto: llamada aislada sin system prompt/tools, 2.9s; con el system prompt e identidad completos (19.696 caracteres) y las 12 herramientas, 2.25s — el prompt grande no es la causa de lentitud. La causa real era el costo de la primera conexión: 6-7s en frío vs 1.3-1.5s en caliente, medido en la misma sesión de Python reutilizando el cliente. Con el calentamiento al arrancar, la primera consulta real bajó de ~10.8s a ~5s; la segunda y siguientes, ~1.5-2s.

## Consecuencias

- El calentamiento agrega unos segundos al arranque del servidor (antes de que "Application startup complete" se imprima), invisible para el uso normal.
- Queda un margen de ~3s sin explicar del todo entre el calentamiento y la primera consulta real; no se investigó más a fondo por rendimientos decrecientes — el caso común (segunda consulta en adelante) ya está resuelto.
- `@app.on_event("startup")` está deprecado en FastAPI (advertencia, no error); migrar a `lifespan` queda como deuda técnica menor, no urgente.
