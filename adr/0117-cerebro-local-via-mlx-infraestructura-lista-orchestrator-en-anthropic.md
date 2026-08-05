# ADR 0117 — Cerebro local vía MLX: infraestructura construida y probada, `orchestrator` se queda en Anthropic

**Fecha:** 2026-08-05
**Estado:** Aceptado (con reversión documentada — ver Consecuencias)

## Contexto

El fundador pidió migrar el rol `orchestrator` (el cerebro conversacional principal de Snarf) a un
modelo de lenguaje local, para dejar de depender de tokens pagos y límites de contexto de Anthropic —
decisión explícita, con el riesgo de calidad/velocidad explicado y aceptado de antemano. Pedido
explícito adicional: "el modelo más complejo que podamos correr y el más rápido para respuestas
cortas".

Hardware real de la Mac: Apple M2 Max, 32GB de memoria unificada — pero la memoria *realmente libre*
durante uso normal (navegador, IDE, el propio server de Snarf corriendo) resultó ser mucho menor que
el nominal, y variable en el tiempo. Esto se descubrió empíricamente en el camino, no de antemano.

## Decisión (infraestructura, permanente)

- `mlx-lm==0.31.3` instalado nativo en el `.venv` (nunca Docker/Colima — sin acceso a Metal/GPU ahí,
  correría solo por CPU, inutilizable).
- `snarf/capabilities/openai_compatible_llm.py`: soporta un proveedor `local=True` sin API key real
  (`_LOCAL_DUMMY_API_KEY`), y **`LOCAL_TIMEOUT_SECONDS = 90`** — el default de 10 minutos de la SDK de
  OpenAI es inaceptable contra un modelo local que puede volverse lento por presión de memoria del
  sistema (ver Verificado); con el timeout corto, `openai.APITimeoutError` (subclase real de
  `APIConnectionError`) dispara el fallback automático en vez de dejar el chat colgado.
- `snarf/runtime/llm_routing.py`: preset `mlx_local` (reusa `OpenAICompatibleLLM`, sin clase nueva),
  `MLX_LOCAL_BASE_URL`/`MLX_LOCAL_MODEL` configurables por env var. `is_provider_level_error()` ahora
  también trata errores de **conexión** (no solo status HTTP) como disparadores de fallback —
  reabre deliberadamente el alcance que la versión original de este mecanismo había dejado afuera a
  propósito, porque un proveedor local puede estar caído sin devolver ningún status HTTP.
- `web/index.html`: `mlx_local` seleccionable desde Configuración → LLM por rol, como cualquier otro
  proveedor.
- Modelo probado y validado con tool-calling real (formato `tool_calls` idéntico al esperado por
  `OpenAICompatibleLLM`, sin necesitar ningún código de traducción): `mlx-community/Qwen3-14B-4bit`
  (denso, ~8.3GB en disco).

## Decisión (routing en vivo, revertida tras medir)

Se probó primero `mlx-community/Qwen3-30B-A3B-Instruct-2507-4bit` (MoE, 30B totales/~3B activos por
token — elegido para dar más capacidad con velocidad de un modelo chico, siguiendo el pedido textual
del fundador). Contra el contexto real de Snarf (system prompt + **88 tools reales**, ~16.000
caracteres) crasheó con `RuntimeError: [METAL] Command buffer execution failed: Insufficient Memory`.

Se bajó a Qwen3-14B (denso, ~8.3GB). No crasheó, pero el mismo request pasó de **38.6s** (con ~15GB
libres) a **991s** (con ~7.5GB libres) según la memoria real disponible en el momento — confirmando
que el cuello de botella es memoria del sistema, no el modelo en sí. Verificado en vivo contra
producción real (server 8002, request autenticado real vía `/send`, disparando una búsqueda real en
Drive): **289.8 segundos** para una sola respuesta — muy por encima de cualquier umbral usable para
un chat interactivo, incluso después de que el fundador cerrara Chrome para liberar memoria.

**`orchestrator` se revierte a `anthropic`/`claude-sonnet-5`** — la prioridad del día (nunca más
respuestas que dejen al fundador esperando) pesa más que completar el pedido de cerebro local hoy.

## Verificado

- Tool-calling real contra `mlx_lm.server` (formato OpenAI, sin traducción necesaria).
- `tests/test_llm_routing.py`: preset `mlx_local`, disponibilidad sin credencial, `is_provider_level_error`
  ante `anthropic.APIConnectionError`/`openai.APIConnectionError`.
- `tests/test_openai_compatible_llm.py`: cliente local sin API key real, timeout corto vs. default de
  la SDK para proveedores cloud.
- 946/946 tests de la suite completa.
- Verificación end-to-end real contra producción (ver arriba) — la que motivó la reversión.

## Consecuencias

- El pedido del fundador de "cerebro local como rol principal" queda **sin cumplir hoy**, documentado
  con evidencia real (no una decisión arbitraria): esta Mac, en su estado real de uso normal, no tiene
  memoria libre suficiente y estable para sostenerlo a velocidad usable, ni siquiera con el modelo más
  chico probado.
- Toda la infraestructura queda lista y verificada para retomarlo sin trabajo de cero: alcanza con
  levantar `mlx_lm.server` y cambiar el routing del rol `orchestrator` desde la interfaz — candidatos
  para una sesión futura: más memoria libre disponible de forma sostenida (nada más corriendo), un
  modelo más chico todavía (7-8B) priorizando velocidad sobre capacidad, o hardware con más memoria.
- Punto 6 del plan de la sesión (que Claude Code pueda usar este mismo modelo local) queda **sin
  intentar** — no tiene sentido construir un shim de traducción Anthropic↔OpenAI para un backend que
  hoy no es utilizable de forma estable.
