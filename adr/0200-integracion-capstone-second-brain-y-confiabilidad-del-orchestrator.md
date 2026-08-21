# ADR 0200 — Integración capstone: Second Brain y confiabilidad del Orchestrator

**Fecha:** 2026-08-21
**Estado:** Aceptado

## Contexto

Fase D5, última fase de `ROADMAP_SECOND_BRAIN_NOTION.md` (ver ADR 0179) — cierra el plan completo de 22
fases que arrancó como un solo pedido combinado: Notion como Second Brain del fundador, y confiabilidad
real del Orchestrator (entender bien un pedido complejo, convocar al equipo correcto, iterar un plan hasta
uno bueno, escribirlo completo sin cortarse). Track D construyó las 3 piezas necesarias por separado:
supervisores periódicos (D2/ADR 0197, contexto real de estado financiero/de ánimo), un mecanismo de equipo
que itera y aprueba internamente (D3/ADR 0198), y escritura confiable de documentos largos (D4/ADR 0199).
D5 es, por diseño del plan original, "fase de integración pura, sin componentes nuevos grandes" — conecta
lo que ya existe en el escenario real que motivó todo el pedido, no construye nada nuevo de peso.

**Gap real encontrado al integrar, no anticipado en el detalle del plan original**: `TeamSession.run()`
devuelve un `draft` en texto libre — no hay ningún contrato estructurado entre lo que el equipo aprueba y
lo que `document_write_start` espera (`sections: [{title, brief}]`). Se evaluaron dos caminos: (a) un
parser de código nuevo que extraiga secciones de un formato de borrador fijo, o (b) dejar que el propio
Orchestrator (la LLM de Snarf, ya en el loop de herramientas) lea el `draft` de texto y arme el array
`sections` en su propia siguiente llamada a `document_write_start` — el mismo tipo de puente que ya hace
sin ayuda entre cualquier par de tools encadenadas (ej. `notion_search` → `notion_read_page` con el
`page_id` que encontró). Se eligió (b): no se construyó ningún parser nuevo en `snarf/specialists/`. Un
parser de código sería más frágil (un formato de borrador que cambia rompe el parser) y una abstracción
sin necesidad real — la LLM ya resuelve esto mejor de lo que resolvería un regex. Se guio explícitamente
al equipo, vía el `objective` que le pasa el Orchestrator, a devolver un PLAN de secciones (título + brief
corto por línea) en vez del documento redactado entero — evita además la tensión de que el propio borrador
del equipo (una sola llamada de LLM, `TeamSession._generate_draft`) reintroduzca el límite de tokens que
D4 existe para evitar.

## Decisión

**Sin código de "integración" nuevo en `snarf/specialists/`** — las 3 piezas de Track D ya componen
correctamente a través del propio loop de herramientas del Orchestrator, sin necesitar wiring nuevo entre
ellas. La integración real está en:

1. **Guía nueva en el system prompt del Orchestrator** (`SYSTEM_PREFIX`, `snarf/core/orchestrator.py`):
   un párrafo para `executive_team_run` que instruye pedir un PLAN de secciones (no el documento entero)
   cuando el objetivo es planear un documento largo, y sumar los snapshots de los supervisores (D2) como
   contexto real del `objective` cuando sea relevante (ej. una restricción de presupuesto real). Un
   párrafo para `document_write_start`/`continue`/`status` que explica el flujo completo: conseguir el
   `page_id` real (nunca inventado), escribir/verificar sección por sección, nunca declarar "listo" si
   `sections_stuck` no viene vacío, y que el progreso persistido permite retomar en una conversación
   distinta si la actual se corta.
