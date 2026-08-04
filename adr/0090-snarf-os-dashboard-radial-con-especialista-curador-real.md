# ADR 0090 — SNARF OS: dashboard radial con Especialista curador real, reversible por toggle

**Fecha:** 2026-08-04
**Estado:** Aceptado

## Contexto

El fundador vio el dock de globos contextuales del panel Cerebro (ADR 0089)
y pidió que dejara de ser un experimento acotado a un widget: quiere que
sea **el nuevo dashboard principal de Snarf** — una esfera central animada,
widgets distribuidos por toda la pantalla (no una grilla fija) que se
reposicionan solos según qué es relevante ahora, con animación completa
(entrada/salida/carga/actualización), cada widget clickeable a una vista de
detalle, y el chat integrado como una barra inferior colapsable/expandible.

Mostró una imagen de referencia con métricas de negocio (trading, leads,
ingresos) que Snarf no trackea hoy. Su respuesta a cómo tratar eso, verbatim:
no quiere una lista fija de widgets — quiere el ecosistema construido de
forma que, a medida que se agreguen capacidades reales a Snarf, el propio
sistema sepa extraer qué es relevante de ellas y presentarlo en el
dashboard, sin trabajo de UI nuevo cada vez. Confirmó además: quiere
Especialistas de IA reales (no solo módulos de código) ayudando a curar el
dashboard, y todo esto en un solo desarrollo grande, no por fases.

Tras presentar un primer plan, pidió una condición más: **reversibilidad
real, con un botón**, igual que el toggle Vista clásica/HUD que ya existe
en el panel Cerebro — "si no me gusta el desarrollo, podemos siempre volver
a la versión clásica." Esa condición gobierna toda la arquitectura de este
ADR: nada de lo nuevo reemplaza código existente, todo es aditivo detrás de
un toggle persistido.

## Decisión

### 0. Reversibilidad real (no solo conceptual)

Nuevo toggle "Vista clásica / Vista HUD" en la cabecera de `#viewDashboard`
(mismo componente visual que `#brainViewToggleClassic`/`#brainViewToggleHud`
del panel Cerebro, ADR 0080). A diferencia de aquel (efímero, por sesión),
este se persiste de verdad: `dashboard_view: "classic" | "hud"`, nuevo campo
en `DashboardPreferences`. Default `"classic"`.

**Todo el código existente de la grilla clásica (`renderDesktopDashboard()`,
`reparentChatIntoDashboard()`, `xBodyHTML()` por widget, `WIDGET_IDS`) se
conserva exactamente igual, sin una línea tocada.** Todo lo de este ADR es
una segunda rama de render aditiva, activada solo cuando el toggle está en
"HUD". Con el toggle en "clásica", el dashboard se comporta bit a bit como
antes de este ADR.

### 1. Motor de datos único, compartido con el dock de globos (ADR 0089)

Nuevo módulo `snarf/telemetry/widget_summary.py`: `summarize_node(node_id,
events, now)` agrega, por nodo real, `count_recent`/`count_total`/
`last_timestamp`/`last_detalle`/`has_error_recent`/`score` — cada campo ya
existe en algún lugar del backend (`relevance.rank_nodes()`,
`events.all_events()[].detalle`), esto es pura agregación, cero riesgo de
inventar contenido (Principio VI). `None` si el nodo nunca tuvo actividad
real. `all_widget_summaries()` cubre TODOS los nodos con `score > 0`
(nuevo endpoint `GET /dashboard/widget_summaries`); `curation_snapshot()`
recorta al top-N para alimentar al Especialista (punto 2).

