# ADR 0125 — Títulos legibles del feed del cerebro (nodo `llm`) y detalle real al hacer click

**Fecha:** 2026-08-06
**Estado:** Aceptado

## Contexto

Pedido explícito: "el nombre openai:mlx-comunity/qwen.... no aporta, podría decir razonamiento y el
nombre de modelo de lenguaje, y despues un verbo. y al hacer click nos puede mostrar el detalle del
proceso, tiempos, data útil." Investigación confirmó dos code paths reales mostrando el mismo string
crudo `"vendor:model"` para eventos del nodo `llm`: `app.py::/dashboard/telemetry_feed` (Vista HUD) y
`snarf/telemetry/brain.py::snapshot()` (feed clásico del panel Cerebro) — y confirmó, además, que el
`vendor` mostrado ahí ya era engañoso de por sí: los roles locales (MLX) quedan etiquetados `"openai"`
por un detalle de implementación de `OpenAICompatibleLLM` (usa `OPENAI_API_KEY` como env var dummy para
proveedores sin credencial real), exactamente el caso del ejemplo del fundador.

## Decisión 1: `verbs.resumen_llm()` — nombre de modelo legible, sin vendor

Nueva función en `snarf/telemetry/verbs.py` (mismo archivo ya responsable de la derivación de texto del
feed): recorta el prefijo de organización de HuggingFace (`mlx-community/Qwen3-4B-...` →
`Qwen3-4B-...`) y devuelve el modelo solo — **sin** un prefijo "Razonamiento —" agregado a mano. Motivo
real encontrado con Playwright en vivo: el único lugar donde esto se renderiza hoy
(`brainFeedRowHTML()` en `web/index.html`) ya antepone `BRAIN_NODE_LABELS["llm"] = "Razonamiento"` antes
del texto del evento — agregar el prefijo acá también duplicaba la palabra
("Razonamiento · Razonamiento — Qwen3-4B..."). El resultado final en pantalla sigue siendo exactamente
lo pedido ("razonamiento" + modelo), compuesto por dos piezas que ya existían en vez de una string nueva
que las repetía.

Aplicado en los dos lugares reales: `app.py::dashboard_telemetry_feed` (campo `resumen`) y
`brain.py::snapshot()` (campo `label`, solo para `node_id == "llm"` — `stt`/`tts` se quedan con
`vendor:model` tal cual, esos strings ya son legibles y no fueron parte del pedido).

## Decisión 2: detalle al click, reusando el drill-down por nodo ya existente

En vez de construir un panel nuevo, se reusa `openNodeDrillPanel(nodeId)` (ya existía, disparado al
clickear un nodo del grafo HUD) — ahora también se dispara al clickear cualquier fila del feed clásico
(`#brainFeedList`, nuevo `data-node` por fila + listener delegado). Mismo endpoint real
(`GET /dashboard/node_activity/{node}`), sin ruta nueva.

`renderNodeDrillBody()` gana una línea de "timing" nueva (`nodeDrillTimingLine()`) que muestra
modelo/tokens/latencia/costo cuando el evento los trae — nunca inventa un campo ausente, cada pieza es
opcional.

## Decisión 3: `latencia_ms` real para eventos de LLM (antes siempre `None`)

El schema de evento (`events._event`) ya tenía un campo `latencia_ms`, pero `record_vendor_event()`
nunca lo poblaba para llamadas de LLM — el "tiempos" del pedido no tenía de dónde salir. Plomería real
agregada en cadena: `AnthropicLLM._create()`/`OpenAICompatibleLLM._complete_once()` miden
`time.monotonic()` alrededor de la llamada real (ya eran el único punto de la llamada HTTP real en cada
clase) → `_record_usage()`/`_record_usage_from_parts(duration_ms=...)` →
`usage_tracker.record_anthropic_call()`/`record_generic_llm_call(duration_ms=...)` →
`usage_tracker.record(duration_ms=...)` → `events.record_vendor_event(duration_ms=...)` →
`_event(latencia_ms=...)`. Cinco funciones, un solo campo nuevo threaded de punta a punta — sin cambiar
ninguna firma existente de forma incompatible (todos los parámetros nuevos son opcionales).

## Verificado

- `.venv/bin/python -m pytest -q` — 990 passed (incluye tests nuevos: `resumen_llm()` en aislamiento,
  el endpoint `/dashboard/telemetry_feed` con un evento LLM real, `brain.snapshot()` con el label nuevo,
  y `duration_ms` verificado en cada capa de la cadena hasta `events.recent()`, incluidos
  `AnthropicLLM.generate()`/`OpenAICompatibleLLM.generate()` (streaming y no-streaming) midiendo un
  valor real).
- Playwright: feed row muestra "Razonamiento · Qwen3-4B-Instruct-2507-4bit" (sin duplicar, sin
  "openai"), cursor `pointer`, click abre el panel de detalle real, línea de timing muestra
  modelo/tokens/latencia/costo con los valores reales del evento mockeado. Cero errores de consola.

## Consecuencias

- `resumen_llm()` depende de que `modelo` viaje en el evento — ya viaja para todo evento de vendor
  desde `events._event`, ningún cambio de schema adicional.
- El mislabeling real de vendor (local queda como "openai") **no se corrigió acá** — quedó documentado
  como causa raíz del ejemplo del fundador, pero tocar `_VENDOR_BY_API_KEY_ENV`/cómo `OpenAICompatibleLLM`
  deriva `_vendor` afecta además el tracking de costo real por proveedor, fuera del alcance de esta
  ronda (solo UI de display).
