# ADR 0131 — El modelo local como motor suficiente para correr Snarf

**Fecha:** 2026-08-06
**Estado:** Aceptado

## Contexto

Pedido explícito del fundador: "no tengo crédito en Grok ni Anthropic APIs. Y necesito que el LLM
local sea suficiente para correr Snarf" — con instrucciones concretas de que solo el/los server(s)
MLX que Snarf usa de verdad deben correr (los de modelo intermedio/pesado, apagados), y de resolver
todo lo que se pueda desde este lado antes de evaluar un modelo distinto más adelante.

Investigación real en vivo, en esta misma Mac, antes de tocar nada:

1. **Recurrencia real del bug de ADR 0128**: `~/Library/Logs/snarf/mlx_fast.log` muestra un crash real
   de Metal (`Command buffer execution failed: Insufficient Memory`) a las 17:55 del mismo día, sobre
   un prompt de **82.284 tokens** — 4x el que motivó esa ADR — con la misma falla de limpieza
   posterior. El watchdog de memoria (ADR 0128) evitó que escalara a 31GB otra vez, pero no evitó el
   crash ni la degradación real alrededor del incidente. Origen exacto del prompt: sin identificar (no
   vino de un `POST /send` — el último real fue 45 minutos antes).
2. **11 de 25 roles + `drive_vision` fijados a mano a xAI/Anthropic**, ambos sin crédito real
   confirmado por el fundador — cada llamada fallaba, intentaba fallback, y perdía tiempo real.
3. **3 servers MLX corriendo 24/7** (`com.snarf.mlx-fast`/`mlx-heavy`/`mlx-mid`, los tres
   `RunAtLoad`+`KeepAlive`) pero ningún rol apuntaba a `mlx-heavy`/`mlx-mid` — RAM/CPU real
   consumida sin ningún uso real.
4. **Evidencia directa de contención de recursos**: la suite completa de tests, que normalmente tarda
   ~8-10s, tardó **247 segundos** durante esta misma sesión de trabajo.
5. `GROQ_API_KEY` (usada hoy solo para STT) SÍ tiene crédito real (confirmado con `client.models.list()`
   real) pero `RECOMMENDED_MODEL["groq_llama"]` apuntaba a `"llama-4-scout"`, un modelo que **ya no
   existe** en la API real de Groq (404 confirmado en vivo) — cualquier intento de fallback a este
   proveedor fallaba siempre, en silencio, desde antes de esta ronda.

## Decisión

**A. Ruteo reseteado a los defaults locales.** `llm_routing.save_routing({})` — los 11 roles atascados
en xAI vuelven a `mlx_local_fast` (el default real desde el 2026-08-05). `drive_vision` se queda en
Anthropic a propósito (no es un pin atascado: los modelos locales de hoy no tienen soporte real de
imágenes — sigue siendo la excepción documentada de siempre, se degrada solo cuando vuelva el crédito).
De paso, `RECOMMENDED_MODEL["groq_llama"]` corregido a `"llama-3.3-70b-versatile"` (confirmado real,
con precio real verificado por búsqueda web: $0.59/$0.79 el millón) — OJO documentado en el propio
código: el tier real de esta cuenta tiene un límite de 12.000 tokens/minuto, así que este proveedor
nunca es un fallback viable para el rol `orchestrator` (su prompt completo ya son ~16.000 tokens), pero
sí lo es para el resto de los roles (prompts propios mucho más chicos).

**B. Solo el server que se usa, corriendo.** `com.snarf.mlx-heavy`/`com.snarf.mlx-mid` — `launchctl
bootout` + `launchctl disable` (persiste across reboots sin tocar los `.plist`, reversible con
`enable`+`bootstrap` cuando el fundador quiera probar otro modelo). Solo `com.snarf.mlx-fast` (puerto
8991) sigue corriendo — el único que cualquier rol usa hoy.

