# ADR 0041 — Gmail resiliente ante fallos transitorios, uso real por API, y dashboard con tamaños más justos

**Fecha:** 2026-07-29
**Estado:** Aceptado

## Contexto

El fundador reportó varios problemas reales del dashboard en la misma tanda:

1. El widget de Gmail no cargaba bien. Inspeccionado en vivo contra el server real: `/dashboard/widgets/gmail` devolvía `{"connected": true, "error": "[SSL] record layer failure (_ssl.c:2648)"}` — un fallo transitorio de la conexión cacheada de `googleapiclient`, no un problema de credenciales.
2. Ni la lista de correos ni la interpretación ("digest") de Gmail mostraban fechas o enlaces reales, lo que generaba confusión sobre cuándo llegó cada mensaje.
3. El fundador cargó crédito real en su cuenta de ElevenLabs y no vio ningún cambio en el dashboard — y notó que no había ningún panel con datos de uso real (llamadas, tokens, caracteres) de las APIs que usa Snarf.
4. El layout del dashboard en modo desktop usaba más espacio del que su contenido real necesita.
5. El cuadro de texto de envío (`#textInput`) es de una sola línea — un texto largo (tipeado o transcripto) se corta sin poder verse completo antes de enviar.

## Decisión

### 1. Reintento único con cliente fresco ante fallos transitorios de Google

`GoogleDrive`, `GoogleGmail`, `GoogleCalendar` y `GoogleYouTube` cachean su `self._service` de `googleapiclient` como singleton — en un proceso de larga vida (el server real corre días), esa conexión puede quedar rota tras un cambio de red o que la Mac durmiera. Nuevo decorador `retry_once_with_fresh_client` (`snarf/capabilities/google_retry.py`): ante cualquier excepción, resetea `self._service = None` y reintenta una sola vez (nunca oculta un fallo persistente y real — si el reintento también falla, se propaga).

Aplicado solo a operaciones de lectura, idempotentes: `list_files`, `list_files_page`, `read_file_text`, `read_file_bytes`, `create_folder`, `move_file`, `delete_file` (Drive); `list_messages`, `read_message`, `list_labels` (Gmail); `list_calendars`, `list_upcoming_events`, `search_events` (Calendar); `list_subscriptions`, `list_liked_videos` (YouTube). **Deliberadamente no aplicado** a `upload_file` (su `MediaIoBaseUpload` consume el stream de bytes al ejecutar — reintentar subiría contenido vacío en silencio), `send_message` (riesgo de envío duplicado), y las mutaciones de labels/eventos/calendarios (riesgo de efecto duplicado).

### 2. Fechas y enlaces reales en Gmail

`GoogleGmail.list_messages()` ya devolvía `date` por mensaje — el frontend simplemente no lo mostraba. `gmailBodyHTML()` ahora arma `from · fecha` en la línea secundaria de cada mensaje.

Para la interpretación: el texto del digest es prosa libre de un LLM, y no se le pide que invente fechas o enlaces (sería fabricar datos, contra el Principio VI). En cambio, `GmailDigestSpecialist.refresh()` ahora persiste también `messages` — una referencia estructurada real (id/asunto/de/fecha) de los mensajes que interpretó — y el frontend la renderiza como una lista corta con enlaces reales debajo de la prosa del LLM, para que la interpretación nunca quede sin fecha ni enlace verificable.

### 3. Widget de "Uso real de APIs" + cupo real de ElevenLabs

El panel de costo (`cost`) es un estimado calculado desde llamadas trackeadas localmente (`usage_tracker.summarize()`) — cargar crédito en la cuenta de ElevenLabs no lo cambia porque nunca fue un saldo real, ya está aclarado en su subtítulo. Lo que faltaba era un dato real de cuenta.

- `usage_tracker.usage_metrics()`: nueva agregación por vendor de las métricas ya registradas (llamadas, tokens de entrada/salida, tokens de embeddings, caracteres de TTS, segundos de STT) — consumo real, sin convertir nada a dólares.
- `ElevenLabsTTS.subscription_info()`: nueva llamada real a `GET /v1/user/subscription` de ElevenLabs — devuelve el cupo de caracteres real de la cuenta (`character_count`/`character_limit`/`tier`). Este sí es el dato real que faltaba.
- Nuevo endpoint `/dashboard/widgets/usage` y widget `usage` en el dashboard (agregado a `WIDGET_IDS`, con su propio fetch asíncrono igual que los widgets de Google) que muestra ambas cosas: consumo trackeado localmente para los tres vendors, y el cupo real de ElevenLabs cuando está disponible (con degradación visible, no oculta, si la consulta al cupo real falla).

### 4. Tamaños de dashboard recalibrados con evidencia real

Los defaults de ADR 0037 dejaban espacio vacío de más en widgets de contenido fijo y corto (`system`, `conversations`, `memory`) y quedaban justos en los de listas densas (`drive`). La señal usada para recalibrar no fue estética a ciegas: el propio fundador, usando la grilla en vivo, ya había redimensionado a mano varios widgets — esos valores reales fueron la evidencia para los nuevos defaults (`system` 3/7→3/5, `conversations` 3/9→3/7, `memory` 3/9→3/6, `drive` 3/8→3/9, `cost` 3/7→3/8, `calendar` 3/8→3/5, `youtube` 3/8→3/6). Importante: esto solo cambia el default para instalaciones nuevas o sin preferencias guardadas — el layout ya guardado por el fundador (`data/dashboard_prefs/fundador.json`) no se tocó.

### 5. Cuadro de texto que crece

`#textInput` pasa de `<input type="text">` a `<textarea rows="1">`, con auto-crecimiento vía JS (`autoResizeTextarea`, en el evento `input` y tras asignar `.value` programáticamente desde una transcripción) hasta `max-height: 9rem` (~6 líneas), scrolleando internamente más allá de eso. `Enter` solo sigue enviando; `Shift+Enter` ahora inserta un salto de línea real (antes no aplicaba, al ser un input de una sola línea). Mismo tratamiento en `#reviewText` (revisión de la transcripción por voz antes de enviar), que antes tenía una altura fija de 4rem sin margen para texto largo.

## Verificado

- 305/305 tests (incluye los nuevos `tests/test_google_retry.py`, casos nuevos en `tests/test_gmail_digest.py` y `tests/test_usage_tracker.py`, y `tests/test_app.py` para `/dashboard/widgets/usage`).
- Playwright contra una copia aislada del repo (nunca el server real ni sus datos): grilla de dashboard con los nuevos defaults sin overflow en ningún widget a 1920×1080; cuadro de texto crece de ~50px a los 162px del tope y scrollea más allá; `Shift+Enter` inserta salto de línea real en vez de enviar.

## Consecuencias

- El widget de "uso" y el de "costo" muestran ángulos distintos a propósito (consumo real vs. dólares estimados) — si en el futuro se agrega otro vendor, hay que darle su entrada en ambos: `usage_tracker` para el consumo, y `pricing.py` si se puede estimar un costo honesto.
- Si ElevenLabs cambia su endpoint de suscripción o sus campos, `subscription_info()` degrada mostrando el error en vez de romper el widget — pero alguien tiene que notar el error mostrado y actualizar el parseo.
