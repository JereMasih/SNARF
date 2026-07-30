# ADR 0050 — Notas de voz reproducibles (estilo WhatsApp) y caché de audio de Snarf

**Fecha:** 2026-07-29
**Estado:** Aceptado

## Contexto

El botón de "escuchar" seguía sin convencer al fundador tras ADR 0049. Pidió repensarlo de fondo, mirando WhatsApp/ChatGPT como referencia: que la nota de voz del usuario quede guardada y reproducible como un audio real (no solo transcripta y descartada), con la transcripción disponible debajo como desplegable; que la respuesta de Snarf siga mostrándose como texto por defecto (sin cambios ahí), pero que escucharla varias veces no vuelva a pagar ni esperar una síntesis nueva cada vez; y un protocolo real de limpieza de espacio, porque **las transcripciones y respuestas de texto se guardan para siempre, pero los archivos de audio en sí no deberían acumularse indefinidamente**.

Confirmado con el fundador antes de implementar: purga **automática a los 7 días** para los archivos de audio (elegido explícitamente entre esa opción, 30 días, o solo manual — coherente con priorizar espacio sobre "replay histórico" de audios viejos). El texto/transcripción nunca se toca por esta purga.

## Decisión

### 1. `snarf/memory/audio_store.py` — nuevo módulo

`AudioStore`: guarda bytes de audio reales en `data/audio/` (nunca en `episodic_memory.jsonl`, que sigue siendo texto puro). Tres usos:
- `save(data, ext)`: nota de voz nueva del usuario → id `uuid4().hex + ext`.
- `save_tts(text, data)` / `get_cached_tts(text)`: caché de respuestas de Snarf ya sintetizadas, indexado por **hash del contenido** (`sha256(text)[:32]`) — mismo texto de respuesta siempre da el mismo archivo, así escuchar la misma respuesta más de una vez nunca vuelve a llamar a ElevenLabs.
- `purge_older_than(seconds)`: borra por antigüedad real de archivo (`mtime`), sin distinguir tipo — ambos casos son "audio caro en espacio, ya no necesario".
- `path_for(audio_id)`: única función que traduce un id que llega crudo por URL a una ruta de disco — valida extensión contra una lista fija y rechaza cualquier `/`, `\` o `..` antes de tocar el filesystem.

### 2. Nota de voz del usuario: persistida y reproducible

`POST /transcribe` guarda el audio real **antes** de intentar transcribir (así sigue existiendo aunque el STT falle o no detecte voz — se pierde solo si nadie la usa y pasan 7 días) y devuelve `audio_id` junto al transcript de siempre. `SendRequest`/`Orchestrator.handle()`/`EpisodicMemory.append()` suman `input_audio_id` opcional (default `None`, compatible con entradas viejas del log). Nuevo `GET /audio/{audio_id}` sirve el archivo (mismo `require_user` que el resto de la API).

Frontend: el flujo de grabación (ADR 0049) pasa el `audio_id` real a `sendText()`. `addMessage()` renderiza el mensaje del usuario como una nota de voz —botón "▶ nota de voz" que reusa el mismo reproductor flotante ya existente (`playAudio("/audio/" + id)`, sin cambios en ese componente) más un desplegable "▾ transcripción" oculto por defecto— en vez de mostrar el texto transcripto directo. `loadConversation()` reproduce el mismo render al recargar historial real.

### 3. Respuestas de Snarf: sin cambio de interfaz, con caché real

A pedido explícito, la respuesta de Snarf sigue mostrándose como texto igual que siempre — lo único que cambia es `POST /tts`: antes de sintetizar, consulta `audio_store.get_cached_tts(text)`; si ya existe, la sirve directo sin tocar ElevenLabs. El botón "▶ escuchar" no cambió de código — la eficiencia vive enteramente del lado del servidor.

### 4. Purga automática

`app.py` suma `_periodic_audio_purge_loop()` (mismo patrón que `_periodic_backup_loop` de ADR 0042), cada 6 horas, más una pasada inmediata al arrancar — purga archivos de `data/audio/` con más de 7 días, sin distinguir notas de voz de caché de TTS. `data/audio/` sumado a `.gitignore`.

## Verificado

- 414/414 tests (16 nuevos: `AudioStore` completo incluyendo rechazo de path traversal y extensión inválida, `/transcribe` guardando audio real aunque el STT falle, `GET /audio/{id}` sirviendo bytes reales y devolviendo 404 ante un id inválido/inexistente, `/send` persistiendo `input_audio_id`, y `/tts` cacheando — confirmado con un contador de llamadas reales a `synthesize` que la segunda petición con el mismo texto no vuelve a sintetizar).
- Playwright contra una instancia real aislada: `POST /transcribe` con audio real guarda y devuelve un `audio_id` real; `GET /audio/{id}` sirve exactamente los mismos bytes subidos; un id inventado devuelve 404; el bubble de nota de voz renderiza con el desplegable de transcripción oculto por defecto y visible al togglear; el botón de reproducir llama al reproductor flotante ya existente y degrada con gracia (sin errores de consola) cuando el audio no es decodificable.

## Consecuencias

- Si en algún momento se quiere mostrar "cuánto durará" antes de escuchar una nota de voz (duración real), hace falta leer la duración del archivo en el servidor o calcularla en el browser al grabar — hoy no se persiste, solo los bytes.
- El caché de TTS es por contenido exacto del texto — una respuesta editada o regenerada (no debería pasar hoy, las respuestas del LLM no se reescriben) generaría un archivo de caché distinto; consistente con el resto del sistema, que nunca reescribe respuestas ya dadas.
