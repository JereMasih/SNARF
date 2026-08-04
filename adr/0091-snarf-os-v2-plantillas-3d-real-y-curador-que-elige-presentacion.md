# ADR 0091 — SNARF OS v2: 24 plantillas, profundidad 3D real, y el curador elige presentación

**Fecha:** 2026-08-04
**Estado:** Aceptado

## Contexto

El fundador probó ADR 0090 (Vista HUD v1) en producción y pidió una segunda
pasada mucho más profunda, con inspiración explícita en cómo se construyó
el HUD de Iron Man: widgets más grandes con más información real (viendo
procesos "en vivo" mientras ocurren), una sensación 3D genuina (no solo el
orbe: también el chat alejándose hacia el fondo, y los widgets con
profundidad real entre sí), líneas de conexión entre la esfera y cada
widget, más jerarquía por transparencia, una barra de input siempre visible
con un botón de modo-enfoque sutil (no la barra grande de v1), posición
configurable del chat, y un agente curador que decida activamente **cómo**
presentar cada widget — no solo qué texto poner — eligiendo entre una
biblioteca de plantillas y pudiendo proponer plantillas nuevas.

El pedido original también mencionaba delegarle al curador crear/modificar
otros agentes ("le podemos dar la delegación de crear/modificar agentes").
Se contrastó contra `CONSTITUTION.md` (Art. III, V y línea 109): ninguna
autoridad es inherente a ningún proceso de Snarf, y cualquier acción
irreversible o que altere el registro canónico "requiere el ejercicio
directo de autoridad... sin importar qué capacidad técnica exista para
ejecutarla" — no puede cubrirse con una delegación general. El fundador,
tras ver esa cita, confirmó separar el pedido en dos: **Track A** (este
ADR: el curador propone plantillas visuales, nunca ejecuta código ni crea
Specialists) y **Track B** (crear/modificar agentes de verdad — fuera de
alcance acá, queda como iniciativa aparte con su propio plan de gobernanza
y autorización caso por caso).

## Decisión

### 1. Biblioteca de 24 plantillas — 3 tamaños × 8 variantes (Track A)

`snarf/telemetry/widget_templates.py` (nuevo): `WIDGET_TEMPLATES`, 24
entradas (`id`, `tier`, `width`, `height`, `slots`, `description`). El
**tamaño** de cada widget se asigna acá mismo, mecánicamente, por posición
real en el ranking de `relevance.dock_priority()` (`assign_tier`: rank 0 →
`large`, ranks 1-3 → `medium`, resto → `small`) — nunca por el LLM, para
que "más relevante = más grande" sea siempre consistente. El curador
**solo** elige la variante dentro del tamaño ya asignado (1-de-8), nunca el
tamaño en sí — mismo principio de legibilidad que gobierna todo el resto de
este ADR: score → tamaño → distancia al centro → opacidad → animación
apuntan siempre en la misma dirección.

Vocabulario de "slots" compartido (`icon`/`body`/`caption`/`narrative`/
`chart`/`badge`/`list`/`timeline`/`wall`/`stat`/`stat_grid`/`gauge`/
`ticker`) — una plantilla nueva combina estos, nunca hace falta CSS/JS a
medida por plantilla individual (`dashHudBodySlotHTML` en el frontend).

### 2. Curador v2: variante + posible propuesta de plantilla nueva

`DashboardCuratorSpecialist` (ADR 0090) extendido: el prompt lista, por
nodo del top-N (`curation_snapshot` ahora recorta a `top_n=4`, exactamente
cuántos nodos reciben un tamaño que amerita curación), su tamaño ya
asignado y las 8 variantes válidas para ese tamaño — el modelo responde
`node_id: template_id | caption`, con profundidad de caption creciente por
tamaño (grande: hasta 2-3 oraciones de análisis real; mediano: 1-2). Sigue
siendo **una sola llamada LLM** por ciclo (mismo cadenciado 10 min + señal,
sin cambios). Si la variante elegida no es válida para el tamaño real del
nodo, cae al default mecánico de ese tamaño — nunca rompe el render.

El nodo sintético `cost` ahora se cura igual que cualquier nodo real (en
v1 era solo una línea de contexto aparte) — una alerta de costo real puede
mostrarse con `critical_alert`/`deep_chart` en vez de texto plano fijo.

