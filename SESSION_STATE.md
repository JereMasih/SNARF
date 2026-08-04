# SESSION_STATE — Plan HUD/Dock radial + telemetría

Documento vivo de continuidad. Si se pierde el historial de la
conversación, retomar leyendo esto (y los ADRs referenciados) no debería
perder nada importante ni ninguna decisión ya fijada. Reescrito/compactado
el 2026-08-03 a pedido explícito del fundador, tras varias fases y varias
rondas de feedback — la versión anterior (append-only) se estaba volviendo
difícil de navegar.

## Reglas de gobernanza de esta sesión

1. **Pausa entre fases:** regla original del fundador ("al terminar cada
   fase, PARÁ y esperá mi aprobación") — **waived** desde la Fase 2 en
   adelante ("el sentido de esto es la visualización... haz lo
   solicitado"). Se sigue actualizando este archivo al cierre de cada
   fase igual, pero sin pausa de aprobación entre ellas.
2. **Fase 7, pausa por nodo — NUNCA waived, sigue vigente.** Por su propio
   texto en el prompt original: "Esperá mi aprobación explícita antes de
   modificar cada uno [nodo/prompt]". Es una regla distinta de la (1), no
   se levantó con ella.
3. **MASTER_MAP.md / CLAUDE.md** siguen aplicando igual que a cualquier
   otra iniciativa del repo: ADR + CHANGELOG cuando una fase mueve código
   real (Fase 0 fue la única excepción, solo diseño/documentación).

## El plan (9 fases + 1 nota futura)

| # | Fase | Estado |
|---|---|---|
| 0 | Fundaciones: `TELEMETRY_SCHEMA.md` + `web/hud_design_tokens.css` | ✅ completa |
| 1 | Instrumentación real (evento unificado en los 3 logs existentes) | ✅ completa |
| 2 | Dock radial con datos mock (prototipo aislado) | ✅ completa |
| 3 | Historial de costos por día/agente/sesión | ✅ completa |
| 4 | Vista clásica intacta + Vista HUD del cerebro | ✅ completa |
| 5 | Motor de relevancia contextual → dock radial | ✅ completa |
| 6 | Panel de optimización de entrada | ✅ completa |
| 7 | Auditoría nodo por nodo (pausa obligatoria por nodo) | 🔶 en curso — nodo 1/4 cerrado |
| 8 | Refactor de eficiencia (sobre lo aprobado en Fase 7) | 🔶 nodo 1 ya refactorizado junto con su auditoría |
| 9 | (nota, no ejecutar) prep. eye-tracking/Vision Pro — la capa de gestos de Fase 2 ya está desacoplada para esto | sin arrancar |

Detalle de qué construyó cada fase, con sus ADRs: ver "Entregables por
fase" más abajo. CHANGELOG.md tiene la versión narrativa completa,
ADR 0077 a 0084 tienen el detalle técnico de cada una.

## Fase 7 — Auditoría nodo por nodo (estado detallado)

**Orden decidido por Claude** (pedido explícito: "decide vos el orden"),
por impacto real medido en `usage_log.jsonl`:

1. **Orchestrator (Sonnet 5, rol principal)** — ✅ **CERRADO** (Fase 7+8
   completas). 96%+ del gasto histórico real. `SYSTEM_PREFIX`: 15.385 →
   13.211 chars (-14,1%), solo contenido verificado palabra por palabra
   como duplicado con las `description` del schema `TOOLS` — el modelo ya
   las recibe aparte, no hacía falta repetirlas en prosa. Protocolo de
   confirmación en dos pasos y toda guía de orquestación cruzada real
   quedaron intactos a propósito (safety-critical / no duplicados en
   ningún tool individual). FOUNDATION/CONSTITUTION/CHARACTER evaluados,
   **no tocados** — ya económicos para lo que son, sin grasa retórica real
   verificada para cortar sin arriesgar matiz. Ver ADR 0084.
2. **Especialistas en Haiku** (Gmail digest, resumen de proyecto,
   sugerencia de subcarpetas, visión de Drive) — pendiente. 109 llamadas
   reales, 155.617 tokens de entrada / 32.689 de salida, $0.46 — volumen
   de entrada llamativo para prompts cortos, candidato a revisar si hay
   contenido no cappeado (mismo patrón del bug de ADR 0067).
3. **`conversation_title` (xAI Grok)** — pendiente, prioridad baja. El
   volumen alto de tokens ahí **ya está explicado por el fundador**: no es
   bug ni ruido, fue el fallback real usado mientras se agotó el crédito
   de Anthropic hasta volver a él. Solo falta confirmar que el ruteo
   post-recuperación sigue siendo el deseado.
4. **Voz (STT/TTS)** — pendiente, prioridad más baja. Ya casi sin costo
   (Kokoro local gratis, Groq barato).

## Trabajo en curso, fuera de la numeración de fases (2026-08-03, feedback real post-Fase 7)

El fundador empezó a usar la Vista HUD real y mandó feedback concreto,
más un pedido de rediseño visual grande. Orden de trabajo pedido: resolver
esto primero, compactar contexto (este archivo), después retomar Fase 7
nodo 2.

### 1. Verbos por tool — ✅ resuelto
`VERB_BY_SKILL` en `snarf/telemetry/verbs.py`, 68 entradas (una por tool
real), prioridad `skill` > `nodo` > `agente`. Ver ADR 0083.

### 2. Dock radial ("la rueda") — ✅ integrado (ADR 0083) y ✅ rediseñado (ADR 0086)
Se integró la lógica del prototipo de Fase 2/5 directo dentro de
`#brainHudView` (`web/index.html`) — arco de nodos con datos reales de
`/dashboard/dock_priority`, click filtra el feed de texto al lado. Bug de
sintaxis JS real encontrado y corregido en el camino (rompía TODO el
dashboard). Ver ADR 0083.

**El fundador mandó 6 referencias visuales (HUD Iron Man Mark III) + la
transcripción completa de un video real sobre cómo se construyó ese HUD**,
pidiendo aplicar esa lógica (nunca colores/marca literal, límite ya
establecido en ADR 0006/0037, reafirmado en ADR 0086). Rediseñado: el dock
ahora arranca colapsado en un solo anillo compacto ("widget Omega" — click
lo desbloquea/abre en abanico, mismo click lo cierra), con los bordes
desvanecidos (profundidad implícita, nunca corte duro) y reacción real: se
auto-abre una sola vez cuando una alerta genuina de costo aparece (Fase 5),
nunca simulada. Verificado con Playwright: colapsado/abierto/auto-apertura
por alerta real, los tres funcionando. 605/605 tests, sin backend tocado
(no hizo falta reiniciar producción). Ver ADR 0086.

**El fundador rechazó ese primer resultado** ("círculos horribles, sin
gracia, sin profundidad, sin luz volumétrica, sin efecto 3D") y pidió
fidelidad literal a sus referencias, autorizando explícitamente reusar su
estética (colores incluidos) — aclarado que esto nunca fue una regla de
FOUNDATION/CONSTITUTION, solo un ADR de diseño ordinario, revisable con su
autoridad real (Constitution Art. II), sin necesidad de ningún atajo.

**Dock v2 (ADR 0087) — reconstrucción real con SVG:** glow volumétrico
real vía filtros SVG (`feGaussianBlur`), anillo con marcas rotando, líneas
guía SVG desde el hub hasta cada chip (alineadas en píxeles reales),
chips en paralelogramo con glow en tres capas, acento rojo nuevo
(`--hud-signal-red`, acotado solo a este componente). Dos bugs reales
encontrados verificando con Playwright (`elementFromPoint`, no a ojo): un
typo (`position:relative` en vez de `absolute`) rompía el click/hover de
todos los chips; el hitbox del anillo de apertura seguía tapando al chip
más cercano al centro con el dock abierto. 605/605 tests.

**Limitación honesta, no resuelta:** el dock vive en una franja de ~190px
dentro del panel modal — a esa escala el detalle fino es necesariamente
menos legible que en las referencias (ilustraciones a pantalla completa).
Si el fundador quiere el dock a pantalla completa, es una decisión de
layout aparte, no tomada todavía.

**Dock v3 (ADR 0088) — la rueda como escenario principal, reacción real
automática:** el fundador señaló el problema de fondo — el dock v2
requería click para abrir, por default no mostraba nada ("un orbe en
standby"). Cambiado: arranca abierto (`data-open="1"` por defecto), ocupa
casi todo el panel (`flex:1`, antes 190px fijos), etiquetas siempre
visibles, tabla de texto reducida a un renglón. Generalizado el
"story moment" de la alerta de costo a TODO evento real: cada evento
nuevo real destella su chip y línea guía correspondiente sin ninguna
interacción — verificado con Playwright sembrando un evento real y
capturando el destello en vivo (~1.8s después). 605/605 tests, cambio
100% frontend (no requirió reiniciar producción, solo recargar la
pestaña).

**Pendiente, no pedido explícitamente todavía:** el mismo rediseño (v1,
v2 y v3) no se aplicó a `web/hud_dock_prototype.html` (el standalone de
Fase 2/5) — cambio menor si se pide.

### 2b. Globos contextuales (ADR 0089) — ✅ resuelto

El fundador vio Dock v3 en producción y señaló el problema de fondo real:
"no está mostrando absolutamente nada... es un orbe que late... pero eso
es todo lo que hace." Con un ejemplo concreto (preguntar por un canal, ver
a Snarf revisar el historial, armar un documento de Drive y mandarlo por
mail), pidió que cada skill/capacidad/especialista tenga su propio widget
con contenido real. **Rechazó un primer plan de cobertura parcial**
("representativo, no exhaustivo") explícitamente: "no veo en el plan
incluir el desarrollo de los globos contextuales para cada skill capacidad
o especialista, ni sus sub elementos" — el plan final entrega cobertura
completa.

Causa raíz real: el evento unificado nunca capturó CONTENIDO, solo
identificadores (`skill` = `tool_name` literal). `snarf/telemetry/detail.py`
(nuevo) agrega el campo `detalle`: un extractor real por cada uno de los
**60 tools** del Orchestrator (número real verificado contra
`orchestrator.TOOLS`, no 68 como se estimó en la exploración inicial),
cobertura exigida por test (`test_detail_extractors_cover_every_orchestrator_tool`).
Wireado en los tres chokepoints reales (`activity_log`, `usage_tracker`
para LLM/STT/TTS — usa texto real ya en scope en cada capability de
vendor —, `input_log`).

`DOCK_NODE_IDS` (antes 9 nodos a mano) pasó a ser `list(brain.NODE_TIER.keys())`
— los 24 nodos reales completos; el frontend muestra el top-9 por
relevancia real (`HUD_MINI_MAX_CHIPS`), no un subconjunto fijo. Capa nueva
`#hudBubbleLayer`: un globo por nodo activo, anclado al chip real, con 9
familias visuales compartidas (`HUD_BUBBLE_FAMILY`), TTL real (~20s) y
prioridad por conversación activa. Tabla de feed eliminada por completo
(pedido explícito: "no aporta nada").

**Dos bugs reales de layout encontrados y corregidos verificando con
Playwright** (bounding box del hub contra `#brainPanel`, no a ojo): el hub
se geometrizaba con el fallback 300×190 mientras la Vista HUD seguía
oculta al abrir el panel (hasta 130px fuera del panel real) — corregido
forzando un rebuild al activar la vista; el offset vertical del hub
(heredado de antes de sacar la tabla de feed) no dejaba margen real una
vez el dock pasó a ocupar todo el panel — ajustado en dos iteraciones
medidas hasta confirmar margen real.

621/621 tests (16 nuevos). Verificado con Playwright en servidor aislado:
4 familias de globos con contenido real, expiración real por TTL de punta
a punta, hub dentro del panel con margen real, cero errores de consola
reales. Backend requiere reinicio de producción; capa de globos y layout
son 100% frontend. Ver ADR 0089.

**Hallazgo aparte, no corregido (fuera de alcance):** `EpisodicMemory._read_all()`
(`snarf/memory/episodic.py`) no chequea si `episodic_memory.jsonl` existe
antes de leerlo (a diferencia del resto de módulos de telemetría) — 500
real en `/dashboard/summary` contra un directorio de datos nuevo desde
cero. No afecta al fundador hoy (su archivo real ya existe). Pendiente de
una corrección aparte.

### 3. Bug real encontrado y CORREGIDO: fuga de test pollution visible en producción
La captura del fundador mostró filas `gemini:gemini-3-pro-preview` /
"pontificando" ahogando el feed real. Causa real: **solo**
`tests/test_gemini_llm.py` (y un test suelto en `test_kokoro_tts.py`) —
**corrige una atribución imprecisa anterior**: `test_llm_routing.py`
nunca fue la fuente (nunca llama `.generate()`, el grep original matcheaba
un string usado como valor de configuración en el test, no una llamada
real). Arreglado con el mismo patrón de aislamiento ya usado en
`test_app.py`, y **purgadas** las 605 + 11 entradas sintéticas ya
existentes en `data/usage_log.jsonl`/`data/telemetry_events.jsonl` reales
(huella exacta e inequívoca, backup tomado antes). Confirmado 0 entradas
sintéticas después, y conteo estable (605→605) tras correr la suite de
nuevo — la fuga está cerrada, no solo purgada una vez. No hizo falta
reiniciar el servidor (solo se tocaron archivos de test/datos). Ver ADR
0085. 605/605 tests.

## SNARF OS — dashboard radial (2026-08-04, ya excede el plan original de 9 fases)

El fundador vio el dock de globos contextuales (ADR 0089) y pidió que deje
de ser un experimento acotado a un widget y se convierta en **el nuevo
dashboard principal de Snarf**: esfera central animada, widgets
distribuidos por toda la pantalla que se reposicionan solos por relevancia
real, animación completa, drill-down por widget, chat integrado como barra
inferior colapsable. Sobre la imagen de referencia (con métricas de negocio
que Snarf no trackea): pidió explícitamente el ecosistema genérico, no una
lista fija — que una capacidad nueva futura entre sola al dashboard sin
trabajo de UI nuevo. Confirmó Especialistas de IA reales curando el
dashboard, y todo en un solo desarrollo. Tras revisar el plan, agregó una
condición más: **reversibilidad real con un botón** (toggle persistido,
igual que el del panel Cerebro) — "si no me gusta el desarrollo, podemos
siempre volver a la versión clásica."

**✅ Resuelto, ver ADR 0090** — resumen:
- Motor de datos único (`snarf/telemetry/widget_summary.py`), compartido
  con el dock de globos de ADR 0089 — nunca dos pipelines paralelos.
- `DashboardCuratorSpecialist` (`snarf/specialists/dashboard_curator.py`)
  real, patrón cache-first como `GmailDigestSpecialist`, nunca decide qué
  widgets existen (eso sigue siendo determinístico), refresca en un loop
  de backend cada 10 min — nunca por poll del navegador.
- Toggle Vista clásica/HUD persistido (`dashboard_view` en
  `DashboardPreferences`, default `"classic"`) — TODO el código de la
  grilla clásica se conservó sin tocar una línea; todo lo nuevo es
  aditivo, detrás del toggle.
- Esfera central (reusa `.orb-sphere`, no el anillo Omega del dock — ese
  queda intacto para el panel Cerebro), layout radial en anillos
  concéntricos, reposición real vía FLIP (nunca destruye un widget que
  sigue relevante), drill-down genérico por nodo, `#chatDock` colapsable
  (mismo criterio "mover el nodo vivo, nunca clonar" ya establecido).
- Vista HUD es desktop-only (`≥900px`) — mobile no se tocó.
- **Cuatro bugs reales encontrados y corregidos verificando con
  Playwright**: colisión de `transform` real (orb ~90px fuera de centro,
  mismo tipo de bug que ADR 0069/0078); `#chatDock` no se ocultaba al
  angostar a mobile; el parser de captions del curador fallaba contra una
  respuesta REAL del LLM (el modelo repetía el `(score N.N)` del prompt);
  el layout radial amontonaba widgets en medio círculo por dividir el
  ángulo por capacidad máxima del anillo en vez de ocupación real.
- 660/660 tests (39 nuevos). Curador verificado con una llamada real al
  LLM (no mock), generando `headline` + 5 `node_captions` correctos sobre
  datos reales sembrados.

**Hallazgo aparte, no corregido (documentado en ADR 0090):** el propio
`DashboardCuratorSpecialist` es, en sí mismo, una llamada real al LLM — su
`detalle` en el nodo `llm` a veces muestra un fragmento de su propio
`headline` anterior (dato 100% real, pero temáticamente circular). Mejora
incremental futura, no bloqueante.

**Pendiente, no pedido explícitamente todavía**: vista rica por nodo en el
drill-down (hoy es un panel genérico de actividad para los 24 nodos, a
propósito — evita dejar controles interactivos de Drive/Gmail/Calendar/
YouTube a medio wirear dentro de un panel nuevo).

## SNARF OS v2 — plantillas, 3D real, y el curador elige presentación (2026-08-04)

Tras probar v1 en producción, el fundador pidió una pasada mucho más
profunda, inspirada en el HUD de Iron Man: widgets más grandes con más
información real, sensación 3D genuina (no solo el orbe — también el chat
y los widgets entre sí), líneas de conexión esfera→widget, jerarquía por
transparencia, input siempre visible con un botón de foco sutil (no la
barra grande de v1), posición configurable del chat, y un curador que
elija **cómo** presentar cada widget, no solo qué texto poner. También
pidió delegarle crear/modificar otros agentes — contrastado contra
`CONSTITUTION.md` (Art. III/V/línea 109), se separó en Track A (este
ciclo) y Track B (fuera de alcance, iniciativa aparte).

**✅ Resuelto, ver ADR 0091** — resumen:
- `snarf/telemetry/widget_templates.py` (nuevo): 24 plantillas, 3 tamaños
  (`assign_tier`, mecánico por ranking real) × 8 variantes (elegidas por
  el curador, nunca el tamaño en sí).
- `widget_summary.py`: `recent_activity_buckets`/`recent_items`
  (histograma/lista real, mecánicos, sin LLM) + `size_tier` por widget.
- `dashboard_curator.py`: elige variante + puede proponer una plantilla
  nueva (cola de solo lectura, nunca aplicada sola — techo real de
  autonomía de esta ronda); el nodo `cost` se cura como cualquier otro.
- `web/index.html`: primera escena con perspectiva CSS real del archivo
  (antes, la "3D" del cerebro era proyección a mano en JS/canvas) —
  widgets con profundidad por anillo, chat con burbujas alejándose hacia
  el fondo (acotado a `#chatDock`); líneas de conexión SVG; chat-dock
  rediseñado (input siempre visible, botón de foco chico,
  `openChatFocus`/`closeChatFocus` corregidos para funcionar desde
  cualquier vista); posición configurable del chat; drawer lateral de
  conversaciones/proyectos con pin.
- **Seis bugs reales encontrados y corregidos verificando con
  Playwright**, cuatro de ellos en el mismo problema (layout radial,
  visibles en cadena): dos colisiones de z-index nuevas contra modales
  existentes; alineación radial sistemática entre anillos; un radio
  circular que no cabe en un rectángulo angosto de escritorio (la elipse
  probada después rompía la garantía de separación); **un solver
  iterativo de pares que no convergía** en grupos densos (más
  iteraciones/amortiguación lo empeoraron — reemplazado por completo por
  un empaquetado constructivo por espiral, que garantiza cero
  superposición por construcción, no por convergencia); el dock de chat
  fijo, invisible para el cálculo de layout. Más una regresión de cache:
  el `template` del curador se validaba contra el tamaño que el nodo
  tenía al curarlo, no el actual.
- 688/688 tests (28 nuevos). En el camino: una fuga real de test
  pollution (mismo tipo que ADR 0085) — `test_app.py` no aislaba el
  `CACHE_DIR` de `dashboard_curator`, leía cache real de producción.
  Verificado con Playwright, datos reales sembrados: cero superposiciones
  confirmadas programáticamente (bounding boxes reales), curador probado
  con LLM real, drawer/foco/posición/reversibilidad verificados de punta
  a punta.

**Fuera de alcance explícito — Track B**: delegarle al curador (o a
cualquier agente) crear/modificar Specialists de verdad. Fundamento:
`CONSTITUTION.md` Art. III/V/línea 109 — ninguna autoridad de ese tipo
nace de una delegación general. Iniciativa aparte, con su propio plan de
gobernanza y aprobación caso por caso, si se retoma.

## Operativo — servidor real (no parte del plan de 9 fases)

- Servidor de producción: puerto 8002, `nohup .venv/bin/python -m uvicorn
  app:app --host 0.0.0.0 --port 8002 >> server_8002.log 2>&1 & disown`,
  corrido desde la raíz del repo.
- Link real, fijo, no cambia con reinicios:
  `https://macbook-pro-de-jeremas.tailb10c73.ts.net` (Tailscale Serve,
  proxya a `127.0.0.1:8002`).
- Reiniciado 3 veces en esta sesión (autorización explícita del fundador:
  "si debes reiniciar el servidor... hazlo"): (1) para levantar
  Fase 1-6 por primera vez — el proceso venía corriendo desde antes de la
  sesión, sin nada de la instrumentación nueva; (2) para el fix del bug de
  sintaxis JS; (3) para el recorte de `SYSTEM_PREFIX`. Siempre verificado
  con el log real (`tail server_8002.log`) antes de dar por hecho el
  reinicio.
- El fundador ya generó actividad real de punta a punta post-reinicio
  (verificado: llamada real a Sonnet 5, $0.0285, conversación real, TTS
  local real en `data/telemetry_events.jsonl`).

## Decisiones de diseño fijadas (no reabrir sin motivo nuevo)

- **Esquema de telemetría extiende, no reemplaza** los 3 logs reales
  (`activity_log`/`usage_log`/`input_log.jsonl`) ni la normalización de
  `brain.py` — `nodo`/`agente` son literalmente `node_id`/`tier` de ahí.
- **Instrumentación por chokepoint** (adentro de las 3 funciones
  `record()`), no por los ~80 call sites individuales.
- **`conversation_id` real por thread** (`snarf/telemetry/context.py`,
  `threading.local()`, mismo criterio que el fix de ADR 0041) — seteado
  por `Orchestrator.handle()`, leído automáticamente por el evento
  unificado sin parámetro nuevo en ningún `record_*`.
- **Paleta HUD reusa `--glow` (cian) existente.** Ámbar (`--hud-amber`,
  `#ffb454`) es una decisión de diseño **nueva** de esta iniciativa, no
  viene de ningún documento real del fundador (a diferencia de la paleta
  del cerebro clásico, ADR 0033) — reservado para atención/alerta.
- **Verbo temático es un dict determinístico, nunca generado por LLM**
  (`snarf/telemetry/verbs.py`) — prioridad `skill` (68 tools reales) >
  `nodo` > `agente`.
- **Costo desconocido nunca es cero** — se cuenta aparte
  (`llamadas_sin_costo_estimado`), mismo criterio en `cost_history.py` y
  `usage_tracker.summarize()`.
- **`DAILY_COST_ALERT_THRESHOLD_USD = 1.00`** (`relevance.py`) — decisión
  de diseño nueva, no fijada por el fundador, fácil de ajustar.
- **"Tarea activa"/"alertas pendientes" (Fase 5) interpretados con
  honestidad**: no hay sistema real detrás en Snarf. Tarea activa = nodo
  con actividad más reciente. Alerta = error reciente. Documentado en ADR
  0081, no se inventó infraestructura nueva.
- **Resumen input/output del feed = recorte mecánico de texto ya real**
  (`skill`, truncado), nunca una llamada nueva al LLM.
- **Selección exclusiva con cambio directo en el dock** (Fase 2): con un
  nodo ya anclado, clickear OTRO lo selecciona directo, sin forzar cerrar
  primero. Decisión de UX no especificada en el prompt original.
- **Archivos de Fase 2/3 (`web/hud_dock_prototype.html`,
  `hud_cost_history_prototype.html`, `hud_input_efficiency_prototype.html`)
  siguen sin enlazarse desde `web/index.html`** — son prototipos aislados,
  verificados con datos reales vía fetch-con-fallback-a-mock. Solo el
  dock (Fase 7, feedback real) se portó de verdad a la app — el resto
  sigue pendiente de integración final.

## Gaps reales conocidos, no resueltos (documentados a propósito, no en abstracto)

1. `latencia_ms` no existe para llamadas de vendor puro (`usage_log`),
   solo para `activity_log`. No bloqueaba nada de lo pedido hasta ahora.
2. Los logs no comparten `event_id` — si una fase futura necesita
   correlacionar un tool call con el LLM call que dispara adentro, hay que
   definirlo contra el código real.
3. ~~Fuga de test pollution real~~ — **RESUELTA** (ver ADR 0085): era solo
   `test_gemini_llm.py` (corrige atribución anterior a `test_llm_routing.py`,
   nunca fue la fuente real), aislada y purgada.
4. El ahorro de `SYSTEM_PREFIX` (Fase 7 nodo 1) no se midió todavía en
   dólares reales (el prompt está cacheado — el ahorro pega en cache-write,
   no en cada turno) — pendiente si el fundador lo pide con tráfico real.

## Entregables por fase (archivos + ADRs, para navegar rápido)

- **Fase 0:** `TELEMETRY_SCHEMA.md`, `web/hud_design_tokens.css`. Sin ADR.
- **Fase 1:** `snarf/telemetry/{events,verbs}.py` (nuevos);
  `activity_log.py`/`usage_tracker.py`/`input_log.py`/`brain.py`/
  `anthropic_llm.py` (modificados). ADR 0077.
- **Fase 2:** `web/hud_gestures.js`, `web/hud_dock_prototype.html`
  (nuevos, prototipos aislados). ADR 0078.
- **Fase 3:** `snarf/telemetry/{context,cost_history}.py` (nuevos),
  `GET /dashboard/cost_history`, `web/hud_cost_history_prototype.html`.
  ADR 0079.
- **Fase 4:** `GET /dashboard/telemetry_feed`, toggle Vista clásica/HUD en
  `web/index.html` (`#brainLayoutClassic`/`#brainHudView`). ADR 0080.
- **Fase 5:** `snarf/telemetry/relevance.py` (nuevo),
  `GET /dashboard/dock_priority`, dock del prototipo conectado a datos
  reales. ADR 0081.
- **Fase 6:** `snarf/telemetry/input_preprocessing.py` (nuevo),
  `GET /dashboard/input_efficiency`,
  `web/hud_input_efficiency_prototype.html`. ADR 0082.
- **Feedback post-Fase 7 (verbos + dock real + bug JS):** `verbs.py`
  extendido, `web/index.html` (mini-dock dentro de `#brainHudView`,
  `HUDGestureControllerMini`). ADR 0083.
- **Fase 7/8, nodo Orchestrator:** `snarf/core/orchestrator.py`
  (`SYSTEM_PREFIX` recortado). ADR 0084.
- **Fix de fuga de test pollution real:** `tests/test_gemini_llm.py`,
  `tests/test_kokoro_tts.py` (aislamiento), purga de
  `data/usage_log.jsonl`/`data/telemetry_events.jsonl` reales. ADR 0085.
- **Dock v1, anillo Omega:** `web/index.html` (`#hudRingIdle`,
  `data-open`). ADR 0086.
- **Dock v2, glow volumétrico SVG real:** `web/index.html` (hub SVG,
  líneas guía, chips en paralelogramo, `--hud-signal-red`). ADR 0087.
- **Dock v3, escenario principal + reacción automática:** `web/index.html`
  (`flex:1` en `.hud-mini-dock`, `pulseHudDockNode`, orden de poll
  corregido). ADR 0088.
- **Globos contextuales, cobertura total:** `snarf/telemetry/detail.py`
  (nuevo); `events.py`/`activity_log.py`/`usage_tracker.py`/`input_log.py`/
  `orchestrator.py`/`relevance.py` (modificados); capabilities de vendor
  (`anthropic_llm.py`, `gemini_llm.py`, `openai_compatible_llm.py`,
  `elevenlabs_stt.py`, `elevenlabs_tts.py`, `groq_stt.py`, `local_stt.py`,
  `kokoro_tts.py`) pasan `detalle` real; `web/index.html`
  (`#hudBubbleLayer`, `HUD_BUBBLE_FAMILY`, `HUD_MINI_MAX_CHIPS`, tabla de
  feed eliminada); `tests/test_telemetry_detail.py` (nuevo). ADR 0089.
- **SNARF OS, dashboard radial con curador real:**
  `snarf/telemetry/widget_summary.py` (nuevo),
  `snarf/specialists/dashboard_curator.py` (nuevo); `app.py`
  (`GET /dashboard/widget_summaries`, `/curation`, `/node_activity/{id}`,
  loop periódico del curador); `dashboard_prefs.py` (`dashboard_view`,
  `hud_widget_state`/`hud_widget_options`, aditivo); `llm_routing.py`
  (rol `dashboard_curator`); `web/index.html` (toggle Vista clásica/HUD,
  esfera central, layout radial + FLIP, drill-down genérico, `#chatDock`);
  `tests/test_widget_summary.py`/`test_dashboard_curator.py` (nuevos),
  `test_dashboard_prefs.py`/`test_app.py` (extendidos). ADR 0090.
- **SNARF OS v2, plantillas + 3D real + curador que elige presentación:**
  `snarf/telemetry/widget_templates.py` (nuevo, 24 plantillas);
  `widget_summary.py` (`recent_activity_buckets`/`recent_items`,
  `size_tier`); `dashboard_curator.py` (variante + propuestas de
  plantilla); `app.py` (`GET /dashboard/widget_templates`,
  `/template_proposals`, validación de template cacheado contra tier
  actual); `dashboard_prefs.py` (`hud_chat_position`,
  `hud_sidebar_pinned`, aditivo); `web/index.html` (perspectiva 3D real
  para widgets y chat, líneas de conexión SVG, chat-dock sin barra grande
  + botón de foco chico, `chatHomeEl`, drawer lateral con pin,
  empaquetado radial constructivo `packHudWidgets`);
  `tests/test_widget_summary.py`/`test_dashboard_curator.py`/
  `test_dashboard_prefs.py`/`test_app.py` (extendidos). ADR 0091.

Suite completa: 688/688 tests al cierre de la última fase documentada.
