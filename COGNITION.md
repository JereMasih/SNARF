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

# Memoria

La memoria episódica es un registro append-only (`data/episodic_memory.jsonl`). Nunca se edita ni se borra una entrada existente; solo se agregan nuevas. Esto implementa directamente el Principio VIII de Foundation (Continuidad: preservar evidencia y evolución, no versiones idealizadas) y el Artículo VIII de Constitution (trazabilidad e irreversibilidad).

No existe todavía memoria semántica (recuperación por relevancia sobre un conocimiento acumulado grande). Mientras el volumen de historia sea pequeño, el Core carga las últimas N entradas completas; un mecanismo de recuperación más sofisticado solo se justifica cuando ese volumen deje de ser manejable así.

# Modo sin credenciales

Si no hay una credencial de modelo de lenguaje configurada, el Core no simula una respuesta razonada: lo declara explícitamente y opera en modo de verificación estructural (eco), para no violar el Principio VI de Foundation (Honestidad Intelectual) presentando una salida como razonamiento cuando no lo es.
