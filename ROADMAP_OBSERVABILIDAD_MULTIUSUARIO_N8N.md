# Evolución de Snarf hacia un AI Operating System observable, multi-usuario y Jarvis-style

> **Por qué este documento vive acá y no solo en un plan de Claude Code:** un plan guardado por
> `ExitPlanMode` queda en `~/.claude/plans/`, fuera del repo — una sesión nueva de Claude Code no tiene
> garantía de poder leerlo (pasó de verdad: una sesión que retomó la Fase 5 no pudo acceder al texto
> original y tuvo que reconstruir el alcance desde ADR 0139, dejándolo anotado como nota de honestidad
> en el CHANGELOG). Este archivo es la copia autoritativa, versionada en git, que cualquier sesión futura
> puede leer siempre — indexado desde `CLAUDE.md`.

## Estado actual (retomar una sesión nueva desde acá)

**Última actualización:** 2026-08-14. **Hechas: Fases 0-7 + Fase 8/1 (HITL) + Fase 9.1 (parcial) + Fase
9.2 (4 rondas de iteración real) + Fase 9.3 (completa) + Fase 10 (primer corte) + Fase 11 (completa) +
Fase 14 (primer corte real, ver abajo) + Fases 15-21 (n8n control-plane) con su extensión real del
2026-08-13 (Prototipo E promovido a oficial, ADR 0164, ver abajo) + Fase 22 (Project Manager + área
reales, ADR 0165) + Fase 23 (spike n8n, mecanismo Wait/resume verificado) + Fase 24 (canvas en vivo real,
ADR 0166) — las tres del 2026-08-14**. **Pendiente real, no bloqueante: `N8N_LIVE_CANVAS_ENABLED` no está
activa en el server de producción — prenderla requiere reiniciar el puerto 8002, decisión aparte del
fundador (ver "Pendiente real" en ADR 0166).**

**Incidente real 2026-08-12 (post Fase 21, durante iteración de prototipo de UX en n8n) — server real
colgado dos veces, mitigado, sin código propio todavía revertido a esto en un ADR:** probando en vivo un
prototipo de canvas del Executive Board con nodos editables (`Set` → `Proponer` → `Aplicar` encadenados,
disparados por el fundador desde n8n), el server real (puerto 8002) quedó no-responsivo dos veces
seguidas — 0% CPU, sin excepciones en el log, ambas correlacionadas con una llamada real
`POST /n8n/agent/{id}/apply`. Sospecha fundada, **no confirmada con certeza**: ese endpoint disparaba un
hilo en background (`threading.Thread(target=n8n_generator.sync_executive_board_safe)`) que llamaba DE
VUELTA a la propia API de n8n (`push_workflow`) — un acoplamiento reentrante real (n8n → Snarf → n8n)
mientras n8n podía estar todavía en medio de la ejecución que originó el pedido, nunca antes ejercitado en
vivo. **Mitigación aplicada ya:** se sacó ese disparo automático de `app.py::n8n_apply_agent_change`
(código sin cambios en `n8n_generator.py` en sí — la función `sync_executive_board_safe()` sigue existiendo
y sigue siendo invocable a mano vía la Skill `n8n-map-sync`, solo dejó de dispararse sola tras un apply
real). Server reiniciado con confirmación explícita del fundador cada vez, verificado sano después de cada
uno. **Cero cambios reales quedaron aplicados** a ningún agente en ninguno de los dos intentos fallidos
(verificado directo contra `/n8n/agent/cto`: prompt sin tocar, historial en v1).

**Investigación real hecha esta misma ronda (post-mitigación) — resultado honesto: la hipótesis original
NO se confirmó.** Reproducción fiel en entorno aislado (nunca contra producción): server de prueba
(puerto 8001, throwaway) + dos workflows throwaway reales en la misma instancia de n8n (un `webhook`
disparable por curl sin intervención humana + un target) replicando EXACTAMENTE el patrón sospechoso —
un endpoint disparado por n8n que arranca un hilo en background que llama de vuelta a la API real de n8n
con un `PUT` de payload grande (~30 nodos, mismo tamaño real que `push_workflow`) — **nunca reprodujo el
cuelgue**, siempre resolvió en <0.1s. La teoría del acoplamiento reentrante queda sin confirmar (puede ser
real bajo una condición que no se logró replicar, o puede no ser la causa real). Workflows throwaway
borrados de n8n al terminar (`ZZZ-repro-*`, ya no existen).

**Hallazgo real, independiente, sí corregido:** el proceso real bajo `launchd` tenía un límite de **256
descriptores de archivo** (default de macOS para un LaunchAgent, confirmado con `launchctl print
gui/501/com.snarf.server` antes del fix) — bajo para un server de larga duración con polling constante del
dashboard (cada widget cada ~15s) más conexiones salientes reales (Gmail/Drive/Anthropic/n8n). Sin
evidencia de un leak activo en el momento del chequeo (112 de los ~130 FDs abiertos eran bibliotecas de
Python cargadas una sola vez al importar, no conexiones acumulándose), pero es una debilidad real e
independiente de la teoría de arriba. **Corregido:** `~/Library/LaunchAgents/com.snarf.server.plist` ahora
tiene `SoftResourceLimits`/`HardResourceLimits` → `NumberOfFiles: 4096` (el `.plist` vive fuera de este
repo, en `~/Library/LaunchAgents/`, no hay nada que commitear en git por este cambio) — confirmado real y
activo en el proceso corriendo (`launchctl print` muestra `maxfiles (soft/hard) => 4096`).

**Estado real, honesto:** la mitigación de la Fase 21/incidente (regeneración automática desactivada)
sigue en pie — no depende de haber confirmado la causa raíz, es una simplificación razonable de todos
modos. El límite de archivos, ahora 16x más alto, es un endurecimiento real independiente. Si el cuelgue
vuelve a pasar, el paso correcto AHORA es correr `py-spy dump --pid <pid>` (ya instalado en el venv) ANTES
de reiniciar — eso sí daría una respuesta definitiva de dónde está bloqueado el proceso, cosa que no se
pudo capturar en los dos incidentes reales de esta ronda porque se priorizó restaurar el servicio. Sin ADR
nuevo para este incidente — quedó mitigado y parcialmente investigado, no hay una decisión de arquitectura
que documentar todavía.

**Fix real separado, mismo día — Skill Factory (ver ADR 0163):** el fundador había intentado construir un
skill nuevo (`document_to_reader_optimized`, conversión de documentos a EPUB) y la construcción abortó por
un bug real de concurrencia (el chequeo de alcance de `build_skill()` comparaba diffs de `git status`
contra todo el repo, y confundió archivos de ESTA MISMA sesión con archivos del motor de escritura).
Corregido: `LocalCodeWriterResult` ahora expone `files_written` (autoritativo, armado en el momento de
cada escritura real), `build_skill()` ya no consulta git en absoluto para esa decisión. El código
placeholder que había escrito el intento anterior (link de Drive inventado, nunca llamaba a las
capacidades reales) se descartó — **pendiente real: reconstruir ese skill bien, con una Capacidad de
conversión a EPUB de verdad (`document_processor` no existe todavía en el repo)**, es trabajo aparte,
no arrancado.

**Iteración de UX de n8n con el fundador (en curso, sin decisión final) — arrancar sesión nueva DESDE ACÁ:**
el fundador pidió que el mapa de n8n (Fase 14/18) se sienta como una herramienta real, no un mapa de solo
lectura con formularios aparte. Fueron ~5 iteraciones de prototipo en vivo, cada una con un hallazgo real:
- Prototipo B/C: nodos `Set` con campos editables (texto + un checkbox real por cada una de las 19
  tools posibles) en vez de `noOp` de solo lectura — el fundador confirmó que esta dirección SÍ sirve.
- El fundador pidió explícitamente que `apply` no requiera una confirmación en un segundo workflow aparte
  ("estoy haciendo las cosas yo, no es necesario confirmar otra vez") — la cadena `Set → Proponer → Aplicar`
  ahora corre encadenada, un solo gesto real del fundador (editar + ejecutar) alcanza. Esto es una
  enmienda real a ADR 0156/0160 (que asumían un paso de confirmación separado) — **sin ADR escrito
  todavía**, porque el diseño final de la UX no está cerrado.
- Prototipo D (canvas único con 7 triggers, uno por rol): **descartado, no funcionó** — confirmado en vivo
  que el botón de play de un nodo individual solo corre ESE nodo, nunca la cadena completa; con 7 triggers
  compartiendo un canvas no había forma inequívoca de correr "solo este rol" con el botón real de
  "Test workflow". Se borró de n8n (`CU43BQyLEQuEx5mS` ya no existe).
- **Prototipo E (estado actual, 2026-08-12, sin confirmar todavía por el fundador vía la UI):** 7
  workflows SEPARADOS, uno por rol (`Snarf - Editar CTO`, `Snarf - Editar COO`, etc.), cada uno con un
  único trigger real — así "Test workflow" es inequívoco, corre esa cadena y ninguna otra. IDs reales:
  `cto: K74wbPPll8HOKB19, coo: iDzcBKCwjAx5Zlyr, research: 5banqA7qoKUeYAqZ, ceo: iY91KHc0ixQNdltR,
  cfo: 2jjQE22nggMW1mim, cmo: del2dYdbbk1QisyY, creative: ZmlhrtKO40YadiE9` (no persistidos en
  `n8n_workflows/ids.json` todavía — siguen siendo prototipo, no la versión oficial). Generador real
  (idempotente, IDs ya guardados) copiado al repo en `n8n_workflows/_prototype_e_editar_agente.py` — el
  script original vivía en el scratchpad de la sesión anterior, que no sobrevive entre sesiones, por eso
  se guardó acá antes de cerrar. Correrlo de nuevo actualiza (PUT) los mismos 7 workflows, nunca crea
  duplicados. Si el diseño se confirma bueno, hay que llevar este patrón a `snarf/runtime/n8n_generator.py`
  de verdad (con tests reales, integrado a `n8n_workflows/ids.json`), generalizado a los 7 roles y después
  a las otras 8 ramas de Specialists.

