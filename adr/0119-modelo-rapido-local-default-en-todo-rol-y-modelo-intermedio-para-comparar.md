# ADR 0119 — Modelo rápido local como default en TODOS los roles, modelo intermedio probado y descartado en vivo, indicador de conexión en la UI

**Fecha:** 2026-08-05
**Estado:** Aceptado — decisión final tomada tras prueba real en producción (ver Epílogo)

## Contexto

Tras ADR 0118 (mismo día, ronda anterior): `orchestrator` había quedado en el fallback automático
(`xai`) por picos de latencia reales del modelo local pesado (Qwen3-8B) bajo presión de memoria. El
fundador, tras probar manualmente el rol rápido en el orquestador, reportó que "el pequeño está
funcionando muy bien en la práctica" y pidió tres cosas en paralelo:

1. Poner el modelo rápido local (`mlx_local_fast`, Qwen3-4B) como default en **todos** los roles, "para
   probar todo absolutamente" — no solo los 3 roles chicos ya ruteados ahí.
2. Instalar un modelo **intermedio** para comparar contra rápido/pesado antes de fijar una decisión
   final, dejando la elección concreta a criterio de esta sesión ("cuales son los disponibles? define
   FODA para cada uno y toma una decisión argumentada").
3. Confirmar que no quedara ningún server MLX corriendo de más, y agregar un indicador de carga
   "Snarf se está conectando..." en la interfaz.

## FODA de candidatos para el modelo intermedio

Investigado en vivo (no de memoria): `Qwen3.5` es una familia nueva (posterior al corte de
entrenamiento), con soporte ya mergeado en `mlx-lm` 0.31.3 (`qwen3_5`/`qwen3_5_moe` confirmados vía
`pkgutil` contra el propio `.venv`, no asumido).

- **Qwen3-14B-4bit** (el mismo "pesado" original de ADR 0117/0118): Fortalezas: ya conocido, sin
  sorpresas de compatibilidad. Debilidades: es exactamente el modelo con 2 incidentes reales de
  auto-revert por presión de memoria ya documentados. Oportunidad: los fixes de timeout/`max_retries=0`
  de ADR 0118 no existían en esas pruebas, podría comportarse mejor ahora. Amenaza: repetir el mismo
  patrón de inestabilidad con evidencia ya real de que la causa (presión de memoria de esta Mac, no
  solo el timeout) sigue sin resolverse.
- **Qwen2.5-14B-Instruct-4bit**: Fortalezas: arquitectura probada en otros proyectos MLX. Debilidades:
  generación vieja (2024), sin historial en Snarf. Oportunidad: ninguna real frente a las otras dos
  opciones. Amenaza: correr una prueba a ciegas sin ganancia clara sobre las otras opciones.
- **Qwen3.5-9B-MLX-4bit** (elegido): Fortalezas: generación más nueva que el propio Qwen3-8B ya
  instalado, tamaño en disco casi idéntico (~5GB vs ~4.6GB) — permite comparar "generación nueva, mismo
  tamaño" en vez de solo "más parámetros". Tool-calling confirmado funcionando en vivo (`tool_calls`
  bien formado contra una tool de prueba). Debilidades reales encontradas en vivo: es un modelo de
  *thinking* — emite un campo `reasoning` separado en cada respuesta, incluso para pedidos triviales
  (217 tokens de razonamiento para responder "OK" a un pedido de una palabra) — esto es costo real de
  latencia/tokens que Qwen3-4B-Instruct-2507 (variante explícitamente no-thinking) no paga. Oportunidad:
  puede rendir mejor en tareas que sí se benefician de razonar antes de responder. Amenaza: el costo de
  thinking por defecto podría hacerlo más lento que Qwen3-8B para el mismo tamaño en la práctica — no
  medido todavía de forma limpia (ver Hallazgo real más abajo).

**Decisión:** Qwen3.5-9B-MLX-4bit, instalado como tercer preset `mlx_local_mid` (puerto 8992,
`com.snarf.mlx-mid.plist`). Descargado (~5GB, 5m27s) y verificado con una llamada de tool-calling real
antes de continuar.

