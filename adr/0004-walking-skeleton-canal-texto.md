# ADR 0004 — Walking skeleton por canal de texto

**Fecha:** 2026-07-25
**Estado:** Aceptado

## Contexto

BUILD MODE 001 pide un Runtime multicanal (voz, texto, PDFs, imágenes, APIs) y un walking skeleton ejecutable de punta a punta, construyendo hasta donde sea posible sin depender de credenciales externas todavía no provistas (ElevenLabs, Anthropic).

## Decisión

Se implementa primero el canal de texto (`TextChannel`), que no requiere ninguna credencial y corre de punta a punta hoy mismo: entrada por stdin → Core Cognitivo → memoria episódica → salida por stdout. El canal de voz (`VoiceChannel`) se define con el mismo contrato (`Channel`) pero sus métodos dependen de `ELEVENLABS_API_KEY`; sin esa credencial, lanzan un error explícito señalando qué falta, en vez de fallar de forma confusa o simular una respuesta.

Un walking skeleton se mide por profundidad de punta a punta, no por amplitud de canales simultáneos. Construir los cinco canales mencionados en el mismo momento habría dejado todos a medias; construir uno completo deja una arquitectura real sobre la cual el resto se agrega por extensión, no por reescritura.

## Consecuencias

- Hoy es posible conversar con Snarf por texto de punta a punta, con memoria persistente entre sesiones.
- Agregar el canal de voz consiste en completar `VoiceChannel` y `ElevenLabsTTS`/`ElevenLabsSTT` una vez provista la credencial — no en rediseñar el Runtime.
- PDFs, imágenes, APIs y automatizaciones futuras se agregan como nuevos `Channel` o `Capability` cuando exista un caso de uso real, conforme al principio de evitar proliferación sin contenido que la justifique.