**C. Tope universal de tamaño de prompt para proveedores locales**
(`snarf/capabilities/openai_compatible_llm.py::MAX_LOCAL_PROMPT_CHARS = 60000`,
`LocalPromptTooLargeError`): a diferencia del tope de ADR 0128 (acotado solo a `history_compaction`),
este corre para CUALQUIER rol ruteado a un proveedor local, re-chequeado en cada ronda del loop de
herramientas (no solo antes de empezar — un resultado de herramienta grande puede hacer crecer el
prompt a mitad de turno). Reconocida como fallback-worthy en `llm_routing.is_provider_level_error()`:
un prompt demasiado grande para el hardware local puede seguir siendo viable en un proveedor cloud con
más memoria.

**D. Trazabilidad real de qué rol dispara cada llamada.** `snarf/telemetry/context.py` suma
`set_llm_role`/`get_llm_role`/`clear_llm_role` (mismo patrón exacto que `conversation_id`, ADR 0079) —
seteado por `_ResilientLLM.generate()` y por los dos roles de instancia fija de `Orchestrator`
(`handle()`/`generate_conversation_title()`), leído por `events.py` y persistido como campo nuevo
`llm_role` en `telemetry_events.jsonl`. Motivo directo: el incidente del punto 1 de esta misma ronda no
se pudo diagnosticar del todo porque no había forma de saber, mirando los logs después, qué rol lo
generó — la próxima vez que algo así pase, va a estar.

## Deliberadamente NO resuelto en esta ronda

- **Fuente exacta del prompt de 82.284 tokens** de hoy — el tope universal (C) lo vuelve
  estructuralmente imposible de repetir, pero la causa puntual (qué rol/flujo lo generó) queda sin
  identificar; el campo `llm_role` nuevo (D) es la herramienta para encontrarla la próxima vez.
- **Interfaz de Mac para visualizar/gestionar los servers y procesos Python locales** — idea real que
  planteó el fundador ("quizás lo oportuno sea..."), pero es un proyecto propio y separado (una
  superficie nueva, no una optimización de lo que ya existe) — queda anotada para una conversación de
  scoping aparte, no construida acá.
- **Evaluar un modelo local distinto** (Qwen3.5-9B/`mlx_local_mid` u otro) — explícitamente pospuesto
  por el fundador hasta que el resto (A-D) esté resuelto y la única palanca real que quede sea la
  calidad/eficiencia del modelo en sí.
- **Separar el rol `orchestrator` de los roles de background en servers MLX distintos** (para que una
  curación de dashboard en background nunca compita con el chat interactivo) — evaluado y descartado
  para esta ronda: contradice directamente el pedido explícito del fundador de "solo los servers que
  usamos deben usarse" (correría un segundo server 24/7 para lograrlo). Queda como opción real si la
  contención entre roles vuelve a ser un problema medible con un solo server.

## Verificado

- 13 tests nuevos: `tests/test_context.py` (3), `tests/test_openai_compatible_llm.py` (4, incluida la
  regresión directa del incidente de 82.284 tokens y el re-chequeo por ronda), `tests/test_llm_routing.py`
  (2), `tests/test_telemetry_events.py` (2), `tests/test_orchestrator.py` (2).
- 1058/1058 tests de la suite completa — corrida en **10.13s**, contra **247s** antes de apagar
  `mlx-heavy`/`mlx-mid` en esta misma sesión — evidencia real y medida (no una promesa) de que la
  contención de recursos por los dos servers sin uso era real.
- `ps aux`/`launchctl list` confirmaron en vivo: solo `com.snarf.mlx-fast` corriendo tras B; `data/
  llm_routing.json` confirmado con los 25 roles en `mlx_local_fast` salvo `drive_vision` tras A.

## Consecuencias

- Snarf queda operable de punta a punta sin depender de crédito de Anthropic/xAI — el modelo local es
  ahora el motor real y único de casi todos los roles, con las salvaguardas nuevas (C) para que no
  vuelva a tumbar el server que los sirve a todos.
- Menos RAM/CPU consumida 24/7 (un solo server MLX en vez de tres) — beneficio medible más allá de la
  confiabilidad, confirmado con el tiempo real de la suite de tests.
- El campo `llm_role` queda como precedente: cualquier instrumentación futura de "qué rol hizo esto"
  ya tiene un lugar real donde vivir, sin inventar un mecanismo nuevo cada vez.
