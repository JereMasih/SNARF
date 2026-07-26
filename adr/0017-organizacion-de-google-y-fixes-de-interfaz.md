# ADR 0017 — Gestión de calendarios, organización de Gmail/Drive, y fixes de interfaz

**Fecha:** 2026-07-25
**Estado:** Aceptado

## Contexto

El fundador reportó un bug real (había que refrescar el chat tras un error), pidió que la interfaz cediera más espacio al texto reduciendo la prominencia del selector de modo, señaló scroll horizontal indeseado, y pidió ampliar las Capacidades de Google para gestionar calendarios completos y organizar carpetas de Gmail/Drive.

## Bugs corregidos

1. **Estado de error sin salida en modo "mantener presionado".** `handleHoldStart` solo procedía si `state === "idle"`; un error dejaba el estado en `"error"` y no había ningún camino en ese modo para volver a intentar sin refrescar la página. Se corrigió para que cualquier interacción con el orbe, en cualquier modo, limpie un error previo y reintente en el mismo gesto.
2. **`/transcribe` fallaba con 500 crudo.** Ahora degrada con gracia: archivos de audio muy pequeños (menos de 2000 bytes, probablemente grabaciones casi vacías) y errores de la API de ElevenLabs devuelven transcript vacío en vez de una excepción sin manejar — el frontend ya sabía mostrar "no se escuchó nada, probá de nuevo" para ese caso.
3. **Scroll horizontal nuevo e indeseado.** Causa real: Snarf empezó a devolver links en formato Markdown (`[texto](url)`, por ejemplo el link a un evento creado) que el renderer no convertía en `<a>` — quedaban como texto suelto con una URL larga sin espacios, que desborda cualquier contenedor. Se agregó soporte de links al renderer y `overflow-wrap`/`overflow-x: hidden` como cinturón de seguridad adicional para cualquier token largo futuro.

## Interfaz: menos protagonismo del selector de modo

El selector de modo (antes tres botones siempre visibles) se reemplazó por un ícono chico fijo en la esquina superior derecha (mismo lenguaje visual que el menú de conversaciones, en la esquina opuesta) que despliega un menú pequeño solo al tocarlo. Libera espacio vertical para el chat y reduce la prominencia visual, tal como se pidió.

## Gestión de Google ampliada

- **Calendar:** `list_calendars`, `create_calendar`, `delete_calendar` (las dos últimas con protocolo de confirmación de ADR 0015). `list_upcoming_events` y `create_event` ahora aceptan `calendar_id`, ya no están atadas al calendario principal.
- **Gmail:** `list_labels`, `create_label`, `modify_message_labels` (organizar/mover correos) sin confirmación — son reversibles y no salen de la cuenta del fundador. `delete_label` sí requiere confirmación.
- **Drive:** `create_folder`, `move_file` sin confirmación (mismo criterio). `delete_file` con confirmación. Esto requirió ampliar el alcance de OAuth de `drive.readonly` a `drive` completo — se re-autenticó con el fundador para obtenerlo.
- El despacho de herramientas en `Orchestrator` se refactorizó de una cadena `if/elif` a un diccionario de handlers (`self._tool_handlers`), anticipando el crecimiento señalado como riesgo de escalabilidad en la conversación previa sobre prolijidad del proyecto.

## Verificado

Lectura real: calendarios y etiquetas reales del fundador, incluyendo que Snarf señaló por su cuenta un calendario marcado "(DELETED)" y etiquetas residuales de una migración de IMAP — comportamiento de colaboración crítica, no solo ejecución mecánica. Ciclo completo de escritura verificado de punta a punta e independientemente: creación de un calendario de prueba (confirmada, verificada que existía), y su eliminación (confirmada, verificada que ya no existía).

## Consecuencias

- La re-autenticación de Drive con alcance completo significa que, a partir de ahora, Snarf técnicamente puede escribir y borrar en todo el Drive del fundador — mitigado por que `delete_file` exige confirmación explícita; `create_folder`/`move_file` no la exigen porque son reversibles, pero quedan igual sujetos al criterio de "usalas solo cuando el fundador lo pida" del prompt de sistema, no autonomía espontánea.
