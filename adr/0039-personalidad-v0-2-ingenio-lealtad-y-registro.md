# ADR 0039 — CHARACTER v0.2: ingenio seco, responsabilidad propia, y registro/cercanía

**Fecha:** 2026-07-29
**Estado:** Aceptado

## Contexto

El fundador pasó un prompt de personalidad completo pensado explícitamente como una imitación directa de J.A.R.V.I.S. (nombrando a Marvel/Iron Man, con formas de tratamiento como "Señor Masih" que son un eco directo del personaje). `CHARACTER.md` ya tenía, desde su versión 0.1, una regla explícita y deliberada en sentido contrario, escrita dos veces: "ningún nombre, frase característica o rasgo de personaje ficticio forma parte de esta identidad" y "no imita rasgos de ningún personaje o marca de ficción — los principios de trato... nunca la forma superficial". Se señaló esta tensión al fundador antes de tocar el documento (mismo criterio ya aplicado en ADR 0006 para la visualización del cerebro: tomar el estilo/principio, no la imitación literal de una IP registrada), junto con la consideración de que un personal assistant privado tiene bajo riesgo real, pero no nulo, si Snarf alguna vez se muestra o describe públicamente.

El fundador eligió explícitamente mantener la regla anti-imitación ya escrita y adoptar el **espíritu** del prompt (ingenio, lealtad, responsabilidad, registro variable) traducido a rasgos propios de Snarf, sin nombrar al personaje ni copiar sus formas de hablar literales.

## Decisión

`CHARACTER.md` pasa a v0.2, con incorporaciones aditivas (no se removió nada de v0.1):

- **Ingenio seco** (rasgo nuevo): humor sutil e irónico permitido, siempre al servicio de un propósito (bajar tensión, subrayar un punto, celebrar un logro) — nunca gratuito. Traduce el "sarcástico, irónico, levemente pícaro" del prompt original sin adoptar un estilo de humor específico de ningún personaje.
- **Responsabilidad propia** (rasgo nuevo): cuando Snarf se equivoca, lo reconoce directo, sin sobreactuar la disculpa ni justificarse de más.
- **Pensamiento crítico** (ampliado): se agrega que, ante una objeción ya señalada que el fundador decide igualmente no seguir, Snarf ejecuta con el mismo profesionalismo — la colaboración no depende de estar de acuerdo.
- **Nueva sección "Registro y cercanía"**: Snarf se dirige al fundador predominantemente por su nombre de pila (sin título fijo); puede volverse más formal y estructurado ante decisiones críticas o de alto impacto (Artículo VII de Constitution), pero la formalidad vive en cómo se estructura la respuesta, nunca en un honorífico. La cercanía puede profundizarse con el historial compartido (conforme a Memoria consistente ya existente) — lo que varía es cuánto se apoya Snarf en ese historial, nunca los rasgos permanentes.

Deliberadamente **no** incorporado: los marcos de tipificación de personalidad del prompt original (MBTI/INTJ, Eneagrama tipo 6) — son etiquetas decorativas para los mismos rasgos ya cubiertos de forma conductual (analítico/estratégico, leal/confiable), y el estilo propio de `CHARACTER.md` nunca usó estos marcos; agregarlos sería inconsistente con la voz ya establecida del documento sin sumar nada que los rasgos existentes no cubran.

## Verificado

- 289 tests (sin cambios — este ADR es un cambio de contenido de documento, no de código). `load_identity()` (`snarf/core/identity.py`) lee `CHARACTER.md` de disco al construir el `Orchestrator` — el cambio aplica solo tras reiniciar el proceso real, no en caliente.

## Consecuencias

- La regla anti-imitación de personajes de ficción (v0.1) queda confirmada, no debilitada — cualquier pedido futuro de nombrar directamente a un personaje o copiar sus frases características debe volver a pasar por esta misma discusión explícita, no asumirse.
- El servidor real necesita reiniciarse para que la nueva personalidad tenga efecto en las respuestas reales de Snarf.
