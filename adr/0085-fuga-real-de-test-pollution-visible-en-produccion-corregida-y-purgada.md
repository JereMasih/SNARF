# ADR 0085 — Fuga real de test-pollution visible en producción: corregida y purgada

**Fecha:** 2026-08-03
**Estado:** Aceptado

## Contexto

El fundador reportó, con una captura real de su Vista HUD en producción,
un feed inundado de filas `gemini:gemini-3-pro-preview` / "pontificando".
Esto ya se había detectado y documentado como gap en ADR 0077/0079 —
pero mal atribuido en parte, y clasificado como "fuera de alcance" cuando
en realidad ya estaba corrompiendo datos reales del founder en producción.

## Corrección a ADR 0077/0079

Esas ADRs atribuían la fuga a `tests/test_gemini_llm.py` **y**
`tests/test_llm_routing.py`. Verificado ahora con el código real:
`test_llm_routing.py` **nunca llama a `.generate()`** — solo construye
objetos `LLM` y chequea tipos/atributos, nunca dispara
`usage_tracker.record_*`. La mención de "gemini-3-pro-preview" que hizo
que apareciera en el grep original era un string literal usado como valor
de configuración de ruteo en los tests, no una llamada real. **No es, ni
fue nunca, una fuente de la fuga.** La fuente real y única es
`tests/test_gemini_llm.py` (6 tests que sí llaman `.generate()` de
verdad) más un test suelto en `tests/test_kokoro_tts.py`.

## Decisión

- `tests/test_gemini_llm.py`: fixture `autouse` nueva que redirige
  `usage_tracker.DEFAULT_PATH` y `events.DEFAULT_PATH` a `tmp_path` —
  mismo patrón ya usado en `tests/test_app.py` (ADR 0077/0079).
- `tests/test_kokoro_tts.py`: el único test que no mockeaba
  `record_kokoro_tts_call` (`test_speak_lets_the_caller_override_the_default_voice`)
  ahora lo mockea, igual que el resto del archivo ya hacía.
- **Purga real de los datos ya polucionados**, con huella de fixture
  exacta y sin ambigüedad (`model == "gemini-3-pro-preview"`,
  `input_tokens/tokens_in == 10`, `output_tokens/tokens_out == 5`,
  `cost_usd/costo_usd == 8e-05` — los defaults literales de
  `fake_response()` en el test, un patrón que ninguna llamada real podría
  reproducir por casualidad): 605 líneas removidas de
  `data/usage_log.jsonl`, 11 de `data/telemetry_events.jsonl`. Backup
  tomado antes de purgar (`/tmp/usage_log.jsonl.bak_before_purge`).
  Verificado que las entradas restantes siguen siendo JSON válido línea
  por línea y que ninguna entrada real (Anthropic, xAI, ElevenLabs, Groq,
  Kokoro, Voyage) se tocó.

## Verificado

- `.venv/bin/python -m pytest -q` — 605/605 passed. Conteo de
  `gemini-3-pro-preview` en `data/usage_log.jsonl` antes/después de correr
  la suite completa: 605 → 605 (sin cambio — confirma que la fuga está
  cerrada, no solo que se purgó una vez).
- `grep -c gemini-3-pro-preview` en ambos archivos reales: 0.
- Servidor de producción: **no hizo falta reiniciarlo** — este cambio
  solo tocó archivos de test y los datos en disco (ambos endpoints leen
  el archivo fresco en cada request, sin caché en memoria), confirmado
  con una request real (`401` esperado sin cookie, servidor respondiendo).

## Consecuencias

- La Vista HUD real del fundador debería verse limpia ahora, sin el ruido
  sintético que la ahogaba.
- Este era el último gap de test-pollution real conocido en el proyecto
  (ver gap #3/#4 de `SESSION_STATE.md`, ahora cerrados).
