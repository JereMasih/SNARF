# ADR 0019 — Auditoría técnica completa y base de calidad (tests, CI, dependencias fijadas)

**Fecha:** 2026-07-27
**Estado:** Aceptado

## Contexto

El fundador pidió asumir un rol de Arquitecto Principal y auditar el sistema completo (estructura, dependencias, flujos, bugs conocidos) antes de construir observabilidad, dashboards o cualquier visualización nueva. El pedido original imaginaba, en fases posteriores, un dashboard en tiempo real con paneles de Trading, Mercado, GitHub y MCP, y una visualización tipo "Jarvis brain" con nodos iluminándose por el flujo real del sistema.

La auditoría (`ARCHITECTURE_AUDIT.md`, 22 secciones, cada hallazgo anclado a archivo y línea) encontró un código base pequeño y limpio — sin dependencias circulares, sin imports innecesarios, sin duplicación accidental de alcance amplio — pero con cero madurez operacional: sin un solo test automatizado, sin CI, sin versiones de dependencias fijadas, sin logging estructurado. También encontró que ninguno de los subsistemas que las fases de dashboard/Jarvis brain asumían como existentes (base de datos, MCP, múltiples agentes, trading, integración con GitHub) está construido hoy.

## Decisión

Se decidió, con el fundador, no avanzar a observabilidad ni visualización todavía, y en cambio cerrar primero la deuda de base identificada como la de mayor apalancamiento en la sección 21 del audit:

1. **Dependencias fijadas**: `requirements.txt` pasó de no tener ninguna versión especificada a tener cada paquete pineado a la versión exacta ya instalada y verificada en el entorno de desarrollo. Nuevo `requirements-dev.txt` (`-r requirements.txt` + `pytest`, `httpx`) para no mezclar dependencias de test con las de producción.
2. **Primera suite de tests automatizados** (`tests/`, 27 tests con `pytest`):
   - `test_episodic_memory.py`: cubre `append`/`recent`/`list_conversations`/`get_conversation`/`search`, incluyendo un test que documenta explícitamente el comportamiento real (no necesariamente deseado) de que `recent()` sin `conversation_id` mezcla memoria de todas las conversaciones — el mismo hallazgo de la sección 8 del audit.
   - `test_orchestrator.py`: cubre el modo eco, el dispatch de herramientas desconocidas/con excepción, y — el test de mayor valor de todo el conjunto — que las 8 herramientas de alto impacto (Artículo VII) nunca ejecutan la acción real sin `confirmed=true`, verificado una por una vía parametrización, no de forma genérica.
   - `test_app.py`: smoke test de los 7 endpoints de `app.py` con `TestClient` de FastAPI, sin depender de credenciales reales y sin escribir en `data/episodic_memory.jsonl` real (memoria redirigida a un archivo temporal antes de cada test).
   - Todos los tests corren con las credenciales de Anthropic/ElevenLabs eliminadas del entorno antes de cada uno (`tests/conftest.py`), para que la suite nunca pueda disparar una llamada de red real ni gastar cuota de API, incluso si el `.env` real del proyecto tiene claves válidas.
3. **CI** (`.github/workflows/tests.yml`): corre la suite completa en cada `push` a `main`/`master` y en cada pull request.
4. **No se tocó ningún bug todavía.** El audit ya identificó, con evidencia de código y sin asumir nada, la causa más probable de los tres bugs reportados por el fundador (respuestas cortadas por `max_tokens=1024` fijo sin chequear `stop_reason`; push-to-talk de iPhone por un `MediaStream` cacheado indefinidamente sin revalidar; botón de enviar cortado en mobile por `min-height: 100vh` conviviendo con `height: 100dvh`). Corregirlos queda para la siguiente fase de trabajo, ya con la red de tests como respaldo.

## Consecuencias

- Cualquier cambio futuro al `Orchestrator`, a la memoria episódica o a los endpoints de `app.py` corre ahora contra una suite real, no solo contra el juicio de quien lo escribe. En particular, el protocolo de confirmación de dos pasos (el control de seguridad más importante del sistema, según la sección 20 del audit) ya no depende únicamente de leer el código para confirmar que sigue intacto.
- `requirements-dev.txt` es nuevo y debe mantenerse sincronizado si se agregan más herramientas de test a futuro.
- El dashboard, la visualización tipo Jarvis brain, y cualquier observabilidad en tiempo real quedan explícitamente pospuestos hasta que (a) exista contenido real que mostrar más allá del flujo único LLM+herramientas+memoria de hoy, y (b) se decida, junto con el fundador, cómo calibrar el alcance de esas fases a lo que el sistema realmente tiene construido — evitando así la "arquitectura astronauta" que el propio proyecto ya se prohíbe en `MASTER_MAP.md`.
