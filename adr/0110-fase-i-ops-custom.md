# ADR 0110 — Fase I: rama Ops/Custom (cierra la Fase I completa)

**Fecha:** 2026-08-05
**Estado:** Aceptado

## Contexto

Novena y última rama de la Fase I. El plan original registraba esta rama como "parcialmente tapada
en la captura de referencia que usó el fundador — es una foto incompleta, no una decisión
pospuesta", con la instrucción explícita de aclararla con el fundador antes de detallarla más. Se
consultó: el fundador pidió que se generen, con criterio propio, las skills operativas que Snarf
necesita hoy — en vez de reconstruir una captura que ni él mismo recordaba completa.

## Decisión

**Vault Cleanup — confirmado sin código nuevo**, mismo criterio que otras piezas ya cerradas en
esta fase: `snarf/runtime/data_backup.py` (backup real cada 6hs, `BACKUP_TARGETS` cubre todo el
estado real e irremplazable) + la purga de audio a los 7 días (`app.py`, `AudioStore.purge_older_than`)
ya cubren esto completo.

**Dos tools nuevos, elegidos por criterio propio a partir de lo que ya se registra en este repo**:

1. **`snarf/runtime/ops_health.py::system_health()`** → tool `ops_system_health`: diagnóstico real
   consolidado (disponibilidad de LLM/Google, llamadas y errores recientes reales del Orchestrator,
   tamaño real en disco de `data/`) — reúne señales que ya existían dispersas (LLM.available,
   GoogleDrive.available, activity_log.recent()) en un solo resultado, nunca inventa una cifra
   nueva. Determinístico, cae en el nodo `utility` ya existente (mismo tier que
   `telemetry_cost_summary`), no un Especialista Cognitivo nuevo.
2. **`data_backup.backup_now()` expuesto como tool** (`ops_backup_now`): ya existía como función,
   usada solo por el loop periódico de `app.py` — ahora también invocable a pedido, sin esperar
   hasta 6hs. Aditivo, nunca toca datos en vivo (solo agrega un snapshot nuevo), no requiere
   confirmación.

**Deliberadamente NO se expone `data_backup.restore_latest()`** como tool: a diferencia de
`backup_now()`, restaurar SÍ sobreescribe datos en vivo reales — exponerlo a una llamada
conversacional casual sería una acción de alto impacto real sin el resguardo que amerita. Queda
como operación manual/CLI, no una herramienta de chat.

## Bug real evitado en esta misma ronda

`data_backup.backup_now(data_dir=DATA_DIR, backup_dir=BACKUP_DIR, ...)` resuelve sus paths default
al momento de DEFINIRSE la función (Python evalúa defaults una sola vez), no en cada llamada —
monkeypatchear `data_backup.BACKUP_DIR` en un test no alcanza para aislarlo del disco real. El
primer intento del test para `ops_backup_now` hubiera escrito un snapshot real en
`data_backups/` durante la suite; corregido parcheando la función `backup_now` en sí en vez de sus
constantes de módulo, verificado que `data_backups/` real queda intacto tras correr la suite.

## Verificado

- 6 tests nuevos: `tests/test_ops_health.py` (4), cobertura de orchestrator (2).
- 917/917 tests de la suite completa.

## Consecuencias — cierre de la Fase I completa

Con esta ADR se completan las 9 ramas de la Fase I (Memory, Productivity, Research, Content, Sales,
Finance, Community, Agency, Ops/Custom) — y con eso, las 10 fases (A-J, contando la J implícita en
la secuenciación general) del plan de expansión "Inteligencia Ejecutiva" completo: mapa evolucionado,
gobernanza fijada, Knowledge Layer generalizada, servidor MCP, los 7 roles asesores, el Harness
nombrado, el Skill Framework, la Skill Factory operativa, y las 9 ramas de capacidades reales. Ningún
ítem quedó bloqueado por falta de vendor — cada pieza sin construir en esta ronda (TaxPrep,
AnomalyScan/SubsAudit, ReceiptsTracker, MemberOnboarding/WeeklyQADigest/CommentTriage, Client AIOS
Builder) está nombrada con un motivo concreto y accionable, no silenciada.
