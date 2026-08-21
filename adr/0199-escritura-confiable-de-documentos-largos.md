# ADR 0199 — Escritura confiable de documentos largos

**Fecha:** 2026-08-21
**Estado:** Aceptado

## Contexto

Fase D4 del plan Second Brain (`ROADMAP_SECOND_BRAIN_NOTION.md`, ver ADR 0179), penúltima pieza de Track D
(confiabilidad del Orchestrator). El fundador nombró explícitamente 3 tipos de corte que quiere que Snarf
deje de sufrir al escribir un documento real y largo: el límite de caracteres/tokens del modelo, una caída
de proceso/RAM, y fallas transitorias de la API de destino (Notion). Ninguno de los tres estaba resuelto:
`notion.append_to_page`/`create_page` (ADR 0180) ya trocean en tandas de ≤100 bloques con reintento, pero
eso resuelve el límite de la API de Notion — no el hecho de que generar el CONTENIDO de un documento largo
entero en una sola llamada de LLM sigue estando sujeto al límite de tokens del modelo, ni el hecho de que
si el proceso muere a mitad de camino no había ningún estado persistido desde el cual retomar.

## Decisión

**`DocumentWriter` (`snarf/specialists/document_writer.py`, nuevo)** — compone la Capacidad Notion ya real
(A1/ADR 0180), namespaced por `user_id` desde el día uno (mismo criterio que todo Track D). Resuelve los 3
cortes:

1. **Límite de tokens**: cada sección es una llamada de LLM independiente, con contexto acotado (título del
   documento, objetivo, título+brief de la sección actual, y solo los TÍTULOS de las secciones ya
   verificadas — nunca su contenido completo). El prompt nunca crece con el tamaño del documento ya
   escrito.
2. **Caída de proceso/RAM**: el estado completo (`data/document_writes/<user_id>/<write_id>.json`) se
   persiste a disco después de cada paso — un proceso o sesión completamente nueva puede seguir exactamente
   donde quedó llamando `continue_write(write_id)`, sin nada en memoria.
3. **Fallas de API**: cada sección se **verifica releyendo la página real** (`read_page_text`) antes de
   avanzar a la siguiente. Reintento acotado (`MAX_SECTION_ATTEMPTS = 3`, nunca infinito — mismo criterio
   que `_max_continuations` de ADR 0113 y `max_rounds` de `TeamSession`, ADR 0198).

**Decisión de diseño clave, no anticipada en el detalle del plan original**: una sección pasa por dos
sub-pasos con semántica distinta — "pending → written" (generar y hacer el `append_to_page` real) y
"written → verified" (releer y confirmar). **Si falla la verificación después de que el `append` ya
sucedió de verdad, nunca se reintenta el `append`** — solo se reintenta la lectura. Reintentar el append
ahí duplicaría contenido real en la página del fundador, que es peor que quedarse en un estado
"unverified" declarado explícito. Estados terminales de una sección: `verified` (feliz), `failed` (nunca
se logró ni generar ni escribir tras agotar los intentos — nada real llegó a Notion), `unverified`
(SÍ se escribió de verdad, pero nunca se pudo confirmar releyendo — queda para revisión manual, nunca se
presenta como "listo"). El documento completo (`completed=true`) exige que TODAS las secciones estén
`verified` — un `failed`/`unverified` nunca se esconde, aparece en `sections_stuck`.

**Cada llamada avanza como máximo un paso** (nunca un loop interno que procese todas las secciones de
una sola vez) — `document_write_start` procesa la primera sección (incluyendo su verificación, si todo
sale bien en el primer intento), `document_write_continue` avanza una más por llamada. El avance completo
de un documento largo queda en manos de quien llama repitiendo la tool, mismo principio que ya rige el
propio loop de herramientas del Orchestrator (ADR 0113): ninguna operación de una sola llamada queda sin
tope.

**Desviación honesta del plan original**: el diseño pedía un motor "genérico por destino" desde el
arranque. No se construyó esa generalización — hoy `DocumentWriter` solo sabe escribir a una página de
Notion. Generalizar a un segundo backend real (ej. Drive) queda diferido hasta que exista un caso de uso
real que lo justifique, en vez de una abstracción sin ningún segundo consumidor (Principio VI: mejor
declarar la desviación que fingir generalidad no usada).

**Orchestrator**: `self._document_writer = DocumentWriter(self._notion, llm_factory, user_id)`, propiedad
pública `orchestrator.document_writer`. 3 tools nuevas: `document_write_start(page_id, title, sections,
objective)`, `document_write_continue(write_id)`, `document_write_status(write_id)` — ninguna gateada
(cada una internamente usa `notion_append_to_page`, ya no gateado por ser aditivo/reversible, ver
`POLICY_HIGH_IMPACT_ACTIONS.md`). Nodo del cerebro propio `specialist_document_writer` (mecanismo distinto
de CRUD crudo de Notion, mismo criterio que separó `specialist_second_brain_reports`). Rol de ruteo nuevo
`document_writer_section`, barato por default.

## Verificado

- `.venv/bin/python -m pytest -q` — 1679/1679 (1665 previos + 14 nuevos en `tests/test_document_writer.py`:
  rechaza lista de secciones vacía, escribe+verifica la primera sección en la misma llamada, avanza una
  sección por `continue_write`, es no-op sobre un documento ya completo, `write_id` desconocido devuelve
  error, `status()` nunca avanza ni escribe, el estado sobrevive una instancia de `DocumentWriter`
  completamente nueva sobre el mismo disco (simula reanudar tras un corte real), namespacing real por
  usuario, una falla de generación nunca escribe nada a Notion y termina `failed` tras agotar intentos,
  sin `llm_factory` igual de honesto, una falla de `append_to_page` reintenta sin duplicar y termina
  `failed`, una falla de lectura de verificación NUNCA reintenta el append y termina `unverified`, un
  desajuste de verificación que se resuelve en una lectura posterior queda `verified` sin volver a
  escribir, y el prompt de una sección nunca incluye el contenido completo de secciones anteriores, solo
  sus títulos) — más cobertura completa en
  `tests/test_brain.py`/`tests/test_verbs.py`/`tests/test_telemetry_detail.py`/`tests/test_llm_routing.py`.
- No verificado en vivo contra una página real de Notion del fundador — sin caso de uso real todavía que
  lo dispare en producción, mismo estado que D2/D3.

## Consecuencias

- Fase D5 (integración capstone) puede encadenar `executive_team_run` (D3, produce el plan de secciones
  aprobado) → `document_write_start`/`continue` (D4, lo escribe verificado) como el escenario real que
  motivó todo Track D.
- Pendiente real, sin resolver acá: ninguna superficie de UI para ver el progreso de una escritura en
  curso (solo tools conversacionales por ahora, mismo criterio ya aplicado en B1/A4/D2/D3).
- La generalización "por destino" pedida en el plan original queda explícitamente diferida — cualquier
  sesión futura que agregue un segundo backend real debe revisar si el contrato actual de `DocumentWriter`
  (acoplado a los métodos de Notion) alcanza o necesita una interfaz nueva.
