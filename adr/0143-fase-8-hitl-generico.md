# ADR 0143 — Fase 8 (parte 1/2): HITL genérico sobre el event bus

**Fecha:** 2026-08-11
**Estado:** Aceptado

## Contexto

`ROADMAP_OBSERVABILIDAD_MULTIUSUARIO_N8N.md` fija la Fase 8 en dos partes reales, de naturaleza
distinta: **HITL** (código, ejecutable ahora) y una **decisión de stack de observability** (Langfuse,
condicionada a que arranque el rollout de usuarios de prueba). Esta ADR cubre solo la primera — ver
"Fuera de alcance" abajo para por qué la segunda no se ejecuta hoy.

**HITL, según el texto del plan:** *"generaliza el protocolo de dos pasos ad-hoc de HIGH_IMPACT_TOOLS
(ADR 0015) en un evento reusable (ApprovalRequested/Granted/Rejected) sobre el event bus de Fase 2,
consumible desde n8n sin que n8n pase a decidir nada."*

Auditando el código real: el protocolo de confirmación en dos pasos NO vive en un solo chokepoint por
handler — cada `_tool_XXX` de `orchestrator.py` llama a `self._pending(preview)` (un `@staticmethod`
que arma `{"status": "pending_confirmation", "preview": ..., "instructions": ...}`) cuando
`i.get("confirmed")` es falso. Pero `_handle_tool` (Chokepoint A, ya establecido en ADR 0135) SÍ recibe
el `result` de cada handler antes de devolverlo — es el único lugar real que necesita tocarse.

## Decisión

**Ningún cambio al protocolo de confirmación en sí — CLAUDE.md ya marca este código como
safety-critical, no duplicado en ningún tool individual (ver ADR 0084).** Esta ADR es puramente
observacional: agrega dos `event_type` nuevos (`snarf/telemetry/events.py`) — `approval.requested`,
`approval.granted` — y los emite desde `Orchestrator._handle_tool` (nunca desde un handler individual)
usando el mismo `record_lifecycle_event()` genérico que ya usan workflow/agent/tool/llm, reusando el
`span` (`tool.started`) que `_handle_tool` ya abre: mismo `event_id`/`trace_id`, correlación real sin
código nuevo de correlación.

- **`approval.requested`**: emitido cuando `result.get("status") == "pending_confirmation"` — el handler
  ya decidió que hace falta confirmar, este evento solo lo hace visible en el event bus (con el mismo
  `preview` real que ya se le muestra al fundador en el chat).
- **`approval.granted`**: emitido cuando `tool_input.get("confirmed") is True` y el tool es de
  `HIGH_IMPACT_TOOLS` o `BULK_READ_GATED_TOOLS` — la ejecución real ya ocurrió (o falló por su cuenta,
  sin relación con esto), este evento solo documenta que hubo una confirmación explícita de por medio.
- **Sin `approval.rejected`**: no existe ninguna señal real de "el fundador dijo que no" en el código —
  es silencio conversacional (el LLM simplemente no vuelve a llamar la tool), no una acción de Snarf.
  Emitir este evento sería inventar una capacidad de detección que no existe (Principio VI,
  FOUNDATION.md) — documentado como gap honesto, no como pendiente técnico.
- **n8n nunca decide nada nuevo acá**: estos eventos viajan por el mismo dispatcher/sinks ya reales
  (Fases 1/2/4) — n8n puede observarlos (ej. avisar por Slack "Snarf está por borrar un archivo"), pero
  no hay ningún endpoint nuevo que le permita aprobar/rechazar en nombre del fundador. Quien confirma
  sigue siendo, exclusivamente, el fundador en el chat.

## Fuera de alcance — decisión de stack de observability (Langfuse)

El propio plan condiciona esto a *"cuando arranque el rollout de usuarios de prueba"* — que todavía no
pasó (ver Fase 3, ADR 0137: verificación OAuth de Google y onboarding guiado siguen pendientes). No hay
nada real que decidir ni desplegar hoy sin ese driver — instalar Langfuse ahora sería infraestructura
por delante de una necesidad que todavía no existe, exactamente el patrón que `ROADMAP_...md` pide evitar
("Fundación técnica vs. modo Capacidades"). Se deja registrado, sin ejecutar, para retomar cuando el
rollout arranque de verdad.

## Verificado

- 3 tests nuevos en `tests/test_telemetry_events.py`: `approval.requested` lleva el preview real y
  comparte `event_id`/`parent_event_id` con su span; `approval.granted` comparte `trace_id`; ambos
  invisibles para consumidores legacy por default (`recent()` sin `include_lifecycle=True`).
- 15 tests nuevos de wiring en `tests/test_orchestrator.py`: los 8 `HIGH_IMPACT_TOOLS` emiten
  `approval.requested` al pedir confirmación y `approval.granted` al confirmarse; los 6
  `BULK_READ_TOOLS` por encima del umbral, lo mismo; un tool sin protocolo de confirmed (
  `list_conversations`) nunca emite ninguno de los dos eventos.
- 1259/1259 tests de la suite completa (`.venv/bin/python -m pytest -q`), 1241 previos (post Fase 7) +
  18 nuevos.