## Cambios

- `snarf/runtime/llm_routing.py`: nuevo preset `mlx_local_mid` (mismo patrón que `mlx_local`/
  `mlx_local_fast`, `local=True`, sin credencial). `DEFAULT_ROUTING` cambia: **todos** los roles pasan a
  `mlx_local_fast`, con una única excepción real — `drive_vision` se queda en `claude-haiku-4-5`, porque
  necesita soporte real de imágenes (`VISION_FALLBACK_ORDER` ya documentaba esta restricción) y
  Qwen3-4B-Instruct-2507 es texto-solo. Setearlo igual hubiera roto en silencio la descripción de
  imágenes de Drive.
- `data/llm_routing.json`: actualizado en producción real vía `PUT /llm-routing` autenticado (sesión
  generada a mano con el `SESSION_SECRET` real del `.env`, nunca impreso) — los 24 roles reales, con la
  misma excepción de `drive_vision`.
- `web/index.html`: `LLM_PRESETS` suma la entrada de `mlx_local_mid` (Qwen3.5 9B) para que sea
  seleccionable desde Configuración → LLM por rol, igual que las otras dos.
- `web/index.html`: overlay nuevo `#connectingOverlay` — pantalla completa, bloquea toda interacción
  (z-index alto, sin necesidad de deshabilitar elementos uno por uno) mientras `/status` no responde.
  Cubre dos casos reales: arranque en frío del server, y la pestaña ya abierta cuando el server se
  reinicia solo (LaunchAgent `KeepAlive` tras un crash — ver hallazgo de abajo). No hace falta un chequeo
  separado de "modelo caliente": `orchestrator.warmup()` corre en el evento `startup` de FastAPI, que
  bloquea el bind del socket — si `/status` responde, el modelo del rol activo ya terminó de calentar.
  Verificado con Playwright contra el server real: sin errores de consola, el overlay se oculta apenas
  `/status` responde, y una captura forzando que `/status` falle confirma el estilo visual.

## Hallazgo real: crash de Metal por correr dos servers MLX concurrentes

Al intentar medir latencia rápido-vs-intermedio con ambos servers activos a la vez, el server rápido
(`com.snarf.mlx-fast`) crasheó de verdad:

```
RuntimeError: [METAL] Command buffer execution failed: Insufficient Memory
(00000008:kIOGPUCommandBufferCallbackErrorOutOfMemory)
```

Memoria libre real medida con `vm_stat` en el momento del crash: **0.06GB** (con solo rápido + intermedio
+ el uso normal de la Mac, nada del server pesado). Apagar el server intermedio liberó memoria de
inmediato (0.06GB → 6.83GB). El proceso del server rápido quedó "vivo" pero no respondía a nuevos
requests (el bucle interno de generación había muerto) — tuvo que reiniciarse a mano
(`launchctl bootout`/`bootstrap`).

**Conclusión:** en esta Mac (M2 Max, 32GB unificados), dos modelos MLX de tamaño no-trivial (4B+9B ya
alcanza) generando **al mismo tiempo** puede agotar la memoria de Metal y crashear el proceso, no solo
ponerse lento — un nivel de severidad mayor al de los picos de latencia ya documentados en ADR 0118.
Por eso: `com.snarf.mlx-mid` queda **instalado pero apagado** (no `RunAtLoad` activo) tras esta ronda —
nada lo rutea por default, así que no hay riesgo de que compita por memoria con el rápido en uso normal.
Levantarlo (`launchctl bootstrap gui/501 ~/Library/LaunchAgents/com.snarf.mlx-mid.plist`) queda como
acción manual y deliberada para cuando el fundador quiera un A/B puntual — nunca automático mientras el
rápido siga siendo el default de facto en 23 de 24 roles.

La comparación de latencia limpia rápido-vs-intermedio (secuencial, no concurrente) queda pendiente —
no se completó esta ronda por el tiempo que tomó diagnosticar y recuperarse del crash real. Ver
Consecuencias.

## Bug real encontrado y corregido: tests pegándole a un server local real

