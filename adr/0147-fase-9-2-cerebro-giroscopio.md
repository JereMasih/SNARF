# ADR 0147 — Fase 9.2: el cerebro como "giroscopio" (anillos independientes + junta directiva real)

**Fecha:** 2026-08-11
**Estado:** Aceptado

## Contexto

El fundador pidió llevar el "Cerebro de Snarf" (`#brainPanel`, el grafo de nodos real en
`web/index.html`) hacia la estética real del HUD de Iron Man — referencias enviadas: las esferas
holográficas de partículas que Stark/Banner manipulan (Jarvis/Ultron). **Alcance explícito, para no
confundir dos features con nombre parecido**: esto es "Cerebro de Snarf", nunca la "Vista HUD del
dashboard" (`#dashHudStage`, ADR 0090/0091, otro modelo de datos), que queda completamente afuera de
esta ronda.

Pedido concreto: el Orchestrator sigue en el centro, capas hacia afuera (capacidades, especialistas,
nodos de conexión), la junta directiva (7 roles, hoy un solo nodo) representada como sub-agentes, y que
cada capa exista como un anillo de giroscopio que rota/pulsa/gira de forma independiente según actividad
real — usando la observabilidad de las Fases 1-9 para reflejar procesos reales, nunca decorativo.

Dos decisiones confirmadas explícitamente con el fundador antes de tocar código:
1. Los "skills" se representan como un 4to anillo, agrupado por familia — nunca un nodo por tool (~90).
2. La junta directiva suma 7 nodos reales (confirmado factible: la telemetría ya distingue cada rol vía
   `agent.finished` con `skill=<rol>` — el trabajo real es taxonomía, no instrumentación nueva).

## Decisión

### Fase A — 7 nodos reales para la junta directiva (`snarf/telemetry/brain.py`)

`EXECUTIVE_ROLE_TO_NODE` (nuevo) mapea los 7 roles reales a 7 node_id nuevos
(`specialist_executive_board_<rol>`), sumados a `NODE_TIER` (tier `specialist`). `NODE_PARENT` (nuevo) es
la primera jerarquía padre/hijo real del cerebro — el resto de la taxonomía sigue plana a propósito (así
lo fijó ADR 0054), esta es la excepción real y documentada. `snapshot()` gana `lifecycle_entries`
(opcional): filtra `agent.finished`/`agent.failed` con `nodo == "specialist_executive_board"`, resuelve
el node_id real por `skill`, cuenta en finalización (nunca `.started`, mismo criterio que el resto de la
función) — **decisión explícita: nunca vuelve a tocar `CENTER_NODE`**, el Orchestrator ya se contó una
vez por el despacho real de `executive_board_consult`.

**Gap real encontrado y cerrado en el camino**: `AGENT_FINISHED`/`AGENT_FAILED` no estaban en
`LEGACY_EVENT_TYPES` (`snarf/telemetry/events.py`) — `events.recent()`/`all_events()` los ocultaban por
default en todos lados, incluido `/dashboard/brain` (`app.py`), que ahora pasa
`include_lifecycle=True` explícitamente.

### Fase B — verbo temático real en `/dashboard/brain`

`verbs.verbo_tematico()` (ya usado por `/dashboard/telemetry_feed`) se suma también acá — es lo que
etiqueta los chips del anillo 4 con texto real, determinístico, nunca generado por LLM. Traducción de
shape (brain.snapshot usa `node`/`label`/`status`, verbo_tematico espera `nodo`/`skill`/`estado`) vía
`events.TOOL_STATUS_TO_ESTADO`, nunca una segunda fórmula de verbo.

### Fase C — el giroscopio real (`web/index.html`)

**Nunca se reemplazó el motor 3D existente** (`project3D()`, `BRAIN_RING_Z`, `brainCamera3D.rotY`) — todo
se compone sobre él:

- `BRAIN_RING_SPIN_BASE`/`brainRingSpinAngle`: cada tier gana su propia velocidad angular (signos
  distintos a propósito), acelerada `×1.8` mientras tenga actividad real reciente
  (`brainTierHasRecentActivity`, mismo criterio que `BRAIN_ACTIVE_WINDOW_S` ya usa). `orchestrator` no
  gira (un solo nodo central).
- `brainApplyRingSpin(id, x, y)`: rota `(x,y)` alrededor del centro del grafo por el ángulo propio del
  anillo de `id`, ANTES de `project3D()` — compone la rotación de anillo con la vuelta de cámara
  compartida, nunca la reemplaza.
- `tierForNode(id)` consolida la lógica que antes vivía repetida e inline en 4 lugares distintos — única
  fuente de verdad de a qué anillo pertenece cada nodo.
