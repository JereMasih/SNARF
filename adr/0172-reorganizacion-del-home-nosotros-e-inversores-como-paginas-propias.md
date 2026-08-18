# ADR 0172 — Reorganización del home: Nosotros e Inversores como páginas propias

**Fecha:** 2026-08-18
**Estado:** Aceptado

## Contexto

Pedido explícito del fundador: el home (`GET /vision`) no debía seguir mostrando "todo" — tenía que
competir con los máximos estándares de la industria (comunicación eficiente y profesional), con el
contenido profundo viviendo en sub-páginas accesibles desde la barra de navegación superior, no
necesariamente en el home.

Tras el ADR 0171, `web/vision.html` acumulaba 13 secciones + hero: Problema, Qué es Snarf (4
principios), Cómo funciona, Capacidades (6 tarjetas), Capturas (3 screenshots), Estado en vivo
(métricas + changelog), Roadmap, Por qué sumarte (pitch de inversores), El creador, Blog, Hablar con
Snarf. Esto continúa un patrón ya iniciado en ADR 0170 (que ya sacó del home el contenido de
arquitectura, capacidades y roadmap hacia páginas propias) — esta ronda termina esa poda.

## Decisión

**El home queda con 6 secciones + hero**: Problema → Cómo funciona (teaser) → Capacidades (teaser
recortado de 6 a 4 tarjetas insignia) → Roadmap (teaser de 3 nodos) → Blog (teaser de 3 artículos) →
Hablar con Snarf (lead + demo, la conversión principal) → footer. Sin cambios de backend: todo el
contenido movido sigue sirviéndose desde los mismos endpoints públicos ya existentes
(`/vision/status`, `/vision/blog`).

**Dos páginas nuevas**, separadas a pedido del fundador (no una sola página mixta):
- `GET /nosotros` (`web/nosotros.html`) — los 4 principios ("Qué es Snarf") y "El creador", movidos
  tal cual desde el home. Ícono de masthead violeta, primer uso de ese color en un masthead (los
  existentes son magenta=Arquitectura/Roadmap, aqua=Capacidades).
- `GET /inversores` (`web/inversores.html`) — el pitch "Por qué sumarte a Snarf ahora", movido tal
  cual. Audiencia de nicho: deliberadamente **fuera** del nav principal, alcanzable solo desde
  `/nosotros` (línea "¿Sos inversor o socio? →") y desde el footer de las 7 páginas públicas.

**Dos secciones migran a páginas ya existentes**, no a páginas nuevas, por ser su lugar temático
natural:
- Capturas (3 screenshots) → `web/capacidades.html`, justo después de su masthead — mostrar la
  interfaz real al lado de la lista de capacidades, no en el home.
- Estado en vivo (stat tiles + resumen del roadmap + tabla de changelog) → `web/roadmap.html`,
  reemplazando el stub `.status-teaser` que ya vivía ahí desde ADR 0170 y que solo linkeaba de vuelta
  a `/vision#estado` — confirma que ese siempre fue el lugar natural. El JS (`renderStatus`, `tile`,
  `animateCountUp`, `watchCountUp`) se porta desde `vision.html`; `vision.html` conserva solo
  `renderHeroTrust`/`renderRoadmapDynamic` (la barra de confianza del hero y el badge "Hoy · Fase N"),
  alimentados por el mismo fetch a `/vision/status`.

**Nav y footer, las 7 páginas públicas**: nuevo link de primer nivel "Nosotros" (desktop + mobile),
al lado de "Producto ▾" y "Blog" — "Inversores" no entra al nav principal. El logo/marca pasa a ser
un link a `/vision` (antes un `<div>` sin destino en `vision.html`; ya era un link en las demás
páginas). Se saca el ítem "Visión" (`#que-es`, sección que ya no existe) y "El creador" como ítem de
nav de primer nivel (ahora vive dentro de `/nosotros`, alcanzable por scroll o desde el footer).
Footer, columna "Sobre el proyecto": agrega "Nosotros" e "Inversores"; "El creador" repunta a
`/nosotros#creador`. Columna "Contenido": "Estado en vivo" repunta a `/roadmap#estado`.

## Consecuencias

- CSS muerto eliminado de `vision.html` junto con las secciones que lo usaban (`.shot-*`,
  `.status-grid`/`.stat-tile`/`.status-panel`/`.mark-note`/`table.changelog`/`.adr-badge`,
  `.card-grid`/`.principle-card`/`.governance-line`, `.creator-card`/`.creator-avatar`,
  `.invest-grid`/`.invest-card`) — nada de reglas huérfanas apuntando a markup que ya no existe ahí.
- Sin tests de backend nuevos: las 2 rutas nuevas son `FileResponse` estáticas, mismo patrón sin test
  dedicado que `/arquitectura`/`/capacidades`/`/roadmap` ya tenían. 1472/1472 sin cambios.
- Verificado con Playwright (script ad hoc, servidor de prueba en :8010, no el de producción) en las 7
  páginas públicas, desktop (1440×900) y mobile (390×844): cero errores de consola, home con altura de
  body reducida (~4900px vs. las 13 secciones previas), panel de Estado en vivo renderizando datos
  reales en `/roadmap`, 3 screenshots en `/capacidades`, nav "Nosotros" funcional en desktop y mobile,
  `grep` de `vision#estado|vision#creador|vision#que-es|vision#invertir` en `web/` y `app.py` vacío.
- Servidor real de producción (puerto 8002) pendiente de reinicio para que `/nosotros` e
  `/inversores` queden disponibles ahí — a confirmar con el fundador antes de reiniciar, por
  convención de este repo.
