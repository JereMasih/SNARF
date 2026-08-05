# ADR 0109 — Fase I: rama Agency

**Fecha:** 2026-08-05
**Estado:** Aceptado

## Contexto

Octava rama de la Fase I. El plan ya distinguía: 5 de los 6 ítems (Sponsor Pitch Deck,
Scope-of-Work Gen, Weekly Client Status, Deliverable QA, Retainer Renewal Brief) son
"análisis/generación de documentos sobre Proyectos + `AnthropicLLM` + `DocumentBuilder`, ya
existentes" — llamarla "cero capability" hubiera sido confundir "sin plataforma/CRM dedicado" con
"sin nada construible". El único ítem genuinamente grande, **Client AIOS Builder**, ya estaba
secuenciado por el propio plan "al final de esta rama, por tamaño real" — no una decisión de scope
de esta ronda.

## Decisión

**`ClientStatusSpecialist`** (`snarf/specialists/agency/client_status.py`) — único código
genuinamente nuevo de la rama. Distinto de un simple "draft a partir de un brief" (que ya cubre
Sponsor Pitch Deck/Scope-of-Work/Deliverable QA/Retainer Renewal Brief sin código nuevo, mismo
criterio que Proposal Drafts en la rama Sales): parte de datos REALES y estructurados de un Proyecto
real (`ProjectManager.get()` — tareas completadas/pendientes, notas recientes), no de un brief
conversacional. Redacta el status vía LLM, nunca inventa un avance no reflejado en las
tareas/notas reales, publica el documento con `DocumentPublisher`. Tool nuevo `agency_client_status`,
nodo `specialist_agency`.

**Client AIOS Builder**: sigue diferido, mismo motivo que ya registró el plan original — tamaño real
(generar una versión acotada del propio mapa de capacidades de Snarf, por cliente), no bloqueo de
vendor. Se construye como su propio proyecto dentro de esta rama cuando corresponda.

## Bug real encontrado y corregido en esta misma ronda

El primer intento de wiring instanciaba `ClientStatusSpecialist` ANTES de que
`self._projects`/`self._document_publisher` existieran en `Orchestrator.__init__` —
`AttributeError` real en tiempo de construcción, detectado corriendo la suite completa (no solo los
tests nuevos, que no lo hubieran visto). Corregido moviendo la instanciación a después de
`self._projects = ProjectManager(...)`.

## Verificado

- 6 tests nuevos: `tests/test_client_status.py`.
- 911/911 tests de la suite completa.
