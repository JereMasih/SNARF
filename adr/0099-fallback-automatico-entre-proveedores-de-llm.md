# ADR 0099 — Fallback automático entre proveedores de LLM

**Fecha:** 2026-08-04
**Estado:** Aceptado

## Contexto

El fundador vio el rol `dashboard_curator` roto en el HUD ("No se pudo curar
el dashboard: ... Your credit balance is too low to access the Anthropic
API") mientras el rol `orchestrator` (chat principal) seguía andando bien —
lo había cambiado a mano a xAI/Grok en una sesión anterior. Preguntó por
qué el sistema no cambiaba solo de proveedor, ya que había uno disponible y
funcionando.

Investigando el ruteo real (`snarf/runtime/llm_routing.py`, ADR 0068) se
confirmó: el ruteo es **por rol**, no global — cada uno de los roles
(`orchestrator`, `gmail_digest`, `drive_vision`, `project_summary`,
`conversation_title`, `dashboard_curator`) tiene su propio proveedor
configurado de forma independiente, y **no existía ningún fallback
automático en ningún punto del código** — confirmado explícitamente
revisando los tres capabilities de LLM (`anthropic_llm.py`, `gemini_llm.py`,
`openai_compatible_llm.py`): ninguno atrapa errores de proveedor en
`generate()`, la excepción del SDK se propaga cruda hasta el llamador, que
hoy la muestra como texto de error sin reintentar. Decisión de diseño
explícita hasta ahora (selección manual, ver ADR 0068), no un bug.

Pedido explícito del fundador: que el fallback sea automático, que avise
cuando pasa, y que deje un registro trazable.

## Decisión

### 1. `is_provider_level_error(exc)` — clasificación honesta del error

Solo dispara fallback ante una excepción de status REAL del SDK del
proveedor (`anthropic.APIStatusError`, `openai.APIStatusError`,
`google.genai.errors.APIError`) con código `{400, 401, 403, 429, 500, 502,
503, 504, 529}` — nunca ante cualquier excepción genérica. El 400 está
incluido a propósito: así es como Anthropic devuelve "credit balance is too
low" (no existe un tipo de error dedicado para eso en su SDK). Riesgo
conocido y aceptado: un 400 real por un bug nuestro (forma de request rota)
también dispara el intento con otros proveedores antes de fallar —
probablemente falle igual en todos, así que solo agrega latencia, nunca
esconde el error real (la excepción que se propaga al final si TODOS los
proveedores fallan es la del intento ORIGINAL). Errores de conexión/timeout
sin status code no disparan fallback en esta versión — alcance
deliberadamente acotado al caso real reportado.

### 2. `attempt_fallback(role, entry, first_exc, **kwargs)` — núcleo real

`snarf/runtime/llm_routing.py`. Si el error es de proveedor, prueba cada
proveedor disponible (`available_providers()`, filtra por credencial real
cargada) en `FALLBACK_ORDER = ("anthropic", "xai", "gemini", "openai",
"groq_llama")` — mismo orden que ya venía usando el fundador a mano. Al
primero que funcione: persiste el cambio como nuevo default del rol
(`save_routing`), deja un registro real en `data/llm_fallback_log.jsonl`
(timestamp, rol, de qué proveedor a cuál, error real truncado) y devuelve
la respuesta. Si todos fallan, devuelve `(None, None)` — nunca inventa un
éxito.

`drive_vision` usa una lista separada, `VISION_FALLBACK_ORDER = ("anthropic",
"gemini")` — no hay confirmación de que xAI/Groq-Llama soporten imágenes
reales, mejor un fallback más corto que arriesgar una descripción de imagen
rota en un proveedor sin soporte de visión.

### 3. Dos formas de conectarlo — respetando la arquitectura de capas

Se encontró (por un test que reventó) que `snarf/specialists`,
`snarf/capabilities` y `snarf/knowledge` **no pueden importar
`snarf.runtime`** (deben ser reusables fuera de Snarf, ver
`test_capabilities_and_specialists_never_import_orchestrator_or_web_runtime`)
— un primer intento de conectar el fallback importando `llm_routing`
directo en `dashboard_curator.py`/`gmail_digest.py`/`project_manager.py`/
`extraction.py` violaba ese límite. Se revirtió y se resolvió en la capa de
wiring:

- **`build_resilient_llm(role)`** (nuevo, en `llm_routing.py`): devuelve
  `_ResilientLLM`, un envoltorio con el mismo contrato (`.available`,
  `.generate()`) que cualquier Capacidad de LLM, pero que reintenta sola y
  se auto-cura (la siguiente llamada al mismo objeto ya usa el proveedor
  que funcionó, sin volver a fallar contra el caído). Usado para los 4
  roles resueltos vía factory (`gmail_digest`, `drive_vision`,
  `project_summary`, `dashboard_curator`) — los Specialists siguen
  recibiendo su `llm_factory` de siempre, sin saber que el fallback existe.
- **Inline en `Orchestrator`** (`handle()`/`generate_conversation_title()`):
  los 2 roles de instancia fija (`orchestrator`, `conversation_title`) NO
  pasan por `_ResilientLLM` — decenas de tests reales hacen
  `monkeypatch.setattr(orchestrator._llm, "_client"/"generate", ...)`
  reaching directo a la Capacidad concreta; envolverla rompía ~20 tests con
  `AttributeError` (el wrapper no tiene `._client`). `self._llm`/
  `self._title_llm` siguen siendo `build_llm(role)` sin envolver; el
  `except Exception` de cada uno llama a `attempt_fallback(...)` inline y,
  si hay éxito, usa la respuesta y llama a `refresh_llm_routing()` (mismo
  mecanismo que ya usaba `PUT /llm-routing`).

### 4. Aviso real — mensaje en el chat, en cualquier vista

`GET /llm-routing/fallback_events?since=<ts>` (nuevo, `app.py`) expone
`recent_fallback_events()` (lee `data/llm_fallback_log.jsonl`). El frontend
(`web/index.html`) hace poll cada 60s, independiente de qué vista esté
abierta (clásica/HUD/mobile) — cualquier evento nuevo desde la última vez
visto (`localStorage`) se agrega como un mensaje más en el chat (mismo
patrón ya usado para cualquier otro aviso informativo, ej. "no pude subir
el archivo..."), nunca un toast nuevo acoplado a una sola vista. Nunca
muestra el historial completo en la primera carga (mismo criterio que
`pollBrainHudFeed`, ADR 0088) — solo lo que pase de acá en adelante.

## Bug real encontrado (no de este ADR, corregido igual)

Al escribir el primer intento de conexión, un test de arquitectura
(`test_capabilities_and_specialists_never_import_orchestrator_or_web_runtime`)
detectó la violación de capas antes de que llegara a producción — exactamente
la razón de que ese test exista. Documentado acá porque cambió el diseño
final (punto 3), no porque haya llegado a romper nada real.

## Verificado

- `.venv/bin/python -m pytest -q` — 787/787 passed (26 tests nuevos en
  `tests/test_llm_routing.py`: clasificación de errores con excepciones
  reales de los 3 SDKs, `attempt_fallback` con proveedores simulados,
  `_ResilientLLM`/auto-curación, registro trazable; 4 nuevos en
  `tests/test_orchestrator.py`: fallback exitoso y agotado para
  `handle()`/`generate_conversation_title()`; 3 nuevos en `tests/test_app.py`
  para el endpoint).
- Aplicado ya en producción vía el mismo mecanismo manual (`PUT
  /llm-routing`) mientras se investigaba: `gmail_digest`, `project_summary`,
  `conversation_title` y `dashboard_curator` pasados a xAI de inmediato
  para destrabar el error real visible en el HUD — el fallback automático
  de este ADR es la versión que no va a necesitar que alguien lo haga a
  mano la próxima vez.
- Playwright contra el servidor real de producción: el endpoint nuevo
  responde 404 hasta que se reinicie el proceso (cambio de backend, mismo
  requisito ya documentado en CLAUDE.md) — el frontend lo tolera con
  gracia (try/catch silencioso, sin romper la carga de la página).

## Consecuencias

- El fallback recién entra en vigencia para llamadas reales después de
  reiniciar el servidor de producción — confirmar con el fundador antes
  (convención ya establecida).
- `FALLBACK_ORDER`/`RECOMMENDED_MODEL` son constantes globales, no
  configurables por rol todavía — si el fundador quiere un orden de
  respaldo distinto para un rol puntual, es una extensión futura, no algo
  que este ADR prometa.
- El aviso en el chat depende de `localStorage` (por navegador, no
  sincronizado entre dispositivos) — suficiente para un único usuario
  fundador, no pensado para multi-dispositivo real todavía.