- **Sincronía real, no solo cosmética**: `spawnBrainBurst`, `triggerBrainCameraFocus` y
  `updateAndDrawFlowParticle` (partículas de flujo, recalculadas cada frame) también aplican
  `brainApplyRingSpin` — sin esto, un burst/foco de cámara aparecería en la posición VIEJA del nodo
  mientras el nodo ya rotó a otro lado del anillo (mismo bug de desincronización que motivó tener
  `project3D` como única función de proyección, ver comentario original en el código).
- **Límite honesto, documentado**: la malla de partículas ambiente (`initBrainMesh`/`drawBrainMesh`, el
  "polvo" decorativo alrededor de cada nodo) NO sigue el spin de su anillo en esta ronda — son puntos
  generados una sola vez al abrir el panel, re-anclarlos en vivo a la posición girada de su nodo es un
  refactor más grande que se deja para una iteración futura si hace falta. Es la única pieza que no
  quedó 100% sincronizada; todo lo demás (nodos, edges, bursts, foco de cámara, flujo) sí.

**Sub-cluster de la junta directiva**: `createBrainGraphNode()` (extraído de `buildBrainGraphSkeleton`,
reusado por ambos anillos — nunca una segunda implementación) crea los 7 nodos del board en su propio
mini-anillo (`brainLayoutRing`, radio 42) centrado en la posición real de `specialist_executive_board`,
radio/ícono más chicos (satélites, no compiten visualmente con el anillo principal). Sus edges y
partículas de flujo salen del padre real (`boardProj`, calculado con el mismo spin que el resto), nunca
del centro — jerarquía real, no decorativa.

**Anillo 4 (skills)**: sin taxonomía nueva de "familias" — cada chip (`spawnSkillChip`, SVG `<text>`
transitorio, TTL 5s, `pointer-events: none` para nunca tapar el click de un nodo) cuelga del nodo padre
real que disparó el evento, con el verbo real como label. "Agrupado por familia" sale gratis de eso: los
chips de Gmail siempre orbitan el nodo real de Gmail. Excluidos del primer corte (alcance ya acordado):
`orchestrator`, los 3 vendors LLM/STT/TTS (demasiado frecuentes, inundarían el anillo), los 3 canales de
entrada, y `knowledge` (sin un skill real y legible por evento).

**Real-time vía SSE: NO esta ronda, decisión explícita.** Se mantuvo el poll de 3.5s
(`BRAIN_POLL_MS`) — aísla el rediseño visual (la parte de mayor riesgo/iteración) de una migración de
capa de datos aparte. `GET /events/stream` (Fase 2) sigue sin consumidores en el frontend; candidato
real para una fase separada una vez el fundador apruebe este corte visual.

## Verificado

- **Backend**: 6 tests nuevos en `tests/test_brain.py` (routing de `agent.finished`/`agent.failed` por
  rol, `.started` ignorado, `nodo` ajeno ignorado, `CENTER_NODE` nunca vuelto a tocar, jerarquía
  padre/hijo consistente), 1 test extendido en `tests/test_app.py` (verbo real en `/dashboard/brain`).
  1288/1288 tests de la suite completa.
- **Frontend, verificado con Playwright real en servidor aislado (puerto 8001, nunca 8002)**, contra
  datos reales de producción (no sintéticos):
  - Panel abre sin errores de consola; 41 nodos renderizados (1+3+14+7+16, exacto).
  - `BRAIN_EXECUTIVE_ROLE_NODES`: los 7 nodos del board existen y se agrupan en un cluster circular real
    (verificado numéricamente: mismo centro, mismo radio ~40px entre los 7).
  - Ángulo de rotación de cada anillo (`brainRingSpinAngle`) avanza de forma real y distinta por tier
    entre dos lecturas separadas por tiempo real — confirma la composición de rotaciones, no una sola
    vuelta compartida.
  - Anillo 4: un evento de tool real spawnea un chip con el verbo real, un evento excluido (`llm`) no
    genera chip, el TTL de 5s limpia el chip solo sin dejar DOM huérfano.
  - El drill-down por click en una fila del feed (única forma real de abrir detalle en este panel — no
    existe, ni existía antes, un click-handler en los nodos SVG en sí) sigue abriendo el panel real con
    datos reales, sin regresión.
  - Resize de ventana con el panel abierto: sin crash, sin desincronización SVG/canvas.
  - Feed real mostrando actividad real de la junta directiva ("Board: CTO · cto", "Board: COO · coo",
    etc.) — confirma que Fase A/B funcionan de punta a punta con producción real, no solo en tests.
