# ADR 0130 — Skill Factory: motor de escritura local, en vez del CLI de Claude Code

**Fecha:** 2026-08-06
**Estado:** Aceptado

## Contexto

Pedido explícito del fundador: quiere que la Skill Factory (ADR 0095/0102) pueda construir skills
usando el modelo local de su Mac, después de un intento real que falló por falta de crédito en la
API de Anthropic (`snarf/capabilities/claude_code.py::ClaudeCode` invocaba el CLI real `claude -p
...`, que factura contra esa API salvo que el CLI esté logueado con una suscripción).

Investigado en vivo antes de tocar código (`claude --help`, versión 2.1.220 real instalada en la
máquina del fundador): el CLI de Claude Code **no tiene ninguna forma soportada de apuntar a un
modelo no-Claude**. `--model` solo acepta alias (`sonnet`/`opus`/`fable`) o nombres reales de
modelos Claude; los únicos "otros backends" documentados son Bedrock/Vertex/Foundry, que siguen
sirviendo modelos Claude reales (solo cambia la nube de facturación, nunca el modelo). No existe una
variable tipo `ANTHROPIC_BASE_URL` genérica para redirigirlo a un server MLX propio. Conclusión
honesta, presentada al fundador antes de construir nada: "hacer que Claude Code use el modelo local"
no es una opción real — la única forma de que la Skill Factory corra 100% local es reemplazar el
motor de escritura de código por uno nuevo, propio, que hable directo con el modelo local.

El fundador eligió ese camino explícitamente, con la advertencia server real de que un modelo local
(ya demostrado en esta misma jornada: inventó un `message_id` de Gmail inexistente y una tool que no
existía, ver ADR 0129) es notablemente menos confiable que Claude para escribir código real — pidió
proceder de todas formas.

## Decisión

1. **`snarf/capabilities/local_code_writer.py::LocalCodeWriter`** reemplaza a `ClaudeCode` (eliminado
   junto con `tests/test_claude_code.py`) — mismo shape de resultado
   (`ok`/`result_text`/`session_id`/`cost_usd`/`num_turns`/`raw`), así que
   `SkillFactorySpecialist.build_skill()` casi no cambió: sigue haciendo su propia verificación
   independiente (diff de git contra el alcance esperado + su propia corrida de la suite completa)
   después, sin importar qué motor escribió el código — esa doble verificación **no se relaja ni un
   poco** por el cambio de motor; es, si acaso, más importante ahora.
2. **Loop de herramientas deliberadamente angosto**, no una sesión agéntica de propósito general:
   `read_file` (cualquier path, solo lectura), `write_file` (restringido a los archivos NUEVOS
   calculados por `SkillFactorySpecialist` antes de invocar — el módulo del Specialist, su test),
   `edit_file` (restringido a los 4 archivos de wiring ya existentes — reemplazo de un
   `old_string` exacto y único, misma semántica segura que la tool Edit real: nunca reescribe un
   archivo entero a ciegas), `run_tests` (corre la suite real). El alcance que antes solo se
   verificaba DESPUÉS por diff de git ahora también se gatea EN EL MOMENTO — defensa en
   profundidad, no un reemplazo del chequeo posterior.
3. **`ok` nunca confía solo en lo que el modelo dice de sí mismo**: requiere que el texto final
   contenga `LISTO` (y no `NO PUDE`) *y* que `run_tests` se haya invocado al menos una vez de
   verdad — un modelo local afirmando éxito sin haber corrido nunca los tests no cuenta.
4. **Presupuesto de rondas de herramientas separado del chat interactivo**: `MAX_TOOL_ROUNDS=5`
   (`openai_compatible_llm.py`, también `anthropic_llm.py`/`gemini_llm.py` por paridad de interfaz)
   es el número correcto cuando la latencia real importa (una conversación en vivo) — una
   construcción de skill corre en background tras una confirmación explícita, sin esa restricción.
   `generate()` de las 3 Capacidades de LLM ahora acepta `max_tool_rounds` como parámetro opcional
   (default = la constante de siempre, mismo comportamiento para todo el resto del repo);
   `LocalCodeWriter` pasa `MAX_BUILD_TOOL_ROUNDS = 40`.
5. **Rol nuevo `skill_factory_writer` en `llm_routing.ROLES`** — default `mlx_local_fast`, mismo
   criterio que el resto de los roles (decisión del fundador del 2026-08-05: modelo rápido local
   como default en todo, elegible aparte desde Configuración). Si la calidad no alcanza para código
   real, el fundador puede subir a `mlx_local`/`mlx_local_mid` (más capaces, más lentos) sin tocar
   código ni reiniciar el server.
6. **Manifest de `data/skill_proposals/` renombrado** de `claude_code_session_id`/
   `claude_code_cost_usd` a `code_writer_session_id`/`code_writer_cost_usd` — siempre `None` con el
   motor local (no hay sesión de cuenta ni costo real de API que trackear), nunca un valor
   inventado.

## Alcance de autoridad — sin cambios respecto de ADR 0095

Esta ADR reemplaza el motor de escritura, no el modelo de autoridad: las dos confirmaciones
explícitas (construir, activar), el alcance nombrado y estrecho (nunca FOUNDATION/CONSTITUTION/
CHARACTER/COGNITION/MASTER_MAP), la verificación de diff, la suite completa obligatoria y el
registro de auditoría en `data/skill_proposals/` siguen exactamente como los fijó ADR 0095. Nada de
esto necesitó reabrirse.

## Deliberadamente NO resuelto en esta ronda

- No se intentó ni se investigó ningún proxy/shim que traduzca el protocolo de la API de Anthropic
  al formato OpenAI-compatible del server MLX local para que el CLI de Claude Code lo use vía
  `ANTHROPIC_BASE_URL` — el fundador ya eligió el camino de reemplazar el motor entero antes de que
  esa alternativa se evaluara a fondo; queda registrada acá como la opción no tomada, no como
  pendiente.

## Verificado

- 17 tests nuevos: `tests/test_local_code_writer.py` (gateo de paths de escritura/edición, semántica
  de `edit_file` con `old_string` no encontrado/no único, determinación honesta de `ok`, presupuesto
  de rondas real). Más ajustes en `tests/test_skill_factory.py` (fake reemplazado, 1 test nuevo de
  paths permitidos) y `tests/test_skill_proposals_endpoint.py`.
- 1045/1045 tests de la suite completa.

## Consecuencias

- La Skill Factory ya no depende de crédito real de la API de Anthropic ni de que el CLI de Claude
  Code esté instalado/logueado — corre enteramente contra el modelo local del fundador.
- Tasa de éxito esperada notablemente menor que con Claude Code real (motivo documentado arriba,
  evidencia real de esta misma jornada) — mitigado, no eliminado, por la verificación independiente
  de `build_skill()` (nunca activa nada que no pase la suite completa) y por el gateo de paths en el
  momento (nunca escribe fuera de alcance, ni siquiera transitoriamente).
