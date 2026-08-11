# ADR 0142 — Fase 7: Configuración dinámica de generación

**Fecha:** 2026-08-11
**Estado:** Aceptado

## Contexto

`ROADMAP_OBSERVABILIDAD_MULTIUSUARIO_N8N.md` fija la Fase 7: *"Extiende el patrón de `llm_routing.py` a
`MAX_OUTPUT_TOKENS`, temperatura (hoy ni se pasa), timeout/retry por rol. Versionado igual que el Prompt
Registry."* Auditando el código real se confirmó: `MAX_OUTPUT_TOKENS = 16000` es una única constante en
`anthropic_llm.py`, reimportada por los otros dos proveedores — nunca configurable por rol.
`temperature` en efecto nunca se pasaba a ningún SDK. `LOCAL_TIMEOUT_SECONDS` solo aplicaba (fijo) a
proveedores locales. El único "retry" real que existe en el código, más allá del fallback entre
proveedores que ya cubre `attempt_fallback` (ADR de ronda anterior), es `MAX_CONTINUATIONS = 2`: cuántas
veces el loop de generación le pide al modelo continuar cuando corta por tope de tokens — esa es la
interpretación que se le dio a "retry" en esta ADR, documentada explícitamente por si no coincide con lo
que el fundador tenía en mente.

## Decisión

**`snarf/runtime/generation_config.py` (nuevo)** — mismo patrón exacto que `prompt_registry.py` (Fase
6): `data/generation_config.json`, clave = rol, versión activa + historial, `rollback()`. Diferencia
real con Prompt Registry: acá una edición puede ser PARCIAL (`{"temperature": 0.7}` sin tocar
`max_output_tokens`) — cada campo ausente en el override hereda el valor de la versión ACTIVA (nunca de
la última agregada, que puede diferir tras un rollback), nunca del último guardado a ciegas.

**Los 3 capabilities de LLM (`AnthropicLLM`/`OpenAICompatibleLLM`/`GeminiLLM`) ganan parámetros de
constructor** (`max_output_tokens`, `temperature`, más `timeout_seconds`/`max_continuations` donde
aplica — ver tabla abajo), todos con default = la constante hardcodeada de siempre. Cada punto interno
que antes usaba la constante del módulo directo (`MAX_OUTPUT_TOKENS`/`MAX_CONTINUATIONS`/
`LOCAL_TIMEOUT_SECONDS`) pasa a usar `self._max_output_tokens`/etc. — construir sin estos parámetros
(cualquier test existente, un consumidor externo futuro) se comporta exactamente igual que antes.

**Gotcha real encontrado corriendo la suite**: varios tests reales construyen estas clases con
`AnthropicLLM.__new__(AnthropicLLM)` (evita el `__init__` real — credenciales, cliente HTTP — para
setear a mano solo `_client`/`model`). Esas instancias quedaban sin los atributos nuevos → 53 tests
rotos con `AttributeError`. Fix: los tres nuevos atributos (`_max_output_tokens`/`_temperature`/
`_max_continuations`) son también atributos de CLASE con el mismo default — una instancia por `__new__`
los hereda del default de clase, una instancia normal los pisa con el valor real de `__init__`.

**`snarf/runtime/llm_routing.py::_build(provider, model, role)`** gana el parámetro `role` (los 5 call
sites internos, incluidos los 3 dentro de `_ResilientLLM`, ya tenían `role` en scope) y resuelve
`generation_config.get_active_config(role, default)` antes de construir la Capacidad — el `default` que
le pasa depende del proveedor (`timeout_seconds` solo tiene default real para proveedores locales, el
resto viene de las constantes ya conocidas de `anthropic_llm.py`/`openai_compatible_llm.py`).

## Campos reales por capability

| Campo | `AnthropicLLM` | `OpenAICompatibleLLM` | `GeminiLLM` |
|---|---|---|---|
| `max_output_tokens` | sí | sí | sí |
| `temperature` | sí | sí | sí |
| `timeout_seconds` | — (SDK sin override hoy) | sí, solo si `local=True` | — (SDK sin override hoy) |
| `max_continuations` | sí | sí | — (sin loop de continuación propio, ver abajo) |

`GeminiLLM` no tiene loop de continuación por longitud (a diferencia de Anthropic/OpenAI-compatible,
`MAX_TOOL_ROUNDS` cubre reintentos de tool-calling, no de longitud) ni timeout configurado — se dejaron
sin esos dos campos en vez de agregar código muerto que nunca se ejercita.

**Fuera de esta ADR, con motivo:** `max_retries=0` de `OpenAICompatibleLLM` (proveedores locales) es una
decisión de seguridad ya documentada en el propio código (evitar que la SDK duplique en silencio un
timeout ya largo) — no se expone como configurable por rol, sería reabrir ese riesgo real sin pedido
explícito. Ningún endpoint HTTP nuevo — mismo criterio que Prompt Registry (Fase 6): escribir desde
n8n/el cockpit del fundador es Fase 9.3, todavía sin construir.

## Verificado

- 7 tests nuevos en `tests/test_generation_config.py` (mismo esqueleto que `test_prompt_registry.py`,
  más uno específico de merge parcial: guardar solo `temperature` nunca resetea `max_output_tokens`).
- 1 test de wiring en `tests/test_llm_routing.py`: `build_llm(role)` con un override real guardado
  devuelve una Capacidad con `_max_output_tokens`/`_temperature` overrideados y `_max_continuations` en
  su default (campo no tocado por el override).
- Los 13 `fake_build(provider, model)` de `tests/test_llm_routing.py` actualizados a
  `fake_build(provider, model, role)` — firma nueva de `_build`.
- 1241/1241 tests de la suite completa (`.venv/bin/python -m pytest -q`), 1233 previos (post Fase 6) +
  8 nuevos.
