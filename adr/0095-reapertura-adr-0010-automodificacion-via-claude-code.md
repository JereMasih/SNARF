# ADR 0095 — Reapertura de ADR 0010: automodificación de Snarf vía Claude Code, con confirmación en dos pasos

**Fecha:** 2026-08-04
**Estado:** Aceptado

## Contexto

ADR 0010 (2026-07-25, día uno del proyecto) registró que el fundador pospuso explícitamente "que Snarf pueda conversar para automodificarse... a través de una herramienta tipo Claude Code" — el motivo registrado ahí es de secuencia, no de gobernanza: "el fundador pidió terminar primero interfaz y funcionamiento base." No hay ningún artículo de Constitution que lo prohíba.

Con más de 90 ADRs y el producto en producción real (LaunchAgent, puerto 8002), el fundador pidió explícitamente reabrir esto: quiere que la Skill Factory (ver Fase G/H del plan de expansión) quede totalmente funcional de punta a punta — Snarf pregunta si conviene construir una skill nueva, un "sí" explícito dispara la construcción real invocando a Claude Code, y Snarf puede usarla de inmediato para resolver el pedido original, en vez de solo proponerla a una cola de revisión manual.

Se revisó FOUNDATION.md y CONSTITUTION.md específicamente buscando qué lo bloquearía. No se encontró nada: Principio VI (Honestidad Intelectual) restringe qué puede afirmarse como verdadero, no qué código puede escribirse. Constitution Art. III hace de la competencia operativa la regla por defecto ("la restricción es la excepción"). Art. VII exige autoridad directa del fundador para acciones irreversibles — y una confirmación explícita, específica, caso por caso, en el momento, **es** exactamente esa autoridad directa; no es una delegación general, que es lo único que Art. VII prohíbe. Es el mismo mecanismo exacto que ya usa la confirmación en dos pasos de ADR 0015 para `gmail_send_message`/`drive_delete_file`.

## Decisión

1. **Se reabre la postergación de ADR 0010.** Esta ADR no la edita en el lugar (Constitution Art. VIII) — la supera con este registro nuevo, que referencia al anterior.
2. **No se requiere una enmienda de Constitution (Art. IX).** El texto vigente ya permite esto bajo confirmación directa caso por caso; no hace falta debilitar ni reescribir ningún artículo.
3. **El flujo real, con dos confirmaciones explícitas** (diseño completo en la Fase H del plan de expansión):
   - Snarf junta la especificación de la skill conversando con el fundador (nunca la Skill Factory habla directo — COGNITION.md sigue rigiendo).
   - **Confirmación 1 (construir):** Snarf presenta el spec y qué va a cambiar; sin un "sí" explícito, no pasa nada.
   - Una Capacidad nueva (`snarf/capabilities/claude_code.py`) invoca a Claude Code en modo headless, sobre el mismo working directory del repo, con el spec confirmado y la convención del Skill Framework (Fase G).
   - Se verifica que el diff solo tocó los archivos esperados (nunca FOUNDATION/CONSTITUTION/CHARACTER/COGNITION/MASTER_MAP, nunca código fuera del scope de la skill nueva) y que la suite completa de tests pasa.
   - **Confirmación 2 (activar):** con los tests reales en verde, Snarf pide confirmar el reinicio del server que activa la skill (mismo criterio que ya está en CLAUDE.md: "si hace falta reiniciarlo, confirmar con el fundador primero").
4. **Alcance autorizado, estrecho y nombrado.** Esta ADR autoriza únicamente: construir y activar una skill nueva siguiendo el Skill Framework, con las dos confirmaciones de arriba. Nunca autoriza editar los documentos fundacionales/de gobernanza, nunca autoriza tocar código fuera de ese flujo confirmado. Cada construcción quema su propia confirmación — no existe un "sí, siempre que quieras" que se recuerde para la próxima skill; eso sería exactamente la delegación general que Art. VII prohíbe.
5. **Registro de auditoría.** Cada intento (construido, activado, o abortado y por qué) queda en `data/skill_proposals/`, conforme al Artículo VIII de Constitution (trazabilidad).

## Alcance de la implementación

El código (`snarf/capabilities/claude_code.py`, `snarf/specialists/skill_factory.py`, los tools `skill_factory_build`/`skill_factory_status`) se construye en la Fase H del plan de expansión, después de que el Skill Framework (Fase G) exista. Esta ADR fija el modelo de autoridad; se verifica en vivo con una skill real y chica al implementarlo.

## Consecuencias

- Primera capacidad de este repo donde Snarf participa en modificar su propio código vivo — con un límite estructural explícito (dos confirmaciones, diff acotado, tests obligatorios, reinicio confirmado) en vez de autonomía abierta.
- `POLICY_HIGH_IMPACT_ACTIONS.md` (nueva, ver Fase B del plan de expansión) registra "construir y activar una skill nueva" como acción que siempre requiere confirmación de Art. VII — consistente con el punto 4 de esta decisión.
- Si en el futuro se pide que un rol de Inteligencia Ejecutiva o la propia Skill Factory puedan crear/modificar *otros* agentes más allá de este flujo (Track B de ADR 0091, en su forma más amplia), eso sigue siendo una iniciativa aparte, con su propio plan de gobernanza — esta ADR no lo autoriza.
