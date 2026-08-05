# ADR 0106 — Fase I: rama Sales

**Fecha:** 2026-08-05
**Estado:** Aceptado

## Contexto

Quinta rama de la Fase I. El plan ya distinguía qué de esta rama necesita código nuevo y qué reusa
lo que ya existe: "Sponsor Inbox Triage reusa el patrón de digest de Gmail. Proposal Drafts
construible hoy. Lead Enrichment/Pipeline Review: sin CRM dedicado, se construyen igual sobre
Proyectos + `knowledge_search`."

## Decisión

**Único código genuinamente nuevo — `SponsorInboxTriageSpecialist`**
(`snarf/specialists/sales/sponsor_inbox_triage.py`): mismo patrón cache-first exacto que
`GmailDigestSpecialist`, pero con una búsqueda de Gmail real y acotada (`DEFAULT_QUERY = "sponsor OR
sponsorship OR partnership OR collab OR propuesta OR presupuesto OR budget"`) en vez de la bandeja
entera, y un system prompt que separa oportunidades reales de menciones casuales de la palabra
clave. Tool nuevo `sales_sponsor_inbox_triage`, nodo `specialist_sales`.

**Proposal Drafts — cerrado sin código nuevo.** Ya cubierto por lo que existe hoy: Snarf puede
redactar cualquier propuesta en conversación y publicarla con `drive_create_document` (o, si el
fundador quiere un modo dedicado más adelante, sumar un cuarto config a `ContentSpecialist` —
Fase I, rama Content — sería trivial, no antes de que haga falta de verdad).

**Lead Enrichment / Pipeline Review — cerrado sin código nuevo.** Mismo criterio que la rama Memory:
Proyectos (`project_list`/`project_get`/`project_search`, ADR 0045/0047/0054) ya trackea estado real
por proyecto — sirve como pipeline liviano sin necesidad de un CRM dedicado. `knowledge_search`
enriquece un lead con lo que ya esté indexado. Una integración de CRM real (ej. HubSpot) queda
nombrada como upgrade futuro, no como bloqueo de v1 — mismo patrón que Plaid en Finance.

## Verificado

- 8 tests nuevos: `tests/test_sponsor_inbox_triage.py` (6), cobertura de orchestrator (2).
- 872/872 tests de la suite completa.
