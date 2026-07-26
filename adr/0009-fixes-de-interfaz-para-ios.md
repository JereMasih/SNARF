# ADR 0009 — Correcciones de interfaz para iOS y rediseño de layout móvil

**Fecha:** 2026-07-25
**Estado:** Aceptado

## Contexto

El fundador reportó que el modo de voz no funcionaba en el iPhone, y pidió además: reubicar el orbe abajo de la pantalla (alcance cómodo del pulgar), que el chat crezca hacia arriba desde encima del orbe, corregir bordes blancos visibles en Safari de iOS, y sumar más efectos visuales técnicos.

## Diagnóstico

Dos causas técnicas concretas explican la falla en iOS, ambas conocidas limitaciones de Safari/WebKit:

1. **`MediaRecorder` en Safari no soporta `audio/webm`.** El código anterior creaba el grabador sin especificar `mimeType` y etiquetaba el Blob resultante como `"audio/webm"` sin importar el formato real — en iOS, Safari graba en otro contenedor (típicamente `audio/mp4`), y la discrepancia entre el contenido real y la etiqueta podía romper la transcripción.
2. **Bloqueo de reproducción de audio fuera del gesto del usuario.** iOS exige que `audio.play()` ocurra dentro de la misma cadena síncrona de un gesto de usuario (click/touch). Como la respuesta de Snarf llega después de varias llamadas asíncronas (transcripción, razonamiento, síntesis), para cuando el audio está listo el "permiso" del gesto original ya expiró y Safari rechaza la reproducción silenciosamente.

Además, los bordes blancos en Safari son el comportamiento por defecto de WebKit en las zonas de "safe area" (notch, barra de estado, home indicator) cuando la página no declara explícitamente que ocupa toda la pantalla ni un color de fondo en `<html>`.

## Decisión

1. `pickMimeType()` detecta con `MediaRecorder.isTypeSupported` qué formato soporta el navegador real y etiqueta el Blob y el nombre de archivo subido de forma consistente con ese formato — ya no se asume `webm` en todos los casos.
2. Se agregó el patrón estándar de "desbloqueo de audio" de iOS: un elemento `<audio>` compartido se reproduce una vez (silenciosamente) en el primer gesto del usuario, y se reutiliza el mismo elemento para todas las respuestas posteriores, en vez de crear un `Audio()` nuevo cada vez.
3. `viewport-fit=cover` en el meta viewport, fondo negro explícito en `<html>`, `overscroll-behavior: none`, y relleno con `env(safe-area-inset-*)` en vez de márgenes — el negro ahora cubre toda la pantalla física, incluidas las zonas de notch y home indicator.
4. Layout invertido: el orbe y sus controles quedan fijos en una barra inferior (alcanzable con el pulgar), y el historial de chat ocupa el resto de la pantalla arriba, ancla sus mensajes al fondo de su propio contenedor y crece hacia arriba a medida que se acumulan turnos.
5. Más elementos técnicos: dos capas de rayos (conic-gradient) rotando en direcciones opuestas, dos manchas de "nebulosa" difuminadas en el fondo con deriva lenta, partículas ascendentes sutiles, y marcas de esquina tipo HUD.
6. Mensajes de error ahora incluyen el detalle técnico (`e.message`) en pantalla, no solo un texto genérico — necesario porque no hay forma de inspeccionar la consola del navegador del fundador de forma remota.

## Consecuencias

- No se pudo verificar el fix directamente contra un iPhone real desde esta sesión; el diagnóstico se basa en limitaciones documentadas y públicamente conocidas de WebKit/iOS, no en un log de error real del dispositivo. Si el problema persiste, los mensajes de error ahora visibles en pantalla (punto 6) deberían acotar la causa real en el siguiente intento.
- El elemento de audio compartido (`sharedAudio`) implica que solo puede reproducirse una respuesta de voz a la vez; esto es aceptable para una conversación por turnos.