**Sesión 2026-08-13 — Prototipo E confirmado en vivo y promovido a oficial (ADR 0164):** el fundador abrió
`Snarf - Editar CTO` (`K74wbPPll8HOKB19`) y apretó "Test workflow". Confirmado del lado del server real, no
solo por la UI de n8n (mismo criterio de honestidad de siempre): `POST /n8n/agent/cto/propose` → 200 y
`POST /n8n/agent/cto/apply` → 200 en el mismo instante, ejecución de n8n real `2844` (`mode: manual`,
`status: success`), `GET /n8n/agent/cto` posterior confirma el prompt del CTO en v2 activa — primer `apply`
real de todo este camino (ADR 0162 había verificado `propose` pero deliberadamente no `apply` contra
producción). Con esa confirmación, y pedido explícito del fundador de proceder ("veamos como queda,
procede... asegurate de que quede todo prolijo y correctamente nombrado"):

- El patrón de 7 workflows separados **reemplaza** a `Snarf - Proponer/Confirmar cambio de agente` (ADR
  0160) como camino real de escritura estructural — esos dos workflows se borraron de n8n (nunca tuvieron
  un `apply` real) y sus exports/links quedaron limpiados (ver ADR 0164 para el detalle completo).
- `Snarf - Executive Board` deja de ser la superficie de edición y pasa a ser overview + navegación: cada
  rol del canvas enlaza ahora a su propio editor dedicado en vez del editor de texto genérico.
- El generador del Prototipo E se migró del script suelto `n8n_workflows/_prototype_e_editar_agente.py`
  (borrado) a `snarf/runtime/n8n_generator.py` real (`build_agent_edit_workflow`,
  `sync_agent_edit_workflows`), con 16 tests en `tests/test_n8n_generator.py` (antes 14).
- La Skill `n8n-map-sync` quedó actualizada para cubrir ambas superficies.
- **Generalizar este patrón a las otras 8 ramas de Specialists sigue sin arrancar** — sigue siendo trabajo
  de seguimiento, no bloqueante, mismo estado que ya anotaba ADR 0159.

**Sesión 2026-08-14 — Fase 22 hecha (ADR 0165: Project Manager + área como etapas reales), Fase 23 (spike
real contra n8n vivo) arrancada, con un hallazgo real que bloquea seguir a la Fase 24 sin una decisión del
fundador:**

Fase 22: `snarf/runtime/areas.py` (nuevo) reagrupa los 7 dominios de Specialists ya existentes en 4 áreas
(Operaciones/Administración/I+D/Marketing) — `Orchestrator._handle_tool` ahora anida dos spans
`workflow` reales (`project_manager` → `area:<id>`) para las 14 tools de esas áreas, ruteo por lookup
determinístico (nunca un LLM clasificando texto). Verificado real (no solo tests): un turno real con
`finance_monthly_pnl` produce en `data/telemetry_events.jsonl` la cadena `project_manager` →
`area:administracion` → `finance_monthly_pnl`, bien anidada, mismo `trace_id`. 1399/1399 tests
(1388 previos + 11 nuevos).

Fase 23 (spike, workflow `ZZZ-spike-wait-resume` creado y borrado en la instancia real): dos hallazgos
reales antes de escribir el generador de la Fase 24 —

1. **Un nodo `Webhook` creado vía la API de n8n necesita un campo `webhookId` explícito en el nodo (UUID),
   no solo `parameters.path`** — sin eso, el workflow queda `active: true` pero el webhook nunca se
   registra de verdad para tráfico real (404 "not registered" incluso después de reactivar). Confirmado
   comparando contra "My workflow" (creado desde la UI, sí tiene `webhookId`) — el generador de la Fase 24
   tiene que setear este campo a mano, `push_workflow()` de hoy no lo hace.
2. **Hallazgo más importante, sin resolver:** la instancia real de n8n (`docker-compose.n8n.yml`) no tiene
   seteada ninguna variable `EXECUTIONS_DATA_SAVE_*` — corre 100% con los defaults de n8n, que NO guardan
   progreso de una ejecución mientras está en curso (`EXECUTIONS_DATA_SAVE_ON_PROGRESS` default `false`).
   Confirmado en vivo: el workflow del spike, disparado de verdad y pausado en un nodo `Wait`, no aparece
   en `GET /api/v1/executions` (ni sin filtro, ni con `status=waiting`) — cero rastro vía la API mientras
   está esperando. Esto afecta cualquier cosa que dependa de *consultar* el estado de una ejecución en
   curso vía la API (verificación automatizada, "double click" después de que ya pasó el momento real si el
   canvas no estaba abierto en ese instante) — probablemente NO afecta la experiencia principal que pidió
   el fundador (ver un canvas abierto en el navegador iluminarse en vivo), porque esa animación en la UI de
   n8n corre por su propio mecanismo de push en tiempo real (websocket) mientras el editor está abierto,
   independiente de si la ejecución queda persistida en la base — pero **esto es una hipótesis, no
   verificado todavía con el canvas realmente abierto en un navegador real durante una pausa**.

**`EXECUTIONS_DATA_SAVE_ON_PROGRESS=true` activado (2026-08-14, decisión real del fundador):**
`docker-compose.n8n.yml` actualizado, contenedor `snarf-n8n` reiniciado y confirmado sano (`GET /healthz`
200, variable presente en el proceso real). Esto NO resolvió el problema de fondo — ver abajo.

**Bloqueo real, sin resolver — el diseño de "un solo workflow con nodos `Wait` encadenados" (aprobado en
el plan de esta sesión) no pudo verificarse funcionando en esta instancia real:** aislando el problema
nodo por nodo con workflows descartables reales (`ZZZ-spike-bare`/similares, todos borrados al terminar):

- `Webhook` solo → ejecución real registrada (confirmado, `GET /api/v1/executions` la muestra).
- `Webhook` → `Code` (`$execution.id`) → ejecución real registrada (confirmado).
- `Webhook` → `Code` → `Wait` (`resume: webhook`) → **ninguna ejecución nueva aparece nunca**, ni durante
  la espera ni después — probado con dos formas distintas de parámetros del nodo `Wait` (una propia, y una
  segunda copiada literal de la documentación oficial de n8n vía búsqueda real), con
  `EXECUTIONS_DATA_SAVE_ON_PROGRESS=true` ya activo, y repitiendo el ciclo completo
  desactivar→reactivar del workflow entre cada intento (por si la Fase 23 de arriba, sobre registro de
  webhooks, aplicaba de nuevo). El trigger siempre responde `200 "Workflow was started"` — pero la
  ejecución nunca queda registrada, ni como `waiting`, ni como `success`, ni como `error`; los logs del
  contenedor no muestran ningún error asociado.
- **No se pudo determinar la causa raíz solo con la API** (misma honestidad que el incidente del 12/08:
  mejor decir "no sé por qué" que inventar una explicación). Hipótesis reales sin confirmar: un límite de
  este build/versión de n8n (1.121.0) con nodos `Wait` disparados por un trigger `responseMode: onReceived`
  específicamente vía la API pública (no probado nunca a mano desde la UI); o un paso de configuración que
  la documentación no cubre para este caso.

**Resuelto (2026-08-14, mismo día) — el fundador armó a mano `Webhook → Wait` en la UI real y SÍ
funcionó:** la ejecución quedó real y visible en `waiting` (canvas con el nodo `Wait` resaltado, pantalla
"Executions" mostrándola en vivo) — confirma que el mecanismo central del diseño (nodos `Wait`
encadenados, canvas que se ilumina en vivo) funciona de verdad en esta instancia. El bloqueo de arriba
(cero ejecuciones visibles vía mis pruebas por API) tenía una causa completamente distinta a la sospechada,
aislada con el propio workflow del fundador como control real:

- **`GET /api/v1/executions` (el endpoint de LISTA) no devuelve ejecuciones en estado `waiting`** — ni sin
  filtro, ni filtrando por `workflowId`, ni con `status=waiting`. Es un límite real de esa ruta de la API
  pública de n8n 1.121.0, no un bug del lado de Snarf. **`GET /api/v1/executions/{id}` (por ID directo) sí
  funciona perfecto** — devuelve `status: "waiting"` correctamente. El diseño de la Fase 24 nunca necesitó
  el endpoint de lista (el `execution_id` se captura directo de la respuesta del trigger, nunca se busca
  después) — este límite queda documentado pero no bloquea nada real.
- **Un nodo `Wait` con `resume: "webhook"` necesita su propio campo `webhookId` (UUID) además del que ya
  necesita el nodo `Webhook` disparador** (mismo hallazgo #1 de arriba, pero aplica también al `Wait`, no
  solo al trigger) — confirmado comparando el workflow armado a mano por el fundador (que sí tiene
  `webhookId` en ambos nodos) contra los míos por API (que no lo tenían en el `Wait`).
- **Ronda final de verificación real, completa, con un workflow descartable propio
  (`ZZZ-spike-final`, borrado al terminar):** `Webhook (responseMode: responseNode)` → `Code` (captura
  `$execution.id`) → `Respond to Webhook` → `Wait (httpMethod: POST explícito, si no default a GET)`.
  Resultado real: el POST inicial al trigger devolvió `[{"executionId":"3166"}]` en el body de la
  respuesta (sin necesidad de leer `$execution.resumeUrl` desde dentro del workflow); un POST directo a
  `http://127.0.0.1:5678/webhook-waiting/3166` (URL 100% predecible, construida solo con el
  `execution_id` — más simple que lo que asumía el diseño original) avanzó la ejecución de `waiting` a
  `success` real. **Ciclo completo start→resume verificado de punta a punta contra la instancia real.**

**Fase 24 queda DESBLOQUEADA.** Detalles concretos que `build_live_turn_workflow()` tiene que respetar:
`webhookId` explícito (UUID) en el nodo `Webhook` y en cada nodo `Wait`; `httpMethod: "POST"` explícito en
cada `Wait` si el resume va a mandar payload por POST; el trigger con `responseMode: "responseNode"` +
`Code`+`Respond to Webhook` para devolver el `execution_id` en la respuesta inicial; el sink construye la
URL de resume él mismo (`{n8n_base}/webhook-waiting/{execution_id}`), sin necesidad de capturar ni
persistir un `resumeUrl` dinámico. Pendiente real, menor, no bloqueante: no se probó si el timeout de un
`Wait` sobrevive un reinicio del proceso de n8n, ni concurrencia real de dos triggers simultáneos — quedan
como verificación futura si aparece un problema real, no bloquean escribir el generador.

**Trabajo siguiente ya diseñado y aprobado (2026-08-12):** Fases 15-21 — n8n como control-plane completo de
la construcción de agentes (no solo texto de prompt: también herramientas, ruteo, y conexiones/secuencia
entre roles del Executive Board), con confirmación de dos pasos y una nueva ADR de gobernanza que
distingue escritura autónoma de escritura confirmada por el fundador en vivo. Ver sección "Fases 15-21"
más abajo para el detalle fase-por-fase. **Las siete fases están HECHAS: Fase 15 (ADR 0156, gobernanza),
Fase 16 (ADR 0157, Agent/Capability Registry), Fase 17 (ADR 0158, motor de stages), Fase 18 (ADR 0159,
generador n8n), Fase 19 (ADR 0160, propose/apply), Fase 20 (ADR 0161, replay/debugging — la Fase 12
original del roadmap, que llevaba sin arrancar desde siempre, quedó cerrada acá) y Fase 21 (ADR 0162,
verificación end-to-end real contra n8n y el server de producción, incluido un reinicio real del puerto
8002 confirmado explícitamente con el fundador).** El fundador pidió explícitamente continuar las 7 fases
sin pausar a confirmar cada una ("continua con todas las fases. no me preguntes"). **Ninguna de estas
fases se commiteó/pusheó todavía** — sigue pendiente ese paso, que sí se pide explícitamente antes de
hacerlo; si una sesión nueva retoma esto, ese commit es lo primero a confirmar con el fundador, no a
asumir.

**Hallazgo real de esta ronda, sin resolver — confirmar con el fundador:** hay contenido sin trackear en
git, ajeno por completo a esta serie de fases (`tests/test_document_to_reader_optimized.py`,
`snarf/specialists/productivity_documents/`, `data/document_to_reader_optimized/test.json`) — parece
trabajo de una sesión anterior que nunca se commiteó. No se tocó ni se investigó su origen; los tests de
ese archivo suman a los conteos de `pytest` de esta ronda (ver notas de honestidad en ADR 0158/0160) sin
ser parte de este trabajo.

Todo lo anterior salvo esta última ronda, incluida la Fase 11 (`adr/0152-*`, tool real `system_introspect`
expuesto por MCP — ver sección de la Fase 11 más abajo), ya está **commiteado y pusheado** (`622f184`, con
un commit adicional `c537e23` actualizando el pointer de MASTER_MAP encima) — working tree limpio, `master`
al día con `origin/master` antes de esta ronda. **Fase 8 parte 2/2 (decisión de stack de
observability/Langfuse) NO se ejecutó** — condicionada al rollout de usuarios de prueba, que todavía no
pasó (ver Fase 3). **Las otras dos deudas de 9.1 ("ver logs desde la UI", asistente de migración a VPS)
tampoco** — features aparte.

**Sesión 2026-08-12 (continuación, el fundador pasó la API key de n8n) — Fase 14 construida de punta a
punta:** el fundador generó la API key de n8n (paso a paso de la sección de Fase 14) y la pasó. Con eso:
credencial `httpHeaderAuth` nueva creada en n8n vía API (`X-Snarf-Token`), 13 workflows reales creados
(`Snarf - Mapa` + 9 ramas + reuso de los 2 ya existentes), verificados estructuralmente contra la API real
de n8n (sin targets huérfanos) y la llamada HTTP subyacente probada de punta a punta **desde dentro del
contenedor `snarf-n8n`** contra el server real (8002). Detalle completo, incluido el único pendiente real
(no hay forma de disparar el *trigger* de un workflow vía la API pública de n8n community — falta un clic
de "Test workflow" del fundador en la UI), en `adr/0154-*`. **Ya hecho y commiteado esta ronda:** ADR 0153
— extensión de cobertura del Prompt Registry a los 7 roles del Executive Board, motivada por la Fase 14 (de
la ronda anterior, previo a tener la API key). El plan original de esta serie, con el razonamiento
turno-a-turno de la ronda que definió el diseño del mapa, vive en
`~/.claude/plans/effervescent-wandering-hammock.md` si hace falta el detalle completo.

**Fase 9.2 — el fundador mandó las referencias reales del HUD de Iron Man (Jarvis/Ultron) y confirmó dos
decisiones antes de construir**: (1) los "skills" son un 4to anillo agrupado por familia, nunca un nodo
por tool; (2) la junta directiva suma 7 nodos reales — confirmado factible porque la telemetría YA
distinguía cada rol, faltaba taxonomía, no instrumentación. Primer corte visual completo: anillos con
rotación propia (compuesta sobre el motor 3D ya existente, nunca reemplazado), junta directiva como
mini-anillo real, anillo 4 con chips reales. **Mismo criterio que el dock (ADR 0086-0088): tratar este
primer corte como iterable, esperar feedback visual real del fundador antes de seguir puliendo.**

**Decisión de gobernanza real tomada esta ronda**: el fundador decidió que n8n puede escribir
prompts/config directo (`N8N_CONTROL_TOKEN`, sin aprobación humana) — reabre puntualmente, solo para esa
superficie, el principio "n8n observa y propone, nunca decide" de ADR 0093/0139. Ver ADR 0145.

**Hecho y commiteado, con ADR real por cada fase (leer el ADR antes de tocar código relacionado, tiene
el detalle completo de diseño/riesgos/tests):**
- ✅ Fase 1 — modelo de evento v2 + dispatcher in-process (`adr/0135-*`).
- ✅ Fase 2 — transporte opcional Redis Streams + SSE (`adr/0136-*`). Redis sigue sin instalarse de
  verdad (`SNARF_REDIS_URL` sin setear) — el seam está listo, no la infraestructura.
- ✅ Fase 3 — multi-usuario real: `Orchestrator` pasó de singleton a registro por `user_id`
  (`app.py::get_orchestrator`), `EpisodicMemory` per-usuario, login real con Google OAuth vía flujo web
  (reemplazó `InstalledAppFlow`, que era local-only) — `GET /login/google`, `GET /google/connect`,
  `GET /google/oauth/callback` (`adr/0137-*`).
- ✅ Fase 4 — n8n self-hosted real (Colima + Docker, `docker-compose.n8n.yml`), integración
  bidireccional verificada de punta a punta en producción real: `snarf/telemetry/n8n_webhook_sink.py`
  (Snarf→n8n) y `GET /n8n/status` con `N8N_CONTROL_TOKEN` (n8n→Snarf) (`adr/0139-*`).
- ✅ Adelanto real de la Fase 9.1 (control de infraestructura) — no estaba planeado para ahora, se hizo
  porque el fundador lo pidió al ver un uso de RAM que no entendía: nombres de proceso reconocibles
  (`setproctitle`/`snarf/runtime/proctitle_exec.py`) + tools `ops_process_status`/`ops_process_restart`
  (solo founder, con confirmación de dos pasos, `com.snarf.server` excluido de auto-reinicio)
  (`adr/0138-*`).

**Trabajo pendiente de commit:** ninguno — todo lo hecho hasta la fecha ya está commiteado y pusheado (ver
arriba). Sigue pendiente, eso sí, confirmar con el fundador antes de **reiniciar el server real** (puerto
8002, LaunchAgent) si algún cambio de esta serie lo requiere, mismo criterio que siempre.

**Estado real de infraestructura en esta Mac** (verificar que sigue así al retomar, puede haber
cambiado):
- Colima corriendo (`colima start --cpu 2 --memory 2 --disk 20` — perfil acotado a propósito).
- Contenedor `snarf-n8n` corriendo (`docker ps`), n8n real en `http://127.0.0.1:5678/` — el fundador ya
  completó el "Set up owner account" y tiene un workflow activo con un nodo Webhook (**en POST, no el
  GET por default** — gotcha real documentado en ADR 0139).
- `.env` tiene `N8N_WEBHOOK_URL` y `N8N_CONTROL_TOKEN` reales seteados — integración verificada
  funcionando (`POST` a la Production URL devuelve `200 {"message":"Workflow was started"}`).
- **Colima ahora tiene un intento de autostart** (`~/Library/LaunchAgents/com.snarf.n8n.plist`, agregado
  2026-08-11 a pedido del fundador) — `colima start` corre bien bajo `launchd` sin permiso especial, pero
  `docker compose -f docker-compose.n8n.yml up -d` se queda colgado bajo `launchd` porque el binario
  `docker` no tiene Acceso Total al Disco todavía (mismo gotcha de TCC que Python, ver CLAUDE.md). El
  plist está creado pero **deliberadamente sin cargar** (`launchctl bootout` ya corrido) hasta que se
  otorgue ese permiso a mano en Ajustes (paso manual, no automatizable) — después: `launchctl bootstrap
  gui/501 ~/Library/LaunchAgents/com.snarf.n8n.plist`. Hasta entonces, sigue siendo manual tras un
  reboot: `colima start --cpu 2 --memory 2 --disk 20` + `docker compose -f docker-compose.n8n.yml up -d`.
- Puede haber quedado una conversación de prueba real ("ping de verificación real, ignorar") en
  `data/episodic_memory.jsonl` del fundador — inofensiva, generada verificando el flujo de `/send`.

**Recomendación de VPS ya dada, sin decisión tomada todavía**: esquema híbrido (VPS aloja FastAPI/
orquestación, la inferencia local sigue viajando a esta Mac por Tailscale) — no migración completa,
porque MLX es específico de Apple Silicon y una migración completa perdería el costo ~$0 de inferencia
local. Pendiente de que el fundador decida si/cuándo. **La Fase 13 (más abajo) generaliza exactamente
este mismo esquema a cualquier usuario, no solo al fundador — leer esa sección antes de decidir el VPS,
son la misma decisión de arquitectura vista desde dos ángulos.**

**Prompts editables desde n8n — backend ya existía (Fase 9.3), faltaba el workflow real:** dos workflows
nuevos en `n8n_workflows/` (`snarf_ver_prompts.json`, `snarf_editar_prompt.json`) que pegan contra
`/n8n/prompts` ya construido. **Sin probar con una importación real en n8n todavía** (sin API key de n8n
configurada para hacerlo desde acá) — el fundador tiene que importarlos a mano (n8n → Import from File),
crear una credencial "Header Auth" llamada `Snarf n8n token` (header `X-Snarf-Token`, valor =
`N8N_CONTROL_TOKEN` de `.env`) y avisar si algo no calza con esta versión de n8n (1.121.0) para
corregirlo. Base URL usada: `http://host.docker.internal:8002` — verificado real desde dentro del
contenedor (`docker exec snarf-n8n wget ...` respondió 200).

**Qué preguntar/confirmar apenas se retome:** (1) ¿orden de la Fase 13 — app de Mac primero, o
BYO-compute completo? (2) ¿el tier pago se diseña ahora o se pospone? (3) ¿el fundador ya otorgó Acceso
Total al Disco a `/opt/homebrew/bin/docker` para poder cargar `com.snarf.n8n.plist`? La instrucción
vigente de sesiones anteriores fue "continuá con las fases siguientes, no hace falta que preguntes" —
sigue aplicando salvo que el fundador diga lo contrario, pero **no** cubre commits (esos siempre se piden
explícitamente), gasto real/infraestructura paga, ni decisiones de gobernanza nuevas (tier pago,
BYO-compute) — esas siempre se confirman con el fundador explícitamente.

---

## Contexto

El fundador viene charlando con varias IAs sobre hacia dónde llevar Snarf: memoria persistente que evoluciona, auto-mejora, un tablero visual en n8n, y una arquitectura "estilo Jarvis" que deje de sentirse como una caja negra a medida que gana capacidades. Trajo tres documentos: una "Constitución" de sistema cognitivo (aspiracional, sin autoridad sobre este repo), una guía de auditoría (framework de criterios, tampoco con autoridad), y un prompt de misión de 33 secciones pidiendo explícitamente: no reescribir nada, entender primero el repo real, y recién después planificar por fases.

Durante la revisión del plan, el fundador agregó un driver que cambia el ordenamiento de varias fases: **el objetivo inmediato es empezar a tener usuarios de prueba reales**, no seguir siendo un sistema de un solo usuario en una Mac. Eso reordena prioridades: multi-usuario/onboarding deja de ser un track lateral y pasa a ser bloqueante; el Control Center/cockpit del fundador (antes "Fase 11, más adelante") se adelanta porque el fundador necesita poder ver y controlar el sistema mientras crece, no solo al final; y cualquier decisión de herramienta u infraestructura nueva tiene que evaluarse con ojos de costo (self-hosted/gratis primero, pago solo cuando haya capital para sostenerlo).

Se auditó el código real (no los documentos aspiracionales) con tres exploraciones en paralelo — Orchestrator/agentes, memoria/conocimiento/telemetría/prompts, y frontend/API/ADRs/MCP — más lectura directa de `TELEMETRY_SCHEMA.md`, `snarf/telemetry/events.py`, `snarf/mcp/tools.py`, y diseño validado en detalle de implementación para las Fases 1-2 (evento correlacionado + transporte).

**Principio que gobierna todo este plan** (Principio VI de FOUNDATION.md, ya citado en CLAUDE.md): nunca presentar como construido algo que no lo está. Este documento distingue explícitamente qué de la visión del fundador **ya existe hoy en código real** de qué es **genuinamente nuevo**, y marca con honestidad qué queda como verificación pendiente en vez de inventar una respuesta.

---

## Lo que ya existe y no hay que reconstruir

- **Un esquema de evento unificado real**: `snarf/telemetry/events.py` (`TelemetryEvent`) ya normaliza tool calls, llamadas a vendors/LLM y entradas de usuario en una sola forma de dato (`data/telemetry_events.jsonl`), emitido *además* de los tres logs originales.
- **Dos chokepoints, no noventa puntos dispersos**: todo tool call pasa por `Orchestrator._handle_tool` (`snarf/core/orchestrator.py:2286`); toda llamada real a un LLM pasa por un `_record_usage`-equivalente por vendor.
- **Metadata autodescriptiva ya existe, dos veces**: `TOOLS` del Orchestrator (JSON-Schema completo por tool, ya reusado por el servidor MCP) y el convenio `INPUT_SCHEMA`/`OUTPUT_SCHEMA` de cada `Specialist` (ADR 0101).
- **Multi-modelo/multi-proveedor ya está resuelto**: `snarf/runtime/llm_routing.py` enruta por rol entre 3 servidores MLX locales (gratis, en esta Mac) y 5 proveedores cloud, con fallback automático y persistencia editable sin tocar código. Desde ADR 0119, el modelo local es el default en casi todos los roles — esto es, además, la base del control de costos de todo este plan (ver sección "Costos").
- **Un patrón multi-agente real**: la Inteligencia Ejecutiva (`snarf/executive/`, ADR 0093/0094/0098) — 7 roles de solo-lectura, cada uno un subproceso separado hablando MCP-over-stdio, con allowlist de tools por rol. Precedente de seguridad a copiar en todo lo nuevo: allowlist positivo, nunca por exclusión.
- **Soporte per-usuario parcial ya construido**: `data/user_profile/<user_id>.json`, credenciales de Google por usuario desde ADR 0021 (login + credenciales por usuario), `data/dashboard_prefs/<user_id>.json`. Multi-usuario no es un concepto ausente — hay que confirmar cuánto de esto es real hoy vs. asumido (ver Fase 3).
- **HUD/dashboard ya existe** (`web/index.html`, vista clásica + vista radial "HUD"), alimentado hoy por *polling*. Ya reduce carga cognitiva parcialmente — la Fase 9 lo lleva más lejos, no lo reemplaza desde cero.
- **Precedente de rollout reversible por usuario**: el toggle clásico/HUD (ADR 0090) ya demuestra que este repo sabe lanzar una vista nueva de forma opt-in/reversible antes de hacerla default — el mecanismo que la Fase 9 reusa para "cerebro nuevo visible solo para el fundador primero".
- **Precedente de escritura controlada sobre el propio sistema**: Skill Factory (ADR 0101/0102) ya genera/activa Specialists nuevos con confirmación de dos pasos — el mecanismo que la Fase 9 reusa para que n8n pueda proponer cambios a un agente sin que n8n tenga autoridad de ejecutarlos directamente.
- **Búsqueda semántica/vectorizada ya existe y cubre más de lo que parece a simple vista** — hallazgo importante, corrige una versión anterior de este plan: el motor genérico `KnowledgeSource`/`KnowledgeIndexer`/`VectorStore` (ChromaDB + embeddings Voyage, ADR 0096) ya indexa y permite buscar semánticamente **Drive, Notion (ambos bajo el dominio `personal`), este mismo repo (`code`) y, desde ADR 0127, el historial completo de conversaciones** (dominio `conversations`, una conversación entera como ítem indexable, filtrable por `project_id`, reindexado incremental automático). Esto ya es real, en producción, no aspiracional — no hay que reconstruirlo, hay que sumarle los dos dominios que todavía faltan (ver Track paralelo).

Lo que **falta de verdad** (confirmado por código, no por documentos viejos): mecanismo genérico de aprobación humana, un flujo de alta/onboarding para un segundo usuario real, una vista visual real de control de infraestructura, streaming de voz bidireccional (hoy es grabar → transcribir → responder → sintetizar, no un canal continuo), indexado semántico de los propios eventos de telemetría de Snarf, una capa de **hechos** con confianza/versionado (distinta de la búsqueda semántica de documentos, que sí existe), y cualquier mecanismo de proactividad real (hoy Snarf solo responde, nunca inicia).

---

## Arquitectura objetivo

**Snarf sigue siendo el cerebro.** n8n nunca es un segundo orquestador ni contiene lógica de negocio — es una capa de operación visual y automatización, con capacidad de **proponer** cambios (nuevos flujos, edición de un agente existente) que Snarf ejecuta por sus propios caminos ya auditados (Prompt Registry, Skill Factory), nunca por una segunda implementación. El event bus es el sistema nervioso: transporta, no decide.

```
Usuario (founder o de prueba) → Frontend (web/index.html) → app.py (FastAPI) → Orchestrator
                                                                                    ↓
                                                        Specialists / Executive Board (subprocess)
                                                                                    ↓
                                                Capabilities (LLM local/cloud / Drive / Gmail / Notion / voz)

Cada acción real → snarf/telemetry/events.py (evento único, correlacionado)
                        ↓ (dispatcher in-process, nunca bloquea un turno)
              JSONL (piso de durabilidad) + Redis Streams (opcional, transporte)
                        ↓
   n8n (observa y propone) · Cerebro/Cockpit del fundador (SSE) · Claude Code (vía MCP) · usuarios de prueba (HUD)
```

**El cerebro/HUD clásico (`snarf/telemetry/brain.py` + la vista HUD de `web/index.html`) es la visualización principal y permanente.** Cada fase que agregue un tipo de evento, un nodo, un consumidor (Redis, n8n, multi-usuario) extiende su taxonomía (`TOOL_TO_NODE`/`VENDOR_TO_NODE`/`NODE_TIER`, protocolo de crecimiento ya test-enforced), nunca lo deja atrás. La Fase 9 lo lleva a una versión visualmente mucho más ambiciosa ("entidad cognitiva digital"), pero como evolución del mismo cerebro, no como un componente paralelo nuevo.

Regla dura: **si n8n o Redis están caídos, Snarf sigue funcionando exactamente igual.** Ninguno de los dos es una dependencia dura del loop principal.

---

## Costos — principio transversal a todas las fases

Pedido explícito del fundador: máxima calidad, mínimo costo; si algo tiene costo real, se busca primero una alternativa gratuita/self-hosted, y se documenta el plan de upgrade a pago para el día que haya capital — nunca se activa gasto recurrente sin decisión explícita.

| Pieza nueva de este plan | Costo hoy | Alternativa gratis elegida | Cuándo pasar a pago |
|---|---|---|---|
| Redis (Fase 2) | $0 | Redis OSS self-hosted (`brew install redis` / futuro `systemd` en VPS) | Redis Cloud gestionado, solo si el volumen de eventos o la necesidad de alta disponibilidad lo justifican — no antes |
| n8n (Fase 4) | $0 | n8n self-hosted (Community Edition, Docker local → VPS) | n8n Cloud, solo si el founder deja de querer operar el propio server |
| Langfuse (Fase 8) | $0 | Langfuse self-hosted (OSS) | Langfuse Cloud, solo si el volumen de trazas de usuarios de prueba supera lo que vale la pena auto-alojar |
| Grafana/Prometheus (diferido) | $0 si algún día se suman | Self-hosted OSS | — |
| LLM/embeddings por usuario de prueba | Variable real, ya trackeado (`usage_tracker`/`pricing.py`) | Ruteo local-first ya vigente desde ADR 0119 (modelo MLX en esta Mac por default en casi todos los roles) — el costo marginal por usuario de prueba adicional es ~$0 salvo los roles que necesitan de verdad un modelo cloud (ej. `drive_vision`) | Revisar el ruteo por rol si la carga de usuarios de prueba satura la Mac — recién ahí conviene routear más tráfico a cloud, con el costo ya visible en `/dashboard/cost_history` |
| VPS (plan ya existente, no ejecutado) | $0 hasta que se despliegue | — | Se activa cuando el founder decida migrar; `VPS_MIGRATION.md` ya es el plan |
| Google OAuth / APIs de Drive-Gmail-Calendar-YouTube | $0 (cuotas gratuitas de Google Cloud cubren este volumen) | — | — |

**Consecuencia para el roadmap:** ninguna fase de este plan agrega gasto recurrente nuevo por default. Cada vez que una fase menciona una herramienta de pago (Langfuse Cloud, Redis gestionado, n8n Cloud), la entrada de este plan es la versión self-hosted — la versión paga queda anotada como upgrade futuro explícito, nunca como el camino por default.

---

## Fase 0 — Auditoría (completa, este documento)

Sin cambios de código. Resultado: este plan.

---

## Fase 1 — Modelo de evento v2 + dispatcher in-process ✅ HECHO (`adr/0135-*`)

**Objetivo:** cerrar los 3 gaps que el propio equipo ya documentó en `TELEMETRY_SCHEMA.md` (`latencia_ms` de vendor, `estado="truncado"` nunca emitido, sin `event_id` de correlación) y agregar el ciclo de vida completo (`*.started`/`*.finished`/`*.failed`) sobre los dos chokepoints existentes — sin infraestructura nueva, sin romper ningún consumidor actual.

**Diseño de correlación:** `event_id` (uuid), `parent_event_id` (heredado del span activo vía `contextvars`, no un parámetro nuevo por emisor), `trace_id` (= `event_id` del turno raíz). `snarf/telemetry/context.py` pasa de `threading.local()` a `contextvars.ContextVar` — necesario porque FastAPI corre handlers síncronos en un threadpool que **sí** copia `contextvars` pero no `threading.local()`, y porque el fan-out de la Inteligencia Ejecutiva (`ThreadPoolExecutor`) pierde ambos si no se propaga explícitamente con `contextvars.copy_context()`. De paso corrige un bug real ya presente: `_ResilientLLM.generate` (`snarf/runtime/llm_routing.py:577`) limpia `llm_role` a `None` en vez de restaurar el valor del llamador.

**Multi-usuario desde el día uno del esquema:** dado que la Fase 3 (multi-usuario) viene poco después, el evento v2 agrega también `user_id` (mismo origen que `conversation_id`, vía `context.py`) — barato de incluir ahora, evita una segunda migración de esquema cuando lleguen usuarios de prueba reales.

**Compatibilidad hacia atrás:** los eventos nuevos (`*.started`, `agent.*`, `workflow.*`) quedan invisibles por default para los consumidores actuales vía un allowlist positivo (`LEGACY_EVENT_TYPES`) — mismo patrón que `snarf/mcp/tools.py::MCP_EXPOSED_TOOLS`.

**Tests:** `test_telemetry_dispatcher.py`, `test_telemetry_spans.py` nuevos; extensión de `test_telemetry_context.py`, `test_telemetry_events.py`, `test_orchestrator.py`, `test_anthropic_llm.py` (no romper los dos cache breakpoints — CLAUDE.md), `test_executive_specialist.py`, `test_app.py`.

---

## Fase 2 — Transporte para consumidores externos (Redis Streams, opcional y gratis) ✅ HECHO (`adr/0136-*`, Redis en sí sin instalar todavía)

**Por qué Redis y no "nada" ni Kafka:** con el volumen actual (~200 eventos/día) el throughput es irrelevante para cualquier opción. Lo que de verdad falta y ninguna alternativa liviana resuelve bien: (1) los eventos del subproceso MCP de la Inteligencia Ejecutiva son estructuralmente invisibles para un dispatcher in-process; (2) un consumidor caído necesita "todo desde el cursor X" (`Last-Event-ID` de SSE); (3) n8n trae nodos nativos de Redis. Kafka/RabbitMQ son sobre-ingeniería real a esta escala.

**No-negociable:** Redis es **opcional y nunca una dependencia dura**. `SNARF_REDIS_URL` sin setear ⇒ el paquete `redis` ni se importa. Si Redis se cae, un turno real no se entera — el fallo queda contado en `/ops/health`.

**Cómo correr Redis (gratis) en la Mac:** `brew install redis` + `brew services start redis` (Homebrew genera su propio LaunchAgent, mismo modelo que los 3 servers MLX). Aplican los dos gotchas de LaunchAgent de CLAUDE.md: `dir`/logs fuera de `~/Documents`. En el futuro VPS: `systemd`, coherente con `VPS_MIGRATION.md`.

**Diseño del stream:** un único stream `snarf:events`, `MAXLEN ~ 100000`. n8n/Control Center leen con **consumer group** (`XREADGROUP`); el SSE del frontend lee con **`XREAD` simple, sin grupo** (cada pestaña/usuario quiere ver todo desde su propio cursor).

---

## Fase 3 — Multi-usuario y onboarding (bloqueante para tener usuarios de prueba) ✅ HECHO (`adr/0137-*`) — con matices

**Corte real de lo que se hizo vs. lo que quedó pendiente** (ver `adr/0137-*` para el detalle completo):
SÍ — `Orchestrator` por `user_id` real (ya no singleton), `EpisodicMemory` per-usuario, login real con
Google (reemplazó el flujo `InstalledAppFlow` local-only por uno web con redirect/callback real). NO —
el "flujo de onboarding guiado" (vista nueva explicando para qué sirve cada conexión) no se construyó:
se decidió no tocar `web/index.html` (7500+ líneas) sin poder verificarlo en Playwright con el tiempo
disponible en esa sesión — sigue siendo trabajo real pendiente. Tampoco se resolvió el punto de
verificación de OAuth ante Google (límite de 100 testers en modo Testing) — sigue siendo un bloqueo
operativo real para superar al founder + círculo cercano.

---

## Fase 4 — Levantar n8n + integración (observar y proponer, nunca decidir) ✅ HECHO (`adr/0139-*`)

n8n Community Edition self-hosted en Docker local (Colima), alcanzable por Tailscale, nunca expuesto
públicamente. **Snarf → n8n:** webhook HTTP hacia nodos "Webhook" de n8n (push). **n8n → Snarf:** una API
de control/introspección autenticada por `N8N_CONTROL_TOKEN` propio del founder — nunca lógica de
negocio directa.

**Caso de uso explícito del fundador — n8n edita un agente existente:** un flujo de n8n puede *proponer*
un cambio a un prompt o a los pasos de un Specialist (vía la Fase 6, Prompt Registry, o Skill Factory
para cambios más profundos), siempre a través de la misma API de escritura controlada que usaría el
founder desde el frontend — nunca una segunda implementación de esa lógica dentro de n8n.

---

## Fase 5 — API de introspección (solo lectura) ✅ HECHO (`adr/0140-*`)

Expone lo que ya es autodescriptivo en código: `orchestrator.TOOLS`, ruteo real por rol
(`llm_routing.ROLES`), los 7 roles del board de Inteligencia Ejecutiva, conteo de sesiones activas por
usuario. `GET /n8n/introspect`, mismo token que `GET /n8n/status`.

---

## Fase 6 — Prompt Registry ✅ HECHO (`adr/0141-*`)

Migró los prompts hardcodeados (`SYSTEM_PREFIX` en `orchestrator.py` + system prompt propio de cada
Specialist — 20 constantes reales, más de las "~11" estimadas acá, ver ADR 0141 para el mapeo completo)
a `data/prompts.json`, mismo estilo JSON-por-entidad que `llm_routing.json`: versión activa, historial,
rollback. El texto actual se migró como v1 — nada cambia de comportamiento el día del corte. Corrección
real encontrada en el camino: los Specialists no pueden importar `snarf.runtime` (ADR 0026,
`tests/test_architecture_boundaries.py`) — se resolvió con inyección de un `system_prompt_provider`
callable, mismo patrón que `llm_factory`. Ningún endpoint HTTP para editar todavía (eso es Fase 9.3) —
esto habilita técnicamente el caso de uso de n8n de la Fase 4 y la comparación de versiones que hace
valiosa a Langfuse en la Fase 8, pero no los construye.

---

## Fase 7 — Configuración dinámica ✅ HECHO (`adr/0142-*`)

Extendió el patrón de `llm_routing.py` a `max_output_tokens`, `temperature` (hoy ni se pasaba),
`timeout_seconds`/`max_continuations` por rol (interpretación real de "retry": el loop de continuación
automática, único mecanismo de ese tipo que existe hoy más allá del fallback entre proveedores).
Versionado igual que Prompt Registry, con overrides parciales (no resetea campos no tocados). Gotcha
real: varios tests construyen las Capacidades de LLM con `__new__` — necesitó defaults también a nivel
de clase, no solo de `__init__`.

---

## Fase 8 — Aprobación humana genérica (HITL) + decisión de stack de observability

**Parte 1/2 — HITL ✅ HECHO (`adr/0143-*`):** generalizó el protocolo de dos pasos
ad-hoc de `HIGH_IMPACT_TOOLS`/`BULK_READ_GATED_TOOLS` (ADR 0015) en dos `event_type` reales
(`approval.requested`/`approval.granted`) sobre el event bus de Fase 2, emitidos desde el chokepoint
único `_handle_tool` — consumible desde n8n sin que n8n pase a decidir nada. Sin `approval.rejected`
(gap honesto: no existe esa señal en el código, ver ADR). El protocolo de confirmación en sí no se tocó
— safety-critical, ADR 0084.

**Parte 2/2 — decisión de stack de observability: NO EJECUTADA, condicionada.** El propio driver de esta
parte (rollout de usuarios de prueba) todavía no arrancó (ver Fase 3) — instalar/decidir esto ahora sería
infraestructura por delante de una necesidad real, contra el criterio explícito de este mismo plan
("Fundación técnica vs. modo Capacidades"). Queda para retomar cuando el rollout arranque:
- **Grafana + Prometheus**: postergados — ese problema lo crea el VPS multiplicando procesos, no la cantidad de usuarios de prueba.
- **OpenTelemetry**: postergado hasta que haga falta interoperar con un tercero externo real.
- **Langfuse**: el candidato a adelantar, gratis en su versión self-hosted. Se evalúa en paralelo a la Fase 6, cuando arranque el rollout de usuarios de prueba.

---

## Fase 9 — Cockpit del fundador: control de infraestructura + cerebro rediseñado

### 9.1 — Control de infraestructura ⚠️ PARCIAL, la vista real ya hecha (`adr/0138-*`, `adr/0146-*`)

Lo que ya existe: tools `ops_process_status`/`ops_process_restart` (solo founder, confirmación de dos
pasos, `com.snarf.server` excluido de auto-reinicio), nombres de proceso reales en Activity Monitor/`ps`
(`setproctitle`), y ahora también **una vista real en `web/index.html`** (sección "Control de
infraestructura" en Configuración, `GET/POST /ops/processes`, verificado con Playwright — ver ADR 0146).
**Falta todavía**: ver logs desde la UI, asistente guiado de migración a VPS.

### 9.2 — Cerebro como "giroscopio" ✅ HECHO, commiteado (`adr/0147-0150-*`)

Alcance real, confirmado con el fundador antes de construir (referencias del HUD de Iron Man/Jarvis/
Ultron, nunca la Vista HUD del dashboard — features distintas): 7 nodos reales para la junta directiva
(antes 1 solo nodo), cada anillo del grafo con rotación propia independiente (compuesta sobre el motor
3D existente, nunca reemplazado) acelerada por actividad real, y un 4to anillo de skills (chips
transitorios reales, sin taxonomía nueva). Real-time vía SSE deliberadamente diferido a una fase aparte.
**Sin gate `is_founder`** — a diferencia del toggle clásico/HUD del dashboard (ADR 0090), `#brainPanel`
ya era visible para cualquier usuario logueado antes de este rediseño; se extendió en el lugar, no como
preview nueva. Verificado con Playwright contra datos reales de producción — primer corte deliberadamente
iterable (mismo criterio que el dock, ADR 0086-0088: esperar feedback visual real antes de pulir más).

### 9.3 — Escritura real de prompts/config ✅ HECHO, COMPLETO (`adr/0144-*`, `adr/0145-*`)

Cierra el caso de uso completo de la Fase 4: `GET/PUT /prompts/{id}` + `POST /prompts/{id}/rollback`,
mismo trío para `/generation-config/{role}` — tanto el founder (`/prompts`, `require_user`) como n8n
(`/n8n/prompts`, `require_n8n_token`, mismo storage real, nunca dos implementaciones) pueden editar el
prompt/config activo de un agente (Fase 6/7) y activar la nueva versión, con historial y rollback real.
**Decisión de gobernanza real del fundador (ADR 0145)**: n8n escribe directo, sin aprobación humana —
reabre puntualmente el principio "n8n observa y propone, nunca decide" de ADR 0093/0139 para esta
superficie. Sin UI nueva en `web/index.html` — eso sigue siendo 9.2.

---

## Fase 10 — Conversación continua manos libres ✅ HECHO, primer corte (`adr/0151-*`)

Resuelto **sin** el canal WebSocket bidireccional que el texto original de esta fase insinuaba: ni Groq
STT ni Kokoro TTS son streaming del lado del proveedor (confirmado leyendo el código real de ambos
providers), así que un transporte nuevo no bajaría latencia real. En cambio: botón nuevo en la barra de
input (a la derecha del mic existente, que sigue igual) activa un modo de conversación continua con VAD
(voice activity detection) client-side por energía RMS — hablás y Snarf responde con voz sin tap manual
por turno, con barge-in real (empezar a hablar mientras Snarf habla lo interrumpe). Reusa `/transcribe`,
`/send`, `/tts`, `/cancel/{request_id}` tal cual — cero endpoints backend nuevos. Riesgo conocido, no
resuelto esta ronda: VAD sin cancelación de eco acústico real (requiere auriculares o prueba en vivo para
confirmar que no se auto-interrumpe con el propio audio de los parlantes). Si en el futuro Groq o Kokoro
sumaran soporte real de streaming del lado del proveedor, ahí sí valdría reabrir la opción de un transporte
WebSocket — no antes.

---

## Fase 11 — Extensión Claude Code / MCP ✅ HECHO (`adr/0152-*`)

Corrección real encontrada al ejecutar esta fase: la Fase 5 nunca había creado tools de introspección
reales (solo funciones puras detrás de `GET /n8n/introspect`) — se creó el tool real `system_introspect`
(delega a la misma `introspection.system_snapshot()`, nunca una segunda implementación) y se sumó a
`MCP_EXPOSED_TOOLS`. Decisión explícita de NO crear un subset de rol propio para Claude Code: la
restricción por rol (`ROLE_TOOL_SUBSETS`) se aplica del lado del cliente (`_MCPToolBridge`, mecanismo
interno de la Inteligencia Ejecutiva) — no hay identidad de consumidor del lado del servidor, así que un
subset sin punto real de aplicación sería scaffolding decorativo. Conectar esta sesión de Claude Code al
servidor MCP de este repo (`.mcp.json`) queda fuera de alcance — es la política "Skills vs. MCP" de
`CLAUDE.md`, que hoy no identifica ningún candidato real para eso.

---

## Fase 12 — Replay y debugging

Sobre la persistencia de Redis Streams (Fase 2) + `EpisodicMemory` + versiones de prompt/config (Fases 6-7): seleccionar una ejecución pasada por `trace_id` y reproducirla. Diseño explícito para no-determinismo de LLM.

---

## Fase 13 — Multi-dispositivo: apps nativas + BYO-compute (PROPUESTA, sin decisión tomada)

**Origen:** pedido real del fundador el 2026-08-11 (sesión que se cortó a mitad, retomada acá). Pidió
investigación profunda "a los más altos niveles de calidad de la industria" sobre: (1) una app de Mac y
una de celular que permitan gestionar los recursos de la propia máquina, y (2) que cada usuario pueda
aportar el cómputo de su celular/Mac/PC para sostener su propia instancia de Snarf, con un tier pago para
más velocidad/capacidad para quien no quiera depender de su propio hardware. Investigación real hecha con
`WebSearch` esta sesión (no recitada de memoria/entrenamiento) — fuentes al pie de cada hallazgo.

### Hallazgo 1 — esto no es un problema nuevo, es el mismo patrón ya recomendado, generalizado

La sección "Estado actual" de este documento ya venía recomendando un esquema híbrido para el propio
fundador: VPS aloja FastAPI/orquestación, la inferencia local viaja por Tailscale hasta esta Mac (MLX es
específico de Apple Silicon). **Lo que el fundador pide ahora es exactamente ese mismo patrón, generalizado
de "la Mac del fundador" a "la Mac/PC de cualquier usuario".** No hace falta inventar arquitectura nueva —
hace falta (a) un flujo de emparejamiento por usuario (hoy Tailscale solo conecta las máquinas del
fundador), (b) una app que empaquete ese emparejamiento en un click en vez de configuración manual, y (c)
extender `llm_routing.py` (ya multi-proveedor, ya con fallback automático) para que la "máquina del
usuario" sea una entrada de routing más, particionada por `user_id`.

### Hallazgo 2 — "cómputo distribuido para LLMs" es un patrón probado, pero hay que distinguir dos formas muy distintas

- **Forma A — mis propios dispositivos, mi propio workload** (Exo Labs: parte un modelo entre las
  máquinas de una misma persona en su red local, pool de memoria/cómputo real, sin arquitectura
  master-worker). Esto es exactamente lo que describió el fundador ("que el usuario utilice los recursos
  de su celular y su Mac para soportar a Snarf") — **factible, con precedente real**.
- **Forma B — pool de desconocidos para un modelo compartido** (Petals: sirve un modelo público
  colaborativamente entre pares que no se conocen). Esto es un problema completamente distinto (confianza
  entre pares, privacidad de datos de terceros circulando por hardware ajeno) y **no es lo que el
  fundador pidió** — no construir esto sin una conversación aparte y explícita.
  [Fuente: SharedLLM vs Petals vs Exo vs Kalavai](https://sharedllm.org/blog/sharedllm-vs-petals-vs-exo.html),
  [Deep Dive: Exo](https://medium.com/@leif.markthaler/deep-dive-exo-distributed-ai-inference-on-consumer-hardware-068e341d8e3c)

### Hallazgo 3 — el celular NO puede ser un nodo de cómputo confiable, por diseño del propio OS

iOS (y cada vez más Android) restringe arquitecturalmente la ejecución en segundo plano: ~30 segundos de
wall-clock para tareas estándar, sin daemons persistentes posibles, con iOS 26 endureciendo esto todavía
más por gestión de batería. **No hay forma de que un iPhone "aporte cómputo ocioso" de forma continua** —
eso no es una limitación de esfuerzo de ingeniería, es una decisión de plataforma de Apple/Google.
Consecuencia real para el diseño: el celular puede ser cliente (UI, notificaciones, quizás cómputo real en
primer plano vía Neural Engine para tareas puntuales), pero **nunca el nodo que sostiene a Snarf** — ese
rol es de la Mac/PC, igual que hoy. No vender la app de celular como "tu Snarf corriendo en tu bolsillo
24/7".
[Fuente: iOS Background Execution Limits 2026](https://www.appsonair.com/blogs/background-execution-limits-in-ios-what-every-developer-must-know)

### Hallazgo 4 — framework recomendado para las apps: Tauri v2, no Electron

Tauri v2 (Rust + WebView nativo) sobre Electron (Chromium+Node empaquetado completo): ~10x menos peso de
instalador (2-10MB vs 80-200MB), ~50MB de RAM vs 120MB+, seguridad por capacidades explícitas por default
(mismo principio de allowlist-primero que ya rige todo este repo — MCP, `ROLE_TOOL_SUBSETS`, HITL), con
auditoría de seguridad publicada. Y, clave para este pedido puntual: **Tauri v2 compila a Mac, Windows,
Linux, iOS y Android desde el mismo código** — envolviendo el `web/index.html` que YA EXISTE, sin
reescribir la UI desde cero. La capa nativa de Rust es lo que le daría acceso real a recursos del sistema
(CPU/batería/procesos) que una pestaña de navegador nunca puede tener — respuesta directa a "gestionar los
recursos de la Mac desde la app".
[Fuente: Tauri vs Electron 2026](https://tech-insider.org/tauri-vs-electron-2026/)

### Decisiones confirmadas por el fundador (2026-08-11/12, sesión que retomó la anterior cortada a mitad)

1. **No construir Forma B (pool entre desconocidos)** — sigue fuera de alcance.
2. **Motor local: Ollama embebido, confirmado** — la app de Snarf lo instala/gestiona puertas adentro,
   nunca expuesto como producto aparte. MLX (Mac-only) sigue siendo lo que ya corre en la Mac del
   fundador; Ollama es lo que hace esto viable también en Windows/Linux sin construir un motor propio.
3. **BYOK ("usá tu suscripción de ChatGPT/Grok"): descartado.** Investigado con `WebSearch`: una
   suscripción de consumidor no se puede conectar a una app de terceros (lo prohíben los propios términos
   del proveedor) — solo una API key separada, facturada aparte, permitiría esto, y la mayoría de
   usuarios no técnicos no llega a configurarla (problema de UX real y documentado en la industria).
   Onboarding queda en **dos caminos**, no tres: "Usalo ya" (tier pago hosted, cero configuración) y
   "Usá el cómputo de tu compu" (Ollama embebido, gratis, opt-in).
   [Fuente: BYOK y términos de OpenAI](https://docs.warp.dev/agent-platform/inference/bring-your-own-api-key/)
4. **App de escritorio (Mac/Windows) primero, en Tauri v2**, envolviendo `web/index.html` — desbloquea
   control real de recursos + es la base técnica para que la propia Mac/PC del usuario sea su nodo de
   cómputo (generaliza el Tailscale actual). App de celular después, como cliente liviano — nunca nodo de
   cómputo (iOS/Android lo prohíben arquitecturalmente, ver Hallazgo 3).
5. **Notion sumado al alcance de las apps** (pedido nuevo del fundador esta ronda): además de leer, poder
   escribir/modificar/borrar dentro de bases de datos específicas de Notion desde la app. Contexto real
   importante — esto no arranca de cero: `snarf/capabilities/notion.py` (ADR 0075) ya tiene 4 tools
   (`notion_search`, `notion_read_page`, `notion_create_page`, `notion_append_to_page`), y
   `NOTION_API_KEY` **ya está configurada en `.env`** (verificado 2026-08-12 — la nota de memoria que
   decía "sin configurar" quedó desactualizada, hay que confirmar con el fundador si ya compartió páginas
   con la integración antes de asumir que ya funciona contra datos reales). Falta lo que ya estaba
   anotado como pendiente desde esa fase: bidireccionalidad real con Drive, gestión de bases de datos
   específicas (crear/editar/borrar filas, no solo páginas sueltas), indexado en `drive_search_knowledge`.
   Ver memoria `snarf_roadmap_legion_and_notion_deferred_items` para el resto del contexto de esa fase
   (manuales de GNT para la Legión de marketing, agente secretario) — sigue vigente, no se pierde.
6. **Tier pago = cómputo cloud-hosted sin depender de tu propia máquina** — esto ya es, en esencia, la
   Fase 8/parte 2 (Langfuse) + `llm_routing.py` con proveedores cloud, solo falta la superficie de
   facturación — no es infraestructura nueva.
7. Esta fase queda **bloqueada por la Fase 3** (usuarios de prueba reales) igual que la Fase 8/2 — no tiene
   sentido construir emparejamiento multi-dispositivo antes de tener un segundo usuario real que lo use.

**Estado real: todavía sin arrancar el código de las apps** — esta ronda solo dejó las decisiones de
arquitectura confirmadas y un plan (`~/.claude/plans/effervescent-wandering-hammock.md`, ver también el
resumen de decisiones acá). Arranca aparte, cuando el fundador confirme cuándo (después del mapa de n8n
de abajo, o en paralelo).

---

## Fase 14 — Mapa navegable de Snarf en n8n (primer corte real, hecho 2026-08-12, ver ADR 0154)

Pedido del fundador (misma sesión que la Fase 13 refinada): no los dos workflows simples de
`n8n_workflows/` (ver/editar prompts, ya construidos), sino una representación completa y navegable de la
arquitectura real de Snarf en n8n — Orchestrator con todos los agentes/skills debajo, poder entrar
(drill-down) a cada uno y ver su flujo interno, entrar a un subagente si lo tiene, y editar cada nodo
desde ahí.

**Jerarquía real descubierta (explorada 2026-08-11/12, no hay que reinventar una segunda):**
`snarf/telemetry/brain.py` ya tiene la única jerarquía padre/hijo codificada del repo (`NODE_PARENT`,
hoy solo usado para los 7 roles del Executive Board colgando de `specialist_executive_board`) — el mapa
de n8n tiene que reflejar ese mismo taxonomy. 13 Specialists reales agrupados en 7 carpetas
(`agency/community/content/finance/productivity/research/sales` + raíz), Executive Board como rama
separada con 7 sub-roles (el único ejemplo real hoy de "agente con subagentes adentro"), y un único caso
real de un Specialist inyectando a otro (`ClientStatusSpecialist` → `ProjectManager`).

**Extensión de cobertura ya hecha esta ronda (ADR 0153):** los 7 roles del Executive Board ahora sí tienen
`prompt_id` real (`executive_board_{cto,coo,research,ceo,cfo,cmo,creative}`), editable vía `/n8n/prompts`
igual que los otros 20. `community_pulse`/`monthly_pnl` quedan afuera (determinísticos, sin LLM, sin
prompt) y el meta-prompt de Skill Factory queda afuera a propósito (plantilla con guardrails de seguridad
reales, no un texto libre seguro de reescribir — ver ADR 0153 para el razonamiento completo).

**Bloqueante real:** un mapa de ~15-20 workflows interconectados (nodos "Execute Workflow" que navegan
entre sub-workflows) necesita el ID real que n8n asigna a cada uno al importarlo — armar eso a mano sin
poder crear/verificar en n8n desde acá es lento y frágil. El fundador confirmó que va a generar una API
key de n8n. **Paso a paso para cuando esté frente a la Mac** (n8n solo escucha en `127.0.0.1:5678`, no
es alcanzable de otra forma):

1. Abrir `http://127.0.0.1:5678` en un navegador de la Mac, loguearse con la cuenta de owner ya creada.
2. Ir a **Settings** (ícono de engranaje, abajo a la izquierda) → **n8n API**.
3. **Create an API key** → copiar el valor completo (empieza con `n8n_api_...`).
4. Guardarlo en un lugar seguro (ej. gestor de contraseñas) — no se puede volver a ver completo después
   de cerrar esa pantalla, solo regenerar uno nuevo.
5. Pegarlo en la sesión de Claude Code que esté usando en ese momento (puede ser esta misma sesión
   continuada, o una nueva — ver nota de continuidad abajo).

**Continuidad entre sesiones (el fundador puede estar en el iPhone ahora, en la Mac después):** no hace
falta releer nada de este documento a mano ni repetir contexto — es exactamente para esto que este
roadmap vive en el repo y no en `~/.claude/plans/` (ver la nota al principio del archivo). Esto ya se
verificó real: la sesión que retomó el 2026-08-12 con solo "seguimos con la Fase 14, tengo la API key"
tuvo todo el contexto necesario (esta sección, el ADR 0153, los workflows ya construidos) sin reconstruir
nada. El plan original, con el diseño completo del árbol de workflows, queda en
`~/.claude/plans/effervescent-wandering-hammock.md` por si hace falta el detalle turno-a-turno de cómo se
llegó a estas decisiones.

**Hecho 2026-08-12 (ver ADR 0154 para el detalle completo):** 13 workflows reales en n8n — `Snarf - Mapa`
(raíz, drill-down a 9 ramas vía nodos `executeWorkflow`) + 9 workflows de rama (7 carpetas de Specialists +
raíz + Executive Board), cada uno con un nodo `noOp` por Specialist/rol (notas visibles en el canvas con
su `prompt_id` real, o por qué no lo tiene) + reuso de `Snarf - Ver prompts`/`Snarf - Editar prompt` como
única superficie de edición real (nunca un mini-workflow nuevo por `prompt_id`). Credencial
`httpHeaderAuth` (`X-Snarf-Token`) creada en n8n vía API. IDs reales asignados por esta instancia de n8n en
`n8n_workflows/ids.json`. **Pendiente real, único:** la API pública de n8n community no expone forma de
disparar el *trigger* de un workflow — falta que el fundador entre a `http://127.0.0.1:5678`, abra
`Snarf - Mapa` y haga clic en "Test workflow" al menos una vez para la verificación visual/end-to-end
final (la llamada HTTP subyacente sí se probó de punta a punta, ver ADR 0154).

---

## Fases 15-21 — n8n como control-plane completo de agentes (PLAN APROBADO 2026-08-12, sin código aún)

**Por qué:** el fundador probó el mapa de la Fase 14 y lo encontró insuficiente para lo que necesita —
sigue siendo un `manualTrigger` que dispara una lista plana de nodos `executeWorkflow`, sin trazabilidad
visual real, sin orden, y la única edición real (`Snarf - Editar prompt`) es un formulario de texto plano
sin ningún concepto de estructura de agente. Pidió explícitamente: poder controlar desde n8n **toda** la
construcción de un agente (prompt + qué herramientas tiene + qué modelo usa + cómo se conecta/secuencia
con otros agentes), con una confirmación de dos pasos antes de aplicar cualquier cambio, y que — si algún
documento de gobernanza le impide ejercer esa autoridad como fundador vía n8n — ese documento es lo que
está mal, no su pedido. Plan diseñado y aprobado el 2026-08-12 en sesión de Plan Mode; texto completo con
razonamiento turno-a-turno (incluida la verificación contra código real que corrigió dos supuestos del
brief inicial: el ruteo de modelo por rol ya era editable en runtime, y las conexiones entre roles del
Executive Board no existían en ningún lado) en
`~/.claude/plans/necesito-generar-un-plan-cuddly-marble.md`.

**Invariante que no se negocia en ninguna fase de esta serie:** `Orchestrator._handle_tool()` sigue siendo
el único motor de ejecución de Snarf — n8n, aun con el fundador al mando, nunca se convierte en un segundo
runtime paralelo, siempre escribe a un registro de estado versionado que el Orchestrator/`executive/`
leen. La resolución de la tensión de gobernanza no es "borrar la regla vieja" (ADR 0093/0139/0145 sobre
"n8n observa y propone, nunca decide") sino distinguir dos categorías que esa regla nunca había necesitado
separar: escritura **autónoma/de máquina sin humano en el momento** (el caso ya cubierto por ADR 0145,
sigue acotada a texto/config) vs. escritura **iniciada y confirmada por el fundador en vivo en la UI de
n8n** (caso nuevo, autorizado en la Fase 15, sin ese límite porque hay una persona real decidiendo).

Siete fases, una ADR cada una, mismo criterio que el resto de este roadmap:

- ✅ Fase 15 (ADR 0156) — gobernanza: distinción autónomo vs. fundador-confirmado, enmienda por
  superación de ADR 0093/0139/0145 (Constitution Art. II/VII/VIII) referenciándolas desde la ADR nueva
  sin tocar sus archivos (mismo criterio que ya usó ADR 0093 con ADR 0037), sin código todavía.
- ✅ Fase 16 (ADR 0157) — Agent/Capability Registry: `snarf/runtime/tool_subset_registry.py` y
  `snarf/runtime/agent_graph_registry.py` (nuevos, mismo shape versionado que `prompt_registry.py`),
  extensión aditiva de `llm_routing.py` (`routing_history`/`save_routing_versioned`/`rollback_routing`,
  archivo paralelo `data/llm_routing_history.json`, nunca toca el hot path), y `agent_registry.py`
  (composición, `get_agent_recipe()`) como único punto de lectura para las fases siguientes. Sin overrides,
  comportamiento idéntico al hardcodeado de hoy — verificado con 26 tests nuevos, 1336/1336 en verde.
- ✅ Fase 17 (ADR 0158) — motor de stages real en `ExecutiveBoardSpecialist.consult()`
  (`snarf/executive/specialist.py:74`): sin overrides, fan-out 100% paralelo idéntico a antes; con stages
  guardadas en `agent_graph_registry`, corre en el orden real, pasando el resultado de una stage como
  contexto (nunca autoridad, ADR 0094 intacto) a la siguiente. Detectados y corregidos 2 tests
  preexistentes con la firma vieja de `consult_role` al correr la suite completa. 1342/1342 en verde
  (cifra corregida — la primera corrida de esta ronda reportó "1 failed, 1341 passed", ver nota de
  honestidad en ADR 0158).
- ✅ Fase 18 (ADR 0159) — generador de workflows n8n reusable (`snarf/runtime/n8n_generator.py`, nuevo):
  reemplaza el trabajo manual de ADR 0154 por funciones puras y testeables (`build_executive_board_workflow`)
  + una mitad con red (`push_workflow`/`sync_executive_board`, idempotente contra `/api/v1/workflows`).
  Cada nodo del board recalcula su texto real (prompt_id/tools/modelo) en cada corrida; las conexiones
  reflejan las stages reales cuando hay override. Sumado también `GET /n8n/agent/{agent_id}` en `app.py`
  (solo lectura, adelantado desde la Fase 19 original por ser bajo riesgo) y la Skill `n8n-map-sync`.
  **No se corrió contra la instancia real de n8n en esta ronda** (requiere Colima+API key reales, no
  disponibles en esta sesión) — queda para la Fase 21 o para cuando el fundador corra la Skill. 1355/1355
  en verde (1342 previos + 13 nuevos, verificado con `git diff` contra HEAD).
- ✅ Fase 19 (ADR 0160) — `snarf/runtime/agent_change_proposals.py` (nuevo): `propose()` calcula un diff
  real con TTL de 15 min sin aplicar nada; `apply()` revalida optimistic-locking (`StaleChangeError` →
  409 si el estado se movió) y recién ahí escribe a los 4 registros de la Fase 16. Endpoints
  `POST /n8n/agent/{id}/propose` y `.../apply` en `app.py`, con regeneración del mapa en background
  (best-effort, nunca tumba la escritura). Dos workflows n8n nuevos (`snarf_proponer_cambio_agente.json`,
  `snarf_confirmar_cambio_agente.json`) — dos pasos separados en vez del formulario nativo de dos páginas
  de n8n, para no apostar a un schema no verificable sin instancia real corriendo esta sesión (documentado
  en ADR 0160). 1373/1373 en verde — 1355 previos + 15 nuevos de esta fase + 3 tests de un archivo sin
  trackear (`tests/test_document_to_reader_optimized.py`) ajeno por completo a esta serie, ya presente en
  el working tree antes de esta ronda (no se tocó; confirmar con el fundador qué hacer con él). **No
  probado contra la instancia real de n8n** (ninguna fase 18/19 lo fue) — pendiente para Fase 21.
- ✅ Fase 20 (ADR 0161) — `snarf/telemetry/replay.py` (nuevo): reagrupa `data/telemetry_events.jsonl` por
  `trace_id`, nunca vuelve a ejecutar nada. `GET /n8n/traces`/`GET /traces/{id}` en `app.py`. Frontend
  (`web/index.html::startTraceReplay`) reusa el pipeline visual del cerebro en vivo (`spawnPulse`/
  `renderBrainFeed`), disparado por `?replay=<trace_id>`. Workflow `snarf_ver_trazas.json` (n8n como
  lanzador, no visor). **Verificado con Playwright en un navegador real** — instancia de prueba puerto
  8000 (nunca 8002), sesión minteada sin usar la contraseña real, una traza real ya existente (nunca
  datos inventados, ciclo de solo lectura): cero errores de consola, panel abierto, grafo renderizado, 8
  eventos reales animados con sus timestamps reales — screenshot revisado, no solo "no tiró excepción".
  1384/1384 en verde.
- ✅ Fase 21 (ADR 0162) — verificación end-to-end real: Colima+`snarf-n8n` estaban corriendo esta ronda
  (a diferencia de Fases 18-20), así que se pudo cerrar de punta a punta. `n8n_generator.sync_executive_board()`
  corrido de verdad contra n8n real (mismo id, confirma idempotencia); 3 workflows nuevos creados en n8n
  real y enlazados desde el mapa raíz (`Snarf - Mapa`, ahora 16 nodos); **server real de producción
  reiniciado (puerto 8002), con confirmación explícita del fundador antes de hacerlo** (procedimiento de
  CLAUDE.md, `launchctl bootout`/`bootstrap`), verificado sano después con tráfico real de sus
  dispositivos; ciclo real n8n→Snarf de producción probado desde dentro del contenedor (`GET /n8n/agent/cto`,
  `GET /n8n/traces`, `POST /n8n/agent/cto/propose`, los tres 200 reales). Deliberadamente **no** se corrió
  `apply` contra producción con el prompt de prueba — hubiera mutado el comportamiento real del CTO del
  fundador solo para demostrar el endpoint; queda como el primer `apply` real pendiente de que el fundador
  lo dispare cuando tenga un cambio de verdad que aplicar (mismo espíritu que el "clic de Test workflow"
  que dejó ADR 0154). 1384/1384 en verde, sin cambios de código en esta fase.

Las siete fases (15-21) están completas. **Falta commitear y pushear todo este trabajo** — no se hizo
todavía a propósito, se pide siempre explícito antes de un commit (ver CLAUDE.md).

Dependencias: 15 bloquea 16; 16 bloquea 17 y 18; 17+18 bloquean 19; 19+20 bloquean 21; 20 es independiente
(solo depende de telemetría ya existente, `spans.py`/ADR 0135) y puede construirse en paralelo con
16-19.

---

## Norte del plan: "Mark 1" vs. "Mark 2"

Encuadre real dado por el fundador el 2026-08-11: **Snarf v1 ("Mark 1") se considera terminado cuando se
pueda usar Snarf v1 para construir Snarf v2 ("Mark 2")** — el criterio de "listo" no es una lista de
features, es que el propio sistema alcance capacidad real de auto-extensión productiva. Esto no es un
concepto nuevo aislado — ya hay piezas reales apuntando exactamente ahí, hoy dispersas en este documento:
Skill Factory (ADR 0101/0102, el lazo de auto-evolución ya existe), la Pieza C del Track paralelo
(proactividad — la fuente de ideas que le faltaba a ese lazo), y ahora Fase 9.3 + los workflows de
`n8n_workflows/` (el fundador pudiendo hablar con Snarf, construir con Snarf, y verlo reflejado en n8n).
Ninguna fase individual de arriba está etiquetada "Mark 1 completo" — es un criterio transversal a
revisar cuando el Track paralelo + Skill Factory maduren, no una fase más en la lista.

---

## Track paralelo — Memoria semántica completa, proactividad y auto-evolución

Responde al pedido del fundador de que Snarf "recuerde semánticamente conversaciones, proyectos, Drive,
Notion y sus propios eventos, todo vectorizado — y que sea proactivo, no solo reactivo". Tres piezas:

**Pieza A — búsqueda semántica de documentos (ya existe, se extiende).** El motor
`KnowledgeSource`/`KnowledgeIndexer`/`VectorStore` (ADR 0096) ya vectoriza Drive, Notion y conversaciones
completas (ADR 0127). Falta sumarle un `TelemetryEventSource` (eventos de telemetría propios de Snarf) y
evaluar si proyectos necesitan su propio `KnowledgeSource` o alcanza con seguir extendiendo el filtro
`project_id` existente.

**Pieza B — memoria de hechos con confianza (genuinamente nueva).** `snarf/memory/semantic.py`: hechos
extraídos de conversaciones/documentos reales (nunca inventados), cada uno con `confidence` y versionado
explícito — reusando `BASIS: hecho|inferencia|hipótesis|estimación|opinión` (`snarf/executive/opinion.py`).

**Pieza C — proactividad (genuinamente nueva).** Extensión del patrón ya vigente de digests programados
(`morning_routine`, `dashboard_curator`, ADR 0129/0090): un Specialist programado/disparado por evento
que consulta Piezas A+B y produce sugerencias reales, siempre citando de dónde sale cada una.

**El lazo de auto-evolución** ya existe (Skill Factory, ADR 0101/0102). Lo que faltaba era la fuente de
ideas — la Pieza C es exactamente eso: cuando detecta un patrón real que ameritaría una capacidad nueva,
la propuesta pasa por Skill Factory como cualquier otra, mismo camino auditado.

**Multi-usuario:** las tres piezas se particionan por `user_id` desde el diseño inicial.

---

## Qué NO construir todavía (y por qué)

- **Kafka/RabbitMQ/NATS**: sobre-ingeniería real a esta escala; Redis Streams ya da replay + consumer groups con una fracción del overhead, y es gratis.
- **Grafana/Prometheus/OpenTelemetry**: ver Fase 8 — se evalúan cuando el VPS multiplique procesos de verdad, no antes.
- **Reescribir `brain.py`/`verbs.py`/`detail.py` desde cero**: la Fase 9 los evoluciona, no los reemplaza.
- **n8n como segundo orquestador o dueño de lógica de negocio**: viola el principio explícito del prompt de misión y el ADR 0093 ya vigente para MCP — n8n propone, Snarf ejecuta siempre por su propio camino auditado.
- **Cualquier dependencia de pago por default** (Redis gestionado, n8n Cloud, Langfuse Cloud): la versión self-hosted es la entrada en este plan; pasar a pago es una decisión explícita futura, nunca un default.

---

## Verificación

- Cada fase real (no un fix trivial) cierra con una entrada de ADR + CHANGELOG con conteo de tests, por convención de este repo (CLAUDE.md).
- Fase 3: antes de anunciar usuarios de prueba reales, confirmar con un segundo usuario real (no simulado) que cada dato queda particionado por `user_id` sin fugas — y confirmar el estado de verificación de OAuth de Google antes de superar el founder + círculo cercano.
- Fase 9.1: cualquier acción de control de infraestructura se prueba primero contra los servers de test (8000/8001), nunca contra 8002 en el primer intento.

Este documento cubre la arquitectura completa y el roadmap de las 12 fases + el track de memoria semántica.
