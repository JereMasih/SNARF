# ADR 0103 — Fase I: rama Memory (cerrada por equivalencia) y rama Productivity (`calendar_brief`)

**Fecha:** 2026-08-05
**Estado:** Aceptado

## Contexto

Primeras dos ramas de la Fase I (las 9 ramas del mapa de referencia). Working tree limpio — ambas
sesiones en paralelo de esta jornada (Inteligencia Ejecutiva y fallback automático entre proveedores
de LLM) ya quedaron commiteadas y sincronizadas con `origin/master` antes de arrancar esta fase.

## Decisión

**Memory**: cerrada sin código nuevo. Las cuatro piezas que el mapa de referencia pedía ya existen,
con otro nombre, de rondas anteriores de este mismo repo — documentado explícito en `KNOWLEDGE.md`
(nueva sección "Rama Memory"): Obsidian Vault/wiki ≈ Knowledge Layer generalizada; `/projects active`
≈ Proyectos (ADR 0045/0047/0054); `CLAUDE.md` como prompt persistente ≈
FOUNDATION/CONSTITUTION/CHARACTER + `project.prompt`; memoria automática ≈ `EpisodicMemory`. No es una
promesa a futuro — es la equivalencia real, hoy.

**Productivity**: primer skill real construido bajo el sub-paquete por rama que la Fase G dejó
preparado (`snarf/specialists/productivity/`).

1. `CalendarBriefSpecialist` (mismo patrón cache-first que `GmailDigestSpecialist`, mismo criterio de
   modelo barato por rol — `llm_routing.ROLES` suma `calendar_brief`): interpreta los próximos
   eventos reales de `GoogleCalendar.list_upcoming_events()` en un resumen accionable, nunca inventa
   un evento que no esté en el listado real.
2. Tool nuevo `calendar_brief(force_refresh=False)`, mismo patrón cache-first que
   `gmail_summarize_inbox`; nodo nuevo `specialist_calendar`. Widget nuevo
   `GET/POST /dashboard/widgets/calendar/brief`, mismo patrón que el de Gmail.
3. `snarf/runtime/scheduler.py::next_run_at(hour, minute, tz)` — único código genuinamente nuevo de
   infraestructura: los 3 loops periódicos de hoy (backup, purga de audio, curación del dashboard)
   son de intervalo fijo desde el arranque del proceso; una rutina real a una hora de reloj concreta
   necesita este cálculo. Deliberadamente no se construye una "Morning Routine" wireada completa (con
   preferencia de horario por usuario, UI de configuración) en esta ronda — el plan solo pedía la
   infraestructura de scheduling en sí, no la feature completa; queda como el primer consumidor real
   futuro de este helper, no una promesa vacía (la función ya está probada y lista para usarse).
4. Bug real encontrado escribiendo el test de timezone de `next_run_at`: comparar/reemplazar
   directamente sobre un `now` en una zona horaria distinta a `tz` (ej. `now` en UTC, `tz` en
   `America/Argentina/Buenos_Aires`) construía una hora de reloj en la zona equivocada — corregido
   convirtiendo `now` a `tz` antes de cualquier comparación.

## Verificado

- 19 tests nuevos: `tests/test_scheduler.py` (5, incluido el caso de zona horaria distinta),
  `tests/test_calendar_brief.py` (7), más cobertura de widget/orchestrator/schema (7).
- 842/842 tests de la suite completa.

## Consecuencias

- `snarf/specialists/` empieza de verdad su transición a sub-paquetes por rama (Fase G la dejó
  documentada, diferida hasta que hubiera un skill real que la necesitara) — `productivity/` es el
  primero.
