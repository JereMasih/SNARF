# ADR 0056 — Capa de voz con proveedores intercambiables (Groq/Kokoro), split texto/habla

**Fecha:** 2026-07-30
**Estado:** Aceptado (Parte 1 de 4 de un plan de eficiencia de costo; Partes 2-3-4 pendientes)

## Contexto

El fundador planteó un problema de costo real y explícito: la voz sale hoy por ElevenLabs para TODO (STT del audio que graba, TTS de cada respuesta completa) y eso le hace pensar dos veces antes de hablarle a Snarf, lo cual rompe el propósito del canal de voz. Pidió, en una spec detallada de cuatro partes, resolver primero (Parte 1) una capa de voz con proveedores intercambiables detrás de una interfaz, de forma que el costo marginal de una conversación de voz cotidiana tienda a cero — reservando explícitamente ElevenLabs para cuando se pida voz de verdad o el trabajo produzca un asset publicable.

Principios que gobiernan todo el diseño (dados por el fundador, aplicados literalmente): empezar barato y escalar solo ante evidencia de fallo real, nunca por anticipación; ningún proveedor cableado — todo detrás de una interfaz, cambiarlo es una línea de config; nada se mide después — toda llamada real a voz queda registrada con su costo (real o cero); y la optimización más grande no es de proveedor sino de contenido: separar lo que se muestra en pantalla de lo que se dice en voz, para no leer en voz alta una respuesta completa con markdown y desarrollo largo.

## Decisión

### 1. `snarf/voice/` — interfaz + proveedores intercambiables + router

`snarf/voice/interface.py` define dos contratos (`STTProvider`, `TTSProvider`, ambos extienden el `Capability` ya existente en `snarf/capabilities/base.py` — mismo patrón `name`/`available` que ya usa el resto del proyecto). `snarf/voice/providers/` tiene una implementación por proveedor, ninguna importada directamente desde el resto de Snarf:

