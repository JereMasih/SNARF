# ADR 0094 — Inteligencia Ejecutiva: modelo de autoridad y disciplina de honestidad

**Fecha:** 2026-08-04
**Estado:** Aceptado

## Contexto

El fundador pidió una "Inteligencia Ejecutiva": un board asesor de 7 roles (CEO, CTO, CFO, CMO, COO, Chief Research Officer, Chief Creative Officer) que piensan, critican, revisan y priorizan — nunca ejecutan herramientas por su cuenta — y cuyas opiniones Snarf integra en su propia voz. Es, en palabras del fundador, el verdadero diferenciador del proyecto frente al video de referencia que inspiró esta expansión.

Esto es materialmente distinto a cualquier Especialista existente hoy (`GmailDigestSpecialist`, `DashboardCuratorSpecialist`, `ProjectManager`): son 7 roles simultáneos, con opiniones potencialmente en desacuerdo entre sí, corriendo como procesos separados (ver ADR 0093). Necesita un modelo de autoridad explícito antes de escribir una sola línea de código.

Precedente directo: ADR 0091 (mismo día) registra al fundador pidiendo que el `DashboardCuratorSpecialist` pudiera "crear/modificar otros agentes." Se chequeó contra Constitution Art. III/V/VII y se dividió en Track A (proponer, nunca auto-aplicar — aceptado) y Track B (crear/modificar agentes de verdad — pospuesto explícitamente, "iniciativa aparte, con su propio plan de gobernanza"). La Inteligencia Ejecutiva, tal como la describe el fundador, es Track A: agentes que opinan, cero autoridad de ejecución.

## Decisión

1. **Cero autoridad inherente.** La única competencia de un rol ejecutivo es lectura vía un allowlist MCP curado (Fase D del plan de expansión). Es una garantía **estructural**, no una instrucción de prompt: las herramientas mutantes/de alto impacto ni existen en el proceso de un rol — es una postura de Art. VII más estricta que la que tiene el propio Orchestrator (que sí tiene esas herramientas, gateadas por confirmación).
2. **Ningún rol tiene autoridad sobre otro.** Snarf es el único sintetizador — tal cual el propio ejemplo del fundador (CEO/CFO/CMO/CTO opinan sobre abrir un canal de YouTube, Snarf integra esas opiniones). No se adopta una lectura de "el CEO preside al board"; eso reinventaría el rol de integración que COGNITION.md ya le asigna a Snarf, un nivel más abajo.
3. **Toda salida es asesoría.** Vuelve a Snarf como resultado de herramienta (`executive_board_consult`), nunca se muestra directo al fundador en el chat — misma regla de las tres capas que ya rige a todo Especialista. Única superficie donde se muestra texto crudo de un rol: un widget de dashboard, mismo precedente ya establecido para el digest de Gmail (COGNITION.md: "el dashboard es una superficie de datos, el chat es la conversación con Snarf").
4. **Disciplina de honestidad obligatoria, verificada en código.** Toda afirmación de un rol lleva una etiqueta `basis ∈ {hecho, inferencia, hipótesis, estimación, opinión}`. Una afirmación etiquetada `hecho` sin una fuente real citable (un tool del allowlist de ese rol, efectivamente llamado ese turno) se degrada mecánicamente a `inferencia` — nunca confiado al self-report del modelo. Mismo criterio que ya usa `DashboardCuratorSpecialist` con sus `node_id`: verificado con test, no con la palabra del LLM.
5. **Cualquier pedido futuro de que un rol —o la Skill Factory— cree o modifique una capacidad/especialista viva queda fuera del alcance de esta ADR.** Es su propia iniciativa Track B; ver ADR 0095 para el único caso de ese tipo que este plan sí autoriza, con su propio protocolo de confirmación.

## Alcance de la implementación

El diseño de proceso (subproceso corto por consulta, roles en paralelo sin visibilidad entre sí, base compartida + config por rol, `snarf/executive/`) se construye en la Fase E del plan de expansión. Esta ADR fija el modelo de autoridad y honestidad que ese código debe cumplir; se verifica con tests dedicados al implementarlo, no acá.

## Consecuencias

- Primer patrón de "múltiples Especialistas simultáneos, potencialmente en desacuerdo" de este repo — documentado explícitamente en vez de descubierto ad hoc al implementarlo.
- El allowlist MCP por rol (ver ADR 0093/Fase D) queda atado a esta ADR: ampliarlo para un rol es una decisión que debe volver a pasar por el mismo criterio de "agregado, nunca transacción/mensaje crudo," no un ajuste silencioso.
