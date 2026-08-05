# ADR 0120 — Causa real de los crashes de memoria (cache sin límite de mlx_lm.server), Kokoro TTS nativo en la Mac, Docker se preserva como arquitectura del VPS

**Fecha:** 2026-08-05
**Estado:** Aceptado

## Contexto

Tras el epílogo de ADR 0119 (modelo intermedio descartado por inestabilidad real), el fundador reportó
nueva evidencia real de Activity Monitor: 17.93GB usados por Python + 3.87GB por la máquina virtual de
Colima, un fallback automático a `xai` sin haberlo pedido, y preguntó explícitamente si había que bajar
a un modelo más chico. Pidió corroborar antes de proponer downgrade, y por separado, dejar asentada la
arquitectura de voz pensada para el VPS mientras se optimiza el proceso local de hoy.

## Hallazgo real: el problema nunca fue el tamaño del modelo

Medido con `footprint` (la misma herramienta que usa Activity Monitor internamente, no `ps` — `ps` da
RSS clásico, que en Apple Silicon **no** captura los buffers de Metal/GPU de un proceso):

```
Python [21457] (mlx-fast, Qwen3-4B): Footprint: 18 GB
  18 GB  IOAccelerator (graphics)   ← prácticamente el 100% del footprint
```

`mlx_lm.server` cachea el KV cache de cada conversación **sin ningún límite por default** — corriendo
24/7 desde hace horas, esto creció hasta 18GB (el modelo en sí, 4-bit, pesa ~2.5GB). Confirmado
inmediatamente después de un reinicio limpio: **2437 MB**, calzando casi exacto con el tamaño real del
modelo. Esto explica los dos crashes reales de Metal de esta sesión (`kIOGPUCommandBufferCallbackErrorOutOfMemory`,
tanto en el modelo intermedio como, después, en el rápido) sin que el tamaño del modelo elegido tuviera
la culpa.

El fallback a `xai` sin aviso explícito que reportó el fundador fue exactamente ese crash del rápido
(`data/llm_fallback_log.jsonl`, timestamp coincide al segundo con el error de Metal en `mlx_fast.log`)
— el mecanismo de fallback automático hizo lo que tiene que hacer (degradar con gracia en vez de dejar
al fundador sin respuesta), pero el server MLX crasheado se quedó corriendo, sin usarse, ocupando
memoria igual — el "no tiene sentido" que señaló el fundador es correcto: nada volvía a poner el rol de
vuelta en local ni liberaba el proceso roto.

## Decisión 1: acotar el cache de los 3 servers MLX

`mlx_lm.server` expone `--prompt-cache-bytes` (tope real en bytes del KV cache antes de empezar a
evictar). Agregado a los 3 LaunchAgents (`com.snarf.mlx-fast/mid/heavy.plist`) con un tope de 4GB
(`4294967296`) cada uno — generoso para mantener el beneficio real del cache (varias conversaciones
calientes a la vez) sin arriesgar que un server, solo, se coma la Mac entera de nuevo.

- Verificado: `mlx-fast` reiniciado con el flag aplicado, footprint real bajó de 18GB a 2437MB de
  inmediato. El crecimiento futuro queda acotado por diseño, no solo pospuesto.
- `orchestrator`/`dashboard_curator` (los dos roles que habían caído a `xai` por el crash) re-ruteados
  a `mlx_local_fast`, server principal reiniciado limpio.
- Con esto resuelto, **no se recomienda bajar de modelo todavía** — el problema real ya tiene un fix
  aplicado y verificado, downgradear el modelo hubiera sido tratar el síntoma equivocado.

## Decisión 2: Kokoro TTS nativo en la Mac (MPS), Docker/Colima queda solo para el VPS

Investigado con `footprint`-equivalente para Docker: Colima reserva 8GiB de VM, el contenedor de Kokoro
usa 1.7GiB reales adentro — memoria real perdida en la capa de virtualización, sin beneficio en esta
Mac (Colima nunca tuvo acceso a Metal/GPU, así que Kokoro corría 100% CPU adentro del contenedor).

