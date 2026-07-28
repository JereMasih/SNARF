# ADR 0023 — Íconos propios, widgets de Google, configuración y layout Jarvis en desktop

**Fecha:** 2026-07-27
**Estado:** Aceptado — verificado por API real y suite de tests; falta confirmación visual del fundador en su navegador real

## Contexto

Apenas visto el dashboard v1 (ADR 0022), el fundador pidió una ronda de refinamiento bastante más grande que un ajuste: reemplazar los íconos de emoji por íconos propios coherentes con la estética HUD; agregar widgets reales de Drive, Gmail, Calendar y YouTube; poder elegir qué widgets mostrar desde una configuración; poder reordenar los paneles a mano (mouse en desktop, mantener presionado y arrastrar en mobile) y que ese orden se guarde por usuario; y, en desktop, que el dashboard rodee al chat en vez de reemplazarlo — el chat centrado como si fuera el iPhone en el medio de un monitor, con paneles arriba, a la izquierda (empezando por la lista de conversaciones) y a la derecha, en el resto del "real estate" de pantalla disponible.

**Corrección a ADR 0022:** esa ADR había clasificado cualquier widget de Capacidad nueva como "Fase 2, no antes de que la Capacidad exista". Eso fue un error de alcance: `GoogleDrive`, `GoogleGmail`, `GoogleCalendar` y `GoogleYouTube` ya existían como Capacidades reales y verificadas desde ADR 0013/0014 — no son subsistemas hipotéticos como Trading, GitHub o MCP (esos sí siguen en Fase 2, sin construir). Los widgets de Google pertenecen a la Fase 1 (datos reales), y se construyen en esta ronda.

## Decisión

1. **Íconos propios**: reemplazado cada emoji usado como ícono (menú, dashboard/chat, mantener/toque/texto, engranaje de configuración, salir) por SVG inline minimalista (trazo delgado, `currentColor`, sin relleno salvo puntos), coherente con el resto de la interfaz (orbe, rayos, anillos) que también es dibujado a mano en CSS/HTML, sin depender de ninguna librería de íconos externa ni CDN.

2. **Widgets de Google** (`GET /dashboard/widgets/{drive,gmail,calendar,youtube}`, todos de solo lectura): Drive (últimos 5 archivos modificados), Gmail (últimos 5 mensajes), Calendar (próximos 5 eventos), YouTube (últimas 5 suscripciones). Cada endpoint devuelve `{"connected": false}` sin llamar a ninguna API si el usuario no tiene a Google conectado (evita disparar el flujo interactivo de OAuth desde el servidor), y degrada a un mensaje de error visible si la llamada real falla — nunca dato inventado.

3. **Configuración de widgets, persistida por usuario** (`snarf/runtime/dashboard_prefs.py`, `data/dashboard_prefs/<user_id>.json`, gitignorado): `visible_widgets` (qué widgets mostrar, de los 7: sistema, conversaciones, memoria, drive, gmail, calendar, youtube) y `panel_order` (orden de los 7). Endpoints `GET`/`PUT /dashboard/preferences`. Panel de configuración nuevo (reemplaza el placeholder "próximamente" del menú de usuario) con un interruptor por widget.

4. **Reordenar paneles**: un mismo mecanismo basado en Pointer Events sirve para mouse y touch — en mouse el arrastre empieza inmediatamente al presionar el asa (ícono de puntos); en touch requiere mantener ~350ms antes de empezar a arrastrar, para no pisar el gesto de swipe que cambia entre Chat y Dashboard. El nuevo orden se persiste en `panel_order` al soltar.

5. **Layout Jarvis en desktop** (`min-width: 900px` Y el botón de Dashboard activado — `body.jarvis-mode`): grilla CSS de una sola pieza (`grid-template-areas: "top top top" / "left center right"`) donde el chat (`.view-chat`) ocupa el centro sin dejar de ser el mismo componente (no una copia), y `.view-dashboard` pasa a `display: contents` para que sus tres zonas (arriba, izquierda, derecha) se vuelvan hijos directos de esa grilla. Asignación de zona fija por widget (no configurable todavía): arriba = Conversaciones (el gráfico, en formato ancho); izquierda = lista de conversaciones (siempre) + widget de Estado del sistema; derecha = Memoria, Drive, Gmail, Calendar, YouTube (estos sí reordenables entre sí). En mobile (o desktop con el Dashboard sin activar) el comportamiento es el de ADR 0022: una sola vista a la vez, alternada por botón o swipe, con los 7 widgets en una sola columna reordenable.

6. **Corrección de seguridad encontrada durante la construcción**: los widgets de Gmail y Calendar muestran datos que no controla el fundador — el asunto y remitente de un email, por ejemplo, los define quien le escribe. Insertarlos con `innerHTML` sin escapar habría sido una vulnerabilidad real de XSS (un asunto de correo con `<script>` se habría ejecutado en la sesión autenticada del fundador). Se agregó `escapeHtml()` y se aplicó a todo campo de origen externo (Drive, Gmail, Calendar, YouTube) y también, por defensa en profundidad, al título de conversación en la lista lateral.

## Verificado

- Suite completa de tests (ver sección de tests para el conteo exacto).
- El JavaScript se validó sintácticamente con JavaScriptCore (parseo puro) y el HTML completo se verificó con `html.parser` de Python confirmando balance de tags — ninguna herramienta de navegador real (`chromium-cli`, Playwright, Node) está disponible en este entorno de desarrollo.
- Verificado por API real contra una instancia aislada (puerto 8001, sin tocar el servidor real del fundador en el 8000): login, `/dashboard/preferences` (GET/PUT), y los cuatro `/dashboard/widgets/*` contra la cuenta de Google real del fundador.

## Descartado explícitamente en esta ronda

- Zona de cada widget configurable por el usuario (hoy es fija: arriba/izquierda/derecha por id de widget, no elegible). Solo el orden dentro de la columna derecha (desktop) y el orden completo (mobile) son configurables.
- Aplicación de escritorio nativa multi-ventana y visualización de red neuronal ("Jarvis brain"): siguen en Fase 3 de ADR 0022, sin cambios.

## Consecuencias

- **Pendiente crítico:** el layout Jarvis, el arrastre para reordenar y la sensación general de los íconos nuevos no fueron vistos en un navegador real por nadie — ni por mí (sin herramienta de navegador en este entorno) ni, todavía, por el fundador. Se recomienda explícitamente pedir captura de pantalla (o mejor, probarlo en vivo) antes de seguir construyendo sobre este layout, siguiendo la misma lección de ADR 0020.
- Cualquier Capacidad nueva y real que se agregue de acá en más debería sumarse a `WIDGET_IDS` (`snarf/runtime/dashboard_prefs.py`) y a `WIDGET_LABELS`/zona fija en `web/index.html` — la extensibilidad hoy es manual (agregar el id en 2-3 lugares), no un registro automático.
- `data/dashboard_prefs/` es nuevo y queda fuera de git (datos de usuario, no código), igual que `credentials/` y la memoria episódica real.
