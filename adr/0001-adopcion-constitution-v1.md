# ADR 0001 — Adopción de Constitution v1.0

**Fecha:** 2026-07-25
**Estado:** Aceptado

## Contexto

Architecture Review 0001 identificó vacíos de gobernanza urgentes (autoridad, sucesión, arbitraje entre principios). Un primer borrador de CONSTITUTION.md los resolvió parcialmente, pero mezclaba contenido constitucional (quién decide) con contenido operativo (cómo se ejecuta una decisión), lo que habría obligado a reabrir el documento cada vez que cambiara una circunstancia práctica.

## Decisión

Se realizó una auditoría constitucional de segundo nivel que separó explícitamente: reglas constitucionales (permanentes, sobre quién tiene poder y cómo se limita) de políticas y procedimientos (revisables, sobre qué se decide y cómo se ejecuta). Se adoptó CONSTITUTION.md v1.0 con nueve artículos: Supremacía y Jerarquía, Autoridad y Sucesión, Delegación y Competencia Residual, No Asunción de Autoridad, Autonomía y Responsabilidad No Delegable, Reserva Interpretativa, Prueba de Alto Impacto, Trazabilidad e Irreversibilidad, y Enmienda Estratificada.

## Consecuencias

- Las decisiones operativas concretas (lista de acciones de alto riesgo, protocolo de verificación de sucesión, delegado vigente) no viven en Constitution; vivirán en Políticas y Procedimientos cuando ese nivel documental se cree, justificado por contenido real.
- Hasta que ese nivel exista, esas decisiones concretas quedan registradas como precedentes en `adr/` y en CHANGELOG.md.
- Cambios futuros a Constitution requieren un nuevo "Constitution Design" numerado, nunca una edición silenciosa.
