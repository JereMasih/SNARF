# ADR 0128 — Fuga de memoria real en el server MLX local (31GB) y tope duro de cuota de RAM

**Fecha:** 2026-08-06
**Estado:** Aceptado

## Contexto

Reporte del fundador: el modelo local dejó de usarse — todo caía a Grok sin aviso — y `top`/Activity
Monitor mostraban un proceso Python real usando ~31GB de RAM en una Mac de 32GB, sin uso real de CPU.
Pedido explícito: encontrar la causa real, arreglarlo, y garantizar que el server local nunca vuelva a
ocupar más de una cuota razonable (25% máximo) de la RAM de la Mac.

## Diagnóstico

`top -pid <pid>` confirmó el proceso real: `com.snarf.mlx-fast` (puerto 8991, Qwen3-4B-Instruct-2507-4bit),
31G de `MEM`/`RSIZE`, 0% CPU — vivo pero inservible. Revisando `~/Library/Logs/snarf/mlx_fast.log`:

- A las 19:24 (7 horas antes del reporte), una tanda de requests concurrentes incluyó un prompt de
  **20.804 tokens** batcheado junto a ~5 requests más (~1.000-1.300 tokens cada uno) — un volumen agregado
  real que superó la memoria de Metal disponible: `RuntimeError: [METAL] Command buffer execution failed:
  Insufficient Memory`.
- La limpieza del generador (`BatchGenerator.__del__` → `close()` → `mx.synchronize`) **también** falló con
  el mismo error de out-of-memory — la memoria de GPU ya asignada para ese request nunca se liberó.
- A diferencia de 6 incidentes anteriores en el mismo log (cada uno reinició el proceso completo vía
  `KeepAlive` del LaunchAgent, cache en 0 de nuevo), **este** no mató al proceso principal — quedó vivo,
  escuchando en el puerto, aceptando conexiones nuevas, pero con la memoria ya fugada para siempre
  mientras ese proceso siguiera corriendo. Las siguientes ~7 horas de tráfico real solo se sumaron sobre
  ese piso ya roto.

**Causa raíz del prompt de 20.804 tokens**: `Orchestrator._summarize_history_entry()`
(`snarf/core/orchestrator.py`) compacta vía el rol `history_compaction` (modelo rápido local, default para
todo rol desde ADR 0119) cualquier entrada vieja del historial que supere `HISTORY_REPLAY_MAX_CHARS`
(8.000 caracteres) — pero **sin ningún tope superior**: una entrada extrema (ej. una respuesta anterior con
el volcado completo de un resultado de herramienta gigante, el mismo patrón que ya había causado el
incidente de 523.869 tokens documentado en el propio código) se manda ENTERA, sin cortar, al modelo local
de 4B para "compactarla" — exactamente lo que rompió el server esta vez.

**Bug real confirmado en `mlx_lm` 0.31.3** (`.venv/lib/python3.13/site-packages/mlx_lm/server.py:1743`):
`--prompt-cache-bytes` se parsea como flag CLI pero **nunca se pasa** al constructor real de
`LRUPromptCache` (`server.py` solo pasa `prompt_cache_size` — el conteo de secuencias — no
`prompt_cache_bytes`). El límite de bytes que veníamos usando desde ADR 0120 era, en la práctica, casi un
no-op: solo se aplica en una rama muy específica (`trim_to()`, cuando un request nuevo se une a un batch ya
activo), no en cada inserción real a la caché. `--prompt-cache-size` (tope de cantidad de secuencias) sí se
respeta de verdad en cada inserción (`LRUPromptCache.insert_cache`, confirmado leyendo
`mlx_lm/models/cache.py`).

## Decisión

1. **Restart inmediato** de `com.snarf.mlx-fast` (`launchctl bootout`/`bootstrap`) — liberó los 31GB al
   instante.
