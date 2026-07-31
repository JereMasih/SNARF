# ADR 0071 — Fix: `.warmup()` faltante en las Capacidades LLM no-Anthropic

**Fecha:** 2026-07-30
**Estado:** Aceptado

## Contexto

El fundador ruteó el rol `orchestrator` a xAI Grok manualmente desde el selector construido en el ADR 0068. `Orchestrator.warmup()` (llamado una única vez al arrancar el proceso, desde `app.py`) hace `self._llm.warmup()` sin chequear qué Capacidad tiene detrás — `AnthropicLLM` la implementa desde siempre, pero `OpenAICompatibleLLM` y `GeminiLLM` (ADR 0068) nunca la tuvieron. Cualquier rol ruteado a un proveedor no-Anthropic hacía crashear el arranque del servidor con `AttributeError`.

No se manifestó de inmediato porque `refresh_llm_routing()` (ADR 0070) reconstruye `self._llm` al guardar un cambio de ruteo, pero no vuelve a llamar `warmup()` — el bug es latente hasta el próximo reinicio real del proceso.

## Decisión

Se agrega `.warmup()` a `OpenAICompatibleLLM` y `GeminiLLM`, mismo criterio que `AnthropicLLM.warmup()`: una llamada real mínima (`max_tokens=1`), con cualquier excepción silenciada — el arranque nunca debe fallar por esto, es solo para dejar la conexión/cliente "tibio".

## Verificado

- 529/529 tests. Se encontró de paso un test de `test_llm_routing.py` (`test_build_llm_defaults_to_anthropic_for_every_role`) que no aislaba `ROUTING_PATH` — leía el archivo real en disco, y fallaba apenas ese archivo reflejó una elección real distinta del default. Se corrige aislándolo con `tmp_path`, mismo patrón que el resto de los tests del módulo.

## Consecuencias

- Rutear cualquier rol a cualquier proveedor disponible ya no puede crashear el arranque del servidor, sin importar qué se haya guardado en `data/llm_routing.json`.

## Adenda — timeout real de Kokoro TTS

El fundador reportó voz fallando en producción. El log real mostró un `ConnectionError: Read timed out` contra el contenedor Kokoro (detrás de un túnel SSH en :8880) al sintetizar — la síntesis en caliente mide ~2-3s, consistente con un cold-start del contenedor tras estar inactivo superando el timeout de 30s. Se sube a 60s en `KokoroTTS.speak()`. Verificado con 5 llamadas reales seguidas post-fix, todas OK (~3s cada una).