**Propuestas de plantilla (Track A)**: si el curador considera que ninguna
variante de su tamaño describe bien lo que hace falta, puede emitir líneas
`PROPUESTA: nombre: motivo` — se parsean y persisten en
`data/dashboard_template_proposals.json` (cola de solo lectura, tope 20,
nuevo `GET /dashboard/template_proposals`, sección nueva en Configuración)
para que el fundador las revise. **Nunca se aplican solas** — cierra el
pedido de "que pueda proponer" sin cruzar la línea de Track B.

Regresión real corregida durante esta ronda (encontrada con el endpoint,
no con el LLM): el `template` cacheado por el curador se validaba contra
el tamaño que el nodo **tenía al momento de curarlo** — si su relevancia
bajó entre esa curación y un poll posterior (el ranking se recalcula en
cada request, la curación no), el nodo podía quedar con un tamaño más
chico pero una plantilla de un tamaño mayor todavía cacheada. `GET
/dashboard/widget_summaries` ahora valida el `template` cacheado contra el
`size_tier` **actual** del nodo en cada respuesta, cayendo al default
mecánico si ya no corresponde.

### 3. Actividad real en tiempo real, mecánica (sin LLM)

`recent_activity_buckets(node_id, events, now)` (nuevo, en
`widget_summary.py`): histograma real de eventos del nodo en los últimos
~12 minutos, en baldes de 60s — agregación mecánica de datos ya reales,
nunca fabrica un punto. `summarize_node()` gana `activity_buckets` y
`recent_items` (hasta 5 eventos reales con detalle, más reciente primero,
para las plantillas de lista/timeline); el pseudo-nodo `cost` reutiliza
`cost_history.by_day()` (ya real) como `cost_series`. Esto es lo que
resuelve la tensión "tiempo real" vs. "barato": lo mecánico se sirve cada
3.5s por el poll normal, gratis, sin LLM — solo la interpretación
narrativa (captions/variantes/titular) va al ciclo lento del curador.
`renderActivitySparkline()` en el frontend es honesto: sin ninguna señal
real (todo cero), no dibuja nada en vez de simular una serie plana.

### 4. Escena 3D real compartida (widgets + chat)

Primera vez que este archivo usa perspectiva CSS real (antes, la "3D" del
panel Cerebro era una proyección hecha a mano en JS/canvas, no
`transform`/`perspective`). `#dashHudStage` gana `perspective`; cada
`.dash-hud-node` se posiciona con `transform: translate3d(x, y, z)` — la
`z` depende del anillo de empaquetado (más lejos del centro, más atrás),
reforzando "más relevante = más cerca" con un eje más. La jerarquía por
transparencia (pedido explícito) ahora depende del score real de cada
widget (rank más alto, más opaco), no solo del color de borde por familia.

El chat gana su propio canvas 3D, acotado a `#chatDock` (Vista HUD, nunca
en Vista clásica ni en modo enfoque): cada burbuja recibe `--depth` según
su antigüedad (0 = la más nueva, junto al input), animando
`translateZ`/`translateY`/`scale`/`opacity`/`filter: brightness()`
decrecientes — el efecto "se alejan hacia el fondo, oscuras y
transparentes arriba" pedido, recalculado en cada `addMessage()`
(`reindexChatDepth()`).

### 5. Líneas de conexión orbe → widget

`<svg id="dashHudConnections">` dentro de `#dashHudStage`, entre el orbe y
las cards. Una `<line>` real por widget activo, actualizada en el mismo
paso donde `renderDashboardHudWidgets` ya recalcula posiciones — mismo
ciclo de vida que las cards, sin una función paralela. Pulso animado vía
`stroke-dasharray`/`stroke-dashoffset`; opacidad atada al mismo score que
la jerarquía visual de arriba.

### 6. Chat ambiente permanente + modo enfoque real (no una barra grande)

