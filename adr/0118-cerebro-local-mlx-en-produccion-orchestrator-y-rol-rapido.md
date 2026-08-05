# ADR 0118 — Cerebro local MLX en producción: rol rápido a Qwen3-4B, `orchestrator` se queda en el fallback automático

**Fecha:** 2026-08-05
**Estado:** Aceptado — parcial (ver Decisión final, corrige una conclusión intermedia de esta misma ronda)

## Contexto

ADR 0117 (mismo día, sesión anterior) había revertido `orchestrator` a Anthropic tras medir el modelo
local demasiado lento e inconsistente (38.6s–991s). El fundador pidió retomarlo: encontrar el modelo
óptimo para tareas pesadas y sumar un segundo modelo, más liviano, para tareas rápidas.

**Hallazgo nuevo que cambia la conclusión de ADR 0117:** la lentitud medida esa vez no era
mayormente presión de memoria/swap (como se había interpretado) sino **costo de prefill en frío**.
`mlx_lm.server` cachea por prefijo de tokens: el prompt real de Snarf (system prompt + 88 tools,
~15.630 tokens) es casi idéntico en cada request — solo cambia el turno de conversación al final. Una
vez que ese prefijo queda cacheado (una sola vez, tras el primer request real), los requests
siguientes solo procesan los tokens nuevos del turno. Medido en vivo esta ronda:

- **Frío** (primer request tras (re)iniciar el server): ~90-105s, consistente entre `Qwen3-14B-4bit` y
  `Qwen3-8B-4bit` — el costo real es procesar el prefijo fijo de 15.630 tokens, no escala tanto con el
  tamaño del modelo entre 8B y 14B para esta carga.
- **Caliente** (prefijo ya cacheado): `Qwen3-14B-4bit` 14-29s, `Qwen3-8B-4bit` ~5.5-14s — verificado
  tanto de forma aislada (`OpenAICompatibleLLM` directo) como end-to-end contra producción real
  (`/send` autenticado vía HTTPS, ver Verificado).

Importante: el precalentamiento tiene que hacerse contra el prompt REAL de `Orchestrator.handle()`
(`SYSTEM_PREFIX + identidad + sarcasmo + perfil`, no solo `SYSTEM_PREFIX` a secas) — un precalentado
con un system distinto no comparte prefijo con el real y no sirve. La primera llamada real de
producción (97.2s) fue efectivamente el precalentado real; las siguientes ya cayeron a 5.5-7.3s.

## Decisión

- **`Qwen3-8B-4bit` reemplaza a `Qwen3-14B-4bit` como modelo "pesado" default** (`MLX_LOCAL_MODEL` en
  `snarf/runtime/llm_routing.py`). Con el prefijo cacheado ambos rinden similar (14B: 14-29s, 8B:
  5.5-14s) pero 8B usa ~la mitad de memoria residente (~7GB vs ~14GB con el cache del contexto
  completo) — decisivo porque el server corre 24/7 (ver más abajo), y el fundador señaló con datos
  reales (Activity Monitor, 29.57GB usados con 14B+4B simultáneos) que la memoria constante importa
  más que exprimir el modelo más grande posible.
- **Nuevo preset `mlx_local_fast`** (`snarf/runtime/llm_routing.py`): segundo server MLX, otro puerto
  (8991), modelo `Qwen3-4B-Instruct-2507-4bit` (~2.3GB) — para roles chicos sin necesidad de la
  capacidad completa (`history_compaction`, `conversation_title`, `dashboard_curator`, ya ruteados acá
  en `data/llm_routing.json`). Cumple el pedido explícito del fundador de "un modelo para tareas
  pesadas y otro más eficiente para tareas rápidas", con selección por rol ya existente en
  Configuración → LLM (`LLM_PRESETS` en `web/index.html`).
