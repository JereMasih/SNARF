# ADR 0156 — Gobernanza n8n: escritura autónoma vs. escritura confirmada por el fundador en vivo

**Fecha:** 2026-08-12
**Estado:** Aceptado

## Contexto

ADR 0093/ADR 0139 fijaron un principio repetido desde entonces en este repo: "n8n observa y propone, nunca
decide" — n8n nunca se convierte en un segundo orquestador ni contiene lógica de negocio propia. ADR 0145
ya reabrió ese principio puntualmente para una superficie acotada: n8n puede escribir directo (sin
aprobación humana) a `/n8n/prompts`/`/n8n/generation-config`, con su propio `N8N_CONTROL_TOKEN` — pero
solo texto de prompt y parámetros de generación, nunca estructura ni lógica.

El fundador probó el mapa navegable de la Fase 14 (ADR 0154) y lo encontró insuficiente: quiere poder
controlar desde n8n **toda** la construcción de un agente — no solo el texto del prompt, también qué
herramientas MCP tiene, qué modelo/ruteo usa, y cómo se conecta o secuencia con otros agentes (hoy el
Executive Board es fan-out paralelo puro, sin ningún concepto de orden entre roles). Pidió además que
cualquier modificación real muestre una confirmación explícita ("¿estás seguro que querés hacer este
cambio?") antes de aplicarse. Y planteó, en sus palabras, que si algún documento fundacional tiene puesto
algo que le impida a él, como fundador, modificar lo que sea que quiera de Snarf vía una plataforma como
n8n, esa cláusula está mal y hay que corregirla.

**Esta ADR no borra el principio "n8n observa y propone, nunca decide".** Lo que hace es una distinción
que ese principio nunca había necesitado hacer explícita: ninguna decisión de gobernanza anterior de este
repo evaluó el caso de un humano real (el propio fundador) operando la UI de n8n en vivo, con
confirmación en el momento — todas asumían n8n como agente autónomo/de máquina (un flujo disparado por un
webhook, un token de servicio sin sesión detrás). El Artículo II de Constitution reserva al fundador "el
derecho exclusivo e indelegable de... resolver lo que ningún documento resuelve" — este es exactamente ese
caso: una situación que ADR 0093/0139/0145 no habían contemplado, no una que hubieran prohibido a
propósito.

## Decisión

Se establecen dos categorías, antes indistinguibles bajo el mismo principio:

**(a) Escritura autónoma — sin humano en el momento.** El caso ya cubierto por ADR 0145:
`/n8n/prompts`/`/n8n/generation-config`, disparado por cualquier flujo de n8n con su propio token, sin que
nadie confirme nada en vivo. **Sigue exactamente acotada como está** — solo texto/config, nunca estructura
de agente ni lógica de negocio. Esta ADR no amplía esta categoría.

**(b) Escritura iniciada y confirmada por el fundador en vivo, en la UI de n8n** (categoría nueva,
autorizada por esta ADR). Cuando es el propio fundador quien, mirando la pantalla de n8n en el momento,
propone un cambio y confirma explícitamente un diff concreto antes de que se aplique — esto puede tocar
**cualquier** eje de la construcción de un agente: prompt, subset de herramientas MCP, ruteo/modelo, y
conexiones/secuencia entre roles. La razón por la que esta categoría no hereda el límite de "(a)" es que
la garantía de seguridad de "(a)" (nadie decide sin que Snarf lo audite) viene precisamente de que un
humano real está decidiendo y confirmando en el momento — el mismo criterio que Artículo VII (Prueba de
Alto Impacto) ya usa para exigir "el ejercicio directo de autoridad" en vez de una delegación general para
acciones irreversibles o de alto impacto. Una confirmación de dos pasos con diff visible en la UI de n8n
es ese ejercicio directo, aplicado a reconfiguración de agentes.

**Invariante que ninguna de las dos categorías puede tocar, y esta ADR reafirma sin cambios:**
`Orchestrator._handle_tool()` sigue siendo el único motor de ejecución real de Snarf. Ni (a) ni (b)
convierten a n8n en un segundo runtime — ambas categorías siempre escriben a un registro de estado
versionado (Fase 16, ADR 0157) que el Orchestrator/los procesos de `snarf/executive/` leen en cada
consulta real. n8n nunca ejecuta lógica de negocio por su cuenta, con o sin el fundador confirmando —
solo decide qué estado queda activo para que Snarf lo ejecute por su propio camino auditado. Esto es lo
que preserva la explicabilidad de Snarf que ADR 0093/0139 protegían, sin bloquear la autoridad real del
fundador sobre su propio sistema.

**Consentimiento en vivo, no solo un token de servicio:** la categoría (b) requiere un protocolo real de
`propose`→`apply` con un diff mostrado antes de aplicar (implementado en Fase 19, ADR 0160) — el mismo
`N8N_CONTROL_TOKEN` no alcanza por sí solo para calificar como "(b)", porque un token filtrado o un flujo
mal configurado podría disparar una escritura sin que el fundador la haya visto. La distinción real entre
(a) y (b) no es "quién tiene el token" sino "hubo una pantalla de confirmación con un diff real que
alguien miró antes de aplicar".

## Alcance de la implementación

Esta ADR fija la decisión de gobernanza; el código llega en las Fases 16-19 de
`ROADMAP_OBSERVABILIDAD_MULTIUSUARIO_N8N.md` (Agent/Capability Registry, motor de stages, generador n8n,
endpoints `propose`/`apply`), cada una con su propia ADR y su propia verificación — mismo criterio que ya
usó ADR 0093 para separar la decisión de gobernanza del servidor MCP real que se construyó después.

**Supersede parcialmente** la lectura de ADR 0093/ADR 0139/ADR 0145 que trataba "n8n nunca decide" como un
principio sin excepciones para estructura/lógica — sigue vigente para la categoría (a) tal cual está, y
para cualquier escritura de máquina sin confirmación humana en vivo. Conforme al Artículo VIII de
Constitution, ninguna de esas tres ADRs se edita en el lugar ni recibe una nota agregada — el registro de
que quedan superadas en este punto vive acá, en esta ADR nueva que las referencia explícitamente, mismo
criterio que ya usó ADR 0093 con ADR 0037 (sin tocar el archivo de 0037 en absoluto).

## Riesgo real, explícito

El riesgo de la categoría (a) no cambia (ver ADR 0145: token filtrado, mitigado con rollback real). El
riesgo nuevo que introduce la categoría (b) es que un cambio estructural (tools/routing/conexiones) tiene
más superficie de daño potencial que un cambio de texto — un `tool_subset` mal configurado podría, en
teoría, dejar a un rol del Executive Board sin ninguna herramienta útil, o una configuración de stages
circular podría colgar una consulta. Mitigación real exigida en Fase 16 (ADR 0157): toda escritura a los
registros nuevos pasa por validación dura antes de guardarse (subconjunto del allowlist general, sin
ciclos, roles existentes) — nunca confiar en que la UI de n8n por sí sola previno un estado inválido.

## Consecuencias

- La política de "n8n observa y propone, nunca decide" deja de ser un principio único y pasa a tener dos
  variantes explícitas y documentadas, en vez de una ambigüedad implícita que cada ADR nueva tenía que
  redescubrir.
- El registro vivo de esta distinción queda en `ROADMAP_OBSERVABILIDAD_MULTIUSUARIO_N8N.md` (sección
  "Fases 15-21"), no en `CLAUDE.md` ni en `COGNITION.md` — ninguno de los dos documentos tenía hasta ahora
  una sección de gobernanza n8n propia que amendar (la sección "Skills vs. MCP" de `CLAUDE.md` es sobre
  una decisión distinta: cómo se equipa a Claude Code con herramientas, no sobre qué puede escribir n8n
  en Snarf). Una sesión futura debe leer esta ADR y esa sección del roadmap, no las cuatro ADRs sueltas.
- Cualquier futura escritura n8n→Snarf debe evaluarse contra este criterio explícito (¿hay confirmación en
  vivo con diff real, o es un flujo autónomo sin humano mirando?) antes de decidir a qué categoría
  pertenece y qué límites aplican.