2. **Test de integración real** (`tests/test_document_capstone_integration.py`, nuevo): ejercita la cadena
   completa con fakes — `TeamSession.run()` converge en un plan de secciones, se parsea (reproduciendo lo
   que hace el Orchestrator real, sin ningún parser de producción) y se le pasa directo a
   `DocumentWriter.start()`/`continue_write()` hasta `completed=true`, confirmando que el `objective` real
   del equipo efectivamente llega al contexto de cada sección generada — la prueba de que las dos piezas
   construidas por separado en D3/D4 encajan de verdad, no solo en teoría. Un segundo test confirma que un
   plan `approved_by_exhaustion=true` (sin consenso real del equipo) igual fluye por el pipeline sin
   ocultarlo — la responsabilidad de avisarle al fundador que no hubo consenso real quedó en la guía del
   system prompt del Orchestrator, no en un chequeo de código en `DocumentWriter` (que no tiene por qué
   conocer ese concepto de "aprobado por agotamiento", es una propiedad de `TeamSession`).

**Honestidad explícita, no resuelta acá**: no hubo corrida real end-to-end contra el Notion del fundador
con un documento de prueba chico (lo que el plan original llamaba "idealmente" para esta fase, mismo
criterio que el piloto real de ADR 0028) — Claude Code, en este entorno, no tiene acceso directo a las
tools reales de Snarf en producción para ejecutar ese piloto; y el Second Brain del fundador tampoco está
conectado en vivo todavía (bloqueo real ya documentado desde B1: falta el registro manual de la
integración pública en el panel de developers de Notion). Queda como el primer uso real recomendado en
cuanto ese bloqueo se resuelva.

## Verificado

- `.venv/bin/python -m pytest -q` — 1681/1681 (1679 previos + 2 nuevos en
  `tests/test_document_capstone_integration.py`: un plan de secciones aprobado por un equipo real
  (fakeado) alimenta directo una escritura de documento verificada de punta a punta, y un plan aprobado
  por agotamiento de rondas fluye por el mismo pipeline sin que nada lo oculte).
- No verificado en vivo contra Notion real — ver "Honestidad explícita" arriba.
- **Bug real encontrado y corregido antes de cerrar la fase**: los dos tests de
  `tests/test_document_capstone_integration.py` construían `DocumentWriter` sin `monkeypatch.chdir` a un
  `tmp_path` — como `DocumentWriter` usa la ruta relativa `data/document_writes/` por defecto, cada
  corrida de la suite escribía archivos reales dentro del repo (`data/document_writes/fundador/*.json`),
  aunque con contenido de prueba, nunca datos reales del fundador. Corregido agregando el mismo
  `monkeypatch.chdir(tmp_path)` que ya usa `tests/test_document_writer.py`; los archivos ya escritos se
  borraron. De paso, `data/second_brain/`, `data/finance_supervisor/`, `data/founder_mood/`,
  `data/document_writes/` y `data/bug_reports/` (esta última ya existía sin cubrir, gap de ADR 0178) se
  agregaron a `.gitignore` — ninguno de los directorios de datos por usuario nuevos de este plan estaba
  cubierto.

## Consecuencias

- **Cierra Track D completo** (D1-D5) y el plan de 22 fases de `ROADMAP_SECOND_BRAIN_NOTION.md` en su
  totalidad, de código. Quedan 3 fases de Track E (widgets Jarvis del HUD, ADR 0194-0196) explícitamente
  pendientes — bloqueadas desde su primera tarea real (E1 necesita inspeccionar el Notion real del
  fundador antes de diseñar los widgets a ciegas), documentado desde A4.
- El bloqueo real que atraviesa todo el plan sigue siendo el mismo desde B1: el fundador tiene que
  registrar la integración pública de Snarf en el panel de developers de Notion
  (`NOTION_OAUTH_CLIENT_ID`/`NOTION_OAUTH_CLIENT_SECRET` reales) antes de que CUALQUIER parte del Second
  Brain (Track A/B/C/D/E) pueda verificarse en vivo — todo lo construido hasta acá es código real,
  testeado con fakes, nunca ejercitado contra el Notion real de nadie.
- Primer uso real recomendado, una vez resuelto ese bloqueo: un documento chico y de bajo riesgo, para
  confirmar en producción lo que estos tests ya confirman con fakes.
