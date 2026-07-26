# ADR 0018 — Gestión de eventos individuales de calendario

**Fecha:** 2026-07-25
**Estado:** Aceptado

## Contexto

El fundador reportó una contradicción aparente: Snarf decía no poder mover ni borrar un evento, mientras que el arquitecto acababa de anunciar "gestión de calendarios". Investigando: ADR 0017 agregó gestión a nivel de **calendario** (listar/crear/eliminar calendarios completos), pero nunca agregó gestión a nivel de **evento individual** dentro de un calendario (mover, borrar). Eran capacidades distintas y la comunicación no distinguió una de otra con suficiente claridad — el error fue de comunicación y de alcance incompleto, no una contradicción real ni un caso de Snarf negando algo que sí podía hacer.

Investigando el caso concreto que lo expuso, apareció además un segundo hallazgo real: el evento "Nacimiento de Snarf" sí existía, pero `calendar_list_upcoming_events` solo devuelve eventos futuros a partir del momento de la consulta — como el evento ya había pasado, la herramienta nunca lo encontraba, y Snarf concluía (de forma honesta pero incorrecta) que no existía.

## Decisión

Se agregaron a `GoogleCalendar`: `search_events` (búsqueda por texto sin restricción de fecha, incluye eventos pasados), `delete_event`, `move_event` (usa el método `events.move` de la API de Calendar, diseñado específicamente para mover un evento entre calendarios del mismo usuario). Se conectaron como herramientas: `calendar_search_events` (lectura, sin confirmación), `calendar_delete_event` y `calendar_move_event` (alto impacto, protocolo de confirmación de ADR 0015 — `move_event` se clasificó como alto impacto porque mover un evento con invitados puede disparar notificaciones a esos invitados, lo cual es exposición externa aunque el evento en sí sea del fundador).

El prompt de sistema ahora instruye explícitamente a Snarf a usar `calendar_search_events` cuando un evento no aparece en la lista de próximos eventos, en vez de concluir que no existe.

## Verificado

Se resolvió el caso real que expuso el problema, de punta a punta, a través del chat: encontrado el evento pasado "Nacimiento de Snarf" con `calendar_search_events`; borrado el evento de prueba duplicado en MATRIMONIO (confirmado explícitamente); movido "Nacimiento de Snarf" de MATRIMONIO a "El Chabon Detrás de Todo" (confirmado explícitamente). Ambas acciones verificadas independientemente contra la API real de Calendar, no solo por lo que Snarf reportó.

## Consecuencias

- Lección de proceso: al resumir qué se construyó, distinguir explícitamente el nivel de la acción (calendario completo vs. evento individual, archivo vs. carpeta, etc.) para no generar expectativas más amplias que la capacidad real.
- `calendar_list_upcoming_events` sigue sin mostrar eventos pasados por diseño (es su propósito). La mitigación es que Snarf ahora sabe recurrir a `calendar_search_events` cuando corresponde, documentado en el propio prompt de sistema.
