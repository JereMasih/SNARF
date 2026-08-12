# ADR 0160 — Escritura n8n → Snarf con confirmación de dos pasos (propose/apply)

**Fecha:** 2026-08-12
**Estado:** Aceptado

## Contexto

ADR 0156 (Fase 15) autorizó una categoría nueva de escritura — "iniciada y confirmada por el fundador en
vivo" — distinta de la escritura autónoma de un solo paso que ya cubre ADR 0145 (`/n8n/prompts`,
`/n8n/generation-config`). Esa autorización quedó como decisión de gobernanza, sin código. Esta fase la
implementa: el único camino real por el que n8n puede tocar `tools`/`routing`/`stages` de un rol del
Executive Board (ejes que `/n8n/prompts`/`/n8n/generation-config` nunca cubrieron ni van a cubrir — ver
ADR 0145, acotada a texto/config a propósito).

## Decisión

**`snarf/runtime/agent_change_proposals.py`** (nuevo) — dos funciones:

- `propose(agent_id, changes)`: calcula un diff real contra `agent_registry.get_agent_recipe(agent_id)`
  (Fase 16) para cualquier subconjunto no vacío de `{prompt_text, tools, routing, stages}`, lo persiste con
  TTL de 15 minutos (`data/n8n_pending_changes.json`, clave `change_id` random) junto con un `baseline` del
  estado activo en ese momento — **no aplica nada todavía**.
- `apply(change_id)`: revalida que el estado activo de cada campo propuesto sigue siendo igual al
  `baseline` capturado en el `propose` (optimistic locking) — si algo cambió en el medio (el cockpit del
  founder, u otra propuesta ya confirmada), rechaza con `StaleChangeError` en vez de aplicar sobre un
  estado que ya no existe. Si no hubo cambios, escribe cada campo presente delegando a las funciones de
  guardado de la Fase 16 (`prompt_registry.save_new_version`, `tool_subset_registry.save_new_version`,
  `llm_routing.save_routing_versioned`, `agent_graph_registry.save_new_version`) — nunca una segunda
  implementación de esa escritura.

**Endpoints nuevos en `app.py`** (mismo `require_n8n_token`/`N8N_CONTROL_TOKEN` ya validado por ADR 0145):

- `POST /n8n/agent/{agent_id}/propose` → 400 si el payload trae campos desconocidos o vacío.
- `POST /n8n/agent/{agent_id}/apply` → 400 si `change_id` no existe/expiró, **409** (no 400) si
  `StaleChangeError` — el código HTTP distingue "pedido mal formado" de "el estado se movió, proponé de
  nuevo", útil para que el workflow de n8n pueda mostrar un mensaje distinto en cada caso. Tras un apply
  real, dispara `n8n_generator.sync_executive_board_safe()` (Fase 18) en un hilo de background — best
  effort, nunca puede tumbar la escritura que ya se aplicó a los registros (mismo criterio de resiliencia
  que `n8n_webhook_sink.py`: el fallo se cuenta, nunca se propaga).

**Adelantado desde Fase 18:** `GET /n8n/agent/{agent_id}` (solo lectura) ya se agregó en esa fase — ver
ADR 0159 para el porqué de ese reordenamiento.

**Superficie n8n — dos workflows separados, no un formulario nativo de dos páginas:** el plan original de
esta serie de fases proponía el patrón nativo de n8n de formularios multi-página (`$resumeUrl`) para
mostrar el diff antes de confirmar en el mismo flujo. Se optó por **dos workflows separados**
(`Snarf - Proponer cambio de agente` → `Snarf - Confirmar cambio de agente`, el fundador copia el
`change_id` del primero al segundo tras revisar el diff) en vez de apostar a un schema JSON de n8n para
formularios multi-página que no se pudo verificar contra la instancia real en esta sesión (sin Colima/n8n
corriendo acá) — mismo criterio de honestidad que ya aplicó ADR 0154 con el límite de "no se pudo probar
el trigger real": mejor un patrón más simple y construido enteramente con node types ya verificados
(`formTrigger`/`httpRequest`, los mismos que `snarf_editar_prompt.json`) que uno más elegante pero no
probado. La confirmación real sigue existiendo — son dos acciones humanas distintas, no una escritura de
un clic — solo no usa la feature nativa de "página 2 del mismo formulario". Migrar a esa feature nativa
más adelante, con el fundador probándola en vivo, queda anotado como mejora posible, no bloqueante.

## Verificado

- 10 tests nuevos en `tests/test_agent_change_proposals.py`: propose nunca aplica nada; rechaza campos
  desconocidos/payload vacío/agent_id desconocido; apply escribe los cuatro ejes juntos cuando se proponen
  juntos; apply solo toca los campos realmente propuestos; apply borra la propuesta ya aplicada (un
  `change_id` no se puede reusar); apply rechaza un `change_id` inexistente o expirado; apply rechaza con
  `StaleChangeError` cuando el estado se movió en el medio.
- 5 tests nuevos en `tests/test_app.py`: los dos endpoints nuevos exigen el token; el ciclo real
  `propose`→`apply` vía HTTP escribe de verdad y el `GET` posterior lo confirma; `apply` con `change_id`
  inválido da 400; `apply` sobre un estado que cambió en el medio da 409. Los tests del `apply` real
  anulan explícitamente `n8n_generator.sync_executive_board_safe` para nunca disparar una llamada de red
  real (contra `127.0.0.1:5678` u otra instancia) durante la suite de tests.
- **No se probó el ciclo completo contra la instancia real de n8n** (los dos workflows nuevos no se
  importaron/ejecutaron ahí) — mismo motivo que Fase 18, sin Colima/API key reales disponibles en esta
  sesión. Queda para la Fase 21.
- 1373/1373 tests de la suite completa (`.venv/bin/python -m pytest -q`), 1355 previos (post ADR 0159) +
  15 nuevos de esta fase (10 + 5) + 3 tests de `tests/test_document_to_reader_optimized.py` — un archivo
  **sin trackear en git, ajeno por completo a esta serie de fases**, ya presente en el working tree antes
  de arrancar esta ronda (verificado con `git log --all` sobre ese path: nunca se commiteó). Se deja
  anotado acá en vez de omitido por honestidad con la cifra real que reporta `pytest`, no porque sea
  trabajo de esta ADR — no se tocó ni se investigó su origen, corresponde confirmarlo con el fundador antes
  de decidir si se commitea, se descarta, o se ignora a propósito.
