# ADR 0139 — Fase 4: n8n self-hosted + primera integración real (observa y propone)

**Fecha:** 2026-08-10
**Estado:** Aceptado

## Contexto

Con la Fase 3 (multi-usuario real, ADR 0137) y el diagnóstico real de recursos de la Mac (ADR 0138) ya
resueltos, tocaba la Fase 4 del plan aprobado: levantar n8n como capa de operación visual, nunca un
segundo orquestador. Principio ya vigente para MCP (ADR 0093) y reafirmado en el plan aprobado con el
fundador: **n8n observa y propone — la lógica real siempre vive del lado de Snarf.**

## Decisión

### 1. n8n self-hosted, gratis, nunca expuesto públicamente

`docker-compose.n8n.yml` (nuevo, mismo patrón que `docker-compose.voice.yml`): n8n Community Edition
(`docker.n8n.io/n8nio/n8n:1.121.0`), bindeado solo a `127.0.0.1:5678` — nunca `0.0.0.0`. Acceso remoto
real desde otro dispositivo del tailnet queda como un paso aparte (`tailscale serve --bg 5678`, mismo
mecanismo ya documentado en `VPS_MIGRATION.md` para el server principal), no automático. Corre sobre
Colima (`colima start --cpu 2 --memory 2 --disk 20` — perfil acotado a propósito, dado el diagnóstico
de recursos de ADR 0138) — real, ~530MB de RAM en reposo, verificado con `docker stats`.

### 2. Snarf → n8n: `snarf/telemetry/n8n_webhook_sink.py` (nuevo)

Mismo criterio de resiliencia que `redis_sink.py` (Fase 2) — nunca una dependencia dura. Sin
`N8N_WEBHOOK_URL` seteada, el sink ni se instala. Si el webhook falla o n8n está caído, el fallo se
traga y se cuenta (`health()`), un turno real de Snarf jamás se entera. Se registra como un subscriber
más del dispatcher de Fase 1 — no reemplaza ni compite con `event_buffer.py`/`redis_sink.py`, corren
los tres en simultáneo si están configurados.

**Verificado con un listener HTTP real** (no un mock): un `http.server` real en un puerto random
recibió, de punta a punta a través de `dispatcher.publish()` → `n8n_webhook_sink.publish_to_webhook`
→ `requests.post` real, el evento exacto publicado — confirma que el mecanismo de entrega funciona
contra un servidor HTTP de verdad, no solo contra un doble de test.

### 3. n8n → Snarf: `GET /n8n/status` (nuevo, `app.py`)

Autenticado por `N8N_CONTROL_TOKEN` (header `X-Snarf-Token`) — **nunca la cookie de sesión del
founder**: n8n es un segundo proceso automatizado, no un navegador logueado, y mezclar ambos
mecanismos de auth violaría el principio de que n8n nunca actúa con la identidad del founder
(`require_n8n_token`, `snarf/runtime/web_auth.py`, falla cerrado con 503 sin el token configurado,
mismo criterio que `require_user` con `SESSION_SECRET`). Deliberadamente de solo lectura y mínimo:
reusa `ops_health.system_health()` y `process_control.status()` (ADR 0138) tal cual, nunca una segunda
implementación — una API de introspección real y más completa es trabajo de la Fase 5, no de esta.

## Lo que quedó como paso manual real del fundador (no automatizable desde acá)

No se creó una cuenta de owner de n8n en su nombre — es una identidad real sobre infraestructura real,
mismo criterio que no generar credenciales de Google por él. Completado en vivo por el fundador el
mismo día:

1. Abrir `http://127.0.0.1:5678/` y completar "Set up owner account" (email/nombre/contraseña reales).
2. Crear un workflow nuevo con un nodo **Webhook**, activarlo — n8n genera una URL real tipo
   `http://127.0.0.1:5678/webhook/<uuid>`, tomada del campo "Production URL" del nodo.
3. Poner esa URL en `.env` como `N8N_WEBHOOK_URL=...` y un token random propio como
   `N8N_CONTROL_TOKEN=...` (generado con `secrets.token_hex(32)`).
