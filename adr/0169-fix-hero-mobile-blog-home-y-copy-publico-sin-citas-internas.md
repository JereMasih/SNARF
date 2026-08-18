# ADR 0169 — Fix de hero en mobile, home de blog propio, y copy público sin citas a documentos internos

**Fecha:** 2026-08-17
**Estado:** Aceptado

## Contexto

Feedback real del fundador sobre el rediseño de ADR 0168, el mismo día: el cerebro de fondo del hero no
se veía en mobile (solo los orbes de resplandor), el efecto de parallax no se sentía, el blog necesitaba
su propio home con categorías en vez de vivir solo como sección de `/vision`, la página necesitaba más
elementos gráficos/tecnológicos con movimiento en el scroll, y — el punto más importante — el copy público
no debe citar literalmente documentos internos (`FOUNDATION.md`, `COGNITION.md`, `MASTER_MAP.md`,
`PROJECT_CONTEXT.md`, "Principio N", "ADR NNNN", nombres de herramientas internas como Playwright) sino
estar redactado como texto de marketing terminado, derivado de esos documentos pero sin citarlos.

## Decisión

**Bug real de mobile, causa raíz identificada:** el fondo visual del hero (`#heroCanvas` + orbes) estaba
posicionado con `inset: -10%`/`120%` relativo al alto TOTAL de `.hero`, que en mobile es enorme (el título
solo, con `clamp()`, ya ocupa 5-6 líneas). El centro del anillo de nodos (`cy = h * 0.5`) terminaba muy por
debajo de lo que se ve sin scrollear, con partículas de baja opacidad — en la práctica, invisible; solo los
orbes (posicionados con offsets fijos cerca del borde superior) se alcanzaban a ver. **Fix:** nuevo
`.hero-stage`, contenedor separado con `height: 100vh` (`100svh` como mejora progresiva) — nunca atado al
alto del contenido — que ancla el cerebro siempre al viewport real que se ve al entrar. Nodos más grandes y
más numerosos en mobile (`sizeBoost` dedicado), deriva rotacional continua y lenta (vivo aun sin
scrollear), y un `.hero-core-glow` radial detrás de todo. Parallax con diferencial más marcado
(0.05–0.38 según capa, antes 0.04–0.24) y `resize()` diferido a `requestAnimationFrame` (medir
`clientWidth/Height` antes de que el layout real se asiente colapsaba todos los nodos en una esquina).
Verificado con Playwright en iPhone SE/14 y Android chico: el cerebro se ve completo y el parallax es
notorio al scrollear.

**Home de blog propio, `GET /blog` (`web/blog.html`, nuevo):** masthead con gradient de marca, chips de
categoría generados de los `tags` reales de cada artículo (sin categorías inventadas), grid de tarjetas, y
vista de detalle con routing por hash (`#a-<id>`, soporta atrás/adelante del navegador). Reusa
`GET /vision/blog` tal cual, sin API paralela. La sección "Blog" de `/vision` pasa a ser un teaser (3
artículos más recientes) que linkea a `/blog` — ya no expande in-place.

**Más elementos gráficos con movimiento en scroll:** `.tech-divider` (línea con un pulso de luz ámbar
recorriéndola en loop, reusando el ámbar exactamente como lo pidió el fundador: adorno tecnológico, nunca
texto) entre varias secciones; `.ambient-field` (partículas CSS puras, sin canvas, con drift vertical lento)
detrás de "Capacidades" y "Roadmap"; pulso animado en las flechas de "Cómo funciona"; resplandor que
"respira" en las ventanas de captura de `#capturas`.

**Copy público sin citas a documentos internos** — cambios concretos:
- Tags de las tarjetas de "Qué es Snarf": de `"FOUNDATION · Principio I"` a etiquetas cortas sin citar
  archivo (`PROPÓSITO`, `PERSONAS PRIMERO`, `ACTIVOS REALES`, `HONESTIDAD`); los párrafos pasan a primera
  persona ("Priorizo...", "Distingo...") para consistencia con la voz ya establecida en el blog.
- Cita de gobernanza del footer de esa sección: se quita `— PROJECT_CONTEXT.md`, queda la frase sola.
- Subtítulos de "Cómo funciona" (quita `COGNITION.md, ADR 0003`), "Capacidades" (quita
  `MASTER_MAP.md`), "Interfaz real" (quita `Playwright`) y "Estado en vivo" (quita el snippet literal
  `GET /vision/status`) — reescritos como prosa terminada.
- Encabezado del panel de cambios recientes: de `"Últimos cambios (CHANGELOG.md)"` a `"Últimos cambios
  reales"` (la tabla en sí, con badges reales de ADR, se mantiene — es el panel de transparencia explícito
  de ADR 0167/0168, con su propio encuadre honesto, distinto de copy de marketing).
- **Hallazgo real durante la verificación visual, no pedido explícito pero mismo espíritu:** las tarjetas
  "Hoy" y "Norte del plan" del timeline de Roadmap pintaban el texto CRUDO de
  `roadmap.summary`/`roadmap.mark_note` (asteriscos de markdown sin renderizar, citas `ADR 0164`, nombres
  de variables de entorno como `N8N_LIVE_CANVAS_ENABLED`, número de puerto interno) — notas de trabajo
  internas, no copy legible. Se reemplazan por prosa fija, honesta pero redactada (mismo contenido ya
  validado en el artículo 6 del blog); el panel "Estado en vivo" de más arriba sigue mostrando el texto
  crudo tal cual, porque ESE panel es explícitamente la superficie de transparencia cruda — la duplicación
  hacia el timeline narrativo era el problema real, no el panel en sí.
- Los 6 artículos del blog (ADR 0168) se reescribieron para narrar sin parentéticos `(ADR NNNN)` inline —
  `scripts/seed_vision_blog.py` actualizado, `data/blog_posts.jsonl` borrado y re-sembrado.

## Consecuencias

- Ningún cambio de backend/tests — 100% frontend (`web/vision.html`, `web/blog.html` nuevo,
  `scripts/seed_vision_blog.py`) + una ruta nueva sin lógica propia (`GET /blog` en `app.py`, mismo patrón
  `FileResponse` que `GET /vision`).
- El panel "Estado en vivo" sigue siendo la única superficie que muestra texto crudo interno a propósito —
  cualquier sesión futura que quiera "limpiar más copy" tiene que respetar esa distinción, no vaciarla
  también (perdería la transparencia real que fue el mandato original de ADR 0167).
- Suite completa sin cambios: 1450/1450 (nada de Python se tocó esta ronda).
- Verificado en navegador real con Playwright: `/vision` y `/blog` en desktop (1440px) y mobile
  (375/390/360px), cero errores de consola, cerebro del hero visible y con parallax notorio en los tres
  anchos de mobile probados, filtro de categorías y vista de detalle del blog funcionando, flujo completo
  de "Hablar con Snarf" (lead real + demo real contra `mlx_local_fast`) reverificado en mobile tras los
  cambios — instancia de prueba (puerto 8010) apagada y `data/leads.jsonl` de prueba borrado al terminar.
