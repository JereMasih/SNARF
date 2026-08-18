# ADR 0170 — Páginas de profundidad, mapa mental de arquitectura, y CMS del blog

**Fecha:** 2026-08-17
**Estado:** Aceptado

## Contexto

Feedback real del fundador tras la ronda de ADR 0169: la home (`GET /vision`) había quedado demasiado
larga; el blog no llegaba a funcionar en producción (el server real del puerto 8002 seguía con el código
de antes de toda esta sesión, nunca se había reiniciado); faltaba una página de artículo real y un panel
de administración para publicar contenido; el fundador pidió explícitamente un "mapa mental" visual de la
arquitectura de agentes/capacidades, útil para entender el sistema; y pidió reencuadrar toda la superficie
también como material propio para explicarle el proyecto a potenciales clientes e inversores — lo que exige
más profundidad técnica real, no solo brevedad. También pidió sacar el fill sólido violeta→magenta de los
botones principales, a favor de fondo oscuro con borde/resplandor de acento.

## Decisión

**Contenido profundo mudado a 3 páginas propias**, confirmado con el fundador: `GET /arquitectura`,
`GET /capacidades`, `GET /roadmap` (`web/arquitectura.html`, `web/capacidades.html`, `web/roadmap.html`,
nuevos — mismo criterio de archivo único sin build step). La home (`web/vision.html`) acorta sus secciones
de "Cómo funciona"/"Capacidades"/"Roadmap" a una versión corta con un botón "Ver [sección] completa →" a la
página propia — reduce el largo real de la home sin perder el contenido, que ahora vive más desarrollado en
su propia página.

**Sección nueva en la home: "Por qué sumarte a Snarf ahora"** (`#invertir`), dirigida a inversores/socios
que el fundador va a llevar de la mano en una llamada — cuatro puntos honestos (construido en público
verificable, profundidad técnica real con link a `/arquitectura`, un problema real sin resolver, ambición
real de roadmap con link a `/roadmap`) + CTA `mailto:` directo. Sin cifras de tracción inventadas.

**Mapa mental de arquitectura, dato real (`GET /vision/architecture`, nuevo endpoint público):** lee
`NODE_TIER`/`NODE_PARENT`/`CENTER_NODE` directo de `snarf/telemetry/brain.py` (nunca llama a
`snapshot()`, que exige logs de actividad) — la misma estructura que ya gobierna el cerebro en vivo del
dashboard, así que un Especialista/Capacidad nuevo aparece en el mapa solo, sin tocar este endpoint de
nuevo. `web/arquitectura.html` agrupa los 41 nodos reales (1 orchestrator + 3 input + ~21 specialist + 16
capability) en clusters de PRESENTACIÓN legibles (ej. "Google Workspace" agrupa 7 nodos reales de Gmail/
Drive/Calendar/YouTube, mostrados como caption debajo del nombre del cluster) — nunca inventa una
jerarquía: cualquier nodo real no cubierto por un cluster se muestra suelto en vez de desaparecer en
silencio. El único nesting padre/hijo real que existe hoy (los 7 roles del Board Ejecutivo colgando de
`specialist_executive_board`) se dibuja como el caso flagship de "sub-agentes" que pidió el fundador —
corregido en la implementación real un bug de layout (los 7 satélites se superponían ilegibles por un
error de trigonometría en el fan-out y por estar posicionado en el extremo del arco); se corrigió con
espaciado vertical lineal fijo y reordenando el cluster lejos del borde.

**Blog con URL real por artículo + CMS:** `snarf/telemetry/blog.py` gana `slug` (derivado del título una
sola vez en `append()`, único entre todos los artículos, nunca recalculado en `update()` para no romper un
link ya compartido), `list_all()`, `get(id_or_slug)`, `update()`, `delete()` — reescribiendo el archivo
`.jsonl` completo en cada mutación (deja de ser estrictamente append-only: un artículo es contenido
editable, no un log de auditoría). `GET /blog/{slug}` sirve el mismo `web/blog.html`, que pasa de routing
por hash a routing por **path real** (`location.pathname`) — cada artículo tiene una URL compartible de
verdad, con navegación de browser real (no más `pushState` manual).

`web/blog_admin.html` (nuevo, `GET /blog/admin`, gateado a fundador con el mismo patrón 403 ya usado en
`GET /leads`/`GET /ops/processes`): editor Markdown liviano hecho a mano (headers, negrita, links, listas,
imágenes — sin librería externa vía CDN, mismo criterio de autocontención de `web/`) con vista previa en
vivo, subida real de imágenes (`POST /blog/admin/images`, guardadas en `data/blog_assets/`, servidas por
un `StaticFiles` montado solo en esa carpeta — mismo criterio acotado que `/vision/assets`), publicar/
despublicar, eliminar con confirmación. CRUD completo vía `GET/POST/PATCH/DELETE /blog/articles*`, todos
fundador-gated.

**Botones: fill sólido reemplazado por fondo oscuro + borde de acento**, en las 6 páginas públicas —
`.btn-primary` (magenta, CTA de conversión) y `.btn-aqua` (nueva, exploración secundaria) comparten el
mismo fondo oscuro semitransparente con el acento solo en el borde/resplandor, nunca un relleno sólido de
color.

## Consecuencias

- `data/blog_assets/` agregado a `.gitignore` (imágenes subidas, nunca se commitean).
- El mapa mental es presentación sobre datos reales, pero la agrupación en sí (`CLUSTERS` en
  `web/arquitectura.html`) es prosa/estructura escrita a mano — si `brain.py` cambia sustancialmente
  (un Especialista nuevo que merezca su propio cluster en vez de caer en "sin categorizar"), revisar ese
  archivo en la misma sesión que lo toque.
- `blog.py` ya no es estrictamente append-only (justificado: contenido editable, no un log de auditoría)
  — cualquier futuro consumidor que asumiera inmutabilidad tiene que revisar este cambio.
- 20 tests nuevos (`tests/test_blog.py` +8, `tests/test_app.py` +12). 1470/1470 tests de la suite completa
  (1450 previos + 20 nuevos).
- Verificado en navegador real con Playwright (desktop y mobile, las 5 páginas públicas): cero errores de
  consola; mapa mental legible con los 41 nodos reales agrupados; flujo completo del CMS probado en vivo
  (crear artículo con negrita/link/lista/formato real → publicar → aparece en `/blog` con sus categorías
  reales → URL real `/blog/<slug>` con el Markdown renderizado → editar → eliminar) contra el server de
  prueba; artículo y datos de prueba limpiados al terminar.
- **Reinicio del server real de producción (puerto 8002) pendiente como último paso de esta ronda** —
  autorizado por el fundador para hacerse una sola vez al cierre; hasta ese reinicio, `/blog`,
  `/arquitectura`, `/capacidades`, `/roadmap` y el resto de lo construido en ADR 0168/0169/0170 no están
  todavía disponibles en producción.
