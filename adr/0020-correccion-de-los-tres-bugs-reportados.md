# ADR 0020 — Corrección de los tres bugs reportados (respuestas cortadas, push-to-talk iPhone, layout mobile)

**Fecha:** 2026-07-27
**Estado:** Aceptado — los tres bugs confirmados como resueltos por el fundador en su iPhone real

## Contexto

`ARCHITECTURE_AUDIT.md` (ver ADR 0019) había identificado, por inspección de código y sin haber tocado nada todavía, la causa más probable de los tres bugs que el fundador reportó en distintas conversaciones: respuestas largas que se cortan, push-to-talk que deja de funcionar en iPhone después del primer uso, y el botón de enviar cortado en mobile. Con la suite de tests ya en pie (ADR 0019) como red de seguridad, se procedió a corregir los tres.

## Decisión

**BUG 2 — respuestas cortadas (`snarf/capabilities/anthropic_llm.py`):** la causa era `max_tokens=1024` fijo, sin chequear `response.stop_reason`. Se subió el límite a `MAX_OUTPUT_TOKENS = 4096` y se agregó una nota visible (`"*(respuesta truncada: llegó al límite de longitud de una respuesta)*"`) cuando `stop_reason == "max_tokens"`, en vez de devolver el texto parcial como si fuera una respuesta completa. Se agregó `tests/test_anthropic_llm.py` con un cliente falso (sin red real) que verifica las tres cosas: una respuesta completa no lleva la nota, una respuesta truncada sí la lleva, y el límite enviado a la API es el nuevo (4096, no 1024). **Verificado además contra la API real de Anthropic** (round-trip completo vía una instancia temporal de `app.py` en el puerto 8001, sin tocar el servidor real del fundador en el puerto 8000).

**BUG 1 — push-to-talk muerto en iPhone tras el primer uso (`web/index.html`):** la causa era que `ensureStream()` pedía el `MediaStream` del micrófono una sola vez y lo guardaba para siempre; en iOS Safari, backgrounding o bloqueo de pantalla suele terminar los tracks de un stream viejo sin avisar, y reusarlo produce grabaciones vacías indistinguibles de "no funciona". Se eliminó el cacheo: ahora se pide un stream nuevo en cada `startRecording()`, y se liberan sus tracks (`stream.getTracks().forEach(t => t.stop())`) al terminar cada grabación en `stopRecording()`. El navegador no vuelve a mostrar el diálogo de permiso una vez otorgado para el origen, así que no hay regresión de UX.

**BUG 3 — botón de enviar cortado en mobile (`web/index.html`), en dos rondas:**

- *Primera hipótesis (insuficiente):* `min-height: 100vh` conviviendo con `height: 100dvh` en el mismo `body`. Se eliminó la línea `min-height: 100vh`. El fundador confirmó por voz que el problema seguía igual — la hipótesis era plausible pero no era la causa real, o no era la única.
- *Segunda hipótesis (también insuficiente):* capturas de pantalla mostraron el botón "ENVIAR" cortado específicamente en modo texto. Se agregó `min-width: 0` a `.text-row input` — sin eso, un `<input>` dentro de un contenedor flex no se achica por debajo de su ancho mínimo por defecto del navegador, típico causante de overflow horizontal en filas flex angostas.
- *Causa real, encontrada con nuevas capturas:* el fundador reportó que solo podía ver todo "encuadrado" pellizcando para hacer zoom-out — en las capturas, incluso en modo click (sin teclado, sin `.text-row` visible), el ícono superior derecho también aparecía cortado por el borde real de la pantalla. Eso descarta el input como causa única: la página completa estaba renderizando más ancha que el viewport del dispositivo, y Safari permitía hacer zoom en vez de ajustarla al ancho real. Se corrigió agregando `overflow-x: hidden` a `html` (antes solo estaba en `body`) y deshabilitando el zoom táctil en el `<meta viewport>` (`maximum-scale=1, user-scalable=no`), coherente con que esta es una interfaz tipo HUD fija, no una página pensada para hacer zoom o pan. **Trade-off explícito:** esto también desactiva el zoom nativo de accesibilidad para cualquier usuario que lo necesite; se aceptó porque hoy el fundador es el único usuario y la interfaz está pensada como HUD fijo, no como documento navegable.

## Verificado

- BUG 2: con test unitario determinístico + round-trip real contra la API de Anthropic. **Confirmado.**
- BUG 1: corregido con alta confianza por evidencia de código; **confirmado por el fundador en su iPhone real** (mantener presionado y toque, ambos funcionan y la conversación se mantiene activa).
- BUG 3: dos rondas de hipótesis descartadas por evidencia real (capturas de pantalla) antes de llegar a la causa raíz real (overflow horizontal de la página completa, no solo del input). **Confirmado por el fundador en su iPhone real** tras el fix de `overflow-x`/zoom deshabilitado: todo entra en pantalla sin pellizcar, en los tres modos.
- Suite completa de tests (30/30) corrida después de todos los cambios, sin regresiones.
- **Los tres bugs quedan cerrados.**

## Consecuencias

- Al validar `app.py` completo contra la API real durante esta verificación, quedó una conversación de prueba en la memoria episódica real del fundador. Se movió a `data/manual_verification_log.jsonl` (gitignorado, igual que `episodic_memory.jsonl`) para no mezclar verificaciones manuales futuras con la memoria real de conversaciones — nueva práctica adoptada a pedido del fundador para cualquier verificación futura que use una instancia real de `Orchestrator`.
- Lección de proceso: en un proyecto sin tests de frontend ni acceso a un dispositivo real, la verificación por capturas de pantalla del fundador es la única fuente de verdad para bugs de layout mobile — dos hipótesis de causa raíz plausibles por lectura de código resultaron insuficientes hasta ver la evidencia visual real. Vale la pena pedir captura desde el primer reporte de un bug visual, no después de una o dos rondas de hipótesis.
- El fundador pidió explícitamente que, de acá en más, cualquier trabajo de interfaz contemple que (a) debe ser responsive para escritorio y multiplicidad de dispositivos, no solo iPhone, y (b) se viene un dashboard una vez cerrada esta ronda de bugs — a tener en cuenta en el diseño de cualquier cambio de layout futuro, para no tener que rehacer supuestos de una sola resolución/dispositivo.
