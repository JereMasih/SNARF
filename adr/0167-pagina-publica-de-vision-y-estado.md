# ADR 0167 — Página pública de visión y estado (`GET /vision`)

**Fecha:** 2026-08-17
**Estado:** Aceptado

## Contexto

Snarf no tenía todavía una superficie de cara afuera: `/` requiere sesión (fundador o Google), y no existe
ningún lugar donde alguien sin acceso pueda entender qué es Snarf, en qué principios se apoya, y en qué
estado real de desarrollo está. El fundador pidió una página de estado pública dentro de `web/`, con
calidad de referencia visual (moderna, capturas reales pequeñas, sin exagerar) combinada con densidad de
datos real para la sección de desarrollo (paneles, no ilustraciones) — sin perder un viaje de conversión
real (hook → prueba → confianza → acción). Mandato explícito, aplicación directa del Principio VI de
FOUNDATION.md: todo el contenido tiene que derivarse de archivos reales del repo en el momento del build o
del request, nunca texto de relleno inventado.

## Decisión

**Nueva ruta pública, sin gate de login:** `GET /vision` sirve `web/vision.html` (un solo archivo
HTML/CSS/JS, mismo criterio que `web/index.html` — sin build step, sin framework nuevo). Reusa los tokens
`--hud-cyan`/`--hud-amber` de `web/hud_design_tokens.css` (valores inlineados, no un `<link>` externo,
mismo criterio de autocontención que el resto de `web/`).

**`GET /vision/status`** (nuevo `snarf/runtime/vision_status.py`): cada número se lee de los archivos
reales del repo en el momento del request, nunca se cachea ni se hardcodea.
- `roadmap.summary`/`roadmap.mark_note`: primer párrafo real después de los headings `## Estado actual` y
  `## Norte del plan: "Mark 1" vs. "Mark 2"` de `ROADMAP_OBSERVABILIDAD_MULTIUSUARIO_N8N.md` — nunca un
  resumen escrito a mano que pueda desincronizarse del roadmap real.
- `roadmap.latest_phase`: el número de Fase más alto mencionado en ese párrafo (inferencia declarada como
  tal, nunca presentada como un campo "oficial" del roadmap).
- `changelog_recent`: últimas 5 entradas parseadas de `CHANGELOG.md` (fecha, título, ADR si tiene).
- `adr_count`: cantidad real de archivos en `adr/*.md`.
- `test_function_count`: cantidad real de `def test_` en `tests/test_*.py` — deliberadamente distinto del
  conteo de casos de pytest que reporta CHANGELOG.md (ese cuenta instancias parametrizadas; esto cuenta
  funciones), por eso el campo se llama `test_function_count` y no `test_count` — nombrarlo genérico
  hubiera insinuado que es el mismo número que "1421/1421 tests" de una entrada de CHANGELOG, y no lo es.

**Blog de Snarf — nuevo modelo de datos, `snarf/telemetry/blog.py`:** JSONL append-only (mismo patrón que
`activity_log.py`), un artículo por línea (`id`, `created_at`, `title`, `summary`, `body`, `tags`,
`source_ref`, `public`). `public` arranca en `False`: un artículo recién escrito por Snarf a partir de una
investigación real de `snarf/specialists/research` no queda visible en `GET /vision/blog` hasta
publicarse a mano. **Esta ronda deja el modelo de datos y el endpoint construidos y funcionales, sin
ningún artículo real todavía** — `data/blog_posts.jsonl` no existe, `GET /vision/blog` devuelve
`{"articles": []}` y la página muestra un estado vacío explícito. Nada de contenido de ejemplo: rellenar
esa sección con texto que parezca un artículo ya publicado habría violado el Principio VI (fabricar prueba
de un blog activo que no existe).

**"Historias reales" — sección de roadmap, no de testimonios.** Tres tarjetas etiquetadas
`ROADMAP · Fase N` con contenido derivado de fases reales todavía no construidas (Fase 12 — replay; Fase
13 — BYO-compute; "Norte del plan" — Mark 1 → Mark 2). Sin nombres, sin casos de uso ya ocurridos, sin
video — exactamente lo que pidió el fundador para no fabricar prueba social inexistente.

**Capturas reales de la interfaz (3):** tomadas con Playwright contra una instancia real de la app —
nunca contra el server de producción (puerto 8002, ver CLAUDE.md): se levantó una instancia descartable
en un puerto de prueba (mismo criterio ya documentado de "instancias de prueba en 8000/8001", acá 8010),
se generó un cookie de sesión válido con `create_session_token()` usando el `SESSION_SECRET` real del
`.env` (nunca se tocó la contraseña real ni se inventaron credenciales), se navegó y capturó, y la
instancia se apagó al terminar. Tres vistas: cockpit de escritorio (modo "jarvis", ≥900px — chat +
dashboard + widgets reales de costo/memoria/Drive/YouTube), chat en viewport móvil (estado vacío
deliberado: no se capturó ninguna conversación real del fundador para evitar exponer contenido privado en
una página pública), y el cerebro en pantalla completa (invocado con
`page.evaluate("openBrainFullscreen()")`, sin necesidad de mockear datos — es telemetría real del proceso
corriendo). Redimensionadas con Pillow a ancho ≤960px para no servir capturas de resolución completa sin
necesidad. Servidas desde `web/vision_assets/` vía un `StaticFiles` montado **solo en esa carpeta**
(`app.mount("/vision/assets", ...)`) — nunca un mount genérico de `web/` entero, para no exponer nada más
que las tres screenshots.

**Ámbar reusado tal cual de `hud_design_tokens.css` (`#ffb454`)** — no es el naranja de CrewAI ni estética
de circo; es el dorado apagado ya documentado como "capa de atención", reusado sin modificar. **Pendiente
real: confirmar con captura junto al fundador si ese tono lee bien en el contexto nuevo de esta página**
(pedido explícito suyo antes de dar el resultado final por bueno).

**CTA final:** decidido con el fundador — sin formulario ni backend nuevo. Dos enlaces reales: al
repositorio público (`github.com/JereMasih/SNARF`, confirmado público con `gh repo view`) y un `mailto:`
directo. Nada de lead-gen ni superficie de contacto que no exista hoy.

**`<div id="brand-mark">`:** placeholder sin forma ni color definitivo (círculo vacío con borde cian
tenue) — el brief de identidad real (luz, valores de amor/fe/caridad/honor, evitar naranja y estética de
parque de diversiones) queda para una fase de diseño aparte, no resuelto acá.

## Consecuencias

- Primera superficie pública de Snarf — cualquier cambio futuro a `FOUNDATION.md`/`ROADMAP_OBSERVABILIDAD_MULTIUSUARIO_N8N.md`/`CHANGELOG.md` se refleja solo en las secciones parseadas dinámicamente (`/vision/status`); el texto fijo de "Qué es Snarf" y "Historias reales" es prosa escrita a mano y puede desincronizarse con el tiempo — revisar en cada sesión que toque esos documentos.
- `snarf/telemetry/blog.py` queda sin ningún productor real todavía: conectarlo a `snarf/specialists/research` (generar+revisar+publicar un artículo real) es trabajo aparte, no arrancado en esta ronda.
- 12 tests nuevos (`tests/test_blog.py`, `tests/test_vision_status.py`, 3 casos nuevos en `tests/test_app.py`), 1433/1433 tests de la suite completa (1421 previos + 12 nuevos).
