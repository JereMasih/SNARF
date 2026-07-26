# ADR 0007 — Grabación en el navegador, dos modos de interacción, chat y rediseño visual

**Fecha:** 2026-07-25
**Estado:** Aceptado

## Contexto

El fundador pidió: (a) dos modos de grabación intercambiables — mantener presionado para hablar y soltar para enviar, o click para empezar/click para terminar con revisión y envío manual antes de procesar; (b) un historial de conversación estilo chat, con los mensajes de Snarf a la izquierda y los propios a la derecha; (c) un rediseño visual con más efectos técnicos (rayos, anillos, fondo con degradé a negro y textura tipo HUD); (d) saber si la interfaz es accesible desde el celular u otro navegador.

Sobre el punto (d): la implementación anterior (ADR 0006) capturaba audio del lado del servidor con `sounddevice`, es decir, del micrófono de la Mac. Acceder desde otro dispositivo no habría tenido sentido — seguiría grabando el micrófono equivocado.

## Decisión

1. La captura de audio se movió al navegador (`MediaRecorder`), subiendo el clip grabado al servidor. Esto es correcto independientemente del dispositivo: funciona igual desde la Mac que desde un celular en la misma red.
2. `app.py` se simplificó: ya no mantiene estado de grabación del lado del servidor. Dos endpoints nuevos, sin estado entre sí: `POST /transcribe` (audio → texto) y `POST /send` (texto → respuesta + audio en base64). El navegador reproduce el audio de respuesta con un elemento `<audio>`, no el servidor con `afplay` — así el sonido sale siempre por el dispositivo de quien está usando la interfaz, no siempre por la Mac.
3. La interfaz (`web/index.html`) implementa ambos modos de grabación con un selector visible, un panel de revisión (textarea editable + botón enviar) para el modo click, y un historial de chat con burbujas (usuario a la derecha, Snarf a la izquierda) que persiste mientras la pestaña está abierta.
4. Rediseño visual: fondo con degradé radial a negro, grilla técnica sutil enmascarada alrededor del centro, línea de escaneo animada, y el orbe con rayos (conic-gradient enmascarado), dos anillos concéntricos rotando en direcciones opuestas, y brillo en capas. Diseño original, no una reproducción de ninguna interfaz de ficción con derechos de autor.
5. El servidor ahora escucha en `0.0.0.0` (antes `127.0.0.1`), y al iniciar imprime la URL de red local, habilitando acceso desde otros dispositivos en el mismo Wi-Fi.

## Limitación conocida, no resuelta en este ADR

Los navegadores exigen un *contexto seguro* (HTTPS, o el propio `localhost`) para conceder acceso al micrófono vía `getUserMedia`. Acceder desde el celular a `http://<ip-de-la-mac>:8000` va a mostrar la interfaz, pero el micrófono probablemente sea rechazado por el navegador al no ser HTTPS. Resolver esto (túnel con Tailscale, túnel con ngrok, o certificado autofirmado local) es una decisión de infraestructura con costos y compromisos de privacidad distintos, pendiente de decisión explícita del fundador — no se asumió ninguna opción por defecto.

## Consecuencias

- `LocalAudioIO.record`/`start_recording`/`stop_recording` (captura del lado del servidor) ya no se usan desde `app.py`; se mantienen únicamente para `main.py --voice` (REPL de terminal, donde grabar el micrófono de la Mac sí es lo correcto).
- Nueva dependencia: `python-multipart` (requerida por FastAPI para `UploadFile`).