4. Reiniciar `com.snarf.server` para que tome las env vars nuevas (`launchctl kickstart -k
   gui/501/com.snarf.server`).

**Gotcha real encontrado en la propia verificación, no en teoría** (mismo estilo que otros gotchas ya
documentados en CLAUDE.md): el nodo Webhook de n8n nace con "HTTP Method" en **GET** por default —
`n8n_webhook_sink.py` manda `POST` (necesario para viajar el evento completo como JSON en el body; un
GET no puede llevar eso de forma confiable). El síntoma real fue un 404 persistente en la Production
URL pese al workflow ya activado, con el log real del contenedor diciendo explícitamente *"This
webhook is not registered for POST requests. Did you mean to make a GET request?"* — diagnóstico
directo, no adivinado. Fix: cambiar "HTTP Method" del nodo a POST. **Cualquier workflow nuevo que
reciba eventos de Snarf tiene que crear su nodo Webhook en POST desde el principio**, no asumir el
default.

Desde ahí, cada evento real de Snarf (Fase 1: tool/LLM/turno, ya con `event_id`/`trace_id`
correlacionados) le llega a ese workflow en tiempo real.

## Riesgos / lo que queda pendiente

1. **n8n no sobrevive un reinicio de la Mac todavía** — `docker-compose.n8n.yml` tiene
   `restart: unless-stopped` (sobrevive un reinicio del propio Docker daemon), pero Colima en sí no
   arranca solo al bootear la Mac salvo que se configure explícitamente (`colima start --edit`,
   autostart) o se envuelva en un LaunchAgent propio — no se hizo en esta ronda, deliberado hasta ver
   si el fundador de verdad quiere que n8n sea "siempre encendido" como los demás servers.
2. **`GET /n8n/status` es de solo lectura** — "n8n puede pedirle cosas a Snarf" en el sentido de
   disparar acciones reales (editar un prompt, activar una skill) depende de las Fases 5/6
   (introspección real, Prompt Registry) que todavía no existen — este ADR no las adelanta.
3. **El caso de uso "n8n edita un agente existente"** del plan aprobado sigue bloqueado por lo mismo
   (Fase 6, Prompt Registry) — la integración de hoy es puramente observacional.

## Verificado

- 8 tests nuevos: `tests/test_n8n_webhook_sink.py` (instalación condicional a `N8N_WEBHOOK_URL`,
  entrega real de un evento completo como JSON, un `ConnectionError` real tragado y contado, no-op sin
  configurar). 4 tests nuevos en `tests/test_web_auth.py` (`require_n8n_token`: falla cerrado sin el
  token configurado, rechaza header ausente/incorrecto, acepta el real). 3 tests nuevos en
  `tests/test_app.py` (`GET /n8n/status`: 401 sin token, 503 sin configurar, 200 con el estado real).
  Extensión de `tests/test_ops_health.py` (+1: `event_bus_n8n` presente).
- 1211/1211 tests de la suite completa (`.venv/bin/python -m pytest -q`).
- n8n real corriendo (`docker stats`: ~530MB), UI verificada con Playwright (pantalla real "Set up
  owner account" en la versión 1.121.0, sin advertencia de versión desactualizada).
- Entrega real verificada contra un `http.server` real (no un mock) escuchando en un puerto random —
  ver sección 2 arriba.
- **Integración de punta a punta cerrada en producción real**, no solo en tests: tras el fundador
  activar el workflow y corregir el método HTTP del nodo Webhook a POST, un `POST` real contra la
  Production URL devolvió `200 {"message":"Workflow was started"}` — la confirmación real de n8n de
  que ejecutó el workflow, no una suposición. Antes del fix, `event_bus_n8n.health()` (vía
  `GET /n8n/status`, con el token real) ya venía contando honestamente los 404 reales sin inventar
  éxito — confirma que el conteo de fallos de `n8n_webhook_sink.py` refleja la realidad, no solo en el
  caso feliz.