Cuatro tests de `tests/test_orchestrator.py` asumían que "sin credencial real" (conftest.py borra todas
las API keys de proveedores pagos) implicaba automáticamente "LLM no disponible → modo eco". Eso era
cierto mientras el default era `anthropic` (que sí exige credencial) pero dejó de serlo con el nuevo
default `mlx_local_fast`: ese proveedor no exige ninguna credencial (corre en esta Mac), así que
`.available` da `True` sin importar qué haya en el `.env` — y como el server rápido real SÍ estaba
corriendo durante los tests, terminaron pegándole de verdad a `http://localhost:8991` en vez de
ejercitar el modo eco/corte duro que decían estar probando (confirmado viendo una respuesta real del
modelo — "No se proporcionó un mensaje con contenido para resumir..." — donde el test esperaba el
texto fijo de fallback).

Arreglado ruteando esos 4 tests a mano a `anthropic` (sin credencial en el fixture, por lo tanto
genuinamente no disponible) antes de ejercitar el camino que prueban, en vez de depender del default
vigente. Suite completa: **952/952 tests, 0 fallos**, verificado dos veces (una durante la contención de
memoria real del crash de arriba, con tiempos muy anormales — 13 min; otra en frío, 2m07s).

**Riesgo no resuelto, señalado con honestidad:** esta misma clase de bug puede seguir latente en tests
que llaman `orchestrator.handle()` sin mockear `_llm` explícitamente y sin depender de un texto exacto
de modo eco — hoy "pasan" porque este Mac en particular tiene el server local real corriendo, pero en
otra máquina (o CI) sin ningún server MLX escuchando, esos mismos tests probablemente rompan con un
error de conexión sin manejar (el bloque de modo eco solo se activa si `.available` es `False`, y para
un proveedor local eso nunca ocurre aunque el puerto esté cerrado). No se auditó la suite completa en
busca de este patrón — queda como trabajo pendiente real, no resuelto hoy.

## Verificado

- 952/952 tests, suite completa, dos corridas (ver arriba).
- `mlx_local_mid` responde correctamente en `/v1/chat/completions`, con y sin `tools` — tool-calling
  confirmado con una tool de prueba real.
- Overlay de conexión verificado con Playwright contra el server real (HTTPS/Tailscale, sesión
  autenticada): sin errores de consola, se oculta apenas `/status` responde; captura forzando fallo de
  `/status` confirma el estilo visual.
- Memoria real: `com.snarf.mlx-heavy` (Qwen3-8B) confirmado apagado (no en `launchctl list`) desde la
  ronda anterior — solo `com.snarf.mlx-fast` queda activo 24/7 tras esta ronda; `com.snarf.mlx-mid`
  instalado pero detenido.

## Epílogo: prueba real en producción y decisión final (mismo día, después del Hallazgo de arriba)

Con el hallazgo del crash ya conocido, el fundador pidió explícitamente probarlo en real de todos
modos: reiniciar el server de producción para ver el indicador de conexión en frío, y luego una
segunda ronda con el modelo intermedio en `orchestrator` + los 7 Especialistas del board ejecutivo
(`executive_cto/coo/research/ceo/cfo/cmo/creative`), decididos explícitamente por el fundador entre
las opciones ofrecidas.

**Bug real encontrado en el camino:** `PUT /llm-routing` (`app.py`) llamaba a `save_routing(payload)`
con el payload crudo del request — como el frontend manda un solo rol por request
(`persistLlmRouting` en `web/index.html`), y `save_routing`/`_normalize` completa cualquier rol
ausente con `DEFAULT_ROUTING` (no con el archivo ya guardado), **cada cambio de UN rol desde
Configuración reseteaba en silencio todos los demás roles a los defaults del código.**
`attempt_fallback` (mismo archivo) ya hacía el merge correcto
(`save_routing({**load_routing(), role: new_entry})`) — el endpoint era la única ruta rota. Arreglado
mergeando con `load_routing()` antes de guardar, con test de regresión
(`test_llm_routing_put_of_one_role_does_not_reset_the_others`).

