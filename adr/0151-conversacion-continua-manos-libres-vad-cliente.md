# ADR 0151 — Conversación continua manos libres: VAD client-side, sin WebSocket

**Fecha:** 2026-08-11
**Estado:** Aceptado

## Contexto

Fase 10 del roadmap (`ROADMAP_OBSERVABILIDAD_MULTIUSUARIO_N8N.md`) quedaba deliberadamente sin diseño
("fase de diseño propio cuando le toque el turno"). Hoy la voz es grabar → transcribir → Snarf responde →
sintetizar, siempre por turnos discretos vía HTTP request/response — sin WebSocket en todo el repo.

Pedido real del fundador: un botón nuevo, a la derecha del mic actual (que sigue funcionando exactamente
igual, sin tocarlo), que active un modo de conversación continua tipo Jarvis — hablás y Snarf responde con
voz sin tap manual por turno, y si empezás a hablar mientras Snarf está hablando, lo interrumpe (barge-in
real). Alcance de producto explícitamente completo ("procede con todo" en respuesta a la opción más
ambiciosa que se le presentó, streaming bidireccional completo) — la decisión técnica de CÓMO lograrlo
es la que documenta este ADR.

## Decisión

**Sin WebSocket.** Ni Groq STT (`snarf/voice/providers/groq_stt.py`) ni Kokoro TTS
(`snarf/voice/providers/kokoro_tts.py`) son streaming del lado del proveedor — ambos hacen una única
request con el archivo/texto completo. Un transporte WebSocket nuevo no bajaría latencia real, solo
movería el transporte de HTTP a WS sin beneficio. La sensación de "continuo" se logra con **VAD (voice
activity detection) client-side por energía RMS** (`AudioContext`+`AnalyserNode`+`getFloatTimeDomainData`,
sin `AudioWorklet` — un archivo de módulo aparte no encaja con el patrón de este repo de "todo en un solo
`index.html`"), reusando `/transcribe`, `/send`, `/tts`, `/cancel/{request_id}` tal cual existen hoy —
**cero endpoints backend nuevos**.

**Módulo nuevo, estado propio, aislado del flujo legacy** (`web/index.html`, bloque
`continuousMode`/`continuousPhase`/`cm*`, vecindario `~7345-7800`): nunca comparte `state`/
`mediaRecorder`/`stream`/`chunks` globales con el flujo de push-to-talk existente — 3 puntos reales de
colisión encontrados al investigar (`updateSendMicToggle`, el click de `textSendBtn`, el click de
`micBtn`, los tres leen `state === "listening"` con lógica que un `state` compartido rompería). Mientras
el modo está activo, `micBtn.disabled = true` — los dos mecanismos de grabación no conviven sobre el mismo
mic.

**Corrección real encontrada al investigar** (no cambia el diseño, corrige una premisa): el flujo de voz
real que usa el fundador hoy YA auto-envía sin caja de revisión editable (`micBtn` → `beginActualRecording`
→ `finishRecording` → `sendText` directo, línea 7737). El código de `handleClickMode`/
`showTranscriptForReview`/`orbWrap` con caja de revisión es código muerto en la UI actual (`mode` nunca
sale de `"text"`) — no se toca, fuera de alcance de esta ronda.

**Barge-in real, sin llamada nueva al backend para el caso "hablando"**: el VAD queda armado todo el
tiempo que el modo esté activo, incluso durante `thinking`/`speaking`. Al detectar habla nueva en esos dos
estados: `stopActiveRequest()` (reusado tal cual, cancela `/send` en curso vía `POST /cancel/{request_id}`)
si hay un turno en vuelo, y `sharedAudio.pause()` (100% client-side) si había audio reproduciéndose —
después arranca a capturar el turno nuevo.

**Autoplay acotado, sin reabrir ADR 0056**: se threadeó un parámetro `autoPlay` nuevo a través de
`sendText()` → `postAndHandleSend()` → `addMessage()` (todos backward-compatible, parámetro nuevo al
final, todos los demás call sites sin cambios) — cuando es `true`, el player de voz que `addMessage` ya
construye para cualquier turno con `autoSpeak` (línea ~2833) se auto-reproduce (`.vn-play-btn.click()`)
apenas existe. Deliberadamente se reusa el MISMO pathway de síntesis+player existente (nunca una segunda
implementación aparte) — evita doble síntesis y un player duplicado/desincronizado. El resto del chat
sigue sin autoplay, sin excepción.

**Fase de "hablando" real, no asumida**: `continuousPhase` pasa a `"speaking"` únicamente cuando
`sharedAudio` dispara su evento `play` real (nunca cuando `sendText()` resuelve, que es antes de que la
síntesis/reproducción siquiera arranquen) — así el estado visual nunca miente sobre si Snarf está
hablando de verdad en este instante.

**Protocolo de crecimiento del cerebro** (`snarf/telemetry/brain.py`): no aplica. El modo continuo no
agrega tool/Capacidad/Especialista/canal nuevo — dispara los mismos endpoints ya instrumentados
(`input_voice`, `llm`, `stt`/`tts`) desde un disparador distinto. El cerebro ya refleja esta actividad
igual, venga de push-to-talk o del modo continuo.

## Riesgo técnico conocido, no resuelto esta ronda

**Eco acústico sin cancelación real**: el VAD es energía RMS pura, sin AEC (acoustic echo cancellation).
Si el fundador usa parlantes (no auriculares), el propio audio de Snarf sonando puede disparar el VAD y
auto-interrumpirse en loop. No hay forma de confirmar esto con audio sintético — es un límite real,
conocido, a validar en vivo. Mitigación futura posible si aparece en uso real: exigir auriculares, o bajar
la sensibilidad del analyser mientras `continuousPhase === "speaking"`.

**Umbral de VAD sin calibrar en vivo**: `CM_VAD_THRESHOLD = 0.018` (RMS sobre -1..1) es un primer corte,
no calibrado contra la ganancia/distancia real del mic del fundador — puede necesitar ajuste tras probarlo.

## Verificado

- Sin cambios de backend — sin regresión esperada, suite completa sigue corriendo verde.
- Playwright con mic simulado (`--use-fake-device-for-media-stream`
  `--use-file-for-fake-audio-capture=<wav>`, puerto 8001): botón en la posición real del DOM (entre mic y
  enviar), habilitado tras boot, activa/desactiva `continuousMode` real, `micBtn.disabled` correcto
  mientras está activo, VAD detecta inicio de habla (`capturing`) y fin de habla tras el hangover de
  silencio (transición real a `thinking`, dispara `/transcribe` de verdad — confirmado en el log del
  server), barge-in real confirmado (`POST /cancel/{request_id}` disparado al detectar habla nueva durante
  un turno en curso). Apagar el modo en cualquier fase limpia todo (`continuousMode=false`,
  `micBtn.disabled=false`, `continuousPhase="idle"`). Cero errores de consola en todo el ciclo.
- **No verificado con audio sintético, requiere prueba en vivo del fundador**: el barge-in con eco
  acústico real (parlantes físicos) y la calibración real del umbral de VAD — ningún wav fake reproduce
  esa dinámica.