- `groq_stt.py` — STT primario, Groq (`whisper-large-v3-turbo`, ~USD 0.04/hora), hand-rolled sobre `requests` (mismo estilo que `ElevenLabsSTT` ya existente, sin el SDK oficial de Groq — no hace falta, la API es HTTP directa). Usa `response_format=verbose_json` para leer la duración real del audio desde la propia respuesta de Groq (lo que factura), no el tiempo de la request.
- `local_stt.py` — fallback 100% local (`faster-whisper`, CPU, costo cero), para cuando no hay red o Groq falla. Corre en proceso, no en Docker — a diferencia de Kokoro (que se usa en cada turno y por eso vive aislado en su propio contenedor), este solo se invoca cuando ya no hay red, momento en el que un contenedor no ofrece aislamiento real adicional.
- `kokoro_tts.py` — tier 'local' de TTS. Cliente HTTP puro contra un contenedor Docker de [Kokoro-FastAPI](https://github.com/remsky/Kokoro-FastAPI) (`ghcr.io/remsky/kokoro-fastapi-cpu:latest`), endpoint compatible con la API de OpenAI (`POST /v1/audio/speech`). Deliberadamente NO embebe el modelo en el proceso de Snarf — mover este tier de la Mac a un VPS es cambiar `base_url` en `voice/config.yaml` (ver Parte 4 del plan, pendiente).
- `elevenlabs_tts.py` — adaptador de la Capacidad `ElevenLabsTTS` ya existente al contrato `TTSProvider`. Tier 'premium' únicamente — el router nunca escala acá por su cuenta.
- `hosted_tts.py` — stub deliberado para el tier 'hosted' (gpt-4o-mini-tts / Cartesia / Inworld, a elegir). Ver Consecuencias.

`snarf/voice/config.yaml` declara el proveedor activo por tier (STT primario+fallback, TTS local/hosted/premium) y la config propia de Kokoro (`base_url`, `voice`) — cambiar de proveedor o mover un tier a otra máquina es editar este archivo, nunca tocar código. `snarf/voice/router.py` (`VoiceRouter`) es la única puerta de entrada: `transcribe()` intenta el STT primario y degrada al fallback local sin preguntar (costo cero, no aplica la regla de "nunca escalar en silencio" — esa regla es sobre gastar plata de más); `speak()` sin `tier` explícito SOLO intenta el tier 'local' y nunca escala solo a 'premium'/'hosted' — si el tier pedido no está disponible, tira `TierUnavailable` en vez de gastar en silencio, tal como pidió el fundador.

### 2. Split texto/habla — la optimización de mayor impacto real del diseño

`AnthropicLLM.generate()` (`snarf/capabilities/anthropic_llm.py`) ahora devuelve `LLMResponse(text, speech)` en vez de un `str` plano. El system prompt (`SYSTEM_PREFIX`, `snarf/core/orchestrator.py`) instruye a Snarf a cerrar CADA respuesta con un bloque delimitado (`---HABLA---` ... `---FIN-HABLA---`): la versión hablada es el titular, la decisión y lo necesario para actuar — menos de 400 caracteres salvo que se pida el desarrollo completo, sin markdown, nunca oculta un riesgo o dato faltante presente en la respuesta completa (lo que se recorta es la explicación, nunca la advertencia). `split_speech()` separa ambas partes y las quita de lo que se muestra en pantalla; si el modelo no incluyó el marcador (no es estructurado, solo instruido por prompt), `fallback_speech()` cae a una versión mecánica (sin llamada extra al modelo): recorte de markdown básico + truncado a 400 caracteres en el borde de una oración.

`Orchestrator.handle()` devuelve ahora `LLMResponse` en vez de `str`; `EpisodicMemory.append()` persiste el campo `speech` nuevo (opcional, `None` en entradas viejas — mismo patrón que `input_audio_id`). `app.py` (`/send`) devuelve `{"response": ..., "speech": ...}`; `web/index.html` guarda `speech` junto a cada mensaje y lo usa como el texto que de verdad se sintetiza al tocar "generar nota de voz" — nunca la respuesta completa. `main.py --voice` (canal de voz por terminal) también dice `result.speech`, no `result.text`, aplicando la misma optimización ahí.

Verificado en vivo (no es una afirmación sin evidencia): pedida una explicación de dos párrafos sobre el cacheo de prompts, el modelo devolvió una respuesta completa de ~2200 caracteres y una versión hablada de ~400 caracteres que preserva intacta la advertencia de que una parte es inferencia propia, no verificada en el código — exactamente el comportamiento pedido.

### 3. `snarf/runtime/voice_channel.py` también migrado

El canal de voz por terminal (`main.py --voice`) cableaba `ElevenLabsSTT`/`ElevenLabsTTS` directo — se migró a `VoiceRouter` también, para que "ningún proveedor cableado" sea cierto en todo el proyecto, no solo en la interfaz web.

### 4. Registro de costo (adelanto de la Parte 3, sobre la infraestructura ya existente)

`snarf/telemetry/usage_tracker.py`/`pricing.py` (ya existentes desde ADR 0028) suman `record_groq_stt_call` (costo real estimado, con el piso de ~10s/request de Groq — ver Consecuencias), `record_local_stt_call` y `record_kokoro_tts_call` (costo `0.0` explícito, no `None` — es un cero real, no un dato faltante). La Parte 3 del plan (ledger.jsonl con más campos: `task_id`, `agente`, `escalado`, `gatillo_escalado`, `origen`) todavía no se construyó — esto es la base real sobre la que se va a extender, no una duplicación.

### 5. Docker desde el día uno

`docker-compose.voice.yml` levanta Kokoro-FastAPI en un contenedor Linux `arm64` corriendo en Colima (instalado esta sesión, ver Parte 0) — la misma imagen y compose van a correr igual en el futuro VPS (Parte 4, pendiente). No hay healthcheck de Docker: Kokoro-FastAPI no documenta un `/health` real, así que la disponibilidad se chequea a nivel de aplicación (`KokoroTTS.available` contra `/v1/audio/voices`, endpoint real confirmado).

## Verificado

- 444/444 tests (30 nuevos: `test_voice_router.py`, `test_groq_stt.py`, `test_kokoro_tts.py`, `test_elevenlabs_tts_provider.py`, `test_hosted_tts_stub.py`, más split texto/habla en `test_anthropic_llm.py`/`test_episodic_memory.py`/`test_orchestrator.py`).
- Kokoro real levantado en Docker y probado con las 3 voces en español reales (`em_alex`, `em_santa`, `em_dora` — confirmadas contra `/v1/audio/voices`, no las 3 que se suponían de antemano por documentación de terceros).
- Playwright contra una instancia aislada real: `/status` reporta `stt_available`/`tts_available` en `True` (STT vía fallback local automático, sin `GROQ_API_KEY` configurada todavía; TTS vía Kokoro real); un mensaje real de chat, clic en "generar nota de voz", reproductor de nota de voz renderizado con audio real sintetizado por Kokoro — cero errores de consola.
- Verificado en vivo (`curl` directo a `/send`) que el split texto/habla separa de verdad una respuesta larga en una versión hablada corta que preserva la advertencia de "esto es inferencia mía, no verificado" — no solo un recorte ciego.

## Consecuencias

- **`GROQ_API_KEY` todavía no está configurada** — el STT hoy corre 100% sobre el fallback local (`faster-whisper`, gratis, más lento) porque no hay credencial de Groq en `.env`. Falta que el fundador la consiga (gratis, `console.groq.com`) y falta el criterio de aceptación explícito de la Parte 1 (verificar calidad real en español rioplatense con 5 audios de prueba) — no se puede evaluar honestamente sin la API key real.
- **Decisión de diseño que se aparta de la spec original, documentada en vez de implementada en silencio**: no se construyó agrupado ("batching") de clips cortos de audio antes de mandarlos a Groq pese a que Groq factura con un piso de ~10s por request. En el uso real de Snarf cada nota de voz ya es un único archivo completo por request (nunca streaming fragmentado), así que el piso ya se paga una sola vez por nota — construir una cola de agrupado para ahorrar fracciones de centavo es exactamente la clase de complejidad prematura que el propio principio del fundador ("empezar barato, escalar solo ante evidencia de fallo real") pide evitar.
- **Tier 'hosted' es un stub deliberado, sin proveedor real** (`HostedTTSNotConfigured`, siempre `available=False`) — no hay ninguna evidencia todavía de que el tier local (Kokoro) no alcance, así que integrar gpt-4o-mini-tts/Cartesia/Inworld ahora sería anticipación, no necesidad, y cualquiera de los tres implica una cuenta nueva sin motivo real hoy. Activar uno real el día que haga falta es agregar una clase + una línea de config, nunca una refactorización.
- **`faster-whisper` es una dependencia pesada** (arrastra `ctranslate2`, `av`, `onnxruntime`) para un fallback que en el uso real probablemente casi nunca se invoque (solo sin red o con Groq caído) — aceptado porque el fundador pidió explícitamente esta opción, no una decisión unilateral, pero vale la pena tenerlo presente si el tamaño del entorno importa al migrar al VPS.
- **La voz elegida de Kokoro (`em_alex`, masculina) es una elección por continuidad con "Antonio" (voz actual de ElevenLabs), todavía sin confirmar por oído con el fundador** — los tres audios de prueba (`em_alex`, `em_santa`, `ef_dora`) quedaron generados y listos para que el fundador los escuche y elija.
- **El widget "USO REAL DE APIS" del dashboard todavía no tiene una sección visual dedicada para los vendors nuevos** (`groq`, `local`) — el dato ya se registra y es correcto, falta solo el template de UI; no bloquea el uso real, es una mejora cosmética pendiente.
- Partes 2 (router de modelos), 3 (ledger completo + comando `snarf costo` + guardas de presupuesto) y 4 (benchmark real en VPS, topologías, comparación de costos) del plan de cuatro partes siguen pendientes, a arrancar recién con confirmación del fundador.
