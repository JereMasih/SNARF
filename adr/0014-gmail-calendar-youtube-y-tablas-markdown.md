# ADR 0014 — Gmail, Calendar y YouTube conectados; renderer de tablas Markdown

**Fecha:** 2026-07-25
**Estado:** Aceptado

## Contexto

El fundador pidió conectar todo lo posible sin necesitar más credenciales de su parte, dado que la autenticación de Google (ADR 0013) ya cubre Drive, Gmail, Calendar y YouTube en un solo consentimiento.

## Decisión

Se construyeron tres Capacidades nuevas, todas sobre la misma `GoogleAuth`:

- `GoogleGmail`: `list_messages`, `read_message`, `send_message`.
- `GoogleCalendar`: `list_upcoming_events`, `create_event`.
- `GoogleYouTube`: `list_subscriptions`, `list_liked_videos`.

Se conectaron como herramientas del Orchestrator **únicamente las operaciones de lectura**: `drive_list_files`, `drive_read_file`, `gmail_list_messages`, `gmail_read_message`, `calendar_list_upcoming_events`, `youtube_list_subscriptions`, `youtube_list_liked_videos`. `send_message` y `create_event` existen como código, funcionan, pero **deliberadamente no se expusieron como herramientas que Snarf pueda invocar por su cuenta** — enviar un correo o crear un evento es una acción externa e irreversible en el sentido del Artículo VII de Constitution, y hoy no existe un mecanismo de confirmación en la interfaz antes de ejecutar una herramienta. Exponerlas sin ese mecanismo habría contradicho una decisión de gobernanza ya tomada, no solo una omisión técnica.

## Verificado

Conversación real: Snarf consultó Calendar (agenda vacía, correcto) y YouTube (10 suscripciones reales) en una sola respuesta, y en otra consulta leyó los 5 últimos correos reales de Gmail — incluyendo, por iniciativa propia, señalar como dato relevante que el primer correo era la alerta de Google por el consentimiento OAuth recién otorgado (comportamiento consistente con "pensamiento crítico" de Character).

## Hallazgo y corrección adicional

La respuesta de Gmail llegó formateada como tabla Markdown — formato que el renderer del frontend todavía no soportaba (se mostraba como texto plano con barras y guiones literales). Se agregó soporte de tablas al renderer (`web/index.html`) y su estilo correspondiente.

## Consecuencias

- Falta, como trabajo futuro explícito: un mecanismo de confirmación en la interfaz para que `send_message` y `create_event` (y cualquier acción de alto impacto futura) puedan ofrecerse a Snarf sin violar el Artículo VII — probablemente un paso de "Snarf propone la acción, la interfaz la muestra para aprobar/rechazar antes de ejecutarla".
- Quedan pendientes, del pedido original: importación/vectorización de Google Drive completo (más allá de archivos de texto) y la integración de Notion.