- **Dos LaunchAgents nuevos, mismo patrón que `com.snarf.server`** (ver CLAUDE.md): `com.snarf.mlx-heavy`
  (puerto 8990, Qwen3-8B) y `com.snarf.mlx-fast` (puerto 8991, Qwen3-4B) — `RunAtLoad`+`KeepAlive`,
  logs en `~/Library/Logs/snarf/mlx_{heavy,fast}.log`. Corren 24/7 para que el prefijo quede siempre
  cacheado y no se pague el costo de frío en cada sesión de uso real. Mismo gotcha de TCC que
  `com.snarf.server` (ver CLAUDE.md): `ProgramArguments` tiene que invocar `.venv/bin/python -m mlx_lm
  server ...` — invocar el script wrapper `.venv/bin/mlx_lm.server` directo falla con
  `PermissionError` leyendo `pyvenv.cfg` porque ese binario no tiene el mismo acceso TCC ya otorgado al
  intérprete real.
- **`orchestrator` se probó en `mlx_local`/`Qwen3-8B-4bit`, pero terminó revertido al fallback
  automático (`xai`/`grok-4-1-fast`) — ver "Decisión final" más abajo.** El intento inicial (con
  `LOCAL_TIMEOUT_SECONDS = 90`) disparó un fallback FALSO: la primera request real en frío tardó
  97.2s, un pelo por encima del timeout de 90s, así que `attempt_fallback` saltó a xAI y **persistió**
  ese cambio en `data/llm_routing.json` antes de que el prefijo llegara a cachearse. Se subió
  `LOCAL_TIMEOUT_SECONDS` de 90s a 150s para darle margen real al peor caso en frío medido, se volvió
  a rutear `orchestrator` a `mlx_local` (esta vez vía `PUT /llm-routing` real, que sí refresca
  `self._llm` en caliente sin reiniciar) y se reintentó.
- **Bug real corregido en el camino** (`snarf/capabilities/openai_compatible_llm.py`): el cliente
  `openai.OpenAI()` reintenta 2 veces por defecto (`max_retries=2`) ante un timeout — contra un
  proveedor local eso convertía el timeout corto en hasta el triple de tiempo real antes de disparar
  el fallback (confirmado viendo un segundo request idéntico en el log de `mlx_lm.server` tras el
  timeout del cliente). Ahora `local=True` fuerza `max_retries=0` — el propio mecanismo de fallback ya
  cumple ese rol, no hace falta que la SDK lo duplique en silencio.

## Decisión final: `orchestrator` NO queda pinneado al modelo local hoy

Con `LOCAL_TIMEOUT_SECONDS = 150` y el prefijo ya cacheado, tres requests reales consecutivas contra
producción dieron **17.9s, 33.6s y 163.6s** — la tercera volvió a superar el timeout (ahora más
generoso) y `attempt_fallback` revirtió `orchestrator` a `xai` **de nuevo**, solo, automáticamente.
En paralelo, `sysctl vm.swapusage` mostró el swap real subiendo de 6.57GB a **10.7GB** durante la
sesión (macOS incluso agrandó el archivo de swap de 8GB a 12GB) — evidencia de que la presión de
memoria real de esta Mac, con ambos LaunchAgents de MLX corriendo 24/7 más el uso normal del
fundador, sigue siendo suficiente para producir picos de latencia impredecibles, no solo el costo de
arranque en frío que se había identificado como causa dominante más temprano en esta misma ronda.

Conclusión honesta: el hallazgo del cache por prefijo es real y sigue siendo la explicación correcta
del caso típico/bueno (5.5-33.6s) — pero no elimina la variabilidad por presión de memoria real que
ya había documentado ADR 0117, solo la vuelve menos frecuente. Forzar `orchestrator` a quedarse en
local significaría aceptar que, de tanto en tanto, una respuesta tarde 2-3 minutos y el propio
mecanismo de fallback lo revierta solo sin aviso explícito — no es el comportamiento que el fundador
pidió originalmente ("eso no quiero que pase más", Punto 1 de la sesión de hoy). `orchestrator` se
deja en el estado real al que el fallback automático ya lo llevó (`xai`/`grok-4-1-fast`, funcionando)
en vez de volver a forzarlo a local por tercera vez.
- **Modelos sin uso borrados del cache de Hugging Face** (`Qwen3-14B-4bit`, `Qwen3-30B-A3B-Instruct-2507-4bit`
  — este último de la sesión anterior, nunca viable por el crash de memoria de ADR 0117): libera 25.52GB
  de disco.

