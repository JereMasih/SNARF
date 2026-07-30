# ADR 0057 — Multibotón mic/enviar y envío combinado texto+voz

**Fecha:** 2026-07-30
**Estado:** Aceptado

## Contexto

El fundador marcó como urgente el comportamiento del botón de grabar/enviar en la caja de chat: pidió que sea un único multibotón (no dos botones sueltos al lado), con mantener presionado para grabar, deslizar arriba para bloquear en manos libres (pudiendo soltar el dedo sin cortar la grabación), un tachito de basura visible para cancelar, y una flecha de enviar que aparece junto al tachito para terminar y mandar. Pidió además, sin dar más detalle ("investigá si hace falta"), que si ya había texto escrito antes de grabar, al enviar se mande TODO junto — el texto y la transcripción de la nota de voz, como un solo mensaje.

Investigado: gran parte de esto (mantener presionado, deslizar para cancelar/bloquear, tachito, reusar la flecha para terminar en modo bloqueado) ya estaba construido (ADR 0049) — el problema real no era la lógica de grabación en sí, sino que **`micBtn` y `textSendBtn` estaban siempre visibles los dos a la vez**, sin ningún criterio que los mostrara/ocultara según el estado, lo cual no se lee como "un" botón sino como dos sueltos — y que **el borrador de texto escrito antes de grabar se perdía en silencio**: `finishRecording` mandaba solo la transcripción, nunca leía `textInput.value`.

## Decisión

### 1. Multibotón real: mic y flecha nunca los dos ocultos, casi nunca los dos visibles sin motivo

`updateSendMicToggle()` (`web/index.html`) decide en cada cambio de estado qué mostrar:

- Sin nada escrito, sin grabar: solo mic.
- Con un borrador escrito (sin grabar): mic Y flecha visibles juntos — **a propósito, no es un bug**: es lo que permite grabar una nota de voz encima de un borrador ya escrito (ver punto 2). Es la única excepción real al "un solo botón".
- Grabando sin bloquear (dedo todavía apretando mic): solo mic (en rojo, pulsando) — la flecha se esconde para no distraer a mitad del gesto.
- Grabación bloqueada (manos libres): mic desaparece, quedan tachito + flecha juntos — tocar la flecha termina y manda.

CSS nuevo: `.text-row .icon-btn[hidden] { display: none; }` — sin esto, la regla `.text-row .icon-btn { display: flex }` ya existente pisaba el atributo `hidden` en silencio (mismo origen "autor", gana la especificidad) y ocultar por JS no hacía nada visible.

### 2. Envío combinado: borrador de texto + transcripción de voz, un solo mensaje

`finishRecording()` ahora lee `textInput.value` al terminar de grabar (no solo la transcripción), y si había algo escrito arma `${draft}\n${transcript}` antes de mandarlo — un mensaje solo, con el `input_audio_id` de la nota de voz igual adjunto (la nota de voz real sigue siendo reproducible en el chat, con su transcripción como desplegable, ver ADR 0050). Si no había borrador, se manda la transcripción sola como siempre.

## Verificado

- 444/444 tests (sin cambios de backend — esto es 100% frontend).
- Playwright contra una instancia aislada real, simulando el gesto completo con eventos de mouse reales (mover a las coordenadas del botón, presionar, deslizar arriba, soltar): estado inicial (solo mic) → con borrador (mic+flecha) → grabando sin bloquear (solo mic) → bloqueado (tachito+flecha, mic oculto) → soltar el dedo estando bloqueado (sigue grabando, confirmado por el texto "🔒 bloqueado") → tocar la flecha termina y manda.
- Envío combinado verificado con una transcripción determinística stubbeada (para no depender de audio real/Groq en el test): un borrador "recordame comprar leche" + una grabación que transcribe a "y también comprame pan" terminan en un solo mensaje `"recordame comprar leche\ny también comprame pan"`, con el textarea vacío después de enviar. Cero errores de consola.

## Consecuencias

- La excepción real al "un solo botón" (mic+flecha visibles juntos cuando hay un borrador) es deliberada, no un descuido — es lo que hace posible la combinación texto+voz que pidió el fundador. Si en el uso real molesta visualmente, es la primera candidata a revisar.
- No se tocó el modo "Toque" (`data-mode="click"`, con su propia pantalla de revisión `#review`/`#reviewText`) — el pedido era específicamente sobre la caja de chat en modo "Teclado", que es el default real.
