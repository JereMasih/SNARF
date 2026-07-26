# ADR 0015 — Confirmación en dos pasos para acciones de alto impacto

**Fecha:** 2026-07-25
**Estado:** Aceptado

## Contexto

ADR 0014 dejó `gmail_send_message` y `calendar_create_event` construidas pero sin exponer como herramientas autónomas, porque no existía un mecanismo de confirmación previo a ejecutarlas — exponerlas sin eso habría contradicho el Artículo VII de Constitution (acciones irreversibles o de exposición externa requieren autorización explícita). El fundador pidió construir ese mecanismo.

## Decisión

Se implementó un protocolo de confirmación en dos pasos, resuelto enteramente dentro de la conversación misma, sin necesidad de un componente de interfaz nuevo:

1. Ambas herramientas reciben un parámetro `confirmed` (booleano). El prompt de sistema instruye a Snarf a llamarlas **siempre** primero con `confirmed=false` (o sin el campo).
2. Si `confirmed` no es `true`, el handler del Orchestrator **no ejecuta nada real** — devuelve una vista previa estructurada de la acción propuesta (destinatario/asunto/cuerpo, o título/horario/lugar del evento) e instrucciones explícitas de mostrarla al fundador y pedir confirmación.
3. Snarf presenta esa vista previa en lenguaje natural y espera la respuesta del fundador.
4. Solo si el fundador confirma explícita e inequívocamente esa propuesta concreta, Snarf vuelve a llamar a la misma herramienta con `confirmed=true` y los mismos datos, y recién ahí se ejecuta la acción real (envío de correo o creación de evento).

No se construyó un componente visual de aprobación (botones "sí/no" en la interfaz) — la confirmación ocurre en el lenguaje natural del chat, que ya renderiza bien gracias al soporte de Markdown existente. Se prefirió esto por ser la solución más simple que cumple el requisito real, consistente con el principio de simplicidad permanente de Architecture Review 0001.

## Verificado

Flujo completo probado en vivo contra el Calendar real del fundador: (1) pedido de crear un evento, (2) Snarf pidió la fecha de hoy en vez de asumirla — comportamiento correcto de honestidad intelectual, (3) vista previa mostrada, verificado independientemente que el evento **no** existía todavía en el calendario real, (4) confirmación explícita del fundador, (5) verificado independientemente que el evento **sí** existía después, con los datos correctos.

## Limitación conocida

La barrera de confirmación depende de que el modelo siga las instrucciones del prompt de sistema fielmente — no hay un control técnico independiente del modelo que impida que, ante un error de razonamiento o una manipulación del contexto, Snarf llame a una herramienta con `confirmed=true` sin una confirmación real. Para el uso actual (un solo usuario, revisando cada respuesta) el riesgo es visible y corregible en el momento; una garantía más fuerte requeriría un mecanismo de aprobación fuera del modelo (por ejemplo, un paso de la interfaz que exija literalmente un botón, no una frase). Queda anotado como mejora futura si el uso escala más allá de un solo usuario atento.

## Consecuencias

- El mismo patrón (`confirmed` + vista previa) es el que se va a reutilizar para cualquier futura herramienta de alto impacto (por ejemplo, escribir en Drive si algún día se agrega, o acciones de Notion que modifiquen contenido).
