# ADR 0008 — Acceso remoto seguro vía Tailscale

**Fecha:** 2026-07-25
**Estado:** Aceptado

## Contexto

ADR 0007 dejó pendiente cómo resolver que los navegadores exigen HTTPS (o `localhost`) para conceder acceso al micrófono, lo que bloqueaba el uso de la interfaz visual desde el celular. Se plantearon tres alternativas (Tailscale, ngrok, certificado autofirmado). El fundador pidió la opción más barata y escalable.

## Decisión

Se eligió **Tailscale**: gratuito para uso personal, tráfico directo entre dispositivos del propio tailnet (no atraviesa servidores de terceros para los datos, solo para coordinación inicial), y escala a más dispositivos o colaboradores sin cambio de arquitectura ni costo adicional en el rango de uso esperado. Se descartó ngrok (plan gratuito limitado, tráfico por servidores de un tercero, se encarece al escalar) y el certificado autofirmado (sin costo, pero no funciona fuera de la Wi-Fi de casa y genera fricción de advertencias en cada dispositivo nuevo).

Se instaló Tailscale en la Mac (`brew install --cask tailscale`) y en el iPhone del fundador, ambos en el mismo tailnet. Se habilitó la función Serve del tailnet (requiere un click en el admin panel de Tailscale, solo el dueño de la cuenta puede hacerlo). Se expuso `app.py` con `tailscale serve --bg 8000`, que gestiona el certificado HTTPS automáticamente y sirve la app en `https://macbook-pro-de-jeremas.tailb10c73.ts.net/`.

## Consecuencias

- `app.py` no cambió: Tailscale actúa como proxy HTTPS delante del servidor HTTP local, sin que la aplicación necesite gestionar certificados.
- El acceso queda limitado a los dispositivos del tailnet del fundador — no es acceso público a internet (eso sería Tailscale Funnel, una decisión distinta y de mayor exposición, no tomada aquí).
- Dependencia nueva y real: sin el daemon de Tailscale corriendo en la Mac, el acceso remoto se cae (el acceso local en `http://127.0.0.1:8000` no depende de esto y sigue funcionando siempre).
- Verificado: `https://macbook-pro-de-jeremas.tailb10c73.ts.net/` responde 200 desde la propia Mac. Falta verificación manual de uso real desde el iPhone (grabación de micrófono incluida) — depende de una prueba interactiva del fundador.