2. **Fix real de la causa más común** (`snarf/core/orchestrator.py`): tope duro nuevo,
   `HISTORY_COMPACTION_INPUT_MAX_CHARS = 32000`. Por encima de este tamaño, `_summarize_history_entry()`
   ni siquiera intenta compactar vía LLM — corta directo con `_hard_cut_for_replay()`. No hay forma segura
   de "compactar" con un modelo de 4B algo tan grande como para arriesgar tumbar el server que lo sirve.
3. **Defensa en profundidad en los 3 LaunchAgents MLX** (`mlx-fast`/`mlx-heavy`/`mlx-mid`):
   `--prompt-cache-size 3` (bajado del default de la librería, 10) — el knob que sí se respeta de verdad en
   cada inserción, cotas la cantidad de secuencias completas que puede acumular la caché sin importar el
   bug de `--prompt-cache-bytes` de arriba.
4. **Watchdog de memoria nuevo** (`snarf/runtime/mlx_memory_watchdog.py` +
   `~/Library/LaunchAgents/com.snarf.mlx-watchdog.plist`, `StartInterval=90`): revisa cada 90s la memoria
   real (`ps -o rss=`) de cada LaunchAgent MLX real cargado y lo reinicia (`launchctl kickstart -k`) si
   supera el **25% de la RAM total de la Mac** (`sysctl hw.memsize`) — la garantía dura que pidió el
   fundador, independiente de cualquier causa futura no prevista (el bug de limpieza de `mlx_lm` en sí no
   se puede parchear de forma sostenible sin tocar una librería de terceros).

## Por qué no migrar a Ollama/LM Studio ahora

El fundador preguntó si convendría una app dedicada para gestionar el modelo local. Es una opción real —
ambas tienen mejor observabilidad de memoria out-of-the-box — pero es un cambio de arquitectura (reemplazar
la Capacidad completa que habla con `mlx_lm.server`, revalidar streaming/tool-calling/prompt caching contra
otro runtime) mucho más grande que lo que este incidente puntual necesitaba. La causa real ya estaba
identificada y arreglable en su lugar: un tope de tamaño de entrada que faltaba en código propio, más un
bug puntual y acotado de una librería de terceros que un flag distinto (`--prompt-cache-size`, sí
respetado) ya cubre en la práctica. Queda como decisión pendiente para el fundador si más adelante quiere
evaluar el cambio de runtime por otros motivos (observabilidad, gestión de múltiples modelos) — no se
descarta, solo no era lo que este bug requería.

## Verificado

- `.venv/bin/python -m pytest -q` — 1018 passed (9 tests nuevos: 1 en `test_orchestrator.py` para el tope
  de `_summarize_history_entry`, 8 en `test_mlx_memory_watchdog.py` nuevo para la lógica de decisión y el
  reinicio selectivo, con `launchctl`/`ps`/`sysctl` fakeados — nunca tocando procesos reales en tests).
- `com.snarf.mlx-fast` reiniciado con `--prompt-cache-size 3` aplicado: confirmado en vivo con `ps aux`,
  2.59GB de RSS real tras cargar el modelo (contra un presupuesto real de 8.6GB = 25% de 32GB).
- Watchdog cargado (`launchctl list`) y ejecutado en vivo contra los procesos reales: confirmó
  `com.snarf.mlx-fast` dentro de cuota, `mlx-heavy`/`mlx-mid` no cargados (correcto, no son el default
  desde ADR 0119) — sin reiniciar nada innecesariamente.

## Consecuencias

- El mismo patrón de "tope de tamaño antes de mandarle algo grande a un modelo local barato" queda como
  precedente para cualquier rol futuro que reciba contenido potencialmente gigante sin control propio.
- El watchdog es la única garantía real de "nunca más del 25%" — si `mlx_lm` cambia de versión y el bug de
  `--prompt-cache-bytes` se corrige upstream, el watchdog sigue siendo la red de seguridad correcta igual
  (defensa en profundidad, no un parche puntual atado a esta versión exacta de la librería).