**Otro hallazgo real:** con el modelo intermedio activo, una respuesta larga del chat dejaba **todo el
servidor sordo** (dashboard, otra pestaña, `/status`) hasta terminar de generar — confirmado viendo
`curl` local devolver timeout mientras `mlx_lm.server` seguía procesando el prompt real, y volviendo a
responder en milisegundos apenas terminó. Esto explica por qué el fundador reportó "el enlace no
funciona" en medio de la prueba: el server no estaba caído, estaba bloqueado sincrónicamente por su
propio mensaje. Se agregó timestamp por línea al log real (`snarf/runtime/timestamp_lines.py`, pipeado
desde el LaunchAgent `com.snarf.server.plist` vía `/bin/sh -c "... | ..."`) para poder correlacionar
esto con evidencia exacta en el futuro, en vez de logs de acceso de uvicorn sin hora.

**Decisión final del fundador, con Activity Monitor real mostrando 31GB de RAM usada / 24.8GB de
Python:** abandonar el modelo intermedio como candidato para `orchestrator`/Especialistas. Motivos
dados explícitamente: "todo el sistema crashea y se pone lento", y el propio mecanismo de fallback
automático redirigió a `xai` antes de que se pudiera evaluar la calidad real del intermedio (la
inestabilidad de memoria le ganó de mano a la propia prueba de calidad). El modelo rápido, en cambio,
"funcionó bien" en el uso real de toda la sesión.

- `com.snarf.mlx-mid` queda detenido (instalado, sin `RunAtLoad` activo) — mismo estado que tras el
  Hallazgo de arriba, ahora confirmado con una segunda instancia real del mismo problema (memoria
  crítica: 0.06GB libres dos veces en la misma sesión, la segunda vez con el intermedio corriendo
  **solo**, sin el rápido compitiendo — el cache de contexto del propio intermedio acumulando por
  turno, `Prompt Cache` subiendo de 0 a 3.56GB en ~15 minutos de uso real, ya alcanza para llevar esta
  Mac al límite).
- `DEFAULT_ROUTING` y `data/llm_routing.json` quedan en el estado final: `mlx_local_fast` en 23 de 24
  roles, `drive_vision` en `claude-haiku-4-5`. Verificado en vivo: server reiniciado limpio, `/status`
  200 OK, 17.96GB libres con solo `com.snarf.mlx-fast` activo.
- Candidato de reemplazo para el propio rápido, no probado, mencionado pero explícitamente NO
  perseguido esta ronda: `Qwen3.5-4B-MLX-4bit` (misma familia nueva que el intermedio descartado,
  tamaño casi idéntico ~2.9GB) — riesgo real sin verificar: si hereda el comportamiento *thinking* por
  default del Qwen3.5-9B ya probado (emite razonamiento hasta en respuestas triviales, medido en
  217 tokens de `reasoning` para responder "OK"), perdería la ventaja central que hizo funcionar bien
  al rápido actual (sin ese costo). Queda como pendiente real, no una recomendación.

## Consecuencias

- 23 de 24 roles reales corren ahora en el modelo rápido local (`Qwen3-4B-Instruct-2507`, sin costo de
  tokens) — incluido `orchestrator`, revirtiendo la decisión de ADR 0118 de dejarlo en `xai` tras los
  picos del modelo pesado. El fundador aceptó explícitamente este riesgo ("quiero seguir empujando el
  límite del modelo local", decisión de la ronda anterior de esta misma sesión) — sigue sin haber
  `_ResilientLLM` (fallback automático a proveedor pago) para el rol `orchestrator` específicamente (ver
  gap ya documentado en el plan de esta ronda, Punto 5.5) — si el server rápido crashea como el que se
  vio hoy, `orchestrator` queda sin respuesta hasta que `KeepAlive` lo reinicie solo, sin fallback
  automático a un proveedor pago mientras tanto.
- La comparación cuantitativa rápido/intermedio/pesado para decidir un default final sigue sin
  completarse — es trabajo real pendiente, no una conclusión que se está ocultando.
- El riesgo de tests no-herméticos pegándole a un server local real (arriba) queda documentado pero sin
  arreglo estructural — solo los 4 casos que efectivamente rompieron esta ronda.
