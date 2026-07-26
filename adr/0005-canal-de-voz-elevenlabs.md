# ADR 0005 — Canal de voz real con ElevenLabs

**Fecha:** 2026-07-25
**Estado:** Aceptado

## Contexto

ADR 0004 dejó el canal de voz como interfaz sin implementar, a la espera de credenciales. El fundador proveyó `ELEVENLABS_API_KEY`, eligió `voice_id` (Antonio - Confident, Gentle and Clear, es-AR) y actualizó su cuenta a plan Starter tras un primer intento fallido por código 402 (las voces de biblioteca no son usables vía API en plan Free).

## Decisión

Se implementaron `ElevenLabsTTS.synthesize` y `ElevenLabsSTT.transcribe` contra la API real de ElevenLabs (`eleven_multilingual_v2` para síntesis, `scribe_v1` para transcripción), y una nueva Capacidad `LocalAudioIO` (`snarf/capabilities/audio_io.py`) para reproducción (`afplay`, nativo de macOS) y grabación de micrófono (`sounddevice`/`soundfile`). `VoiceChannel` quedó implementado sobre estas tres Capacidades. `main.py` acepta `--voice` para usar este canal en vez del de texto.

## Verificación

- Síntesis + reproducción: verificado end-to-end, audio real generado y reproducido.
- Transcripción: verificado mediante round-trip (el audio sintetizado se transcribió correctamente de vuelta al texto original).
- Captura de micrófono en vivo: implementada, **no verificada en esta sesión** — requiere que el fundador ejecute `python3 main.py --voice` interactivamente (macOS pedirá permiso de micrófono la primera vez).

## Consecuencias

- `LocalAudioIO.play` depende de `afplay`, específico de macOS. Portabilidad a otro sistema operativo queda pendiente y sin urgencia (ADR 0002 ya asume el mismo tipo de costo de cambio acotado a un adaptador).
- El plan de ElevenLabs (Starter) es ahora una dependencia operativa real del canal de voz; su costo y límites de caracteres no están todavía monitoreados por el sistema.
