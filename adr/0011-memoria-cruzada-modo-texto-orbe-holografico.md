# ADR 0011 — Memoria cruzada entre conversaciones, modo de texto y orbe holográfico

**Fecha:** 2026-07-25
**Estado:** Aceptado

## Contexto

Tras agregar la barra lateral de conversaciones (ADR 0010), el fundador notó que Snarf no podía recordar contenido de una conversación distinta a la actual — cada conversación estaba aislada. Pidió además un modo de texto simple (sin voz) y que el orbe se sienta menos sólido, más holográfico, en la línea estética de JARVIS sin copiar el diseño.

## Decisión

### Memoria cruzada entre conversaciones

Se le dieron a Snarf tres herramientas (tool-use de la API de Anthropic), definidas y resueltas en `Orchestrator`, nunca en la Capacidad `AnthropicLLM` (que solo ejecuta el protocolo de llamada a herramientas de forma genérica, sin saber qué significan):

- `list_conversations`: qué conversaciones existen.
- `get_conversation`: contenido completo de una conversación dada.
- `search_memory`: búsqueda por texto en todo el historial (`EpisodicMemory.search`, nueva, búsqueda simple por substring — no semántica todavía, consistente con lo ya anotado en COGNITION.md: un mecanismo más sofisticado solo se justifica cuando el volumen deje de ser manejable así).

El prompt de sistema instruye a Snarf a usar estas herramientas cuando le preguntan por algo de otra conversación, cuando falta contexto, o cuando genuinamente cree que ayuda — no de forma automática siempre. `AnthropicLLM.generate` ahora implementa el loop mecánico de tool-use (llamar, si pide una herramienta ejecutar el handler inyectado y volver a llamar, hasta obtener una respuesta final o un tope de rondas).

Verificado con un caso real: un dato mencionado en una conversación fue recuperado correctamente al preguntarlo desde una conversación distinta, sin dar contexto adicional.

### Modo de texto

Tercer modo en el mismo selector (antes dos: click/click, mantener presionado). En modo texto se oculta el orbe y aparece un campo de texto con botón enviar; Enter también envía. El foco se pone en el campo al activar el modo, lo que en un teléfono despliega el teclado automáticamente por ser resultado directo de un gesto del usuario.

### Orbe holográfico

Se reemplazó el relleno sólido del orbe por un degradé tipo "fresnel" (transparente al centro, brillo concentrado en el borde) y se agregaron seis anillos de wireframe rotados en 3D (`rotateX`/`rotateY` con `perspective`) simulando líneas de latitud/longitud de un globo, más una animación de parpadeo sutil e irregular. Los anillos exteriores y rayos ya existentes (ADR 0007) se mantienen sin cambios.

## Consecuencias

- El costo de cada respuesta puede incluir ahora varias llamadas a la API (una por ronda de herramienta), no solo una — aceptable a esta escala, a revisar si el volumen de conversaciones crece mucho.
- `search_memory` es búsqueda literal por texto, no semántica; preguntas parafraseadas sobre un tema pasado pueden no encontrar coincidencias si no comparten palabras. Limitación conocida, no resuelta aquí.
- Verificado por API (memoria cruzada) y por lectura de código (modo de texto, orbe) — no verificado visualmente en navegador real por el fundador todavía.