Se retira el binario colapsado/expandido de `#chatDock` (v1): la barra de
input (`adjuntar`/`texto`/`mic`, el mismo `.control-bar` de siempre) queda
**siempre visible**; el canvas 3D de mensajes también, ambientalmente. En
su lugar, un botón chico y sutil (`#chatDockFocusBtn`, ícono, no barra)
dispara `openChatFocus()` — función que **ya existía** (reparenta a
pantalla completa) pero no tenía ningún trigger dentro de Vista HUD; su
único trigger real era el ícono de expandir del widget de chat en Vista
clásica. Se corrigió `closeChatFocus()`, que volvía siempre a
`.dash-chat-body` hardcodeado (rompía si el modo enfoque se abría desde
Vista HUD): ahora usa `chatHomeEl`, seteado por cada función de
reparentado "de descanso" (clásica y HUD), y funciona correctamente desde
cualquiera de las dos. Se agregó `textInput.focus()` al entrar en modo
enfoque, en escritorio — pedido explícito de no perder un click extra.

### 7. Posición configurable del chat

`hud_chat_position: "left"|"center"|"right"` (default `"left"`, nuevo
campo aditivo en `DashboardPreferences`), control nuevo en Configuración.
`.chat-dock[data-position]` reemplaza el ancla fija centrada de v1. Solo
aplica en escritorio — mobile sigue centrado siempre (Vista HUD ya es
desktop-only).

### 8. Drawer lateral de conversaciones/proyectos (Vista HUD)

Nuevo botón compacto (`#chatDockDrawerBtn`) reparenta el `#sidebar` real
(mismo criterio "mover el nodo vivo" que `openChatFocus`) hacia
`#dashHudSidebarDrawer`, deslizando desde el borde izquierdo. Botón de
"fijar" (`📌`) evita el auto-cierre al elegir una conversación —
`closeSidebar()` (el punto de cierre "por selección" ya existente, 4
call-sites) ahora también intenta cerrar el drawer de HUD, no-op si no
aplica o si está fijado. El botón ✕ siempre cierra, fijado o no. Al estar
abierto, `#chatDock` gana `.drawer-open` (desplaza de verdad vía
`margin-left`, nunca se superpone). Exclusivo de Vista HUD — el
`#menuBtn`/`openSidebar()` overlay de siempre no se tocó.

### 9. Empaquetado radial constructivo, no un cálculo analítico ni un solver iterativo

Reemplaza el layout de anillos concéntricos de v1. `packHudWidgets()`
coloca cada widget (ya en orden de score real descendente) en el primer
punto de una espiral creciente desde el centro que se verifica **sin
choque contra todo lo ya colocado antes de aceptarlo** — garantiza cero
superposición por construcción, nunca depende de que un cálculo de radios
o un solver iterativo converjan. "Más relevante = más cerca" sale solo de
procesar en orden de score y probar radios chicos primero. Ver bugs reales
más abajo — se probaron y descartaron dos enfoques previos antes de llegar
a este.

## Bugs reales encontrados y corregidos verificando con Playwright

Esta ronda concentró la mayor cantidad de iteración real de toda la sesión
— seis bugs distintos, cuatro de ellos en el mismo problema (el layout
radial), documentados en orden porque cada uno solo se hizo visible
después de corregir el anterior:

1. **Colisión de z-index real, dos veces**: `.chat-dock`(11) coincidía con
   `.settings-panel`(11); `.dash-hud-sidebar-drawer`(12) coincidía con
   `.brain-overlay`(12) — el elemento declarado después en el archivo
   ganaba la pila y tapaba al modal, bloqueando clicks. Ambos bajados a 9
   (capa ambiente, siempre por debajo de cualquier modal 10-17).
2. **Alineación radial sistemática**: cada anillo repartía sus ítems
   arrancando siempre en el mismo ángulo fijo (-90°) — el único widget del
   anillo grande y el primero del mediano quedaban siempre sobre la misma
   línea radial, superponiéndose si el radio no alcanzaba a separarlos.
3. **Círculo vs. rectángulo real**: un radio que crece parejo por anillo
   (pensado para un panel angosto) empujaba el anillo externo por
   arriba/abajo del stage en una pantalla de escritorio real (mucho menos
   alto disponible que ancho) — tapaba el toggle sin importar cuánto se
   ajustaran las constantes; escalar X e Y por separado para aprovechar el
   ancho de sobra deformaba el círculo en una elipse, y en una elipse la
   distancia mínima entre dos radios distintos deja de ser `|r1-r0|` —
   la separación garantizada por el resto del cálculo se rompía en
   ángulos no alineados a los ejes.
