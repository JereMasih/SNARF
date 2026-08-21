# COGNITION

## Cómo Razona Snarf

**Versión:** 0.1
**Naturaleza:** describe el funcionamiento real implementado a la fecha, no una aspiración. Se actualiza cada vez que la arquitectura de razonamiento cambia de forma material, y ese cambio queda registrado en CHANGELOG.md y, si es estructural, en un ADR.

---

# Arquitectura de tres capas

Snarf distingue tres tipos de componentes, definidos en Architecture Review 0001 y su continuación:

- **Capacidades**: ejecutan, no razonan, no tienen identidad (ej. síntesis de voz, transcripción, acceso a APIs externas).
- **Especialistas Cognitivos**: razonan sobre un dominio acotado, con metodología y herramientas propias, pero no tienen identidad propia ni hablan directamente con el fundador.
- **Snarf**: la única identidad. Decide qué Especialistas convocar y qué Capacidades usar, integra resultados, mantiene memoria y responde.

# Estado actual (v0.1 — walking skeleton)

Hoy no existe ningún Especialista Cognitivo implementado todavía. El Core Cognitivo de Snarf razona directamente, sin enrutar a especialistas, de la siguiente manera:

1. Al iniciar, carga el contenido de FOUNDATION.md, CONSTITUTION.md y CHARACTER.md, y las últimas entradas de memoria episódica.
2. Ensambla ese contenido como contexto de identidad para una única llamada a un modelo de lenguaje (Capacidad: `AnthropicLLM`).
3. Genera una respuesta y la entrega al Runtime para su salida por el canal correspondiente.
4. Registra la interacción (entrada, salida, timestamp) en memoria episódica de forma append-only.

No existe todavía selección de Especialistas ni de Capacidades más allá del modelo de lenguaje: el punto de extensión existe en el código (`snarf/specialists/`, `snarf/capabilities/`) pero el registro está vacío. Agregar el primer Especialista real es la siguiente extensión natural de este documento, no un cambio de arquitectura.

# Primer Especialista Cognitivo real (2026-07-27, ver ADR 0025)

`GmailDigestSpecialist` (`snarf/specialists/gmail_digest.py`, dominio: `email`) es el primer Especialista implementado. Razona sobre un dominio acotado (la bandeja de entrada de Gmail): recibe los correos recientes de la Capacidad `GoogleGmail`, y con su propia metodología (un system prompt propio, distinto al de Snarf) le pide a la Capacidad `AnthropicLLM` que los agrupe por categoría y señale cuáles conviene revisar y por qué. No tiene identidad propia ni le habla directamente al fundador en el chat — su salida vuelve a Snarf como resultado de herramienta (`gmail_summarize_inbox`), y es Snarf quien decide cómo y cuándo presentarla, en su propia voz.

**Excepción explícita, y por qué está bien:** en el dashboard (no en el chat), el widget de Gmail muestra el texto del Especialista de forma directa, sin pasar por la voz de Snarf. Esto es consistente con el resto del dashboard (ADR 0022), que ya muestra datos crudos de Capacidades — asuntos de mail, nombres de archivo — sin filtrarlos por la identidad de Snarf; el dashboard es una superficie de datos, el chat es la conversación con Snarf.

**Corrección (2026-07-27, ver ADR 0026):** el refresco en segundo plano del servidor descrito originalmente aquí se eliminó a pedido del fundador — no quería que la interpretación se generara sola sin que el dashboard estuviera abierto. El refresco es ahora 100% impulsado por el navegador: se dispara al abrir el dashboard (comparando barato el id del último mensaje contra la última interpretación cacheada) y se repite cada 5 minutos solo mientras el dashboard sigue abierto y visible. Snarf puede además generarla bajo demanda si el fundador se lo pide explícitamente en el chat (`force_refresh=true` en la herramienta, o simplemente preguntando "¿qué tenemos para hoy?"). El resultado se guarda en `data/gmail_digest/<user_id>.json`.

Usa además su propia Capacidad de LLM, distinta a la de Snarf (`claude-haiku-4-5`, más barato) — categorizar correos es una tarea acotada, no necesita el modelo principal de Snarf. Un Especialista puede elegir la Capacidad de LLM que le convenga; no está atado a la de Snarf.

# Especialistas de proceso separado (2026-08-04, ver ADR 0094)

El contrato de un Especialista Cognitivo (razona sobre un dominio acotado, con metodología propia, sin identidad propia, sin hablar directamente con el fundador) no exige que corra en el mismo proceso Python que el Orchestrator — es una propiedad conceptual, no de despliegue. `GmailDigestSpecialist`/`DashboardCuratorSpecialist`/`ProjectManager` la satisfacen por llamado de método in-process; la Inteligencia Ejecutiva (`snarf/executive/`, board asesor de 7 roles — CEO/CTO/CFO/CMO/COO/Chief Research Officer/Chief Creative Officer) la satisface por un proceso separado que consulta un subconjunto curado y de solo lectura de las herramientas de Snarf vía MCP (ver ADR 0093), y devuelve su resultado a Snarf como resultado de herramienta (`executive_board_consult`) exactamente igual que cualquier otro Especialista. No es una cuarta capa: es una segunda estrategia de implementación de la misma capa ya definida en Architecture Review 0001/ADR 0003.

