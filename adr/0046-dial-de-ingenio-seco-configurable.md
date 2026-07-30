# ADR 0046 — Dial de "Ingenio seco"/sarcasmo configurable

**Fecha:** 2026-07-29
**Estado:** Aceptado

## Contexto

El fundador pidió más presencia de humor/sarcasmo en el trato cotidiano de Snarf, manteniendo intacto el criterio ya vigente de seriedad firme ante crisis o carga psicológica real. CHARACTER.md v0.2 (ADR 0039) ya declaraba **"Ingenio seco"** como uno de los "Rasgos permanentes" — sutil, discreto y fijo, sin ningún dial. El fundador pidió tres cosas concretas: (1) una escala 0-10 configurable, con medio punto de precisión, controlable desde configuración; (2) un default de **7.5** — a diferencia de toda otra preferencia de este repo, acá "sin configurar" es una intensificación deliberada, no "igual que antes"; (3) poder pedirlo directamente por mensaje en la conversación ("subime/bajame el sarcasmo").

Sobre el comportamiento durante una crisis: se confirmó con el fundador que el damping es **puro criterio del modelo, sin tocar el número guardado** — más robusto que mutar y restaurar el valor real (que podría quedar "pegado" abajo si una conversación corta abrupto a mitad de una crisis, o competir entre dispositivos/sesiones).

La tensión real a resolver: la sección de CHARACTER.md se llama "Rasgos **permanentes**", y "Consistencia entre canales" exige que se mantengan idénticos en todo canal — ¿cómo se vuelve configurable un rasgo permanente? Resuelto con el mismo precedente que el propio documento ya usaba: "Registro y cercanía" ya permite que la formalidad varíe situacionalmente sin violar "permanencia", porque lo permanente es el *principio*, no un valor fijo de superficie.

## Decisión

### 1. `CHARACTER.md` v0.2 → v0.3

El bullet "Ingenio seco" declara ahora explícitamente el eje configurable, con los invariantes intactos: nunca a costa de la utilidad/honestidad, siempre con propósito, y — no negociable en ningún nivel — nunca reemplaza la seriedad ante una decisión crítica, un riesgo de alto impacto (Artículo VII de Constitution) o una corrección importante.

### 2. `snarf/runtime/personality_prefs.py` (nuevo módulo)

Mismo patrón defensivo que `dashboard_prefs.py`: un JSON por usuario en `data/personality_prefs/{user_id}.json`, `sarcasm_level` numérico 0-10 en pasos de 0.5, default **7.5**. Guarda contra el mismo gotcha ya documentado (`bool` es subclase de `int` en Python) y contra valores fuera de rango o no numéricos, cayendo siempre al default.

No se reutilizó `dashboard_prefs.py`: un nivel de personalidad es una preferencia global del usuario, no una preferencia de layout de dashboard.

### 3. Inyección por turno — `snarf/core/orchestrator.py`

`sarcasm_instruction(level)` mapea el nivel a una instrucción de intensidad (cadena vacía en 0), incluyendo siempre el recordatorio de la excepción crítica. `Orchestrator.handle()` relee `personality_prefs.load_prefs(self._user_id)` **en cada turno** — a diferencia de `self._identity` (cacheado una vez en `__init__`, solo cambia si se edita un archivo y se reinicia el server), este valor puede cambiar a mitad de una conversación desde configuración o desde la tool nueva, y debe reflejarse sin reiniciar Snarf.

### 4. Ajuste conversacional — tool `personality_set_sarcasm`

Nueva tool de bajo impacto (no pasa por el gate `_pending()` — reversible al instante, no toca datos de terceros ni archivos, mismo criterio que `add_task`/`add_note`) que persiste el nivel pedido. Distinta del damping en crisis: esto SÍ persiste, porque es un cambio de configuración explícito y deliberado del fundador.

### 5. REST + frontend

`GET`/`PUT /personality/preferences`, mismo patrón que `/dashboard/preferences`. Primer control deslizante (`<input type="range">`) de esta UI, en una sección nueva "Personalidad" del panel de configuración — slider 0-10 (paso 0.5) con lectura numérica en vivo, etiquetas en los extremos ("Sobrio"/"Filoso").

### 6. Cerebro

`snarf/telemetry/brain.py` suma un nodo de Capacidad `personality` (tier "capability", igual que `memory`/`drive`) para la tool nueva — no es un Especialista Cognitivo (no compone una llamada a LLM propia), es una operación directa sobre una preferencia, igual que `list_conversations`.

## Verificado

- 369/369 tests (nuevos: `tests/test_personality_prefs.py`, extensiones a `test_orchestrator.py` y `test_app.py`).
- Playwright contra una instancia real aislada (puerto 8001, sesión inyectada vía cookie firmada con el `SESSION_SECRET` real — evita el problema de cookies `Secure` sobre HTTP plano): slider presente con el default 7.5, cambio de valor reflejado en vivo, persistencia real confirmada tras recargar la página vía `GET /personality/preferences`, cero errores de consola.

## Consecuencias

- El default de 7.5 significa que, a partir de esta versión, el tono habitual de Snarf ya es notoriamente más filoso que antes sin que nadie toque nada — una excepción deliberada al criterio de "sin configurar = sin cambios" que rige el resto de las preferencias de este repo.
- El damping en crisis queda enteramente a criterio del modelo en el momento, sin ningún registro/telemetría de cuándo se activó — si en el futuro aparece evidencia real de que el modelo no lo respeta de forma consistente, ahí se evalúa instrumentarlo, no antes.
