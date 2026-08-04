# ADR 0089 — Globos contextuales: contenido real por nodo, y cobertura total del dock

**Fecha:** 2026-08-04
**Estado:** Aceptado

## Contexto

Dock v3 (ADR 0088) resolvió el layout (la rueda como escenario principal,
reacción automática con un pulso por evento real) pero no resolvió el
problema de fondo que el fundador señaló al verlo en producción: "no está
mostrando absolutamente nada... es un orbe que late... pero eso es todo lo
que hace." Un pulso es una señal binaria — "algo pasó en este nodo" —
nunca *qué* pasó. Pedido explícito, con un ejemplo concreto (preguntar "¿en
qué quedó esto?" sobre un canal, ver que Snarf revisa el historial, arma un
documento de Drive y lo manda por mail): que cada skill/capacidad/
especialista tenga su propio widget de información mostrando contenido
real, apareciendo cuando es relevante y desapareciendo cuando deja de
serlo.

Investigando el pipeline de telemetría real se encontró la causa raíz
honesta: el evento unificado (`snarf/telemetry/events.py`) nunca capturó
contenido, solo identificadores (`nodo`, `agente`, `skill` = `tool_name`
literal). No existía el destinatario real de un mail, el título real de un
documento, ni el texto real de una búsqueda — el dock no podía mostrar más
que un pulso genérico porque el dato no existía. Además, el dock solo tenía
9 nodos elegidos a mano (`DOCK_NODE_IDS`), dejando afuera nodos reales como
`documents` o `gmail_send` — justo los que aparecen en el ejemplo del
fundador. Al presentar un primer plan con cobertura parcial ("representativo,
no exhaustivo"), el fundador lo rechazó explícitamente: "no veo en el plan
incluir el desarrollo de los globos contextuales para cada skill capacidad
o especialista, ni sus sub elementos." Este ADR documenta la versión con
cobertura completa.

## Decisión

### 1. Campo nuevo `detalle` en el evento unificado — cobertura completa

`snarf/telemetry/detail.py` (nuevo): tabla `DETAIL_EXTRACTORS`, una entrada
por cada uno de los **60 tools reales** registrados en el Orchestrator
(no 68 como se estimó al planear — el número real, verificado contra
`orchestrator.TOOLS`). Cada extractor lee `tool_input`/`result` reales (los
mismos que `Orchestrator._handle_tool` ya tiene en scope) y devuelve un
string corto (≤100 caracteres) o `None` si no hay nada real que mostrar —
nunca inventa contenido (Principio VI de FOUNDATION.md). Varios tools solo
tienen un ID en su input sin nombre legible (ej. `drive_move_file`); para
esos el `detalle` es honestamente más genérico (el ID acortado), nunca un
nombre inventado.

Wiring en los **tres chokepoints reales** que ya emiten el evento unificado:

- `activity_log.record()` (dispatch de tools) — `Orchestrator._handle_tool`
  llama `detail.extract(name, status, tool_input, result)` y pasa el
  string resultante.
- `usage_tracker.record_*_call()` (vendors LLM/STT/TTS) — cada capability
  (`anthropic_llm.py`, `gemini_llm.py`, `openai_compatible_llm.py`,
  `elevenlabs_stt.py`, `elevenlabs_tts.py`, `groq_stt.py`, `local_stt.py`,
  `kokoro_tts.py`) ya tiene el texto real en scope en el momento de loguear
  (el transcript real de STT, el texto real a sintetizar en TTS, el texto
  real generado por el LLM en esa ronda) — se pasa truncado vía
  `detail.truncate_detalle()`.
- `input_log.record()` (entrada real a Snarf, llamada desde `app.py`
  `/send` y `/files/upload`) — el `payload.text`/`file.filename` real.

`test_detail_extractors_cover_every_orchestrator_tool` exige que
`DETAIL_EXTRACTORS` cubra el 100% de `orchestrator.TOOLS` — no un
subconjunto — mismo criterio de "red de seguridad mínima" que
`test_tool_to_node_covers_every_orchestrator_tool` en `tests/test_brain.py`.

### 2. `DOCK_NODE_IDS` deja de ser un subconjunto elegido a mano

`snarf/telemetry/relevance.py`: `DOCK_NODE_IDS = list(brain.NODE_TIER.keys())`
en vez de una lista literal de 9 nodos. Cubre los 24 nodos reales de
`brain.py` (incluye `documents`, `gmail_send`, `gmail_manage`,
`calendar_edit`, `youtube`, `notion`, `personality`, `utility`,
`specialist_projects_*`, `orchestrator`, `input_*` — todos ausentes antes).
Un nodo nuevo agregado a `NODE_TIER` (protocolo de crecimiento ya existente
en `brain.py`) entra al dock automáticamente en el mismo cambio, sin un
tercer lugar que mantener sincronizado a mano.

### 3. El dock muestra el top-N por relevancia real, no todos a la vez

Mostrar los ~24 nodos reales simultáneamente saturaría el arco. El frontend
(`web/index.html`) toma `HUD_MINI_MAX_CHIPS = 9` del ranking ya ordenado
por score real que devuelve `/dashboard/dock_priority` — el top-9 es
honestamente "lo más relevante ahora mismo" (recencia + frecuencia real de
actividad, ya calculado por `relevance.rank_nodes`), no un recorte
arbitrario. `HUD_MINI_NODE_META` (labels/iconos) y el nuevo
`HUD_BUBBLE_FAMILY` (ver punto 4) sí cubren los 24 nodos + el pseudo-nodo
`cost` completos, así que cualquier nodo puede aparecer cuando su actividad
real lo vuelve relevante.

### 4. Capa de globos contextuales — un componente por familia, no por tool

`#hudBubbleLayer` (nuevo, dentro de `#hudMiniDock`): un globo por nodo
activo, anclado a la posición real y viva de su chip
(`hudMiniNodeEls[nodo].getBoundingClientRect()`), mostrando `verbo` +
`detalle` reales. Nueve familias visuales (`HUD_BUBBLE_FAMILY`, un
componente HTML/CSS compartido parametrizado por familia — un nodo/tool
nuevo hereda un globo agregando una sola línea de mapeo, sin código nuevo
de render):

- `scan` (memoria/conocimiento/notion-búsqueda/gmail-digest) — revelado
  tipo scroll del texto real.
- `document` (creación/edición de contenido) — acento ámbar.
- `list` (enumeración/lectura de items) — números reales, tabulares.
- `dispatch` (mail enviado, evento de calendario editado) — un punto viaja
  del hub hacia el globo, como algo que "se despacha" hacia afuera.
- `voice` (stt/tts) — texto real transcripto/hablado, en cursiva.
- `think` (llm razonando) — más discreto, es contexto de fondo.
- `admin` (personalidad, utilidad, proyectos) — configuración/estado.
- `system` (tool desconocido, alerta de costo) — acento rojo de error.
- `input` (texto/voz/archivo que acaba de entrar) — mismo estilo que scan.

**Ciclo de vida real** ("cuando deja de ser relevante se va"): TTL de 20s
desde el último evento real de ese nodo, con fade-out; tope de 4 globos
simultáneos — al llegar al tope, se descarta primero cualquier globo que
NO pertenezca a la conversación activa (`conversation_id`), y solo si
todos pertenecen a la misma, el más próximo a expirar. Implementa
directamente "que aparezcan contextualmente... en su jerarquía
correspondiente."

Se alimentan del mismo poll incremental que ya disparaba los pulsos
(`pollBrainHudFeed`, cada evento nuevo con `detalle` no nulo dispara
`upsertHudBubble`) — nunca en la primera carga con todo el historial de
una (sería ruido, no una reacción a algo que "está pasando" ahora, mismo
criterio ya establecido en ADR 0088 para `pulseHudDockNode`).

### 5. La tabla de feed se saca por completo

`#brainHudFeedList`/`.hud-feed-live` se elimina del HTML, CSS y JS (pedido
explícito: "no aporta nada"). `pollBrainHudFeed` sigue corriendo — sigue
siendo la fuente de eventos que dispara pulsos y globos — pero ya no pinta
ninguna lista de renglones. `.hud-mini-dock` recupera el alto liberado.

## Bug real encontrado y corregido verificando con Playwright (no a ojo)

Midiendo el bounding box real de `#hudOmegaHub` contra `#brainPanel` (no
solo contra `.hud-mini-dock`, que no es el límite visual real) se encontró
que el hub quedaba **130px por debajo del borde real del panel** al abrir
el panel en Vista clásica (default) y recién después cambiar a Vista HUD.
Causa: `buildHudMiniDock` calcula el tamaño del hub con
`hudMiniDock.clientWidth/clientHeight` — mientras `#brainHudView` tiene el
atributo `hidden` (Vista clásica activa), esas medidas son `0`, así que cae
al fallback `300×190` y geometriza el hub para un contenedor mucho más
chico que el real. Nada volvía a recalcular esa geometría hasta el
siguiente ciclo de poll (hasta 3.5s después) — una ventana real en la que
el hub se veía roto. Corregido: `setBrainView('hud')` ahora fuerza un
`pollBrainHudDock()` inmediato al activar la Vista HUD, contra el tamaño ya
real y visible.

Con esa causa raíz resuelta, una segunda medición mostró que incluso en el
estado geométricamente correcto el anillo externo (r=98) todavía sobresalía
del panel — el offset vertical del hub (`hubY`, heredado sin cuestionar de
antes de sacar la tabla de feed) no dejaba margen real una vez que el dock
pasó a ocupar todo el panel. Ajustado de 34px a 100px (dos iteraciones
medidas, no una sola corrección a ojo) hasta confirmar ~21px de margen real
contra el borde del panel.

## Verificado

- `.venv/bin/python -m pytest -q` — 621/621 passed (605 previos + 16 tests
  nuevos de `tests/test_telemetry_detail.py`, cobertura total incluida).
- Playwright contra un servidor real en un directorio aislado
  (`/tmp/hud_bubbles_verify`, symlinks a `snarf/`/`web/`/`app.py`/`.env`
  reales, mismo patrón que ADR 0086-0088): sembrados eventos reales de 4
  familias distintas (`gmail_send_message` → dispatch, `drive_create_document`
  → document, `search_memory` → scan, `drive_list_files` → list) y
  confirmado en vivo que cada uno dispara un globo con su contenido real
  (no genérico) y su familia visual correcta; confirmado que un globo
  desaparece solo ~20-24s después de su último evento real (TTL de punta a
  punta, no solo el código); confirmado que la tabla de feed ya no existe
  en el DOM (`document.querySelectorAll('.hud-feed-live').length === 0`);
  confirmado el bounding box del hub dentro del panel con margen real, en
  vez de a ojo. Cero errores de consola reales (se excluyó un único 500 ya
  preexistente y no relacionado, ver "Hallazgo aparte" abajo).
- El cambio de backend (campo `detalle`) requiere reiniciar el servidor de
  producción; la capa de globos y el ajuste de layout son 100% frontend y
  solo necesitan recargar la pestaña.

## Hallazgo aparte (no corregido en este ADR, fuera de alcance)

Verificando con el directorio de datos aislado (sin ningún
`episodic_memory.jsonl` todavía) apareció un 500 real en
`GET /dashboard/summary`: `EpisodicMemory._read_all()`
(`snarf/memory/episodic.py`) no chequea si el archivo existe antes de
leerlo, a diferencia del resto de los módulos de telemetría (`activity_log`,
`usage_tracker`, `input_log`, `events`, todos con guardas `if not
target.exists(): return []`). No afecta al fundador hoy (su
`data/episodic_memory.jsonl` real ya existe), pero sí a cualquier entorno
nuevo desde cero. Queda documentado para una corrección aparte, no se tocó
acá para no mezclarlo con el alcance de este ADR.

## Consecuencias

- `web/hud_dock_prototype.html` (standalone, Fase 2/5) sigue sin ninguno de
  los rediseños reales del dock — mismo pendiente ya registrado en ADR
  0086/0087/0088.
- Con 24 nodos reales candidatos y un tope de 9 chips visibles, un nodo con
  actividad real pero de baja prioridad momentánea puede no tener chip (y
  por lo tanto su globo se muestra "flotante", sin línea de anclaje, según
  `.hud-bubble-unanchored`) — decisión deliberada documentada en el CSS/JS,
  no un bug: el contenido real sigue siendo honesto aunque no tenga dónde
  anclarse visualmente ese instante.
