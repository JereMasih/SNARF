# ADR 0044 — El "fallo SSL intermitente" de Google era una condición de carrera entre threads, no la red

**Fecha:** 2026-07-29
**Estado:** Aceptado — corrige el diagnóstico de ADR 0041 y ADR 0043

## Contexto

ADR 0043 subió el reintento de Google de 1 a 3 intentos, asumiendo que `[SSL] record layer failure` era una falla de red genuinamente intermitente. Verificando en vivo después de ese fix, el error **seguía apareciendo** en el widget de Gmail real, incluso con los 3 intentos. Eso no cuadraba con la hipótesis de "red lenta": si fuera solo lentitud/hiccup, 3 intentos con pausa deberían haber bajado la tasa de fallo drásticamente, no dejarla igual.

Se reprodujo el fallo real de forma controlada: se llamó a `GoogleGmail`, `GoogleCalendar` y `GoogleDrive` (cada una con su `self._service` cacheado como singleton, patrón de ADR 0041) desde 24 threads concurrentes con un `ThreadPoolExecutor`. Resultado: **fallos reales, reproducibles a voluntad** — `SSLError: [SSL] record layer failure`, `[SSL] internal error`, `[SSL: LENGTH_MISMATCH] length mismatch`, y timeouts. Ninguno de estos apareció al llamar la misma API secuencialmente, uno por vez, en un loop de 6 intentos.

La causa real: FastAPI corre cada endpoint `def` (sync, no `async def`) en un thread separado de un threadpool. El dashboard dispara varios widgets en paralelo al cargar (`drive`, `gmail`, `gmail/digest`, `calendar`, `youtube`, más el chequeo de correo nuevo) — eso significa que **múltiples threads llaman al mismo objeto `GoogleGmail`/`GoogleCalendar`/etc. al mismo tiempo**, y todos comparten el mismo `self._service` (un objeto de `googleapiclient` construido sobre `httplib2`, que internamente mantiene un socket TLS). `httplib2.Http()` no es thread-safe para uso concurrente — dos threads leyendo/escribiendo el mismo socket TLS a la vez corrompen el estado de la conexión, produciendo exactamente esos síntomas de bajo nivel. El reintento de ADR 0041/0043 "ayudaba" solo por casualidad (a veces el reintento caía en un momento sin colisión), nunca resolvía la causa real — que es por qué el error persistía bajo carga real del dashboard.

## Decisión

`GoogleDrive`, `GoogleGmail`, `GoogleCalendar` y `GoogleYouTube` cambian `self._service` de un atributo simple compartido a una propiedad respaldada por `threading.local()` — cada thread obtiene y cachea su **propio** cliente de `googleapiclient`, nunca comparte el socket TLS de otro thread. `_client()` sigue igual (construye si `self._service is None`); lo único que cambia es que ese "None" y ese "ya construido" ahora son por-thread, no globales a la instancia.

Se agregó un método defensivo `_local_storage()` en cada clase (en vez de crear `self._local` solo en `__init__`) porque los tests existentes de estas 4 Capacidades construyen instancias vía `Clase.__new__(Clase)` y asignan `_service` directo, sin pasar por `__init__` — `_local_storage()` crea el `threading.local()` la primera vez que hace falta, sin importar cómo se haya construido la instancia.

El reintento triple de ADR 0043 **se mantiene** — ya no es la defensa principal, pero sigue siendo una red de seguridad razonable ante una falla de red real y genuinamente transitoria (que sí puede pasar, aparte de esto).

## Verificado

- 313/313 tests: se suman 8 tests nuevos en `tests/test_google_thread_local_service.py` (uno por cada una de las 4 Capacidades × 2 casos) que confirman aislamiento real entre threads (`_service` seteado en un thread nunca es visible en otro) y que el helper defensivo tolera instancias creadas sin `__init__`.
- Reproducido el fallo real ANTES del fix: 24 llamadas concurrentes reales (`ThreadPoolExecutor`, 8 iteraciones × 3 APIs) contra Gmail/Calendar/Drive con un solo `self._service` compartido → múltiples fallos SSL reales.
- Confirmado el fix DESPUÉS: exactamente el mismo escenario de 24 llamadas concurrentes reales, con `threading.local()` → **0 fallos**.

## Consecuencias

- Cada thread del pool de FastAPI que use estas Capacidades construye su propio cliente `googleapiclient` la primera vez que lo necesita — costo menor (no hay llamada de red al construirlo, solo credenciales ya cacheadas por `GoogleAuth`), aceptable dado que el threadpool de FastAPI no crea threads ilimitados.
- Si en el futuro se agrega una quinta Capacidad de Google, tiene que seguir este mismo patrón (`threading.local()`, no un atributo simple) desde el día uno — no porque sea elegante, sino porque el bug real que motivó esto vuelve a aparecer apenas hay dos requests concurrentes tocando la misma instancia.
- Este ADR no reemplaza a ADR 0041/0043 (esos siguen documentando el resto de sus decisiones, que siguen vigentes) — corrige puntualmente el diagnóstico de la causa del fallo SSL, que resultó ser distinta de lo que ahí se documentó.