`snarf/runtime/dashboard_prefs.py`: `WIDGET_IDS` (grilla clásica, sin
tocar) se complementa con `HUD_NODE_IDS = relevance.DOCK_NODE_IDS` (alias
directo, no copia — los 24 nodos reales) y un modelo de 3 estados por nodo,
en campos nuevos y separados: `hud_widget_state: "auto"|"pinned"|"hidden"`
+ `hud_widget_options: {angle, radius}` para los fijados. `auto` (default)
se posiciona por relevancia real; `pinned` queda donde el fundador lo dejó;
`hidden` nunca se muestra. Con esto, el flujo real para que una capacidad
**futura** aparezca en el dashboard es el mismo protocolo de 3 pasos que
`brain.py`/`detail.py` ya fuerzan por test (`TOOL_TO_NODE`,
`DETAIL_EXTRACTORS`, `HUD_MINI_NODE_META`/`HUD_BUBBLE_FAMILY`) — nada nuevo
que aprender.

### 2. Especialista Cognitivo real: `DashboardCuratorSpecialist`

`snarf/specialists/dashboard_curator.py`, mismo patrón cache-first que
`GmailDigestSpecialist`: `cached_curation()` nunca llama al LLM,
`refresh()` sí. **Nunca decide qué widgets existen** (eso es
`relevance.dock_priority`, determinístico) — solo rephrasea/prioriza datos
reales que se le pasan explícitamente, con la misma frontera defensiva ya
usada en `ProjectManager.SUMMARY_SYSTEM_PROMPT` ("a partir únicamente de
los datos reales que se te dan, nunca inventes"). Produce, en un solo
llamado LLM: un `headline` (equivalente honesto de un saludo con contexto)
y `node_captions` (una frase por nodo del top-N, prohibido mencionar
cualquier dato que no esté en el `last_detalle`/conteos recibidos —
verificado con test que el LLM no puede colar un `node_id` fuera de la
lista real que se le dio).

**Costo controlado por diseño**: nunca disparado por el poll del navegador
— un loop de backend (`asyncio.create_task`, mismo patrón que
`_periodic_backup_loop`) refresca cada 10 min, o antes si la señal real
cambió (nodo top distinto, alerta de costo nueva, cambio en errores
recientes) — nunca más seguido que eso. Nuevo rol barato en
`llm_routing.ROLES`: `"dashboard_curator"` (Haiku 4.5 por default, expuesto
en Configuración → LLM por rol).

### 3. Esfera central + layout radial + reposición animada (FLIP)

Base visual: `.orb-sphere`/`#orbWrap` (el orb de tap-to-talk que ya existe
en el chat), **no** el anillo Omega SVG del dock de globos — ese está
geometrizado para el panel Cerebro específico; el orb ya tiene los 3
estados necesarios (`listening`/`thinking`/`error`) y es liviano de animar
en cualquier posición. Nueva instancia visual independiente (mismas clases
CSS reusadas, no reparentada — a diferencia del chat, este orb no tiene
listeners de grabación que perder) al centro del escenario, con un cuarto
estado nuevo, `.curating`: pulso lento mientras
`DashboardCuratorSpecialist.refresh()` corre de verdad en el backend — la
esfera reacciona a una señal real, nunca decorativa.

Layout radial: extiende `hudMiniCenterOutPositions()` (dock de globos) de
un arco de 150° a 360° completos, en anillos concéntricos — más score real,
más cerca del centro.

Reposición real vía **FLIP** (First-Last-Invert-Play, sin librería nueva):
un widget que sigue siendo relevante nunca se destruye y recrea entre
polls — cambia `left`/`top` (con `transition` CSS) y su contenido si
cambió; solo entran/salen del DOM los que aparecen o dejan de ser
relevantes. Cierra una brecha real que también tenían
`renderDesktopDashboard()`/`buildHudMiniDock()` (rebuild completo en cada
refresco). Máquina de estados por widget (`data-anim-state` vía clases
`dash-hud-node-enter`/`-exit`/`-updating`), disparada comparando el array
de `widget_summaries` anterior vs. nuevo por `node_id`.

### 4. Drill-down genérico por nodo

`GET /dashboard/node_activity/{node_id}` (nuevo, mismo query que
`telemetry_feed`, filtrado por nodo) + un panel overlay nuevo
(`#nodeDrillOverlay`/`#nodeDrillPanel`, mismo lenguaje visual que
`.brain-panel`/`.chat-focus-panel`, DOM propio porque el contenido de
`#brainPanel` está armado a medida para el grafo/HUD del cerebro, no para
una lista genérica). Funciona automáticamente para cualquier nodo real,
incluida cualquier capacidad futura sin vista propia — decisión deliberada
de esta ronda: **no** se reusaron `driveBodyHTML()`/`gmailBodyHTML()` (que
traen controles interactivos con IDs fijos, ej. el selector de
`max_results` de Gmail) para no dejarlos a medio wirear dentro de un panel
nuevo; el panel genérico (verbo + `detalle` real + hace cuánto) es
honestamente simple y funciona igual de bien para los 24 nodos reales, sin
riesgo de una interacción rota. Vista rica por nodo queda como mejora
incremental futura, no bloqueante.

### 5. Chat como barra inferior colapsable (solo Vista HUD)

`#chatDock`, hermano `position:fixed` de `#appRoot` (mismo nivel que
`.brain-panel`/`.chat-focus-panel`) para sobrevivir cualquier cambio de
vista. Mismo criterio "mover el nodo vivo, nunca clonar" que
`reparentChatIntoDashboard()`/`openChatFocus()` ya establecen:
`reparentChatIntoDock()`/`reparentChatOutOfDock()` mueven `#chat` +
`.control-bar` entre la grilla clásica y la barra inferior según el
toggle. Colapsado (mini status) → expandido (chat completo) → foco
completo (`openChatFocus()` ya existente, sin cambios). El dock se
auto-expande en cada mensaje/respuesta real (decisión tomada, preserva el
comportamiento de "chat siempre visible" que existía antes de que pudiera
colapsarse) — el fundador lo colapsa a mano cuando quiere más pantalla.

### 6. Alcance mobile

Vista HUD es **desktop-only** (`≥900px`, extiende `jarvis-mode`, mismo
breakpoint). Mobile mantiene `renderMobileDashboard()` sin tocar — esta es
una app de uso real desde el teléfono (notas de voz, tap-to-talk), un
layout radial denso degradaría la interacción principal a cambio de un
diseño pensado para pantalla ancha.

## Bugs reales encontrados y corregidos verificando con Playwright (no a ojo)

1. **Colisión de `transform` real** (mismo tipo de bug ya documentado antes
   en esta sesión, ADR 0069/0078): `.orb-wrap` ya trae su propio
   `transform: scale(0.74)` declarado más abajo en la hoja de estilos —
   una `.dash-hud-orb { transform: translate(-50%,-50%) }` simple perdía
   el centrado porque el `scale()` declarado después en el archivo ganaba
   entero, sin combinarse (CSS no fusiona dos declaraciones de la misma
   propiedad). Medido con el bounding box real del orb contra el del
   escenario: el orb aparecía ~90px fuera de centro. Corregido combinando
   ambas funciones en un solo valor (`translate(-50%,-50%) scale(0.74)`)
   con un selector de mayor especificidad, para que nunca dependa del
   orden de declaración en el archivo.
2. **Fallback de mobile incompleto**: al angostar la ventana por debajo de
   900px con Vista HUD activa, `#chatDock` seguía visible — faltaba
   apagar sus efectos (poll, chat reparentado) en el listener de resize ya
   existente. Corregido con `deactivateDashHudSideEffectsOnly()`, que
   apaga los efectos en vivo sin tocar la preferencia guardada (al volver
   a ensanchar, reactiva HUD sola si correspondía — verificado el ciclo
   completo: desktop→mobile→desktop, misma instancia de `#chat`, sin
   duplicar el nodo).
3. **Parseo de `node_captions` real, no solo con datos de prueba**: contra
   una respuesta REAL del LLM (no un mock), `_parse_curation_response`
   devolvía `node_captions: {}` vacío — el modelo repetía el `(score N.N)`
   que ya aparecía en el prompt de entrada antes de los dos puntos, aunque
   el formato pedido fuera `node_id: caption` a secas, rompiendo el
   `split(":", 1)` estricto. Corregido con una regex tolerante que extrae
   el identificador real al principio de la línea e ignora cualquier texto
   entre eso y el primer `:` — sigue rechazando en silencio cualquier
   `node_id` que no esté en la lista real recibida. Regresión cubierta con
   un test que usa el texto exacto de la respuesta real capturada.
4. **Agrupamiento radial real**: el layout dividía el ángulo de cada widget
   por la CAPACIDAD MÁXIMA del anillo, no por cuántos widgets realmente
   caían ahí — con 3 widgets en un anillo de hasta 6, quedaban amontonados
   en medio círculo en vez de repartidos en los 360° completos (visible
   con una captura real, dos widgets llegaban a superponerse). Corregido
   con una segunda pasada que reparte cada anillo según su ocupación real.

## Verificado

- `.venv/bin/python -m pytest -q` — 660/660 passed (605 previos a esta
  sesión + 16 de ADR 0089 + 39 nuevos de este ADR).
- Playwright contra un servidor real en un directorio aislado (symlinks a
  `snarf`/`web`/`app.py`/`.env`, login real, mismo patrón que ADR
  0086-0089): toggle persiste entre recargas de página; con "clásica"
  activa el DOM es idéntico al de antes de este ADR; activar "HUD" mueve
  el chat de verdad a la barra inferior (mismo nodo `#chat`, nunca
  duplicado); reposición FLIP confirmada por identidad de elemento DOM
  (el mismo nodo persiste entre dos polls con ranking distinto, nunca se
  recrea); drill-down abre/cierra y muestra actividad real filtrada; fijar
  un widget (pin) persiste su posición entre recargas; ciclo completo
  desktop→mobile→desktop sin duplicar ni perder el chat; **curador
  probado con una llamada real al LLM** (no un mock) — el `headline` y los
  5 `node_captions` reales referenciaron correctamente el contenido real
  sembrado (destinatario real de un mail, título real de un documento).
  Cero errores de consola en todos los escenarios.

## Hallazgo aparte, no corregido en este ADR (documentado, fuera de alcance)

Verificando con datos reales apareció un efecto secundario real, no un
bug de datos inventados: cada llamada del propio `DashboardCuratorSpecialist`
es, en sí misma, una llamada real a Anthropic — y por diseño (ADR 0089) el
`detalle` del nodo `llm` se llena con el texto real que esa llamada generó.
Esto significa que el `last_detalle` del nodo `llm` a veces muestra un
fragmento del `headline` que el propio curador generó en su corrida
anterior, no una "reflexión" de una conversación real del fundador — dato
100% real (es exactamente lo que esa llamada generó), pero temáticamente
circular. No se corrigió en este ADR: una opción futura sería excluir al
propio curador del conteo del nodo `llm`, o marcar sus llamadas con un
`agente` distinguible — queda como mejora incremental, no bloqueante para
este pase.

## Consecuencias

- `web/hud_dock_prototype.html` y el resto de los prototipos aislados de
  Fase 2/3 siguen sin ninguno de los rediseños reales — mismo pendiente ya
  registrado en ADRs anteriores.
- El drill-down genérico es intencionalmente más simple que los widgets
  ricos existentes de Drive/Gmail/Calendar/YouTube (ver punto 4) — mejora
  incremental disponible si se pide.
- `web/index.html` pasa a rondar las ~6800 líneas — se mantiene monolítico
  para este pase (consistencia con el resto del repo); separar en archivos
  queda como decisión aparte si se pide.
