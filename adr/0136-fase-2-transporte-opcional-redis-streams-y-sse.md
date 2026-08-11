# ADR 0136 — Fase 2 de observabilidad: transporte opcional (Redis Streams) + SSE

**Fecha:** 2026-08-10
**Estado:** Aceptado

## Contexto

Fase 1 (ADR 0135) cerró la correlación real entre eventos (`event_id`/`parent_event_id`/`trace_id`) y
dejó un dispatcher pub/sub in-process sin consumidores reales todavía. Esta fase le da un transporte
real a ese dispatcher: (1) un endpoint `GET /events/stream` (SSE) para que el frontend deje de
depender de polling HTTP, y (2) un sink opcional hacia Redis Streams para consumidores futuros que un
dispatcher in-process no puede alcanzar por sí solo (el subproceso MCP de cada rol ejecutivo, o un
proceso externo como n8n en la Fase 4 del plan).

Decisión de escala ya tomada en el plan aprobado con el fundador: a ~200-600 eventos/día el throughput
no es el problema — lo que falta es (a) cruzar el límite de proceso del subproceso MCP, (b) que un
consumidor caído pueda pedir "todo desde el cursor X", y (c) que n8n tenga un nodo nativo para
conectarse sin un shim HTTP genérico. Redis Streams es la opción más chica que da las tres cosas.

## Decisión

**Redis nunca es una dependencia dura, en tres capas distintas de degradación honesta:**

1. `SNARF_REDIS_URL` sin setear (default, y default en tests — `tests/conftest.py`) ⇒ el paquete
   `redis` ni se importa. `snarf/telemetry/redis_sink.py::install()` es un no-op que devuelve `False`.
2. `SNARF_REDIS_URL` seteada pero el servidor real caído o inalcanzable ⇒ `publish_to_stream()` (el
   callback que corre en el worker thread del dispatcher de Fase 1) traga la excepción real
   (`ConnectionError`/`TimeoutError`/lo que sea), la cuenta en `redis_sink.health()`, y un turno real
   nunca se entera. Verificado en vivo contra un puerto real sin nada escuchando (no solo con un fake
   en los tests).
3. `GET /events/stream` funciona en los dos casos: con Redis configurado, lee del stream real
   (`XREAD BLOCK`, cursor = Redis Stream ID real, persistente); sin Redis, lee de
   `snarf/telemetry/event_buffer.py` (un `deque(maxlen=500)` in-process, otro subscriber más del
   dispatcher, cursor = número de secuencia local, efímero — alcanza para una pestaña abierta en vivo).

**Diseño del stream**: un único stream `snarf:events` (no uno por tipo de evento — la traza y el
replay futuro necesitan un log ordenado único; los consumidores filtran por campo), `MAXLEN ~ 100000`
aproximado. Campos promovidos para filtrado barato (`event_type`, `trace_id`, `nodo`, `origin_pid`) más
`json` con el evento completo. Distinción documentada para no repetir el error estándar: un futuro
consumidor de trabajo compartido (n8n, un Control Center) debe usar **consumer groups**
(`XREADGROUP`); el propio `/events/stream` de Snarf usa **`XREAD` simple, sin grupo** — cada pestaña
quiere ver todo desde su propio cursor, un consumer group ahí partiría los eventos entre pestañas.

**`GET /events/stream`** (`app.py`): `async def`, no sync — una ruta streaming de larga vida no puede
fijar un worker del threadpool finito de Starlette por cada pestaña abierta (rompería `/send` para
todos los demás mientras alguien mira el HUD). Cursor real vía el header estándar `Last-Event-ID`
(reconexión automática del navegador) o `?last_event_id=`; sin ninguno, arranca solo con eventos
nuevos desde ese momento. Autenticado con la misma dependencia `require_user` (cookie de sesión) que
el resto de `/dashboard/*` — funciona con `EventSource` del navegador, que manda cookies pero no puede
setear headers custom.

**`snarf/runtime/ops_health.py`**: `system_health()` suma `event_dispatcher` (`dispatcher.stats()`) y
`event_bus_redis` (`redis_sink.health()`) — señales reales ya existentes, mismo criterio que el resto
de la función ("nunca una cifra inventada"). Visible vía el tool `ops_system_health` del Orchestrator.

## Riesgos/trade-offs

1. **El buffer in-process (`event_buffer.py`) es efímero** — un reinicio de Snarf lo vacía. Aceptado a
   propósito: es el fallback para cuando Redis (el único transporte persistente) no está configurado;
   no se le agrega persistencia propia, sería reconstruir Redis mal.
2. **Polling interno de 0.5s en el camino sin Redis** (`_events_stream`, `app.py`): más simple y
   correcto que empalmar el worker thread del dispatcher con el event loop de asyncio vía
   `call_soon_threadsafe`, al costo de hasta ~0.5s de latencia extra en vez de push instantáneo. El
   camino con Redis (`XREAD BLOCK`) sí es push real. Revisar si algún día la latencia del camino sin
   Redis importa de verdad — hoy es un HUD para un humano mirando la pantalla, no un sistema de
   trading.
3. **`redis==8.1.0` es una dependencia real nueva en `requirements.txt`**, aunque nunca se active sin
   `SNARF_REDIS_URL` — instalarlo no cuesta nada (gratis, self-hosted, ver sección de Costos del plan
   aprobado), pero es una superficie más en el árbol de dependencias.
4. **El servidor Redis en sí no se instaló en esta ronda** (no hay `redis-server`/`brew install redis`
   corrido todavía) — deliberado: per el plan aprobado, el día de instalarlo de verdad es cuando n8n o
   un Control Center empiecen a leer (Fase 4+), no antes. Esta fase deja el código listo, no la
   infraestructura corriendo.

## Verificado

- 22 tests nuevos: `tests/test_redis_sink.py` (8: `is_configured`/`install` con y sin env var, un
  cliente fake real vía `redis.Redis.from_url` monkeypatcheado — no un doble genérico — confirma
  `xadd(STREAM_KEY, fields, maxlen=MAXLEN, approximate=True)` con el evento completo serializado,
  `publish_to_stream` traga un `ConnectionError` real y lo cuenta, `health()` sin instalar), 
  `tests/test_event_buffer.py` (7: FIFO, cursor por secuencia, buffer acotado, reset, instalación real
  como subscriber del dispatcher), `tests/test_events_stream_endpoint.py` (5: frame SSE real desde el
  buffer, respeta un cursor explícito y el header `Last-Event-ID`, corta limpio cuando el request se
  desconecta, 401 real sin sesión), extensión de `tests/test_ops_health.py` (+2: `event_dispatcher`/
  `event_bus_redis` presentes con la forma esperada).
- 1154/1154 tests de la suite completa (`.venv/bin/python -m pytest -q`).
- Smoke test real fuera de pytest: `SNARF_REDIS_URL` apuntando a un puerto real sin nada escuchando —
  `install()` sucede igual (la conexión de `redis-py` es perezosa), `publish_to_stream` produce un
  `ConnectionError` real (`Errno 61: Connection refused`) capturado y contado, tanto llamado directo
  como a través del worker thread del dispatcher — nunca se propaga.
