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

# Memoria

La memoria episódica es un registro append-only (`data/episodic_memory.jsonl`). Nunca se edita ni se borra una entrada existente; solo se agregan nuevas. Esto implementa directamente el Principio VIII de Foundation (Continuidad: preservar evidencia y evolución, no versiones idealizadas) y el Artículo VIII de Constitution (trazabilidad e irreversibilidad).

No existe todavía memoria semántica (recuperación por relevancia sobre un conocimiento acumulado grande). Mientras el volumen de historia sea pequeño, el Core carga las últimas N entradas completas; un mecanismo de recuperación más sofisticado solo se justifica cuando ese volumen deje de ser manejable así.

# Modo sin credenciales

Si no hay una credencial de modelo de lenguaje configurada, el Core no simula una respuesta razonada: lo declara explícitamente y opera en modo de verificación estructural (eco), para no violar el Principio VI de Foundation (Honestidad Intelectual) presentando una salida como razonamiento cuando no lo es.
