# ADR 0105 — Fase I: rama Content

**Fecha:** 2026-08-05
**Estado:** Aceptado

## Contexto

Cuarta rama de la Fase I. El plan la marcaba "100% nueva, construible sobre `AnthropicLLM` +
`DocumentBuilder`, salvo generación de imágenes (investigado, sin decisión de vendor todavía en
`IMAGE_GENERATION_RESEARCH.md`)".

## Decisión

**`ContentSpecialist`** (`snarf/specialists/content/`): mismo patrón real "una clase, N configs" que
`ResearchSpecialist` (Fase I) y `ExecutiveRoleConfig` (Fase E) — `blog_post` (Sonnet, estructura
larga), `social_post` (Haiku, corto y directo), `newsletter` (Sonnet, tono personal). Redacta un
borrador vía LLM y lo publica con `DocumentPublisher` (indexado de inmediato, sin mecanismo nuevo).

Disciplina de honestidad adaptada a un caso genuinamente distinto de Research: acá el contenido es
mayormente creativo (tono, estructura, ganchos narrativos), no una síntesis de hechos — la regla
real es más angosta: si se pasa `reference_material` (datos reales sobre el fundador/su negocio),
cualquier afirmación concreta tiene que basarse ahí, nunca inventar una cifra/cliente/resultado. El
resto del texto (estilo, forma) es trabajo creativo libre, no algo que deba "citar una fuente".

Generación de imágenes queda explícitamente fuera de esta ronda — `IMAGE_GENERATION_RESEARCH.md` ya
investigó el espacio sin que el fundador haya decidido vendor; se reusa esa decisión cuando exista,
no se revisita acá.

Tres tools nuevos (`content_write_blog_post`, `content_write_social_post`,
`content_write_newsletter`), nodo nuevo `specialist_content` (misma clase real, mismo criterio que
Research/Inteligencia Ejecutiva).

## Verificado

- 6 tests nuevos: `tests/test_content_specialist.py` (5), más cobertura de orchestrator/schema (1
  explícita, el resto vía los tests de cobertura automática ya existentes).
- 864/864 tests de la suite completa.
