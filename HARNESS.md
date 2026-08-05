# HARNESS

## Qué gobierna la ejecución entre el Orchestrator y una Capacidad/Especialista

**Versión:** 0.1
**Naturaleza:** describe el funcionamiento real implementado a la fecha, no una aspiración — mismo criterio que COGNITION.md/KNOWLEDGE.md. La mayor parte de lo que este documento nombra ya existía antes de escribirse, repartido sin un nombre común; este documento no agrega un mecanismo nuevo salvo donde dice explícitamente "nuevo en esta ronda".

---

# Por qué existe este documento

El plan original de esta expansión pedía un Harness con inyección de contexto por skill, validación/tests automáticos por llamada, comparación entre modelos y reintento ante falla de calidad. Revisando el código real antes de construir nada nuevo, casi todo eso ya existe — solo nunca tuvo un nombre que lo agrupara como una sola capa. Este documento es sobre todo un ejercicio de nombrar, no de construir: mapea cada función pedida a su mecanismo real, y solo suma código nuevo donde de verdad faltaba algo (`compare()`, ver abajo).

# El ciclo de vida real de una llamada a herramienta

`Orchestrator._handle_tool()` (`snarf/core/orchestrator.py`) es el punto único de despacho — cada llamada, sin excepción, pasa por acá antes de tocar una Capacidad o Especialista real:

1. **Inyección de contexto.** No es un paso separado del Harness — es literalmente la Knowledge Layer (ver `KNOWLEDGE.md`): un Specialist que necesita contexto real llama a `knowledge_search`/`codebase_search` como cualquier otro tool, nunca abre un archivo directo.
2. **Confirmación de alto impacto** (`_pending()`/`confirmed`, ADR 0015): toda acción irreversible o con exposición externa real (`gmail_send_message`, `drive_delete_file`, etc. — ver `HIGH_IMPACT_TOOLS` en `orchestrator.py`) se ejecuta en dos pasos, nunca en el mismo turno sin un "sí" explícito del fundador.
3. **Confirmación de lectura masiva costosa** (`_bulk_read_gate()`, ADR 0067): un pedido de más de 50 resultados (`BULK_READ_GATED_TOOLS`) avisa el costo real antes de traer todo, mismo mecanismo de dos pasos que el punto anterior, por un motivo distinto (costo, no irreversibilidad).
4. **Trazabilidad.** Cada despacho real queda registrado en `activity_log.jsonl` (qué tool, qué input, qué resultado), `usage_log.jsonl` (costo real por vendor, ver `usage_tracker.py`), `input_log.jsonl` (canal de entrada) y `telemetry_events.jsonl` (evento unificado, ver `TELEMETRY_SCHEMA.md`) — nunca inventado, siempre lo que de verdad pasó.
5. **Alerta de costo** (`relevance.cost_alert()`, ADR 0081): el dashboard señala un gasto real fuera de lo esperado a partir de `usage_log.jsonl`, nunca una proyección inventada.
6. **Reintento ante una respuesta sin llegar a destino.** `AnthropicLLM.generate()` (`snarf/capabilities/anthropic_llm.py`, líneas 210-243), al agotar `MAX_TOOL_ROUNDS` sin una respuesta final, fuerza una última llamada sin `tools` para que el modelo sintetice en prosa lo ya reunido en vez de perder el turno entero — reintento real, ya existente, no algo nuevo de esta ronda.
7. **Ruteo de modelo por rol, multi-proveedor** (`snarf/runtime/llm_routing.py`, ADR 0068): cada rol (`orchestrator`, `gmail_digest`, `dashboard_curator`, los 7 roles de Inteligencia Ejecutiva, etc.) resuelve su Capacidad de LLM real vía configuración persistida, nunca hardcodeada — el fundador puede cambiar de proveedor por rol desde la interfaz sin tocar código. Este mismo módulo es, a la fecha, donde vive el trabajo real (en curso, ver `llm_routing.py` directamente — todavía sin ADR propia al momento de escribir esto) de reintentar automáticamente con otro proveedor ante un fallo real del proveedor configurado (crédito agotado, rate limit, 5xx) — la pieza de "reintento ante falla de calidad" que el plan original pedía, resuelta por necesidad real del fundador, no por anticipación.

# Qué NO se construye en esta ronda, y por qué

El plan original pedía además validación/tests automáticos por skill y una selección automática de "ganador" entre proveedores. Deliberadamente no se construye ninguna de las dos ahora: no hay todavía un caso de falla real y concreto contra el cual diseñar esa validación (los consumidores serían 2-3 Skills reales de la Fase I, que a la fecha de este documento todavía no existen), y una selección automática de ganador necesita un criterio de calidad real y probado, no uno inventado para llenar el hueco. Construir la versión compleja sin kilometraje real de la simple es la misma anticipación que varias ADRs de este repo ya se prohibieron a sí mismas — queda nombrado en Roadmaps, a revisar cuando la Fase I tenga uso real.

# `compare()` — lo único genuinamente nuevo de esta ronda

`snarf/runtime/harness.py::compare(role, system, messages, providers=None)` corre el mismo prompt contra N proveedores reales de `llm_routing.PROVIDER_PRESETS` y devuelve las N respuestas reales, una por proveedor, para inspección manual del fundador — sin juez-LLM automático, sin selección de ganador automática. `providers=None` corre contra todos los que tengan credencial real cargada (`llm_routing.available_providers()`). Un proveedor sin credencial o que falla real se refleja como tal en su propia entrada, nunca oculta el resultado de los demás.
