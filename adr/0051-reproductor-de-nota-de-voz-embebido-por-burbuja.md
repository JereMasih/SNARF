# ADR 0051 — Reproductor de nota de voz embebido por burbuja (reemplaza el reproductor flotante)

**Fecha:** 2026-07-29
**Estado:** Aceptado

## Contexto

Apenas terminado ADR 0050, el fundador probó el flujo real y señaló el problema de fondo que ese ADR no había resuelto del todo: el botón "escuchar" seguía abriendo el reproductor flotante único de siempre (pausa, velocidad, cerrar) — pero **una vez que lo pausabas o cerrabas, no había forma de volver a darle play**. Pidió específicamente:

1. Que el botón deje de decir "escuchar" y pase a ser una acción explícita de generar la nota de voz.
2. Que el resultado sea una burbuja de nota de voz real y persistente, con su propio play/pausa/velocidad — replayable de verdad, no un reproductor de un solo uso.
3. Un menú de opciones (⋮) con **compartir** (pensando en iPhone) y **descargar** (pensando en escritorio).
4. Que la nota de voz PROPIA del usuario (ADR 0050) reciba el mismo tratamiento, no solo la de Snarf.
5. "Optimizalo y elevalo... con la mejor lógica, las mejores prácticas... de la industria."

## Decisión

### Un solo reproductor embebido, reusado por cada burbuja

`buildVoiceNotePlayer(audioId, downloadName)` reemplaza por completo al reproductor flotante (`#audioPlayer`, `playAudio()`, `fetchAndPlay()`, retirados) y se usa **en los dos lugares** (nota de voz del usuario y nota de voz generada de una respuesta de Snarf) — antes cada uno tenía su propio camino distinto. Cada burbuja obtiene su propia fila con:
- Botón play/pausa circular, progreso (barra clickeable/seekable), tiempo transcurrido/duración, velocidad (mismo ciclo `SPEEDS` de siempre) y un menú ⋮ (reusa `buildConvMenu`, el mismo patrón visual ya usado para las conversaciones).

**Por qué un solo `<audio>` real (`sharedAudio`) sigue alcanzando**, en vez de un elemento por burbuja: es el mismo criterio que cualquier reproductor de medios de la industria (Spotify, WhatsApp Web, YouTube) — solo suena una cosa a la vez. `activeVoiceNotePlayer` guarda cuál burbuja es la "dueña" del audio real en cada momento; los listeners de `sharedAudio` (`timeupdate`/`play`/`pause`/`ended`) se registran **una sola vez, globalmente**, y actualizan solo la burbuja activa — evita acumular un listener nuevo por cada nota de voz que aparece en una conversación larga.

### Respuesta de Snarf: acción explícita, no automática

`generateVoiceNote(text, btn)` reemplaza a `fetchAndPlay`: el botón dice "🎙️ generar nota de voz" (antes "▶ escuchar"), pide `/tts` (cacheado desde ADR 0050 — instantáneo si ya se generó antes) y **reemplaza el propio botón por el reproductor embebido real** (`btn.replaceWith(...)`) en vez de reproducir directo. `TTSResponse` suma `audio_id` (además de `audio_base64`, que se mantiene) para que el frontend arme la URL real `/audio/{id}` en vez de depender de un data-URI de un solo uso.

### Compartir y descargar

Dentro del menú ⋮ de cada nota de voz:
- **Descargar** (siempre disponible): pide `/audio/{id}`, arma un blob y dispara una descarga real vía `<a download>` — funciona en cualquier navegador de escritorio.
- **Compartir** (solo si `navigator.canShare` existe — iPhone/Android y algunos navegadores de escritorio modernos): arma un `File` real a partir del mismo blob y usa la Web Share API (`navigator.share({ files: [file] })`) — el mecanismo estándar real para "compartir un archivo" desde una web, no un link ni un truco.

## Verificado

- 414/414 tests de backend (el único cambio de contrato es que `TTSResponse` ahora también expone `audio_id`; test de disponibilidad ajustado).
- Playwright contra una instancia real aislada: mensaje real → "generar nota de voz" real (ElevenLabs) → reproductor embebido aparece reemplazando el botón; con un audio más largo (~16s) se confirmó de punta a punta que **pausar y volver a reproducir funciona de verdad** (el tiempo se congela en pausa y sigue avanzando al reanudar — la funcionalidad que faltaba), el seek por click en la barra de progreso salta al punto correcto, el ciclo de velocidad funciona, y el menú ⋮ ofrece "descargar" (Web Share API no disponible en Chromium headless, comportamiento esperado y ya contemplado en el código). Cero errores de consola.

## Consecuencias

- El reproductor flotante único (`#audioPlayer`) queda completamente retirado — cualquier necesidad futura de reproducir audio en esta interfaz debería partir de `buildVoiceNotePlayer`, no reinventar un tercer mecanismo.
- La nota de voz generada de una respuesta de Snarf no se persiste como "ya generada" al recargar la conversación (no hay `response_audio_id` en el log) — gracias al caché por contenido de ADR 0050, volver a pedirla es instantáneo, pero el botón "generar nota de voz" reaparece en vez de mostrar el reproductor de una vez. Señalado como posible mejora futura si en el uso real resulta molesto.
