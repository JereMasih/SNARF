# ADR 0084 — Fase 7/8, nodo Orchestrator: recorte de duplicación verificada en `SYSTEM_PREFIX`

**Fecha:** 2026-08-03
**Estado:** Aceptado

## Contexto

Primer nodo de la auditoría de Fase 7 (`SESSION_STATE.md`): el rol
principal (Sonnet 5), 96%+ del gasto histórico real. Propuesto un plan de
dos preguntas al fundador:

1. **FOUNDATION/CONSTITUTION/CHARACTER** (20.317 chars) — el fundador
   aprobó evaluarlos. Evaluación real: ya están escritos de forma
   económica para lo que son (documentos de gobernanza/identidad); no se
   encontró grasa retórica real para cortar sin arriesgar perder matiz
   legal/de identidad. **No se tocaron** — cortar "porque sí" hubiera ido
   en contra del pedido explícito de evaluar con cuidado antes de actuar.
2. **`SYSTEM_PREFIX`** (15.385 chars) — el fundador pidió que Claude
   evalúe, proponga un plan concreto, y decidan juntos. Se midió (no se
   asumió) el solapamiento real entre la prosa de `SYSTEM_PREFIX` y el
   campo `description` que cada tool ya tiene en el schema `TOOLS`
   (enviado aparte a la API, el modelo ya lo recibe) — varios pasajes
   resultaron duplicados casi palabra por palabra. El fundador aprobó
   proceder.

## Decisión

Recortado solo lo verificado como duplicado, palabra por palabra contra
las `description` reales del schema:

- Párrafo completo sobre `get_current_datetime`/`measure_text_length`:
  **eliminado entero** — ambas descripciones ya contienen el mismo texto
  casi literal (incluido el flujo "medí → recortá si excede → volvé a
  medir → recién ahí respondé").
- Párrafo de herramientas de solo lectura de Drive/Gmail/Calendar/YouTube
  (enumeración + "usalas para responder con contexto real"): **eliminado
  entero** — cada tool ya se autodescribe, la enumeración no aporta nada
  que el modelo no tenga ya en el array `tools`.
- Nota sobre `calendar_list_upcoming_events`/`calendar_search_events`
  (eventos futuros / dónde buscar si no aparece): **eliminada entera** —
  verificado que ambas direcciones de esa guía ya están en las
  descripciones de esos dos tools respectivamente.
- Enumeración de tools "de alto impacto" antes del protocolo de
  confirmación: **reemplazada** por una referencia genérica ("toda
  herramienta que su propia descripción marque como 'alto impacto'") —
  cada una ya se autodescribe así. **El protocolo en sí (los 3 pasos)
  queda intacto, palabra por palabra** — no está en ningún tool
  individual, es la única fuente de esa lógica de seguridad real
  (Constitution, Artículo VII).
- Excepción de `drive_update_document` (mismo documento no vuelve a pedir
  confirmación dentro de la conversación): **reemplazada por una
  referencia** a su propia descripción, que ya contiene la excepción
  completa y correcta — verificado texto por texto.
- `calendar_move_event` (notificación a invitados): **se mantuvo intacto**
  — verificado que esa nota NO está en la descripción del tool, es
  información real y única.

**Deliberadamente no tocado**, por señal de riesgo/beneficio desfavorable
o por ser seguridad-crítico:

- El protocolo de confirmación en dos pasos en sí (los 3 pasos).
- El protocolo de lectura masiva con costo (`drive_list_files` y
  similares) — el incidente real de ADR 0067 ($1.09 en una sola llamada)
  justifica no arriesgar esa guía por un ahorro modesto.
- Bloques de habla/entregable, convenciones de Proyectos, creación de
  documentos con sus tres destinos — guía de orquestación cruzada real,
  no duplicada en ningún tool individual.

## Verificado

- `.venv/bin/python -m pytest -q` — 605/605 passed (ningún test asertaba
  contra el contenido de `SYSTEM_PREFIX`, verificado antes de tocarlo).
- `len(SYSTEM_PREFIX)`: 15.385 → **13.211 caracteres (-14,1%, -2.174
  chars)**, cero pérdida de guía única verificada.
- Servidor de producción (puerto 8002) reiniciado con el prompt nuevo —
  confirmado con actividad real post-reinicio en
  `data/telemetry_events.jsonl` (llamada real a `claude-sonnet-5`, costo
  real $0.0285, TTS local real).

## Consecuencias

- Como el system prompt está cacheado (ADR 0026/0036), el ahorro real en
  dólares es menor al 14,1% en caracteres — pega sobre todo en cada
  cache-write (primera llamada de cada ventana de 1h), no en cada turno.
  No medido en dólares todavía — requeriría comparar cache-writes
  reales antes/después con tráfico real, pendiente si el fundador lo pide.
- Nodo Orchestrator: Fase 7 (auditoría) y Fase 8 (refactor) para este
  componente puntual quedan **completas** con este cambio. Quedan
  pendientes de auditoría/aprobación los otros 3 nodos del orden ya
  decidido (especialistas en Haiku, conversation_title, voz).
