# ADR 0171 — Hero centrado en Snarf, capa HUD compartida, y rediseño del mapa de arquitectura

**Fecha:** 2026-08-18
**Estado:** Aceptado

## Contexto

Feedback real del fundador tras la ronda de ADR 0170: el texto de primer contacto del hero hablaba de
"para quién es" Snarf en vez de despertar curiosidad por Snarf mismo; la home seguía pesada pese al
recorte anterior; la barra de navegación no reflejaba las secciones reales del sitio ni permitía moverse
entre sub-páginas de forma intuitiva; el pie de página no tenía un mapa de sitio persistente; faltaba un
apartado sobre el fundador; los artículos y páginas de sección no tenían imagen de portada; el lenguaje
visual del hero (partículas, brillo tipo tubo de rayos catódicos / pantalla digital) que ya vive en la
interfaz real de Snarf (`web/index.html`) no se sentía presente en la superficie pública; el hero se sentía
poco animado; y, el ítem marcado como roto explícitamente: el diagrama de arquitectura no se leía ni en
desktop ni en mobile. Además, un bug real de UX: en las tarjetas de blog tanto el título como el resumen
aparecían subrayados, sin distinguir que el resumen debía llevar a la página de sección y el título al
artículo puntual.

Pedido de "buscar en Drive ejemplos de copy sobre el fundador" no se pudo cumplir — no hay herramienta de
Drive disponible en esta sesión y no existe contenido biográfico del fundador en el repo. Se le preguntó
directamente cómo proceder; eligió placeholder honesto ("Biografía completa, próximamente.") en vez de
contenido inventado, consistente con el Principio VI de `FOUNDATION.md`.

## Decisión

**Hero reescrito, centrado en Snarf**: nuevo H1/sub que despiertan curiosidad por qué es Snarf y cómo
simplifica el día a día, no por "para quién es". El canvas del hero gana `crossLinks` (conectores tipo
radio entre anillos del cerebro) y `flowPulses` (pulsos de luz viajando por esos conectores), con
seguimiento de delta-time para el movimiento.

**Capa HUD compartida en las 5 páginas públicas** (`vision.html`, `blog.html`, `arquitectura.html`,
`capacidades.html`, `roadmap.html`): scanline animado, 4 esquinas tipo HUD, y partículas flotantes —
valores portados literalmente de `web/index.html` (la interfaz real de Snarf), como capa decorativa de baja
intensidad (`position:fixed`, `pointer-events:none`), nunca protagonista — la idea explícita del fundador
era que "rime" con el branding de la interfaz real sin competir con ella.

**Navegación por secciones + mapa de sitio persistente**: la barra superior gana un dropdown "Producto ▾"
que agrupa Arquitectura/Capacidades/Roadmap, más un link directo a "El creador"; las 3 páginas de
profundidad ganan una sub-barra de tabs (`Arquitectura | Capacidades | Roadmap`) para moverse entre ellas
sin volver a la home. El pie de página de las 5 páginas gana un mapa de sitio persistente de 3 columnas
(Producto / Contenido / Sobre el proyecto).

**Apartado del creador** (`#creador` en la home): placeholder honesto — nombre, rol, línea de gobernanza,
nota explícita "Biografía completa, próximamente.", sin ninguna cifra ni afirmación biográfica inventada.

**Imágenes de portada**: `snarf/telemetry/blog.py` gana el campo `cover_image` (en `append()`,
`_EDITABLE_FIELDS`, `update()`); `app.py` lo suma a los modelos Pydantic de creación/edición de artículos.
`web/blog_admin.html` gana subida de portada reusando `POST /blog/admin/images` ya existente; `web/blog.html`
la muestra como thumbnail 16:9 en la grilla y como imagen completa en el detalle del artículo;
`web/vision.html` la muestra en el teaser de 3 artículos de la home. Para las páginas de sección
(`arquitectura`/`capacidades`/`roadmap`), en vez de fabricar fotografía de portada (lo que violaría el
Principio VI — no hay imagen real que representar), cada masthead gana un ícono SVG generado a mano en un
badge circular con brillo pulsante, distinto por página y coherente con la paleta ya establecida
(magenta=Arquitectura, aqua=Capacidades, magenta=Roadmap).

**Diagrama de arquitectura, reemplazo completo**: el diagrama SVG radial anterior (ancho fijo, requería
scroll horizontal, nodos satélite amontonados) se reemplaza por un organigrama CSS/DOM responsive —
hub central "Snarf", fila de chips de entrada, dos ramas (Especialistas Cognitivos / Capacidades) con
tarjetas de nodo en grid, conectores por pseudo-elementos. Sin matemática de ángulos/radios: escala
naturalmente con el contenido y el viewport, colapsa a una columna en mobile. Verificado con Playwright que
se lee completo y sin recortes en desktop y mobile.

**Fix de tarjetas de blog**: se separa el bloque "excerpt" (link a `/blog`, la página de sección) del
título (link al artículo puntual, con su propio subrayado solo en `:hover`) — antes toda la tarjeta era un
único `<a>` sin distinción de destino.

## Consecuencias

- Cobertura de tests nueva para `cover_image` en `tests/test_blog.py` (`append`/`update` roundtrip) y
  `tests/test_app.py` (creación/edición vía `POST`/`PATCH /blog/articles`) — el campo ya existía en el
  código pero no estaba cubierto por ningún test hasta esta ronda.
- 1472/1472 tests. Verificado con Playwright en las 5 páginas públicas, desktop (1440×900) y mobile
  (390×844): cero errores de consola, hero con el copy nuevo, dropdown "Producto ▾" funcional, footer con
  mapa de sitio, sección `#creador` con placeholder, diagrama de arquitectura legible en ambos viewports,
  badges de masthead con brillo pulsante, sub-nav de tabs con la pestaña activa marcada, capa HUD presente
  y no intrusiva.
- Ningún artículo real tiene todavía una portada cargada — la UI está lista, pendiente de que el fundador
  suba una desde `GET /blog/admin` cuando tenga la primera imagen real.
