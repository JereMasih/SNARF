# ADR 0124 — Timestamps opcionales en el chat, y fix real de `PUT /dashboard/preferences`

**Fecha:** 2026-08-05/06
**Estado:** Aceptado

## Contexto

Pedido explícito: un toggle en Configuración que, activado, muestre separadores de fecha
(Hoy/Ayer/fecha) arriba de la conversación y la hora dimeada por burbuja de mensaje. Apagado por
default, mismo criterio "cero sorpresa" que el resto de las preferencias del dashboard.

## Decisión: implementación

- `snarf/runtime/dashboard_prefs.py`: nuevo campo `show_message_timestamps` (bool, default `False`),
  mismo patrón de normalización ya establecido (`isinstance(x, bool)` explícito — `bool` es subclase de
  `int` en Python, chequeo ya documentado en CLAUDE.md).
- `web/index.html`: toggle nuevo en la sección "Chat" de Configuración (`.settings-toggle`, patrón ya
  existente). `addMessage()` gana un parámetro final `timestamp` — cuando el toggle está activo, agrega
  un `<span class="msg-time">` dimeado a cada burbuja. `refreshDateSeparators()` reconstruye los
  separadores desde cero a partir de los `data-timestamp` ya presentes en el DOM (en vez de llevar
  estado incremental a través de `loadConversation()`/`loadOlderMessages()`) — más simple y robusto
  contra los bordes de la paginación de Fase 2, donde un tramo viejo puede cruzar varios días o coincidir
  con el día ya cargado.

## Bug real encontrado y corregido: `PUT /dashboard/preferences` no mergeaba

Al verificar esto en vivo, un PUT parcial de prueba (`curl` con un solo campo) pisó en silencio
customización real ya guardada del fundador — tamaños/orden de widgets, y el estado/posición de un nodo
HUD que tenía fijado a mano (`hud_widget_state.llm = "pinned"`, `hud_widget_options.llm` con
ángulo/radio reales). Causa: `DashboardPreferences` (Pydantic) declara un default propio por campo
(`visible_widgets: dict = {}`, etc.) — `payload.model_dump()` completaba cualquier campo ausente del
request con ESE default vacío, no con lo ya guardado. Exactamente el mismo patrón que el bug de
`PUT /llm-routing` ya encontrado y corregido esta misma ronda (ver CHANGELOG del 2026-08-05).

**Recuperación real:** restaurado byte a byte desde el backup automático más reciente
(`data_backups/2026-08-05T23-38-16/dashboard_prefs/fundador.json`, generado por
`data_backup.backup_now()` minutos antes del incidente) — diff confirmado idéntico.

**Fix del endpoint** (`app.py`):
```python
merged = {**load_prefs(user_id), **payload.model_dump(exclude_unset=True)}
return save_prefs(user_id, merged)
```
`exclude_unset=True` es la parte real del fix: solo los campos que el request ACTUALMENTE mandó
sobreescriben lo ya guardado; el resto se preserva. El frontend real nunca se ve afectado (`persistPrefs()`
ya manda el objeto `dashboardPrefs` completo tal cual se cargó) — esto protege contra cualquier otro
cliente (scripts, curl, futuros consumidores) que mande un payload parcial.

**Segundo bug relacionado, mismo hallazgo:** el campo nuevo `show_message_timestamps` nunca se había
agregado a la clase `DashboardPreferences` de `app.py` (solo a `dashboard_prefs.py`) — Pydantic descarta
en silencio cualquier campo no declarado en el modelo, así que el toggle nunca podía persistir de verdad
vía la API real hasta agregarlo también ahí. Encontrado al verificar en vivo contra el server real
(no lo detectaba pytest porque los tests unitarios de `dashboard_prefs.py` llaman `save_prefs()`
directo, sin pasar por la capa Pydantic de `app.py`).

**Hallazgo adicional durante la verificación:** el server de producción venía corriendo desde las 17:38
de ese mismo día — ninguno de los cambios de backend de esta sesión (Fases 0, 1, 2, 4) estaba realmente
desplegado hasta el restart real que cerró esta ronda (`launchctl bootout`/`bootstrap`, confirmado con el
PID/hora de arranque nuevos y una request real post-restart a `/conversations/{id}` devolviendo la forma
nueva `{entries, has_more}`).

## Verificado

- `.venv/bin/python -m pytest -q` — 980 passed (incluye tests nuevos para `show_message_timestamps` en
  `dashboard_prefs.py` y el fix de merge en `test_app.py`).
- Playwright contra el server real, YA reiniciado: toggle activa/desactiva correctamente vía
  `openSettings()`/click real, separadores de fecha en orden correcto (fecha vieja → Ayer → Hoy),
  hora dimeada en las 6 burbujas, todo desaparece limpio al desactivar sin romper el layout, cero
  errores de consola.
- Restauración de `dashboard_prefs` verificada con diff byte-a-byte contra el backup real.

## Consecuencias

- Cualquier pestaña del navegador del fundador que haya quedado abierta durante la ventana de
  corrupción (unos pocos minutos) puede tener en memoria un `dashboardPrefs` desactualizado — un
  refresh de esa pestaña lo resincroniza contra el estado ya corregido en el server. No hay acción de
  código pendiente por esto, es un efecto secundario de sesión, no de datos.
- Este es el segundo endpoint de preferencias con el mismo patrón de bug de merge encontrado en una
  sola sesión (`/llm-routing`, `/dashboard/preferences`) — vale la pena, como tarea futura no urgente,
  auditar el resto de los endpoints `PUT` que reciben un modelo Pydantic con defaults propios por si
  comparten el mismo riesgo.