4. **Un solver iterativo de pares no convergía**: probado como reemplazo
   del cálculo analítico — empujar cada par que se superponía, con
   recorte final contra el borde del stage. En un grupo denso de varias
   cards, resolver un par podía reintroducir el choque con un tercero ya
   resuelto (y viceversa); con más iteraciones y empuje amortiguado la
   situación **empeoró**, confirmando que no era un problema de afinar
   constantes sino de un método sin garantía de convergencia. Reemplazado
   por completo por el empaquetado constructivo de la Decisión 9 — cero
   superposiciones verificadas programáticamente (bounding boxes reales,
   no a ojo) en la corrida final.
5. **El dock de chat fijo, invisible para el layout**: con las cards más
   chicas (bug 3 llevó a reducir tamaños), el nuevo espacio libre permitía
   posicionar un widget detrás de `#chatDock` — `#appRoot` tiene su propio
   `z-index`, así que ese widget quedaba atrapado abajo del dock sin
   importar su z-index local: invisible/inclickeable aunque el layout
   "creyera" que cabía ahí. Corregido reservando la franja inferior real
   (altura del dock) directamente en el cálculo de layout, nunca proponer
   una posición ahí.
6. **Cache de plantilla sin revalidar contra el tamaño actual** (Decisión
   2): documentado ahí arriba — el mismo tipo de bug de "dato cacheado que
   dejó de ser válido" ya visto en otras rondas de este repo, esta vez
   entre curación (lenta) y ranking (recalculado en cada request).

## Verificado

- `.venv/bin/python -m pytest -q` — 688/688 passed (688 = 660 previos +
  28 nuevos de este ADR: `widget_summary`, `dashboard_curator`,
  `dashboard_prefs`, `test_app`, más el fix de una fuga real de test
  pollution encontrada en el camino — `tests/test_app.py` nunca aislaba el
  `CACHE_DIR` de `dashboard_curator`, así que sus tests leían el cache
  REAL de producción si existía en disco; pasó de verdad esta sesión
  porque el loop periódico corrió con datos reales después de un restart
  anterior, mismo tipo de fuga que ADR 0085).
- Playwright contra un servidor real en un directorio aislado (symlinks a
  `snarf`/`web`/`app.py`/`.env`, login real, datos de actividad reales
  sembrados directamente en `telemetry_events.jsonl` — mismo formato que
  produce el código real, técnica de fixture, nunca mostrado como si fuera
  del fundador): 8-9 widgets reales cubriendo los 3 tamaños simultáneos,
  **cero superposiciones** (verificado programáticamente contra los
  bounding boxes reales del DOM, no por inspección visual); templates
  elegidos por una llamada real al curador (incluida una alerta de costo
  real presentada con `critical_alert`); líneas de conexión siguiendo a
  cada widget; profundidad `--depth` de las burbujas de chat confirmada
  numéricamente (0 a 5, más nueva más cerca); drill-down, drawer lateral
  (abrir/fijar/cerrar por X), modo enfoque (autofocus confirmado por
  `document.activeElement`, retorno correcto del chat a su dock de origen
  tras cerrar), posición del chat (persistida, aplicada en vivo), y
  reversibilidad completa a Vista clásica — todo en una sola corrida de
  punta a punta, cero errores de consola.

## Fuera de alcance explícito: Track B

Delegarle al curador (o a cualquier agente) crear/modificar Specialists
queda fuera de este ADR, con `CONSTITUTION.md` Art. III/V/línea 109 como
fundamento — ninguna autoridad de ese tipo puede nacer de una delegación
general de fondo. La Decisión 2 (propuestas de plantilla, nunca aplicadas
solas) es el techo real de autonomía para esta ronda. Queda como iniciativa
aparte, con su propio plan de gobernanza y aprobación caso por caso.

## Consecuencias

- `web/index.html` sigue creciendo (ya superaba las ~6800 líneas antes de
  esta ronda) — se mantiene monolítico, mismo criterio que ADRs previos.
- Los tamaños reales de las 8 plantillas grandes/medianas quedaron ~20%
  más chicos que el diseño original de esta misma ronda (ver bug 3) — el
  fundador puede pedir agrandarlos otra vez si los ve chicos en su
  pantalla real; el empaquetado constructivo (Decisión 9) se adapta solo a
  cualquier tamaño sin volver a romper garantías de superposición.
- El hallazgo de v1 sobre el nodo `llm` contaminándose con las propias
  llamadas del curador (ADR 0090) sigue sin corregir — no se tocó en esta
  ronda, mismo estado.
