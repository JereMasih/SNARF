# ADR 0006 — Interfaz visual y grabación manual start/stop

**Fecha:** 2026-07-25
**Estado:** Aceptado

## Contexto

La primera prueba en vivo del canal de voz (ADR 0005) falló: la grabación de duración fija (5-6s) no coincidía con el momento real en que el fundador hablaba, capturando silencio. Además, el fundador pidió control manual de inicio/fin de grabación y una interfaz visual de interacción en vez de un REPL de terminal, inspirada en el principio (no en la implementación ni la marca) de HUD conversacional de asistentes de ciencia ficción tipo JARVIS.

## Decisión

1. `LocalAudioIO` ahora soporta grabación manual (`start_recording()` / `stop_recording()` sobre `sounddevice.InputStream`), además del método de duración fija que ya tenía (usado como utilidad, no como flujo principal).
2. `VoiceChannel` (REPL de terminal) se actualizó para usar inicio/fin manual por Enter, en vez de una ventana fija.
3. Se agregó un tercer punto de entrada de Runtime: `app.py`, un servidor FastAPI local con dos endpoints (`POST /start`, `POST /stop`) que envuelven grabación manual → transcripción → Orchestrator → síntesis → reproducción, y sirven una interfaz visual (`web/index.html`): un orbe con estados (inactivo, escuchando, pensando/hablando) controlado con un solo click. El diseño es propio — un HUD minimalista con pulso y anillos — no una reproducción de ninguna interfaz de ficción con derechos de autor.
4. Se corrigió un bug real encontrado durante esta prueba: `AnthropicLLM.generate` asumía que `response.content[0]` era siempre un bloque de texto; el modelo puede anteponer un bloque de razonamiento (`ThinkingBlock`), lo que rompía la respuesta. Ahora se concatenan únicamente los bloques de tipo `text`.

## Consecuencias

- Runtime tiene ahora tres puntos de entrada equivalentes en capacidad, distintos en canal: `main.py` (texto), `main.py --voice` (voz por terminal), `app.py` (voz con interfaz visual). Los tres comparten el mismo `Orchestrator` y las mismas Capacidades — ninguno duplica lógica de identidad o razonamiento.
- El estado "hablando" de la interfaz visual es aproximado: `/stop` no responde hasta que la reproducción de audio termina (bloqueante vía `afplay`), así que "pensando" y "hablando" ocurren dentro de la misma espera HTTP. Se documenta como simplificación consciente, no como limitación oculta.
