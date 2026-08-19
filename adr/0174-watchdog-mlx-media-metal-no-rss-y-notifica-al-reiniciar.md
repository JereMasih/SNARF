# ADR 0174 — El watchdog de memoria MLX medía RSS, no la memoria real de Metal; ahora avisa al reiniciar

**Fecha:** 2026-08-18
**Estado:** Aceptado

## Contexto

El mismo incidente de ADR 0128 (`com.snarf.mlx-fast` fugando memoria hasta ~31GB en una Mac de 32GB) volvió
a pasar hoy, con el watchdog de esa ADR ya desplegado y corriendo cada 90s. El fundador reportó la Mac
lenta; `top`/Activity Monitor confirmaron el mismo proceso en 31GB de `phys_footprint`, 0% CPU real, sin
requests en curso desde hacía ~40 minutos.

## Diagnóstico

El watchdog nunca disparó porque medía memoria con `ps -o rss=` (`rss_bytes()`, ver ADR 0128). En procesos
MLX, `ps` solo cuenta la RSS "clásica" del proceso — no ve la memoria unificada de Metal (GPU) que
`mlx_lm.server` retiene en su allocator interno tras procesar prompts grandes. Confirmado en vivo con el
proceso real (PID 1578, 6h12min corriendo):

- `ps -o rss=` → **2.2GB**
- `top -l 1 -pid 1578 -stats pid,mem` (mismo campo que usa Activity Monitor) → **31GB**
- `footprint 1578` (`phys_footprint`) → **31GB**, confirmando que `top` es la cifra correcta.

El tope de cuota (25% de RAM, `MAX_MEMORY_FRACTION`) nunca se evaluó contra un número real: `ps` reportaba
un séptimo de la memoria de verdad, muy por debajo del 25%, sin importar cuánto creciera el proceso de
verdad. La "última red de seguridad" de ADR 0128 tenía, en la práctica, un agujero de origen — nunca se
había verificado contra un caso real de fuga hasta ahora.

## Decisión

1. **`snarf/runtime/mlx_memory_watchdog.py`**: `rss_bytes()` (vía `ps -o rss=`) reemplazado por
   `footprint_bytes()` (vía `top -l 1 -pid <pid> -stats pid,mem`, parseando el sufijo B/K/M/G/T que usa
   `top`) — la misma cifra que Activity Monitor, incluye memoria de Metal.
2. **Notificación de macOS** (`osascript display notification`) cada vez que el watchdog reinicia un agente
   por superar la cuota, con el label y los GB reales — para que el fundador se entere de forma proactiva en
   vez de notar la Mac lenta primero. No hay forma útil de "preguntar antes" en un daemon desatendido que
   corre cada 90s sin nadie mirando: el reinicio es barato (recarga el modelo en ~1 min, sin pérdida de
   datos) y esperar confirmación solo alargaría la ventana de RAM comprometida.
3. Cuota (`MAX_MEMORY_FRACTION = 0.25`) y resto de la lógica de decisión sin cambios — el bug era
   puramente de medición, no de umbral.

## Verificado

- `.venv/bin/python -m pytest -q` — 1485 passed (tests de `test_mlx_memory_watchdog.py` reescritos para
  simular salidas de `top` en vez de `ps`, incluida una fila sin datos para un PID inexistente).
- `footprint_bytes()` corrido en vivo contra el proceso `com.snarf.mlx-fast` real (recién reiniciado,
  2.90GB) — coincide con `top`/Activity Monitor.
- Reinicio manual real de `com.snarf.mlx-fast` (vía `launchctl kickstart -k`, no por el watchdog) confirmado
  en logs: modelo recargado limpio, footprint bajó de 31GB a 2.4GB al arrancar.

## Consecuencias

- El watchdog ahora es una garantía real, no solo nominal — la próxima fuga de este tipo se corta sola
  dentro de los 90s siguientes a cruzar 8GB (25% de 32GB), no después de horas.
- Patrón a tener en cuenta para cualquier chequeo de memoria futuro sobre procesos que usan Metal/GPU en
  Apple Silicon: `ps`/`psutil` no alcanza, hace falta `top -stats pid,mem` o `footprint <pid>`.
