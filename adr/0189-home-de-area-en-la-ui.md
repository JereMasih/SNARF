# ADR 0189 — Home de Área en la UI

**Fecha:** 2026-08-20
**Estado:** Aceptado

## Contexto

Fase C5 del plan Second Brain (`ROADMAP_SECOND_BRAIN_NOTION.md`, ver ADR 0179). Con A7 (rollup + reporte
de Área en el backend) y C2/C3 (tab, drilldown, skeleton) ya resueltos, falta la superficie real: tocar
una Área debe mostrar su home, mismo mecanismo que ya existe para un Proyecto (`renderProjectHome`).

## Decisión

**Backend REST nuevo** (`app.py`), necesario porque `second_brain_get_area_home`/
`second_brain_area_report_refresh` (ADR 0185) son tools conversacionales, no endpoints HTTP:
- `GET /second-brain/areas/{area_id}` → `cached_area_report()`, cada Proyecto enriquecido con
  `snarf_project_id` (mismo helper `_mark_linked_projects` ya usado en C2 para `/projects`, extraído para
  no duplicar la lógica).
- `POST /second-brain/areas/{area_id}/report/refresh` → `generate_area_report()`, mismo patrón que
  `POST /projects/{id}/summary/refresh`.

**Frontend (`web/index.html`)**: `renderAreaHome(home)`, mismo esqueleto visual que `renderProjectHome`
(clase `.project-home` reusada tal cual — header, stats, sección de análisis con botón "actualizar",
lista de Proyectos). A diferencia del home de Proyecto, es mayormente de solo lectura: las Áreas se
gestionan en Notion, nunca desde Snarf (ADR 0182/0184) — el único control real es el refresh del análisis.
Los stats de Recursos/Archivo muestran "—" (no un cero fabricado) cuando `resources_mapped`/
`archive_mapped` son `false`, mismo criterio de honestidad ya establecido en A7.

**`enterArea()` extendido**: mismo patrón dual que `enterProject()` — al entrar a una Área, la barra
lateral (Proyectos de esa Área) y el home (`chatInner`) se cargan juntos, un solo gesto real, vía
`Promise.all`. `exitArea()` gana `clearChat()` (hallazgo real durante la verificación: sin esto, el home
de la Área anterior quedaba colgado en pantalla mientras la barra lateral ya mostraba otro nivel).

Clickear un Proyecto dentro del home de Área reusa exactamente la misma lógica que la lista de la barra
lateral (`enterProject` si ya está vinculado, abrir Notion si no) — un solo criterio, no dos
implementaciones del mismo comportamiento.

## Verificado

- `.venv/bin/python -m pytest -q` — 1614/1614 (1610 previos + 4 nuevos en `tests/test_app.py`: 404 real
  para Área inexistente en ambos endpoints, `snarf_project_id` marcado correctamente en el home, refresh
  devuelve el reporte fresco).
- **Playwright real de punta a punta**, contra un server de prueba real (puerto 8000) — a diferencia de
  C2 (donde el camino "conectado" no se pudo ejercitar por no haber Second Brain conectado todavía), acá
  se interceptaron las 4 llamadas HTTP reales (`page.route`) con datos de prueba fijos para poder recorrer
  el camino completo de punta a punta sin necesitar una conexión real a Notion: nivel superior muestra
  "Áreas" con la Área real, tocarla muestra el breadcrumb "‹ Áreas / SALUD", la lista de la barra lateral
  y el home (header con ícono, stats reales incluyendo "—" honesto para lo no mapeado, análisis real,
  botón actualizar, lista de Proyectos con el link a Notion cuando no hay vínculo) — todo verificado con
  texto real extraído del DOM y una captura de pantalla, **cero errores de consola**. Este es el primer
  ejercicio real de punta a punta del camino "Second Brain conectado" de todo el plan — las fases
  anteriores solo lo habían verificado con tests unitarios mockeados.

## Consecuencias

- Fase C4 (Home de proyecto enriquecido) puede reusar el mismo criterio de "—" honesto para datos no
  mapeados, y el mismo patrón de `page.route()` para verificar en vivo cuando el Second Brain real del
  fundador todavía no esté conectado.
- El helper `_mark_linked_projects` en `app.py` queda como punto único de esa lógica — cualquier endpoint
  nuevo que necesite marcar Proyectos de Notion con su vínculo real de Snarf lo reusa, no lo reimplementa.