`Kokoro-FastAPI` (el proyecto real detrás de la imagen Docker) tiene un modo nativo documentado con
soporte real de MPS (GPU de Apple) vía `uv` — clonado en
`~/Documents/PROGRAMACION/PROYECTOS/kokoro-fastapi` (fuera del repo de Snarf, es una dependencia
externa, no código propio) y levantado como LaunchAgent (`com.snarf.kokoro-tts.plist`, mismo patrón que
`com.snarf.server`/`com.snarf.mlx-*`: invoca `.venv/bin/python -m uvicorn ...` directo, nunca el script
wrapper, por el mismo gotcha de TCC ya documentado en CLAUDE.md).

**Cero cambios de código hicieron falta**: `snarf/voice/config.yaml` ya apuntaba a
`http://localhost:8880` — el mismo puerto que el proceso nativo expone. Mover Kokoro de Docker a nativo
en la Mac es exactamente el caso de uso para el que `base_url` existe (ver ADR 0056).

- Verificado: modelo cargado en `mps` real (`Loading Kokoro model on mps` / `Moving model to MPS device`
  en el log), calentamiento real de 12s, 68 voice packs cargados, audio real generado y confirmado con
  `ffprobe` (5.35s de duración para un texto de prueba), y flujo completo end-to-end a través del propio
  `POST /tts` de Snarf contra producción real (200 OK, audio real recibido).
- Colima detenido (`colima stop`) — ya no corre ninguna VM en esta Mac.

### Arquitectura preservada para el VPS (Parte 4 del plan, sigue pendiente)

Pedido explícito del fundador: no perder la garantía de portabilidad que motivó Docker desde el día uno
(ADR 0056, "si funciona en este contenedor, funciona igual en el VPS") solo por optimizar la Mac hoy.
`docker-compose.voice.yml` (imagen `ghcr.io/remsky/kokoro-fastapi-cpu:latest`) **queda intacto en el
repo, sin tocar** — es la arquitectura real a usar cuando la Parte 4 (deploy a VPS) arranque: un VPS
típico no tiene GPU de Apple (MPS no existe fuera de macOS), así que el modo nativo de hoy no aplicaría
ahí de todos modos — Docker CPU-only sigue siendo la elección correcta para esa instancia futura, no un
compromiso. `snarf/voice/config.yaml` es el único archivo a tocar en ese momento (cambiar `base_url` al
host del VPS), tal como ya documentaba ADR 0056.

**Regla de esta decisión, para no reabrir la pregunta cada sesión:** local = nativo con MPS (más rápido,
sin overhead de VM); VPS = Docker CPU-only (portable, sin asumir GPU). Son dos entornos reales con
necesidades reales distintas, no una elección de "cuál es mejor" — ambos son correctos en su contexto.

## Verificado

- `footprint` (2 corridas, antes/después del fix de cache) — evidencia dura del origen real del
  problema, no una hipótesis.
- Suite completa de tests corriendo tras el cambio de infraestructura (ver CHANGELOG para el conteo
  final — el cambio no toca ningún código de Snarf, solo infraestructura local, por eso el impacto
  esperado en tests es nulo).
- Audio real generado y verificado con `ffprobe`, y flujo end-to-end real vía `/tts` autenticado contra
  producción.
- Tráfico real del fundador (`/send`, `/tts`) sirviendo correctamente durante y después de todos los
  cambios de esta ronda, visto en el log en vivo.

## Consecuencias

- Memoria real liberada: Colima (8GiB de VM) ya no corre; el cache de MLX queda acotado a 4GB por
  server en vez de crecer sin límite.
- Voz local ahora corre acelerada por GPU (MPS) en vez de CPU-only — posible mejora de latencia real,
  no medida formalmente todavía (no era el objetivo de esta ronda).
- Nueva dependencia externa fuera del repo de Snarf (`~/Documents/PROGRAMACION/PROYECTOS/kokoro-fastapi`,
  clon de git + `uv`/`espeak-ng` instalados vía Homebrew) — no versionada dentro de este repo, hay que
  tenerlo presente si esta Mac se reinstala alguna vez desde cero.
- `docker-compose.voice.yml` queda como código muerto en esta Mac específicamente (no se usa mientras
  el LaunchAgent nativo esté activo) pero vivo como especificación real para el VPS — no borrar.
