# ADR 0168 — Rediseño de conversión de `GET /vision`, blog real y demo pública con captación de Leads

**Fecha:** 2026-08-17
**Estado:** Aceptado

## Contexto

`GET /vision` (ADR 0167, mismo día) nació como una página de "estado + filosofía" sobria. El fundador pidió
una vuelta completa orientada a conversión para emprendedores y freelancers: comunicar qué es Snarf, cómo
funciona y por qué importa, con más violeta/magenta, el cerebro como fondo animado del hero con parallax,
scroll-reveal fluido, un roadmap más desarrollado y gráfico, y todas las capacidades (hoy + camino) — sin
perder el Principio VI de FOUNDATION.md (nada de testimonios, contadores o casos de uso inventados). Sobre
la marcha, el fundador sumó dos pedidos más: 6 artículos reales de blog sobre la historia de Snarf, y un
flujo real de captación de leads ("Hablar con Snarf") que pide nombre+email antes de habilitar una
conversación de demo con una versión inicial de Snarf.

## Decisión

**Paleta violeta/magenta reusada, no inventada.** `web/vision.html` adopta los mismos valores ya reales de
`--brain-violet`/`--brain-magenta`/`--brain-aqua` de `web/index.html:20-23` ("PALETA DE COLORES JERE MASIH
TRADER") como acento principal de sección — antes solo vivían dentro del cerebro. El ámbar queda acotado a
lo pedido: adorno tecnológico del entorno (partículas del hero, línea del roadmap, badge "en camino"),
nunca color de texto de sección.

**Hero con canvas de nodos ambiental, declarado explícitamente como decorativo, no como telemetría en
vivo.** El fondo del hero es un `<canvas>` con nodos en anillos (motivo visual del cerebro real, misma
paleta) animados de forma generativa, con parallax de scroll en 2-3 capas (`requestAnimationFrame`,
`translateY` a distinta velocidad), pausado fuera de viewport (`IntersectionObserver`) y con menos
partículas en mobile. Se documenta en el propio código que es arte ambiental inspirado en el cerebro, nunca
un segundo cerebro en vivo — mezclar "decorativo" con "dato real" sin distinguirlos violaría el Principio
VI. La prueba de que el cerebro real mide actividad real sigue siendo la captura de pantalla completa
(`shot-brain.png`, ADR 0167) y el panel de estado en vivo, sin cambios.

**Estructura nueva de la página:** problema/insight (posicionamiento honesto para emprendedores/freelancers,
sin dato inventado), "Cómo funciona" (arquitectura real de tres capas, COGNITION.md/ADR 0003, explicada en
lenguaje simple), "Capacidades" (grid con badge "Disponible hoy" vs. "En camino", tomado literalmente de
`MASTER_MAP.md` → Capabilities/Roadmaps), y "Roadmap" (reemplaza a "Historias reales": timeline visual con
línea animada violeta→magenta, nodos de Origen/Fundación técnica/Hoy — este último dinámico desde
`roadmap.summary`/`latest_phase` de `/vision/status`, sin prosa duplicada —/Fase 12/Fase 13/multi-usuario/
Norte del plan). Scroll-reveal reusa el lenguaje ya definido en `web/hud_design_tokens.css`
(`hud-materialize`: opacity+scale+blur), respeta `prefers-reduced-motion`. Sin cambios a
`snarf/runtime/vision_status.py` — toda la data dinámica ya existente se reusa tal cual.

**Blog: 6 primeros artículos reales, publicados.** `scripts/seed_vision_blog.py` (nuevo, corrido una vez a
mano) usa `snarf/telemetry/blog.append()` sin cambios de código — 6 artículos en primera persona con el
tono de CHARACTER.md, cada uno con `source_ref` a ADRs reales verificados (0003/0025/0026/0028/0032/0033/
0037/0056/0094/0098/0166) o a `FOUNDATION.md`/`ROADMAP_OBSERVABILIDAD_MULTIUSUARIO_N8N.md`, `public: true`
desde la creación (decisión explícita del fundador: sin ronda de revisión previa). `data/blog_posts.jsonl`
no estaba en `.gitignore` desde ADR 0167 (el archivo no existía todavía) — se corrige acá, mismo criterio
que el resto de los logs JSONL generados del proyecto.

**Captación de leads + demo pública ("Hablar con Snarf").** Primera superficie de escritura pública del
proyecto:
- `snarf/telemetry/leads.py` (nuevo): mismo patrón JSONL append-only que `blog.py` — `append(name, email)`,
  `list_all()`, `get(lead_id)`. `data/leads.jsonl` contiene PII real (nombre+email), agregado a
  `.gitignore`, nunca se commitea.
- `snarf/runtime/vision_demo.py` (nuevo): system prompt honesto (se presenta como demo, sin herramientas ni
  memoria más allá de la charla, nunca inventa haber ejecutado una acción real) + `demo_reply(lead_id,
  message, history)`, que llama a `llm_routing.build_resilient_llm("vision_demo")` **sin** `tools`/
  `tool_handler` — conversación pura, ningún visitante anónimo ejecuta una acción real. Tope duro de
  `MAX_DEMO_TURNS = 20` por lead, contado en memoria de proceso — protege el hardware local compartido con
  producción (no es un tema de costo: el modelo es gratis) ante una pestaña dejada abierta indefinidamente.
- **Nuevo rol de ruteo `"vision_demo"`** en `snarf/runtime/llm_routing.py`, default
  `{"provider": "mlx_local_fast", "model": MLX_LOCAL_FAST_MODEL}` — decisión explícita del fundador: el
  modelo del chat demo corre local (gratis) hasta nuevo aviso, y tiene que quedar elegible desde el panel
  de Configuración del fundador como cualquier otro rol (`web/index.html` `LLM_ROLES`), sin código nuevo de
  UI — reusa el selector ya existente.
- `app.py`: `POST /vision/lead` (valida nombre no vacío + forma de email, sin verificar la casilla ni
  enviar confirmación), `POST /vision/demo` (requiere `lead_id` real, 404 si no existe), `GET /leads`
  (founder-gated, mismo patrón 403 que `GET /ops/processes`). Ninguno de los dos primeros requiere sesión.
- **CTA final del flujo → login/registro real (`/login`), nunca una "descarga de app".** Decisión explícita
  con el fundador: hoy Snarf no tiene ningún instalable (PWA/Electron/paquete) — prometer una descarga
  inexistente hubiera violado el Principio VI. El footer y el cierre de la demo (al llegar al tope de
  turnos) apuntan al login real.
- Panel "Leads" nuevo en Configuración (`web/index.html`), gateado igual que "Control de infraestructura"
  (oculto si `GET /leads` no reconoce al fundador) — lista real de nombre/email/fecha, sin funcionalidad
  nueva de UI (reusa las clases `.ops-process-row` ya existentes).

## Consecuencias

- Primera vez que `GET /vision` acepta escritura pública sin autenticar (`POST /vision/lead`,
  `POST /vision/demo`) — superficie nueva de riesgo de abuso, mitigada por el tope de turnos por lead y por
  correr en un modelo local sin costo de API; sin rate-limiting por IP todavía (no existe en ningún endpoint
  del proyecto hoy) — si aparece abuso real, es trabajo aparte.
- El texto fijo de "Problema", "Cómo funciona" y las descripciones de "Capacidades" es prosa escrita a mano
  (igual que "Qué es Snarf" desde ADR 0167) — puede desincronizarse si `MASTER_MAP.md` cambia; revisar en
  cada sesión que toque ese documento.
- 17 tests nuevos (`tests/test_leads.py`, `tests/test_vision_demo.py`, 7 casos nuevos en `tests/test_app.py`),
  1450/1450 tests de la suite completa (1433 previos, post ADR 0167 + 17 nuevos).
- Verificado en navegador real con Playwright (desktop 1440px y mobile 390px): cero errores de consola,
  scroll-reveal y parallax del hero funcionando, timeline de roadmap legible en ambos anchos, flujo
  completo de "Hablar con Snarf" (lead real creado, demo respondiendo con el modelo local real
  `mlx_local_fast`, contador de turnos restantes correcto) probado en vivo contra una instancia descartable
  (puerto 8010, nunca el server de producción 8002) — instancia apagada y datos de prueba (`data/leads.jsonl`)
  limpiados al terminar.