## Cómo pausar/reanudar (para liberar memoria cuando el fundador necesite toda la Mac)

```
launchctl bootout gui/501/com.snarf.mlx-heavy      # apaga el pesado, libera ~7GB
launchctl bootout gui/501/com.snarf.mlx-fast       # apaga el rápido, libera ~2-3GB
launchctl bootstrap gui/501 ~/Library/LaunchAgents/com.snarf.mlx-heavy.plist   # reanuda
launchctl bootstrap gui/501 ~/Library/LaunchAgents/com.snarf.mlx-fast.plist
```

Mientras `mlx_local`/`mlx_local_fast` estén apagados, el fallback automático ya existente
(`is_provider_level_error`, error de conexión) hace que los roles ruteados ahí caigan solos a
Anthropic/xAI en vez de quedar mudos — no hace falta tocar `data/llm_routing.json` para pausarlos.

## Verificado

- 949/949 tests de la suite completa.
- Tool-calling real confirmado en ambos modelos (8B y 4B) contra las 88 tools reales de Snarf.
- Verificación end-to-end real contra producción (HTTPS/Tailscale, sesión autenticada real), dos
  rondas: primera ronda con timeout de 90s (falso fallback a los 97.2s, ver arriba); segunda ronda con
  timeout de 150s: 17.9s / 33.6s / 163.6s — la tercera volvió a disparar el fallback real.
- Memoria real medida con ambos servers activos + apps normales del fundador: el swap subió de
  6.57GB a 10.7GB durante la sesión (`sysctl vm.swapusage`) — señalado explícitamente al fundador, no
  ocultado, y es la base de la decisión final de no forzar `orchestrator` a local hoy.
- Los 3 roles chicos (`history_compaction`, `conversation_title`, `dashboard_curator`) SÍ quedan
  ruteados a `mlx_local_fast` de forma estable — sus prompts son mucho más chicos, sin el mismo riesgo
  de picos por prefill largo.

## Consecuencias

- `orchestrator` sigue dependiendo de un proveedor pago (`xai` tras el fallback automático, con
  Anthropic disponible de nuevo apenas se recargue crédito) — el objetivo de independencia total del
  fundador para el chat principal **no se logró hoy**, a diferencia de lo que la primera versión de
  este ADR concluía. Documentado con la evidencia real que motivó el cambio de conclusión (Principio
  VI de FOUNDATION.md: nunca presentar como resuelto algo que la propia medición en vivo contradijo).
- El modelo local pesado (`mlx_local`, Qwen3-8B) queda construido, probado y seleccionable a mano
  desde Configuración → LLM por rol — el fundador puede rutear `orchestrator` ahí cuando quiera
  experimentar o cuando la Mac tenga memoria libre sostenida, sabiendo que puede haber picos de
  2-3 minutos ocasionales.
- El rol rápido (`mlx_local_fast`) SÍ queda como ganancia neta real y estable: 3 roles corriendo en
  local sin costo de tokens, sin la misma variabilidad.
- Costo real aceptado mientras ambos LaunchAgents sigan activos: memoria residente 24/7 (~7GB pesado +
  ~2.5GB rápido) más el swap adicional que eso genera bajo uso normal — comando de pausa documentado
  arriba para cuando la Mac se necesite libre. Dado que `orchestrator` no depende del modelo pesado
  hoy, apagar `com.snarf.mlx-heavy` y dejar solo `com.snarf.mlx-fast` corriendo es una opción válida
  para reducir esa carga sin perder la ganancia real de los 3 roles chicos.
- Punto 6 del plan original (Claude Code usando este mismo modelo local) sigue sin intentar — no fue
  parte del pedido de esta ronda.
