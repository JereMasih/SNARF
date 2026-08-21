# ADR 0179 — Second Brain de Notion + confiabilidad del Orchestrator: evolución del mapa

**Fecha:** 2026-08-20
**Estado:** Aceptado

## Contexto

El fundador usa Notion como su lugar único de notas, documentos y recursos de referencia por proyecto,
organizado con databases propias al estilo PARA (Áreas/Proyectos/Recursos/Archivo). Snarf ya puede leer y
editar partes de ese Notion (bloques, celdas de tabla, properties, ADR 0075/0115/0173/0175/0176) y tiene
indexado semántico real funcionando (ADR 0173), pero el CRUD está incompleto (no puede mover páginas entre
databases, crear databases nuevas, cambiar cover/icon, ni archivar), el indexado es on-demand nunca
proactivo, los Proyectos de Snarf y los Proyectos de Notion son dos mundos sin vínculo, no existe ninguna
jerarquía de Área en la UI de Snarf, y Notion es una integración global (una sola cuenta) mientras el
fundador quiere ofrecer "conectá tu Notion" como parte de un plan pago — lo cual exige multi-usuario real.

En la misma conversación, el fundador pidió también resolver un problema más profundo y separado: hoy no
puede confiar en que el Orchestrator entienda bien un pedido complejo, convoque al equipo correcto, itere
un plan hasta uno bueno, y lo escriba completo sin cortarse por límites de tokens/RAM/fallas de API.
Investigado el código: no existe hoy ningún supervisor periódico sobre el fundador (ánimo, financiero),
ningún mecanismo de "equipo" multi-agente que itere/apruebe internamente (el Executive Board actual,
ADR 0093/0094/0098, es de una sola ronda, solo lectura, sin visibilidad entre roles, nunca decide nada), y
ninguna escritura incremental/verificada de documentos largos (`create_page`/`append_to_page` mandan todo
en una sola llamada HTTP, sin batching ni verificación). El fundador decidió explícitamente incluir ambos
frentes en el mismo plan grande, en vez de separarlos en dos.

Tres decisiones de alcance las tomó el fundador directamente y no se reabren en este ADR ni en los
siguientes de este plan:

1. Un solo plan, Notion Second Brain + confiabilidad del Orchestrator van juntos.
2. La palabra "Área" se reusa para el nivel superior de la jerarquía de Notion, aceptando la colisión
   conceptual con `snarf/runtime/areas.py` (4 categorías fijas de ruteo interno, ADR 0165) — se documenta
   la diferencia, no se renombra nada existente.
3. Multi-usuario desde el diseño, no como migración posterior — porque el plan de negocio es "conectá tu
   Notion con el plan de $10".

El plan completo (5 tracks, 22 fases, cada una con su propio ADR/CHANGELOG/tests) vive en
`ROADMAP_SECOND_BRAIN_NOTION.md`, en el repo y no solo en `~/.claude/plans/` — hay precedente real
documentado de una sesión que no pudo recuperar un plan guardado solo ahí (ver
`ROADMAP_OBSERVABILIDAD_MULTIUSUARIO_N8N.md`, cabecera).

## Decisión

**Esta primera fase (D1 del roadmap) es puramente documental, sin código.** La Regla de crecimiento de
`MASTER_MAP.md` ("si un nuevo elemento no encuentra lugar dentro del mapa, primero deberá evolucionar el
mapa y después incorporarse el nuevo elemento") aplica directamente: el resto del plan introduce conceptos
que hoy no tienen lugar — la jerarquía Área/Proyecto/Recursos/Archivo de Notion, supervisores periódicos, un
mecanismo de "equipo" multi-agente, y escritura confiable de documentos — así que el mapa evoluciona
primero, siguiendo el mismo patrón que ADR 0094 usó para activar la Inteligencia Ejecutiva antes de que
existiera código.

**`MASTER_MAP.md`, dominio Knowledge:**
- Describe el Second Brain de Notion como jerarquía dentro del namespace ya indexado (`personal`/`notion`,
  ADR 0173) — un nivel de organización *dentro* de Knowledge, no un dominio nuevo de Chroma.
- Documenta con claridad la colisión de "Área": "Área de ruteo" (`snarf/runtime/areas.py`, ADR 0165, 4
  valores fijos, interno, invisible al fundador) vs. "Área de Notion / Second Brain"
  (`snarf/specialists/second_brain.py`, planificado, nivel jerárquico visible y editado por el fundador,
  cantidad arbitraria). Explícito: no se renombra nada existente, es una decisión aceptada del fundador.

**`MASTER_MAP.md`, dominio Capabilities:** anota la futura generalización de `DocumentBuilder`/
`DocumentPublisher` (ADR 0030) hacia escritura confiable e incremental de documentos largos — sección por
sección, verificada leyendo de vuelta, con estado reanudable en disco — sin construir todavía.

**`MASTER_MAP.md`, dominio Roadmaps:** agrega `ROADMAP_SECOND_BRAIN_NOTION.md` como segundo plan vivo en
curso, en paralelo al de observabilidad/multi-usuario — no lo contradice ni lo reemplaza, se apoya en su
multi-usuario real ya construido (login Google, Orchestrator por `user_id`) para la Fase B de este plan
nuevo (OAuth de Notion por usuario).

**`COGNITION.md`:**
- Activa el slot reservado `FOUNDER_MODEL` (hasta hoy solo un nombre en una lista, sin documento ni
  código) — describe un supervisor periódico planificado de ánimo/estado del fundador, con la misma
  disciplina de honestidad que ya rige a la Inteligencia Ejecutiva (etiqueta `basis`, `hecho` exige
  evidencia textual citable, nunca inventar un estado de ánimo sin fuente real).
- Nueva sección "Equipos de agentes", bajo "Especialistas de proceso separado": extensión planificada del
  board de 7 roles — a diferencia del board (una sola ronda, solo lectura, nunca decide), un equipo itera
  con crítica cruzada, converge a una aprobación interna, y puede producir un artefacto real (no solo
  opiniones etiquetadas) — pero nunca ejecuta una herramienta mutante directamente, el artefacto vuelve a
  Snarf igual que cualquier Especialista. Reusa la primitiva de stages ya real de `snarf/executive/`
  (`agent_graph_registry`, `consult_role(upstream_context=...)`, ADR 0157/0158) en vez de duplicar
  infraestructura.

**`ROADMAP_SECOND_BRAIN_NOTION.md` (nuevo):** copia autoritativa y versionada del plan completo, con
sección "Estado actual" al tope y protocolo de cierre de sesión, mismo patrón que
`ROADMAP_OBSERVABILIDAD_MULTIUSUARIO_N8N.md`. Indexado desde `CLAUDE.md`.

## Verificado

- Fase puramente documental — no hay código nuevo que testear. `.venv/bin/python -m pytest -q` corrido
  igual, sin cambios de conteo respecto al ADR anterior (0178, 1531/1531).

## Consecuencias

- Fase A1 (gaps de capability en `snarf/capabilities/notion.py`) y Fase C1 (decisión de UX del árbol de
  drilldown) quedan desbloqueadas para arrancar en paralelo, sin dependencia de esta fase salvo la
  numeración de ADR ya reservada (0180-0200, ver tabla de orden de ejecución en el roadmap).
- La colisión de nombre "Área" queda documentada pero no resuelta de ninguna otra forma — cualquier sesión
  futura que toque código con esa palabra debe verificar de cuál de los dos conceptos está hablando el
  contexto antes de asumir.
