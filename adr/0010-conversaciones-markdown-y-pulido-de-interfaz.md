# ADR 0010 — Conversaciones persistentes, formato Markdown y pulido de interfaz

**Fecha:** 2026-07-25
**Estado:** Aceptado

## Contexto

El fundador pidió, en esta iteración: (a) que las respuestas de Snarf lleguen formateadas (encabezados, listas, negrita, citas) en vez de un bloque de texto plano; (b) reducir la prominencia visual del selector de modo; (c) una barra lateral desplegable para listar y retomar conversaciones anteriores, incluso desde otro dispositivo; (d) explícitamente pospuso la posibilidad de que Snarf converse consigo mismo/con Claude Code para automodificarse — se deja registrado como pendiente futuro, no se implementa todavía.

## Decisión

1. **Conversaciones como unidad de primer orden en memoria.** `EpisodicMemory` ahora etiqueta cada entrada con un `conversation_id` opcional, y agrega `list_conversations()` (agrupa por id, con título derivado del primer mensaje y fecha de última actividad) y `get_conversation(id)`. El log sigue siendo append-only; agrupar por conversación es una lectura derivada, no una reestructuración del archivo.
2. `Orchestrator.handle` acepta `conversation_id` y limita el contexto de memoria reciente a esa conversación (antes mezclaba todo el historial global). `main.py` (canales de terminal) sigue funcionando sin pasar este parámetro — comportamiento previo intacto.
3. Nuevos endpoints en `app.py`: `GET /conversations`, `GET /conversations/{id}`. `POST /send` ahora acepta `conversation_id`. No se agregó un endpoint para "crear" conversación: el id se genera en el navegador (`crypto.randomUUID()`) y una conversación simplemente empieza a existir en la lista la primera vez que tiene un mensaje.
4. **Multidispositivo por diseño, no por sincronización.** Como Mac e iPhone hablan con el mismo backend (vía Tailscale), listar y retomar conversaciones ya funciona igual desde cualquier dispositivo sin ningún mecanismo adicional — es consecuencia directa de que el estado vive en el servidor, no en cada navegador.
5. **Formato de respuesta.** El prompt de sistema del Orchestrator ahora instruye a Snarf a usar Markdown cuando la respuesta se beneficia de estructura, y a mantenerse en texto simple para respuestas conversacionales cortas — no fuerza estructura siempre. El frontend incorpora un renderer de Markdown propio y liviano (encabezados, negrita, itálica, listas, citas, código inline y en bloque) aplicado solo a los mensajes de Snarf; los mensajes del usuario se muestran como texto plano.
6. **Interfaz:** el selector de modo pasó de dos botones prominentes a un único texto pequeño y de bajo contraste que alterna al tocarlo. Se agregó un indicador de "escribiendo" (tres puntos animados) mientras se espera la respuesta, en vez de solo cambiar el texto de estado. Nueva barra lateral (ícono ☰, esquina superior izquierda) con lista de conversaciones ordenadas por actividad reciente y un botón para iniciar una nueva.

## Pospuesto explícitamente

Conversar con Snarf para que se automodifique a sí mismo (editar su propio código o documentos a través de la conversación) — el fundador pidió terminar primero interfaz y funcionamiento base. Queda anotado en MASTER_MAP como capacidad futura, no como algo perdido u olvidado.

## Consecuencias

- El archivo de memoria mezcla entradas con y sin `conversation_id` (las de sesiones de terminal y las pruebas anteriores a este ADR). `list_conversations()` ignora las que no tienen id, por diseño — no rompen nada, simplemente no aparecen en la barra lateral.
- Verificado por API: creación implícita de conversación, listado, recuperación de mensajes, y una respuesta real formateada en Markdown (encabezado + lista) generada por el modelo. No verificado visualmente en navegador (renderer de Markdown, barra lateral, animaciones) — pendiente de confirmación del fundador.