Los roles ejecutivos tienen cero autoridad inherente — su única competencia es lectura vía el allowlist MCP (garantía estructural: las herramientas mutantes ni existen en su proceso, no una instrucción de prompt). Ningún rol tiene autoridad sobre otro; Snarf es el único sintetizador, nunca un rol "preside" a los demás. Toda afirmación de un rol lleva una etiqueta de base real (`hecho`/`inferencia`/`hipótesis`/`estimación`/`opinión`), verificada en código — una afirmación etiquetada `hecho` sin una fuente real citable se degrada mecánicamente a `inferencia`, nunca confiada al self-report del modelo. Mismo principio que ya rige a `DashboardCuratorSpecialist`: nunca inventar un dato que no esté ahí.

## Equipos de agentes (planificado, 2026-08-20, ver ADR 0179 y `ROADMAP_SECOND_BRAIN_NOTION.md` Fase D3)

Extensión planificada del board de la sección anterior, todavía sin código. La diferencia real con el board asesor:

- El board consulta una sola ronda, en paralelo, sin visibilidad entre roles, y nunca decide nada — siempre vuelve a Snarf como opinión etiquetada. Un **equipo** convoca un subconjunto de roles con un objetivo compartido y corre varias rondas: ronda 1 produce un borrador, las siguientes son crítica cruzada (mismo formato `basis` del board) más una revisión que incorpora esa crítica, con un tope real de rondas (nunca infinito, mismo criterio que el límite de continuaciones automáticas de `AnthropicLLM`, ADR 0113).
- El board nunca decide nada por sí solo. Un equipo sí converge a una **aprobación interna** — cuando ningún rol marca una objeción bloqueante en la ronda de crítica, o al agotar el tope de rondas (declarado explícito como "aprobado por agotamiento, no por consenso real" cuando corresponda — mismo estándar de honestidad de la sección anterior).
- El board solo produce opiniones etiquetadas. Un equipo puede producir un **artefacto real** (un plan, el esqueleto de un documento) — pero nunca ejecuta directamente una herramienta mutante: el artefacto vuelve a Snarf como resultado de herramienta, igual que cualquier Especialista, y cualquier acción real que se tome a partir de él (ej. escribirlo en Notion) pasa por las tools mutantes normales con su propio gate de alto impacto.

Reusa la primitiva de stages ya real de `snarf/executive/` (`agent_graph_registry`, `consult_role(upstream_context=...)`, ADR 0157/0158) para la secuenciación y el paso de contexto entre roles, en vez de duplicar infraestructura — es una extensión del mismo mecanismo, no una cuarta capa nueva.

## Slot `FOUNDER_MODEL` (activado conceptualmente, 2026-08-20, ver ADR 0179)

Hasta hoy era solo un nombre reservado, sin documento ni código. Pasa a describir un supervisor periódico planificado (`snarf/specialists/founder_mood.py`, todavía sin construir, ver Fase D2 del roadmap citado) que interpreta señales de ánimo/estado del fundador a partir de la única fuente honesta disponible — la memoria episódica reciente, nunca una fuente inventada. Sigue la misma disciplina de honestidad que ya rige a la Inteligencia Ejecutiva: cada señal lleva su etiqueta `basis`, y `hecho` exige evidencia textual citable — es fácil que un modelo de lenguaje "invente" un estado de ánimo sin evidencia real, así que acá la disciplina de la sección anterior importa más que en cualquier otro Especialista existente. Nunca ejecuta una acción mutante por sí solo; su resultado queda disponible como contexto para Snarf y para los "Equipos de agentes" de arriba.

# Memoria

La memoria episódica es un registro append-only (`data/episodic_memory.jsonl`). Nunca se edita ni se borra una entrada existente; solo se agregan nuevas. Esto implementa directamente el Principio VIII de Foundation (Continuidad: preservar evidencia y evolución, no versiones idealizadas) y el Artículo VIII de Constitution (trazabilidad e irreversibilidad).

No existe todavía memoria semántica (recuperación por relevancia sobre un conocimiento acumulado grande). Mientras el volumen de historia sea pequeño, el Core carga las últimas N entradas completas; un mecanismo de recuperación más sofisticado solo se justifica cuando ese volumen deje de ser manejable así.

# Modo sin credenciales

Si no hay una credencial de modelo de lenguaje configurada, el Core no simula una respuesta razonada: lo declara explícitamente y opera en modo de verificación estructural (eco), para no violar el Principio VI de Foundation (Honestidad Intelectual) presentando una salida como razonamiento cuando no lo es.
