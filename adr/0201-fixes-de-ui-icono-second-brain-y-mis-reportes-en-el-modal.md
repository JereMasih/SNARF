# ADR 0201 — Fixes de UI: ícono de Second Brain y "Mis reportes" dentro del modal de reporte

**Fecha:** 2026-08-21
**Estado:** Aceptado

## Contexto

Feedback directo del fundador probando la interfaz recién construida en el plan Second Brain (ADR
0179-0200): el ícono "2 + cerebrito" del tab "Second Brain" (SVG con un `<text>` "2" + círculos/paths, ADR
0187) no renderiza bien — pidió sacarlo y dejar solo el texto. Además, la pestaña "Mis reportes" (lista de
bug reports del fundador, al lado de "Second Brain" en la misma barra lateral) le resultaba fuera de lugar
ahí — pidió que se mude a la interfaz de reportar un problema, con click-to-expand real sobre cada reporte
(hoy no existía: la lista solo mostraba una línea truncada, sin ningún handler de click).

Investigado antes de tocar código: `GET /bug_reports/{id}` ya existe y devuelve el detalle completo
(descripción, categoría/severidad/plan, resolución, historial) — el gap era puramente de frontend, cero
trabajo de backend.

**Aclaración aparte, no un bug**: el fundador también notó que el tab "Second Brain" no muestra "Áreas",
solo la lista plana de "Proyectos". Investigado: `SecondBrainManager.is_connected()` (ADR 0182) devuelve
`False` porque `data/second_brain/fundador/database_map.json` todavía no existe — el fundador nunca hizo el
onboarding (ADR 0190). Es el comportamiento de fallback documentado a propósito, no un bug de esta fase —
no requiere código nuevo, solo que el fundador pida el onboarding en el chat (no depende de terminar el
registro OAuth público de Notion, que resuelve un problema distinto: multi-usuario, no el propio Second
Brain del fundador, que ya funciona con `NOTION_API_KEY`).

## Decisión

**Ícono**: se quita el SVG de los dos botones `.sidebar-tab-second-brain` (barra lateral normal +
`#dashHistoryParked`, la instancia reparentada al dashboard de escritorio) — queda solo el texto "Second
Brain". Se eliminó también la regla CSS `.sidebar-tab-second-brain svg` (ya sin ningún selector real). El
objeto `ICONS.secondBrain` (reusado en el header de Home de Área, ADR 0189) no se tocó — el pedido fue
específico sobre el tab, no sobre ese uso.

**"Mis reportes"**: se elimina como tab de la barra lateral (ambas instancias) y se muda DENTRO del modal
que ya abre el botón 🐞 (`bugReportOverlay`), como una segunda sub-pestaña junto a "Nuevo reporte". Sub-
switcher propio (`.bug-report-modal-tab`/`.bug-report-modal-panel`), deliberadamente NO reusa la clase
`.sidebar-tab`: el switcher genérico de esa clase resuelve su scope con
`.closest("#sidebar, #dashHistoryParked")` y cae a `document` si no lo encuentra — un botón con esa clase
dentro del modal habría apagado los paneles activos de la barra lateral real al hacer click. El modal
siempre abre en "Nuevo reporte" (punto de entrada predecible, nunca recuerda la última sub-pestaña usada).

**Click-to-expand**: cada ítem de la lista de reportes ahora tiene un handler de click que llama
`GET /bug_reports/{id}` y reemplaza la lista por el detalle completo (descripción, badges de
estado/categoría/severidad, plan, resolución, historial con timestamps) — mismo patrón de "reemplazar la
lista por el detalle, un nivel a la vez" que ya usan `enterProject()`/`enterArea()` (ADR 0181), nunca un
acordeón anidado. Botón "← volver" restaura la lista sin volver a pedirla al servidor (ya estaba en el DOM).

Como consecuencia de que ahora solo existe UNA instancia del modal (no duplicada mobile/desktop, a
diferencia de la barra lateral), `dashBugReportList`/`bugReportList` con dos ids distintos se colapsó a un
solo `id="bugReportList"` — el código de `refreshBugReportList()` se simplificó de "actualizar dos
contenedores" a "actualizar uno solo".

## Verificado

- Playwright real contra un server de prueba (puerto 8000, nunca el 8002 de producción), con la password
  real del `.env`, mobile (390×844) y desktop (1400×900):
  - El tab "Second Brain" renderiza solo texto, sin SVG, en las dos instancias del DOM — cero errores de
    consola.
  - El modal del botón 🐞 abre siempre en "Nuevo reporte"; cambiar a "Mis reportes" carga la lista real
    (`GET /bug_reports`, datos reales del fundador — de solo lectura, sin mutar nada); click en un reporte
    real despliega descripción/estado/plan real; "← volver" restaura la lista.
  - Confirmado que la barra lateral ya no tiene ningún `.sidebar-tab[data-tab="bug_reports"]` (0 en ambas
    instancias).
- `.venv/bin/python -m pytest -q` — 1681/1681 (sin cambios de backend en este fix, cambio puramente de
  `web/index.html`).

## Consecuencias

- Ninguna migración de datos — `GET /bug_reports`/`GET /bug_reports/{id}` no cambiaron, solo el frontend
  que los consume.
- El fundador todavía no hizo el onboarding de su propio Second Brain (`database_map.json` no existe) — se
  le indicó en el chat que puede pedirlo directo, sin depender del registro OAuth público (ese bloqueo es
  para multi-usuario, no para su propio uso vía `NOTION_API_KEY`).
