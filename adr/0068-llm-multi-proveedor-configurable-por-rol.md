# ADR 0068 — LLM multi-proveedor, configurable por rol

**Fecha:** 2026-07-30
**Estado:** Aceptado

## Contexto

Como continuación del protocolo de costos (ADR 0067), el fundador preguntó por qué el loop principal de Snarf usa Sonnet 5 y pidió explorar alternativas más baratas — inicialmente Gemini, luego explícitamente ampliado a "todos los proveedores" (Grok, Llama, ChatGPT), con el objetivo de poder "decidir qué modelo usar en cada cosa que necesitemos" sin quedar atado a Anthropic.

Investigación real con búsqueda web (no estimada, precios de julio 2026):

| Proveedor | Nivel "inteligente" | Nivel barato |
|---|---|---|
| Anthropic | Sonnet 5: $2-3 / $10-15 | Haiku 4.5: $1 / $5 |
| Gemini | 3 Pro: $2.00 / $12.00 | 2.5 Flash-Lite: $0.10 / $0.40 |
| OpenAI | GPT-5: $0.625 / $5.00 | — |
| xAI Grok | 4.5: $2 / $6 | 4.1 Fast: $0.20 / $0.50 |
| Llama (open-weight) | — | Maverick: $0.20/$0.60, Scout: $0.08/$0.30 |

**Hallazgo clave, corrigiendo la premisa inicial del fundador**: ningún proveedor investigado ofrece hoy "tan inteligente como Sonnet" y "notablemente más barato" a la vez — el nivel Gemini Pro cuesta prácticamente lo mismo que Sonnet. El "25x más barato" real (Flash-Lite/Grok Fast/Llama) es clase Haiku, no un reemplazo de Sonnet en calidad. Con esto sobre la mesa, el fundador pidió igual construir el soporte multi-proveedor real, para poder decidir y ajustar según necesidad (no una decisión de una sola vez).

## Decisión

**Un solo rol, una sola interfaz — `LLMResponse`/`generate(system, messages, tools, tool_handler)`**, ya establecida por `AnthropicLLM`. Investigado que xAI y Llama (vía Groq/Together/Fireworks) comparten el mismo formato de tool-calling compatible con OpenAI (Chat Completions clásica, no la Responses API propietaria) — **una sola clase nueva cubre los tres**, solo cambia `base_url`/`api_key_env`/`model`:

- **`snarf/capabilities/openai_compatible_llm.py`** (nuevo): cubre OpenAI, xAI (`base_url=https://api.x.ai/v1`) y Llama vía Groq (`base_url=https://api.groq.com/openai/v1`, reusa el mismo `GROQ_API_KEY` que ya existía para STT). Verificado campo por campo contra el SDK `openai` real instalado (no asumido): `OpenAI(api_key=, base_url=)`, `chat.completions.create(messages=, model=, max_tokens=, tools=)`, `response.choices[0].message.tool_calls[].function.{name,arguments}`, `response.usage.{prompt_tokens,completion_tokens}`.
- **`snarf/capabilities/gemini_llm.py`** (nuevo): SDK `google-genai`. Verificado campo por campo contra el paquete real instalado: `genai.Client(api_key=)`, `client.models.generate_content(model=, contents=, config=)`, `types.FunctionDeclaration(parameters_json_schema=...)` (acepta el JSON schema tal cual, sin traducir a la clase `Schema` propia), `candidate.content.parts[].function_call`, `usage_metadata.{prompt_token_count,candidates_token_count}`.
- **`snarf/runtime/llm_routing.py`** (nuevo, mismo patrón que `personality_prefs.py`): persiste en `data/llm_routing.json` qué `{provider, model}` usa cada rol real del sistema (`orchestrator`, `gmail_digest`, `drive_vision`, `project_summary`, `conversation_title`). **Default = exactamente el comportamiento de siempre** (los 5 en Anthropic, mismos modelos que ya usaban) — cero cambio hasta que el fundador elija otra cosa. `build_llm(role)` resuelve proveedor→Capacidad; `Orchestrator.__init__` y los Especialistas ahora piden su LLM por acá en vez de instanciar `AnthropicLLM(...)` a mano.
- **`GET`/`PUT /llm-routing`** + selector nuevo en configuración ("LLM por rol"): 5 combos con presets legibles (`Anthropic — Sonnet 5`, `Gemini — 2.5 Flash-Lite (barato)`, etc.), deshabilitados con la nota "sin credencial" cuando el proveedor todavía no tiene una API key real cargada — nunca se ofrece elegir algo que en la práctica no va a andar.
- **Costo real de los proveedores nuevos** registrado igual que Anthropic: `pricing.py` suma tablas de tarifas reales (misma fuente/fecha de verificación que el resto del archivo) y `usage_tracker.record_generic_llm_call()` — el dashboard de costos ya agrega por `vendor` genéricamente, sin cambios ahí.

## Verificado

- 529/529 tests (10 de `llm_routing`, 9 de `openai_compatible_llm`, 8 de `gemini_llm` con objetos REALES del SDK instalado — no mocks livianos —, 3 de `pricing`/`usage_tracker`, 3 de los endpoints REST).
- Playwright: los 5 roles se renderizan con su default (= comportamiento actual sin ninguna credencial nueva), Gemini/OpenAI/xAI aparecen deshabilitados con "sin credencial" (ninguna de las 3 claves nuevas está cargada todavía), cambiar un rol persiste y sobrevive un reload real.
- Los campos exactos de ambos SDKs nuevos (`openai`, `google-genai`) se verificaron por introspección directa contra los paquetes reales instalados (`inspect.signature`, `model_fields`) — no se asumió ninguna forma de memoria.

## Consecuencias

- **Honestidad sobre lo que falta**: no hay ninguna de las 3 credenciales nuevas (`GEMINI_API_KEY`, `OPENAI_API_KEY`, `XAI_API_KEY`) cargada todavía — ningún adaptador nuevo se probó con una llamada real de punta a punta. La traducción de formatos está verificada contra la documentación real de cada SDK instalado, pero falta el smoke-test real de cada proveedor apenas el fundador cargue la credencial correspondiente, mismo criterio que se aplicó con Groq/ElevenLabs en su momento.
- Detectado y corregido durante esta misma ronda: un test propio (`test_save_routing_ignores_a_role_that_does_not_exist`) escribía sin querer en `data/llm_routing.json` real por no aislar `ROUTING_PATH` — corregido antes de commitear, sin dejar el archivo contaminando producción.
- El selector de la interfaz ofrece un set curado de presets (no texto libre) — si en el futuro aparece un modelo nuevo de alguno de estos proveedores, sumarlo a `LLM_PRESETS` en el frontend es una línea, no requiere tocar el backend.
