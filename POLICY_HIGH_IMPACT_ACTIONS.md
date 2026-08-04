# POLÍTICA — Acciones de Alto Impacto

## Primera Política real del proyecto

**Versión:** 1.0
**Fecha:** 2026-08-04
**Nivel:** Política (Governance), subordinada a Constitution — ver CONSTITUTION.md, Artículo I (jerarquía) y Artículo IX (las Políticas se actualizan con menor fricción que la Constitution misma, sin necesidad de reabrirla).

---

# Propósito

CONSTITUTION.md Artículo VII fija un criterio — no una lista — para qué acción requiere autoridad directa del fundador: irreversible, con exposición externa (financiera, legal o reputacional), o que altere el registro histórico/canónico. El propio Artículo VII anticipa que esta lista de ejemplos concretos debe vivir en una Política viva, no en el texto constitucional, "precisamente porque nuevas categorías de acción de alto impacto van a aparecer con el tiempo."

MASTER_MAP.md señalaba este hueco desde su primera versión (Governance: "Políticas — posturas operativas revisables... no se crean todavía por no existir contenido real que las justifique"). La expansión de Snarf con Inteligencia Ejecutiva, Skill Factory y las ramas nuevas de capacidades (Finance, Community, etc. — ver ADR 0093/0094/0095 y el plan de expansión de 2026-08-04) introduce la primera categoría real de acciones que necesita esta claridad.

# Acciones ya cubiertas por el mecanismo existente (sin cambios)

El protocolo de confirmación en dos pasos de ADR 0015 ya gatea, desde antes de esta Política: enviar un email (`gmail_send_message`), eliminar un archivo de Drive (`drive_delete_file`), crear/eliminar un calendario, mover/eliminar un evento, eliminar una etiqueta de Gmail, compartir/actualizar un documento, y las demás herramientas listadas como `HIGH_IMPACT_TOOLS` en `snarf/core/orchestrator.py`. Esta Política no las reabre — las nombra acá solo para que la tabla de abajo se lea completa.

# Acciones nuevas, introducidas por la expansión de 2026-08-04

| Acción | ¿Requiere confirmación de Art. VII? | Por qué |
|---|---|---|
| Leer/categorizar transacciones ya provistas por el fundador, calcular P&L/impuestos sobre ellas, generar el reporte | **No** | Competencia operativa ordinaria (Constitution Art. III, cláusula residual) — lectura y análisis sobre datos ya entregados, sin exposición externa nueva |
| Conectar una cuenta bancaria/financiera real nueva (ej. upgrade futuro a Plaid) | **Sí** | Expone al fundador financieramente — mismo criterio que cualquier credencial externa nueva |
| Postear un mensaje en Discord/comunidad en nombre del fundador o de la marca | **Sí** | Exposición reputacional externa — mismo criterio que `gmail_send_message` |
| Buscar en la web (Tavily), indexar un resultado en la Knowledge Layer | **No** | Lectura, sin exposición externa ni alteración de nada fuera del índice propio de Snarf |
| Construir y activar una skill nueva vía Claude Code (Skill Factory, ADR 0095) | **Sí** — protocolo propio de **dos** confirmaciones (construir, luego activar) | Modifica el código vivo del Orchestrator — irreversible en el sentido de Art. VII hasta que se revierte a mano; ver ADR 0095 para el diseño completo |
| Generar un borrador de propuesta/pitch/scope-of-work (Agency, Sales) | **No** | Es un borrador que el fundador revisa; enviarlo o presentarlo a un tercero sí requeriría confirmación, generarlo no |
| Un rol de Inteligencia Ejecutiva emite una opinión/asesoría | **No** | Nunca ejecuta nada — su única competencia es lectura vía el allowlist MCP (ADR 0094); no hay acción que confirmar |

# Cómo se actualiza esta Política

Cada categoría nueva de acción de alto impacto que aparezca al construir una rama nueva de capacidades se suma a la tabla de arriba, con su propio "por qué" — sin necesidad de reabrir Constitution ni de una ADR nueva salvo que el caso sea genuinamente ambiguo bajo el criterio del Artículo VII (en ese caso sí corresponde una ADR, conforme al Artículo VI de Constitution — Reserva Interpretativa). Toda actualización de esta Política es en sí misma un precedente y se registra en CHANGELOG.md, conforme al Artículo VIII de Constitution.
