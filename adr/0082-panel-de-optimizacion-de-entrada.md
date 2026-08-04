# ADR 0082 — Panel de optimización de entrada (Fase 6)

**Fecha:** 2026-08-03
**Estado:** Aceptado

## Contexto

Fase 6 del plan de HUD: "logging del paso de preprocesamiento de input
(antes de llamar al modelo): qué versión final del input se envía vs. lo
que el fundador escribió originalmente", con un panel para auditar
eficiencia de contexto.

Snarf **no reescribe** el mensaje del fundador — viaja verbatim en
`messages` (`Orchestrator.handle()`). No hay ningún paso de
"preprocesamiento" que transforme el texto en sí. Lo que sí varía turno a
turno, y es la fuente real de cualquier ineficiencia de contexto, es todo
lo que viaja **alrededor** del mensaje: el system prompt (identidad +
sarcasmo + perfil + prompt de proyecto) y el historial reciente
re-transmitido (`_capped_for_replay`, ADR 0067). "Versión final enviada"
se interpreta con esta honestidad: el bundle completo (system + historial +
input), no una reescritura del input que no existe.

## Decisión

### `snarf/telemetry/input_preprocessing.py` (nuevo)

`record(conversation_id, input_original, system_chars, history_chars,
history_entries)` — guarda el texto original completo (corto, ya es texto
que el fundador tipeó, sin duplicar megabytes de historial ya guardado en
`EpisodicMemory`) más los **tamaños** en caracteres de cada componente del
bundle. `overhead_ratio = total_sent_chars / input_chars` es la métrica
central: cuántos caracteres viajaron por cada uno que el fundador escribió.
Declarado explícitamente como proxy en caracteres, no una cuenta exacta de
tokens (Snarf no tiene acceso al tokenizer real de cada proveedor sin una
llamada extra — nunca se inventa un número de tokens).

Enganchado en `Orchestrator.handle()` justo antes de `self._llm.generate()`
— tamaños ya calculados ahí mismo (`len(system)`, suma de `len(content)`
sobre los mensajes de historial ya armados), cero llamadas nuevas al
modelo.

### `GET /dashboard/input_efficiency` (nuevo, `app.py`)

`{recent, summary}` — últimos 30 turnos + agregado (`avg_overhead_ratio`,
etc.).

### `web/hud_input_efficiency_prototype.html` (nuevo)

Tiles de resumen + tabla de turnos recientes (lo escrito, tamaño de cada
componente, ratio de overhead), en el lenguaje de Fase 0 — fila/tile en
ámbar cuando el overhead supera 50x. Mismo patrón fetch-con-fallback-a-mock
que Fase 3/5.

## Verificado

- `.venv/bin/python -m pytest -q` — 601/601 passed. Tests nuevos: 2 en
  `tests/test_orchestrator.py` (tamaños reales en el primer turno de una
  conversación — sin historial — y en el segundo — con el turno anterior
  replicado), 1 en `tests/test_app.py`.
- Playwright contra el prototipo: 4 tiles de resumen, tile de overhead
  marcado en ámbar cuando corresponde, tabla con el turno más reciente
  primero, demo real y honesta de la métrica ("gracias", 7 caracteres
  escritos, resultó en 5827 caracteres enviados — 832x de overhead) —
  exactamente el tipo de caso que Fase 8 (refactor de eficiencia) va a
  necesitar auditar con datos reales una vez que haya tráfico real.

## Consecuencias

- Fase 7/8 (auditoría y refactor de eficiencia por nodo) pueden usar este
  panel como evidencia real de dónde se concentra el overhead de contexto,
  en vez de adivinar.
