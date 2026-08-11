# CHANGELOG

Registro de cambios relevantes del proyecto Snarf. Los cambios de gobernanza o arquitectura que requieren justificación quedan además documentados como ADR en `adr/`.

## [2026-08-10] Fase 4: n8n self-hosted + primera integración real, observa y propone (ADR 0139)

- `docker-compose.n8n.yml` (nuevo): n8n Community Edition real, self-hosted vía Colima/Docker, solo
  `127.0.0.1` (nunca expuesto públicamente) — corriendo, verificado con Playwright y `docker stats`
  (~530MB en reposo).
- `snarf/telemetry/n8n_webhook_sink.py` (nuevo): Snarf → n8n, un subscriber más del dispatcher de Fase
  1, opcional (`N8N_WEBHOOK_URL`), nunca una dependencia dura — verificado de punta a punta contra un
  servidor HTTP real (no un mock).
- `GET /n8n/status` (nuevo, `app.py`) + `require_n8n_token` (`snarf/runtime/web_auth.py`): n8n → Snarf,
  autenticado por un token propio (`N8N_CONTROL_TOKEN`, header `X-Snarf-Token`) — nunca la cookie de
  sesión del founder. De solo lectura, reusa `ops_system_health`/`ops_process_status` (ADR 0138) tal
  cual.
- No se creó ninguna cuenta de n8n en nombre del fundador — completó él mismo el "Set up owner
  account" y el primer workflow con nodo Webhook. Gotcha real encontrado en la verificación en vivo:
  el nodo Webhook nace en GET por default, `n8n_webhook_sink.py` manda POST — 404 hasta corregir el
  método del nodo (ver ADR 0139). Cerrado de punta a punta en producción real: `POST` contra la
  Production URL activada devuelve `200 {"message":"Workflow was started"}`. El caso de uso "n8n edita
  un agente existente" del plan aprobado sigue bloqueado por las Fases 5/6 (introspección real, Prompt
  Registry), todavía no construidas.

## [2026-08-10] Nombres reales de proceso + primera pieza del cockpit de infraestructura (ADR 0138)

- **Diagnóstico real primero**: los "22.71GB de RAM" que preocupaban no eran de Snarf — los procesos
  reales de Snarf sumaban ~350MB combinados en el momento del diagnóstico (Chrome/VS Code/Spotify
  eran el uso real). De paso, confirmado que `mlx-heavy`/`mlx-mid` no estaban cargados (solo
  `mlx-fast`), corrigiendo una asunción de rondas anteriores.
- Los procesos de Snarf ahora tienen nombre real reconocible en Activity Monitor/`ps`/`top`
  (`snarf-server`, `snarf-mlx-fast`, `snarf-kokoro-tts`, `snarf-server-logs`) en vez de "Python"
  genérico — `exec -a` desde el shell del LaunchAgent se probó primero y no sobrevivía al arranque de
  este build de Python (evidencia real); `setproctitle` llamado desde adentro del proceso sí. Los tres
  LaunchAgents afectados se recargaron en vivo, cero downtime real más allá de un restart normal, cero
  cambios en `data/`.
- Primera pieza real del cockpit de infraestructura del fundador (adelanto de Fase 9.1 del plan de
  multi-usuario): dos tools nuevas solo para el fundador — `ops_process_status` (estado real de cada
  LaunchAgent de Snarf) y `ops_process_restart` (reinicio real con confirmación en dos pasos, nunca
  del server principal — se mataría a sí mismo a mitad de camino). Vive en el chat, no en una vista de
  dashboard nueva todavía.

## [2026-08-10] Fase 3 del plan de multi-usuario: Orchestrator real por user_id + login con Google (ADR 0137)

- **Hallazgo real de auditoría, antes de tocar nada**: pese a tener credenciales de Google y
  preferencias ya separadas por `user_id` desde ADR 0021, Snarf era single-user de punta a punta —
  `app.py` corría un único `Orchestrator` global sin importar quién estuviera logueado, y
  `EpisodicMemory()` ni siquiera usaba el `user_id` que recibía. Dos cuentas reales habrían compartido
  la misma memoria de conversación, las mismas credenciales de Google, los mismos proyectos.
- `app.py` pasa a mantener un registro real de `Orchestrator` por `user_id` (`get_orchestrator`, lazy +
  cacheado) — cada una de las ~30 rutas HTTP que ya recibían `user_id` de la sesión ahora opera sobre
  la instancia real de quien hizo la request, no siempre la del fundador. `EpisodicMemory` gana rutas
  propias por usuario (`data/users/<user_id>/...`); el fundador conserva sus rutas globales de
  siempre, sin ninguna migración.
- Login real con Google (`snarf/capabilities/google_auth.py`, `snarf/runtime/google_identity.py`,
  rutas nuevas en `app.py`): reemplaza `InstalledAppFlow.run_local_server()` (abría un navegador+server
  local EN LA MÁQUINA de Snarf, estructuralmente imposible para un usuario remoto) por el flujo web
  real de OAuth con redirect+callback y protección CSRF real. Conectar Google ahora ES el login para
  cualquiera que no sea el fundador — un usuario nuevo sale del mismo consentimiento con su cuenta
  identificada Y su Drive/Gmail/Calendar/YouTube ya conectados. Botón real en `web/login.html`,
  verificado con Playwright hasta la pantalla real de Google.
- Bug de seguridad real encontrado y corregido por un test propio antes de mergear: el primer intento
  de derivar `user_id` desde un email dejaba pasar `.` como carácter seguro, permitiendo reconstruir un
  path traversal real (`user_id` se usa como segmento de path de disco). Corregido antes de que
  existiera ningún riesgo en producción.
- **Gaps honestos, documentados en ADR 0137 y no resueltos en esta fase**: el dashboard/HUD sigue leyendo
  telemetría global sin particionar por usuario (no debería exponerse a usuarios de prueba todavía);
  Notion sigue siendo una integración global, sin conexión per-usuario; el redirect URI de producción y
  la verificación de la app OAuth ante Google (límite de 100 testers en modo Testing) requieren acción
  manual real del fundador en Google Cloud Console.

## [2026-08-10] Fase 2 de observabilidad: transporte opcional Redis Streams + push real vía SSE (ADR 0136)

- `GET /events/stream` (nuevo, `app.py`): el HUD deja de depender de re-pollear
  `/dashboard/telemetry_feed` — push real vía Server-Sent Events, con cursor real
  (`Last-Event-ID`/`?last_event_id=`) para reconectar sin perder eventos. Funciona con o sin Redis
  configurado: sin Redis lee de un buffer in-process nuevo (`snarf/telemetry/event_buffer.py`), con
  Redis lee del stream real (`XREAD BLOCK`, persistente).
- `snarf/telemetry/redis_sink.py` (nuevo): sink opcional hacia Redis Streams — **nunca una dependencia
  dura**, verificado en vivo apuntando a un puerto real sin servidor escuchando: el fallo se traga, se
  cuenta, y un turno real jamás se entera. `SNARF_REDIS_URL` sin setear (default) ni siquiera importa
  el paquete `redis`.
- `snarf/runtime/ops_health.py` suma estado real del dispatcher/Redis a `ops_system_health`.
- `requirements.txt` suma `redis==8.1.0` (nunca se activa sin `SNARF_REDIS_URL` seteada). El servidor
  Redis en sí no se instaló en esta ronda a propósito — per el plan aprobado con el fundador, eso se
  hace recién cuando n8n o un Control Center empiecen a leer de verdad (fases siguientes).

## [2026-08-10] Fase 1 de observabilidad: modelo de evento v2 correlacionado + dispatcher in-process (ADR 0135)

- Primer paso de un plan de evolución de 12 fases (auditoría completa del repo real + los tres
  documentos que trajo el fundador — observabilidad, multi-usuario, n8n, memoria semántica, cockpit
  del fundador estilo Jarvis). Esta fase es la base de correlación que todas las demás necesitan.
- `snarf/telemetry/events.py`: el evento unificado suma `event_id`/`parent_event_id`/`trace_id`/
  `event_type` (ciclo de vida completo: `.started`/`.finished`/`.failed` para turno/tool/llm/rol
  ejecutivo, no solo el resultado final), `origin_pid`, `user_id`. Aditivo — los 14 campos v1 no
  cambian, y un allowlist positivo (`LEGACY_EVENT_TYPES`) mantiene invisibles los tipos nuevos para
  todo consumidor existente (dashboards, historial de costos, feed del dock) sin tocarlos.
- `snarf/telemetry/context.py`: `threading.local()` → `contextvars.ContextVar` (FastAPI copia
  contextvars al pasar a un worker de threadpool, pero no `threading.local()`). De paso corrige un bug
  real: una llamada LLM de Specialist anidada dentro de un turno le borraba el `llm_role` al resto del
  turno en vez de restaurarlo al salir.
- `snarf/telemetry/spans.py` + `dispatcher.py` (nuevos): dos chokepoints reales instrumentados
  (`Orchestrator._handle_tool`, y `_create_and_record`/`_complete_once`/`generate` en los tres
  proveedores LLM) más el borde de turno y la Inteligencia Ejecutiva — correlación real de punta a
  punta, incluso a través del límite de proceso del subproceso MCP de cada rol ejecutivo. Dispatcher
  pub/sub in-process, sin infraestructura nueva todavía (base para Redis Streams opcional en la Fase 2).
- Bug real corregido en el mismo cambio: el fan-out de la Inteligencia Ejecutiva (`ThreadPoolExecutor`)
  reusaba un único `contextvars.Context` copiado entre los 7 roles — revienta si dos roles arrancan
  casi al mismo tiempo ("cannot enter context: already entered"); cada rol necesita su propia copia.

## [2026-08-08] Rediseño de chat: boot robusto, sidebar/proyectos/foco, cerebro de "pensando", feed legible, id de mensaje real y responder-a-mensaje (ADR 0134)

- Dos bugs reales reportados en vivo: el cerebro del arranque dependía enteramente de JS ejecutando
  sin errores (nunca aparecía si algo fallaba antes, sobre todo en mobile) — ahora hay un placeholder
  ghost estático embebido en el HTML crudo, visible desde el primer paint, más `textInput` con
  `disabled` también estático. Y clickear una conversación del historial a veces no cargaba nada — un
  doble render (cache + revalidación de red) podía destruir el ítem que el usuario estaba tocando a
  mitad de un click; ahora no se reconstruye la lista si los datos no cambiaron.
- Barra lateral de Proyectos: header fijo con "PROYECTOS" en el listado general, o "← todos los
  proyectos" → nombre del proyecto → "+ nueva conversación" al entrar a uno (antes no había ningún
  título). El título del chat ahora refleja el proyecto cuando no hay conversación abierta. Botón de
  modo foco sin el fondo claro nativo del navegador; su título ya no queda tapado por la barra lateral
  acoplada; el panel es más grande (1440px) y las burbujas ocupan todo el ancho real disponible.
- Burbuja de "pensando": sin los tres puntitos — el cerebro mini-animado (68px, antes 30px) ocupa el
  globo, clickeable para ver el cerebro completo mientras trabaja; el botón "■ frenar" queda como
  contraparte a la derecha. De paso, corregido un nodo real (`specialist_morning_routine`) que faltaba
  en 6 listas del frontend y nunca se dibujaba pese a tener actividad real registrada en el backend.
- Feed del cerebro: banner en vivo con el tiempo real transcurrido del pedido activo (`Date.now()` del
  navegador — nunca un "% completado" inventado, el backend no tiene ese concepto) y la fila más
  reciente resaltada, para ver de un vistazo qué proceso está activo ahora.
- Consolidación de audio: una sola versión (antes "escuchar"/"escuchar completo"/"escuchar entregable"
  convivían sobre el mismo mecanismo de `POST /tts`, solo cambiaba qué texto se sintetizaba) — ahora
  siempre lee la respuesta completa. Botones de escuchar/copiar/responder pasan a ser solo ícono.
- Id real y persistente por turno (`EpisodicMemory.append(id=...)`, reusa el mismo `request_id` que ya
  generaba el frontend para la cancelación, ver ADR 0132) — base de la función nueva "responder a un
  mensaje": cita el texto real de una respuesta anterior de Snarf (resuelto contra la memoria, nunca
  lo que el frontend diga), inyectada solo en el turno actual que ve el LLM, nunca en lo persistido.
- 12 tests nuevos (`test_episodic_memory.py`, `test_orchestrator.py`, `test_app.py`). 1094/1094 tests.
  Verificado con Playwright contra una instancia de prueba en el puerto 8000 (nunca el LaunchAgent de
  producción): los 5 flujos completos, cero errores de consola. Ver ADR 0134.

## [2026-08-08] Skill Factory: fix de falsos abortos en construcciones válidas (ADR 0133)

- Tres intentos reales de construir la skill `drive_incremental_indexer` (rama `knowledge`)
  terminaron en `status='failed'`. Dos fueron por falta de crédito de la API de Anthropic (ya
  cubierto por ADR 0131); el tercero reveló dos bugs reales del propio Skill Framework —
  `diff_files` del manifest confirma que el motor **nunca tocó** ningún archivo fuera de alcance.
- Bug A: el motor no tenía ninguna forma sancionada de corregir un error de sintaxis en el módulo
  del Specialist que él mismo acababa de escribir (`write_file` decía "nunca para un archivo que ya
  existe"; `edit_file` está restringido a los 4 archivos de wiring) — se autobloqueaba y abandonaba
  con `NO PUDE` aunque el gateo real ya permitía reescribir su propio path. Redacción de
  `write_file`/`SYSTEM_PROMPT` corregida en `local_code_writer.py`: ahora puede reescribirse el
  mismo path las veces que haga falta.
- Bug B, más serio: `_default_git_dirty_files()` corría `git status --porcelain` sin
  `--untracked-files=all` — git colapsa un directorio NUEVO entero (la primera skill de una rama que
  todavía no existía, como `knowledge/`) en una sola línea, que nunca matchea contra los paths
  exactos de `_expected_files()`. Cualquier build válida que estrenara una rama nueva se habría
  abortado sola con un falso "tocó algo fuera de alcance". Reproducido con un repo git de prueba
  antes del fix.
- `branch`/`skill_name` ahora se validan como snake_case estricto al principio de `build_skill()`,
  antes de tocar git o invocar el motor — cierra un gap real (nunca explotado) donde un
  `skill_name` con `../` podía definir su propio path de escape del repo.
- 7 tests nuevos (`test_skill_factory.py`, `test_local_code_writer.py`). Restos rotos del intento
  fallido eliminados con confirmación del fundador (nunca trackeados en git). 1094/1094 tests. Ver
  ADR 0133.

## [2026-08-07] Pantalla de boot "Jarvis-style", cache SWR del cliente, y cancelación real de un pedido en curso (ADR 0132)

- Pedido real del fundador: no era claro si Snarf ya estaba listo para escribir (el overlay de
  arranque solo esperaba `/status`, no conversaciones/dashboard), cada F5 repetía todos los fetches de
  arranque sin ningún cacheo, y no había forma de frenar un pedido en curso.
- Pantalla de boot: reusa `brainMiniSvgMarkup()` (mismo cerebro del widget de dashboard/indicador de
  "pensando") en estado "ghost" honesto hasta tener datos reales; recién oculta el overlay y rehabilita
  el input cuando conversaciones/proyectos (y dashboard, en desktop) terminaron de cargar, con timeout
  de 15s como red de seguridad.
- Cache cliente stale-while-revalidate (`localStorage`, `freshMs` por tipo de dato) para conversaciones,
  proyectos, preferencias/resumen del dashboard, y widgets — un reload dentro de la ventana fresca no
  repite el pedido de red.
- Cancelación real de un pedido en curso (no solo visual — decisión confirmada explícitamente con el
  fundador): botón "■ frenar" en la burbuja de "pensando", `AbortController` del lado del navegador +
  `POST /cancel/{request_id}` nuevo que corta el streaming de Anthropic a mitad de camino (ahorra los
  tokens de output que faltaban generar). Reusa el panel de revisión ya existente (voz transcripta)
  para editar y reenviar o cancelar. La respuesta cancelada queda en el historial, marcada, nunca
  desaparece.
- 18 tests nuevos (`test_cancellation.py`, `test_context.py`, `test_anthropic_llm.py`,
  `test_orchestrator.py`, `test_app.py` — incluida una carrera real con `threading.Thread`, no
  simulada). 1076/1076 tests. Verificado con Playwright contra una instancia de prueba en el puerto
  8000 (nunca el LaunchAgent de producción): input deshabilitado durante el boot, cero requests
  redundantes en un reload inmediato, y el flujo completo de frenar/editar/marcar-cancelado sin
  errores de consola. Ver ADR 0132.

## [2026-08-06] El modelo local como motor suficiente para correr Snarf (ADR 0131)

- Pedido real del fundador sin crédito en xAI/Anthropic: encontrado en vivo (mismo día) un crash real
  de Metal (out-of-memory) recurrente en el server MLX local — mismo bug de ADR 0128, esta vez con un
  prompt de 82.284 tokens, origen exacto sin identificar. 11 de 25 roles estaban atascados a mano en
  xAI (sin crédito); 2 de los 3 servers MLX corrían 24/7 sin que ningún rol los usara.
- Ruteo reseteado a los defaults locales (`llm_routing.save_routing({})`); `mlx-heavy`/`mlx-mid`
  apagados (`bootout`+`disable`, reversibles); modelo de `groq_llama` corregido (`llama-4-scout` ya no
  existe en la API real, reemplazado por `llama-3.3-70b-versatile`, precio real verificado).
- Tope universal de tamaño de prompt para proveedores locales
  (`openai_compatible_llm.MAX_LOCAL_PROMPT_CHARS`, re-chequeado en cada ronda del loop de
  herramientas, no solo al inicio) — a diferencia del tope de ADR 0128 (acotado a un solo rol), este
  corre para cualquier rol local.
- Campo nuevo `llm_role` en `telemetry_events.jsonl` (mismo patrón que `conversation_id`) — para poder
  diagnosticar el próximo incidente así sin quedarse a ciegas como esta vez.
- 1058/1058 tests — corridos en 10.13s, contra 247s antes de apagar los servers sin uso en esta misma
  sesión: evidencia real de que la contención de recursos era real. Ver ADR 0131.

## [2026-08-06] Skill Factory: motor de escritura local, en vez del CLI de Claude Code (ADR 0130)

- Pedido real del fundador tras quedarse sin crédito de la API de Anthropic en un intento real de
  construir una skill. Investigado en vivo antes de tocar código: el CLI de Claude Code no tiene
  ninguna forma soportada de apuntar a un modelo no-Claude (`--model` solo acepta Claude real;
  Bedrock/Vertex/Foundry siguen siendo Claude, solo cambia la nube) — "hacer que Claude Code use el
  modelo local" no era una opción real, así que se reemplazó el motor entero.
- `snarf/capabilities/local_code_writer.py::LocalCodeWriter` reemplaza a `ClaudeCode` (eliminado):
  mismo shape de resultado, pero con un loop de herramientas angosto (`read_file`/`write_file`
  restringido a archivos nuevos/`edit_file` restringido a los 4 de wiring con reemplazo exacto de
  string, nunca reescritura ciega/`run_tests`) en vez de una sesión agéntica de propósito general —
  el alcance que antes solo se verificaba después por diff de git ahora también se gatea en el
  momento. La doble verificación real de `SkillFactorySpecialist.build_skill()` (diff + suite
  completa) sigue exactamente igual, independiente de qué motor escribió el código.
- `generate()` de las 3 Capacidades de LLM ahora acepta `max_tool_rounds` opcional (default sin
  cambios) — una construcción de skill en background ya no comparte el presupuesto de 5 rondas
  pensado para la latencia del chat interactivo.
- Rol nuevo `skill_factory_writer` en `llm_routing`, default local — configurable desde Configuración
  como cualquier otro rol si la calidad no alcanza.
- 1045/1045 tests. Ver ADR 0130.

## [2026-08-06] `morning_routine`: Especialista nuevo para la rutina del día (ADR 0129)

- **Causa raíz real, no solo el síntoma**: revisando la conversación real de esta misma jornada, el
  Orchestrator (modelo local de 4B) identificó bien un correo urgente por su snippet pero nunca leyó
  su cuerpo; al pedírselo después, inventó un `message_id` falso y una tool inexistente, agotó las
  rondas de tool-calling del turno y terminó diciendo que no podía acceder al correo. El fix de tool
  descriptions de esta misma jornada corrige el caso puntual — esta entrega ataca la causa
  estructural: dejar de depender de que un modelo chico encadene bien varias tool calls en el orden
  correcto para "qué tenemos hoy".
- `MorningRoutineSpecialist` (`snarf/specialists/productivity/morning_routine.py`) resuelve en Python
  determinístico qué correo leer y cuándo: clasifica por snippet (una llamada LLM acotada), valida
  cualquier id que el modelo marque como prioritario contra el listado REAL de Gmail (un id inventado
  se descarta en silencio, nunca llega a leerse), lee el cuerpo real de hasta 5 prioritarios, y
  sintetiza una versión final con el detalle real ya adentro (segunda llamada LLM acotada). Tool
  nuevo `morning_routine`; `gmail_summarize_inbox`/`calendar_brief` siguen para un pedido acotado a
  solo correo o solo agenda. Deliberadamente fuera del allowlist MCP (mismo motivo que
  `gmail_read_message`: devuelve contenido crudo personal).
- 1034/1034 tests. Ver ADR 0129.

## [2026-08-06] Switch Vista clásica/HUD movido a #topChrome, y fix de un fallback a Grok que quedó pegado

- El switch Vista clásica/HUD (antes una fila de texto solo visible parada en el home del dashboard) se
  movió al centro de `#topChrome` como dos botones de solo ícono (grilla = clásica, mismo glyph que
  `#dashBtn`; anillos concéntricos = HUD, ecoando el orbe/anillos ya usados en el resto de la app) — encaja
  en el alcance ya definido para esa barra (gestión general de la app, ADR 0123) y ahora es un control
  global disponible desde cualquier pantalla, no solo desde el home. Libera esa fila de espacio real
  arriba del dashboard (la Vista HUD ya no reserva un hueco fijo para ella). Verificado en vivo con
  Playwright contra el server real: el switch aparece/cambia correctamente, cero errores de consola.
- **Bug real encontrado y corregido**: el `orchestrator` (el rol que atiende el chat) estaba pegado en
  Grok desde un timeout de ayer 18:45 — de ANTES de que el mecanismo de cooldown/revert automático (ADR
  0121, esta misma ronda) se desplegara. Esa entrada vieja nunca recibió el marcador
  `fallback_expires_at`, así que el código de revert (correcto) la trataba como una elección manual del
  fundador y nunca la tocaba. Backfill puntual del marcador (dato, no código) — confirmado en vivo: el
  siguiente mensaje real volvió a usar el modelo local.

## [2026-08-06] Fix real de fuga de memoria del server MLX local (31GB) + tope duro de cuota (ADR 0128)

- **Causa real encontrada** (reporte del fundador: "el modelo local no se usa, todo cae a Grok", proceso
  Python real con 31GB de RAM en una Mac de 32GB): una entrada extrema del historial (volcado completo de
  un resultado de herramienta gigante) se mandó entera, sin ningún tope, al rol `history_compaction`
  (modelo local de 4B) — 20.804 tokens en un solo prompt, tumbó el server MLX real por out-of-memory de
  Metal, y la limpieza posterior también falló, dejando esa memoria fugada para siempre mientras el
  proceso siguiera vivo (0% CPU, cada request real caía a Grok desde entonces).
- Tope nuevo en `Orchestrator._summarize_history_entry()`: por encima de 32.000 caracteres, corte duro
  directo — nunca se le manda al modelo local algo tan grande como para arriesgar tumbarlo.
- **Bug real confirmado en `mlx_lm` 0.31.3**: `--prompt-cache-bytes` nunca llega al constructor real de su
  caché LRU — el límite de bytes que veníamos usando desde ADR 0120 era casi un no-op. `--prompt-cache-size`
  (tope de cantidad de secuencias) sí se respeta de verdad — bajado a 3 en los 3 LaunchAgents MLX.
- **Watchdog nuevo** (`snarf/runtime/mlx_memory_watchdog.py`, `com.snarf.mlx-watchdog.plist`, cada 90s):
  reinicia cualquier server MLX real que supere el 25% de la RAM total de la Mac — la garantía dura pedida
  por el fundador, independiente de cualquier causa futura no prevista.

## [2026-08-06] Indexado y búsqueda semántica del historial de conversaciones (ADR 0127)

- Dominio nuevo `conversations` para la Knowledge Layer, mismo motor genérico que `code` (ADR 0096):
  `EpisodicConversationSource` + `KnowledgeIndexer` + `VectorStore` propio, reindexado incremental
  automático vía `last_activity`. Tool nueva del Orchestrator: `conversations_search(query,
  project_id=None, top_k=5)`.
- **Bug real encontrado con un smoke test contra las 180 conversaciones reales de producción** (invisible
  para los tests unitarios, que usan un vector store fake): chromadb rechaza `None` como valor de
  metadata — `project_id: None` en conversaciones sin proyecto asignado tiraba `TypeError` al indexar.
  Fix: se omite la clave entera en vez de guardar `None`.

## [2026-08-06] HUD: clickeabilidad real del dock de chat (ADR 0126)

- Bug real encontrado con Playwright: el efecto de profundidad 3D real (`perspective`+`translateZ`) del
  chat en HUD rompía el hit-testing de mensajes que no fueran el más nuevo — un click en "▾
  transcripción" de cualquier mensaje viejo no hacía nada. Simplificado a 2D puro (`scale`+`opacity`+
  `filter`), mismo efecto visual, sin el desajuste.
- El dock entero bloqueaba clicks al grafo de nodos HUD detrás en cualquier zona vacía (sin contenido).
  `pointer-events: none` en los contenedores estructurales, reactivado solo donde hace falta — Vista
  Clásica/modo Foco sin cambios.

## [2026-08-06] Títulos legibles del feed del cerebro + detalle real al click (ADR 0125)

- El feed (Vista HUD y panel Cerebro clásico) dejó de mostrar el string crudo `"openai:mlx-comunity/
  qwen...."` para eventos de LLM — ahora muestra el nombre de modelo solo, sin el vendor (que además
  mentía para roles locales) ni el prefijo de organización de HuggingFace.
- Click en cualquier fila del feed abre el panel de detalle por nodo ya existente, ahora con una línea
  de timing real (modelo/tokens/latencia/costo) — se agregó medición real de `latencia_ms` de punta a
  punta (antes el campo existía en el schema pero nunca se llenaba para llamadas de LLM).

## [2026-08-05/06] Timestamps opcionales en el chat, y fix real de `PUT /dashboard/preferences` (ADR 0124)

- Toggle nuevo en Configuración → Chat: separadores de fecha (Hoy/Ayer/fecha) + hora dimeada por
  burbuja, apagado por default.
- **Bug real encontrado y corregido en el mismo endpoint que ya había mostrado el mismo patrón en
  `/llm-routing` esta ronda**: `PUT /dashboard/preferences` no mergeaba con lo ya guardado — un PUT
  parcial de prueba pisó en silencio customización real del fundador (tamaños de widgets, un nodo HUD
  fijado a mano). Restaurado byte a byte desde el backup automático más reciente; endpoint corregido
  (`exclude_unset=True` + merge) para que esto no pueda volver a pasar.
- El server de producción venía corriendo desde antes de todos los cambios de esta sesión — reiniciado
  al cierre de esta ronda para desplegar Fases 0, 1, 2 y 4 realmente (confirmado con tráfico real
  post-restart).

## [2026-08-05] Barra superior de gestión general (#topChrome) y título de conversación por modo (ADR 0123)

- Barra nueva, oculta hasta hacer hover arriba de la ventana: estado de sistemas + modelo de LLM
  vigente a la derecha; en Clásica desktop, el avatar del fundador se reubica ahí reemplazando la
  hamburguesa (mobile/HUD conservan la suya). Nunca muestra nombre de conversación/proyecto — eso vive
  en el header propio de cada modo (`.dash-widget-head h3` en Clásica, `#chatDockToolbar` reactivado en
  HUD, header nuevo en Foco), sincronizados por `updateChatTitleDisplays()`.
- `#modeFab`/`#modePopover` (selector de modo de entrada en mobile) retirados — confirmado sin uso.
- Verificado en vivo con Playwright contra producción (sin tocar datos reales): título coherente al
  cambiar de HUD a Clásica a Foco, avatar/popover funcionando, mobile intacto, cero errores de consola.

## [2026-08-05] Fix real de hermeticidad: la suite completa disparaba llamadas reales al LLM local de producción

- Encontrado en vivo verificando ADR 0121 (la suite completa, que normalmente corre en segundos, tardó
  40 minutos): antes del routing default a `mlx_local_fast` (sin credencial, siempre "available"),
  decenas de tests en `tests/test_app.py` y `tests/test_orchestrator.py` nunca mockearon el LLM a
  propósito porque el proveedor viejo exigía una credencial real que `conftest.py` ya stripea —
  `.available` daba `False` sola y todo degradaba en modo eco sin llamar a nada. Con el default actual,
  esos mismos tests sin mockear disparan llamadas REALES contra el server local DE PRODUCCIÓN —
  confirmado con `lsof`/`sample`: el proceso de pytest bloqueado en `sock_recv` sobre una conexión TCP
  real a `127.0.0.1:8991`, justo cuando coincide con tráfico real del fundador en el mismo server.
  Exactamente el riesgo que ADR 0119 había señalado ("audit de tests que no mockean `_llm`") sin
  completar nunca.
- Fix sistémico en dos fixtures: el `client` de `test_app.py` ahora neutraliza
  `llm_routing.build_resilient_llm` por default (`_UnavailableLLM`, `.available = False`); el
  `orchestrator` de `test_orchestrator.py` ahora neutraliza `_llm`/`_title_llm._client` a `None` por
  default. Ambos restauran el comportamiento original ("LLM no configurado, degradar") para cualquier
  test que no mockee algo puntual — los que sí necesitan una respuesta real siguen mockeando por encima,
  sin cambios de comportamiento para ellos.
- `test_refresh_project_summary_endpoint` además gana su propio mock explícito (necesita una respuesta
  real de prueba, no solo "no disponible").
- Resultado real: `test_orchestrator.py` pasó de 97s (ya lento, pegándole de verdad al server pero sin
  colgarse) a 2.94s; la suite completa dejó de colgarse contra tráfico de producción real.

## [2026-08-05] Paginación de conversaciones desde el más reciente, botón "ir al final" (ADR 0122)

- `GET /conversations/{id}` ahora pagina (`limit`/`before`, responde `{entries, has_more}`) en vez de
  devolver siempre la conversación entera — el chat carga solo el último tramo y trae los mensajes
  viejos a medida que se scrollea hacia arriba, sin saltos de posición.
- Botón flotante nuevo arriba del micrófono para volver al último mensaje cuando no se está al fondo.

## [2026-08-05] Streaming para el LLM local, timeout más alto, y revert automático del fallback (ADR 0121)

- **`LOCAL_TIMEOUT_SECONDS` pasa a ser un timeout de inactividad, no de duración total**: las llamadas
  locales (`OpenAICompatibleLLM`) ahora usan `stream=True` — confirmado en vivo contra el server real que
  esto hace que httpx corte por falta de bytes ENTRE chunks, no por la generación completa. Una respuesta
  lenta pero que sigue progresando ya no dispara un fallback falso. Subido además de 150s a 240s como red
  de seguridad adicional.
- **Revert automático tras 10 minutos** (`FALLBACK_COOLDOWN_SECONDS`): un rol que cayó a un proveedor
  pago por un timeout puntual ahora vuelve solo al modelo local apenas éste responde de nuevo — antes
  quedaba en el fallback para siempre, sin ninguna señal de que ya podía volver (bug real: "sigue en
  grok" reportado en vivo por el fundador). Nunca toca una elección manual hecha desde Configuración.

## [2026-08-05] 3 plantillas nuevas de widget HUD, a mano, a partir de propuestas reales del curador (ADR 0091)

- Leídas las 19 propuestas vigentes en `data/dashboard_template_proposals.json` (vía `GET
  /dashboard/template_proposals`): varias eran duplicados exactos del mismo pedido nunca resuelto (el
  nodo `cost` repitió "deep_chart" 8 veces — resultó ser una plantilla LARGE que ya existía, pero el
  nodo `cost` rara vez cae en tier LARGE, así que nunca podía usarla) y otras ya estaban cubiertas por
  una plantilla existente (`alert_detail` genérico ya sirve para cualquier nodo, incluido Drive).
- Agregadas 3 plantillas nuevas a `snarf/telemetry/widget_templates.py` (27 en total) por los huecos
  reales que sí quedaban sin cubrir: `breakdown` (medium, desglose por sub-categoría — cubre el pedido
  repetido de "cost"), `process_state` (medium, estado neutral de un proceso activo/pausado/detenido,
  sin implicar error) y `pending_note` (small, nota informativa sin urgencia para datos incompletos).
  Esto sigue siendo Track A de ADR 0091 (el curador solo propone, un humano decide y construye a mano) —
  no una automatización nueva.
- Cola de propuestas vaciada en `data/dashboard_template_proposals.json` para que las próximas entren
  limpias.

## [2026-08-05] Causa real de los crashes de memoria (cache sin límite de mlx_lm.server), Kokoro TTS nativo con GPU (ADR 0120)

- **Hallazgo real, con `footprint` (la misma herramienta que Activity Monitor):** el problema nunca fue
  el tamaño del modelo — `mlx_lm.server` cachea el contexto de cada conversación sin ningún límite por
  default, y corriendo 24/7 llegó a 18GB de footprint real (el modelo, 4-bit, pesa ~2.5GB). Confirmado:
  tras un reinicio limpio el footprint bajó a 2437MB, calzando con el tamaño real del modelo.
- Fix: `--prompt-cache-bytes 4294967296` (4GB) agregado a los 3 LaunchAgents de MLX
  (fast/mid/heavy) — el cache sigue funcionando (beneficio real de latencia), pero ya no puede crecer
  sin límite. El fallback a `xai` que el fundador vio "sin avisar" fue exactamente el crash de Metal ya
  documentado, con este fix aplicado no debería repetirse por esta causa.
- **Kokoro TTS migrado de Docker/Colima a proceso nativo en la Mac**, con aceleración real de GPU
  (MPS) — Colima reservaba 8GiB de VM para correr Kokoro 100% CPU (sin acceso a Metal); el modo nativo
  del propio proyecto (`Kokoro-FastAPI`, clonado fuera del repo) corre con el mismo `base_url` de
  siempre (`localhost:8880`), cero cambios de código. LaunchAgent nuevo (`com.snarf.kokoro-tts`),
  verificado con audio real (`ffprobe`) y flujo end-to-end real vía `/tts` de producción. Colima
  detenido por completo.
- **Docker/Colima no se descarta** — `docker-compose.voice.yml` queda intacto, documentado ahora como
  la especificación real para cuando se despliegue al VPS (Parte 4, sigue pendiente): un VPS típico no
  tiene GPU de Apple, así que Docker CPU-only sigue siendo la elección correcta ahí. Local = nativo con
  MPS; VPS = Docker — dos entornos reales, no una elección de "cuál es mejor".

## [2026-08-05] Desplegable de "pensamiento" del modelo, overlay de reconexión honesto, y otro crash real del modelo rápido

- `LLMResponse` suma un campo `thinking: str | None` — capturado desde el campo `reasoning` que
  devuelven algunos modelos locales "thinking" (ej. Qwen3.5) vía `mlx_lm.server`, fuera del schema
  estándar de OpenAI (`OpenAICompatibleLLM.generate()`, con `getattr` porque la mayoría de
  proveedores/modelos no lo exponen). `split_speech()` lo adjunta tal cual, sin parsearlo (no viaja
  mezclado en el texto). Nunca se persiste a memoria episódica — es transparencia de esa respuesta
  puntual, no parte del historial.
- UI: desplegable "▾ pensamiento" en la burbuja de chat, oculto por default — mismo patrón visual que
  la transcripción de una nota de voz. Verificado con Playwright (server real, `/send` interceptado
  para simular un `thinking` de prueba): oculto por default, visible al click, sin errores de consola.
- **Otro crash real, mismo patrón que el del modelo intermedio (ver entrada anterior):** el modelo
  rápido (`Qwen3-4B`, hasta ahora "estable") también crasheó con un error real de Metal
  (`ValueError: Slice indices must be 32-bit integers` seguido de
  `kIOGPUCommandBufferCallbackErrorOutOfMemory`) bajo uso normal prolongado de la Mac (Chrome + VS Code
  + el resto). El server principal quedó colgado esperando esa respuesta muerta — mismo bloqueo
  sincrónico documentado antes. Recuperado con un `bootout`/`pkill`/`bootstrap` limpio del proceso
  huérfano que había quedado reteniendo el puerto 8002 tras varios reinicios encadenados.
- UI: el flujo de `/send` que antes decía "no se pudo enviar" ante cualquier fallo de red ahora es
  honesto sobre la ambigüedad real — un fallo de conexión no prueba que el mensaje nunca llegó al
  server, solo que se perdió la respuesta de vuelta. Ahora muestra el overlay de reconexión
  ("se perdió la conexión... revisando si tu mensaje llegó a procesarse") y, apenas el server vuelve a
  responder, recarga la conversación real (`GET /conversations/:id`) en vez de asumir que hay que
  reenviar — si el mensaje sí se había procesado, la respuesta aparece sola; si no, el botón
  "reintentar" sigue disponible.
- Investigado y decidido no migrar: Kokoro TTS corre en Docker/Colima (8GiB de VM reservados, 1.7GiB
  reales del contenedor) en vez de nativo en la Mac (como el LLM local) — confirmado que es una
  decisión deliberada y documentada (`docker-compose.voice.yml`) para garantizar portabilidad futura a
  un VPS, no un descuido. No se revierte hoy: la crisis de memoria que la motivó ya se resolvió con el
  fix del LLM, y cambiar esto ahora cambiaría una garantía de arquitectura real a mitad de una sesión
  ya larga.

## [2026-08-05] Modelo rápido local como default en todos los roles, modelo intermedio instalado, indicador de conexión (ADR 0119)

- Pedido explícito del fundador tras probar el rol rápido a mano en el orquestador ("está funcionando
  muy bien en la práctica"): `mlx_local_fast` (Qwen3-4B) pasa a ser el default de **23 de 24 roles**
  reales, incluido `orchestrator` — revierte la decisión de ADR 0118 de dejarlo en `xai`. Única
  excepción real: `drive_vision` se queda en `claude-haiku-4-5` porque necesita soporte real de
  imágenes y el modelo rápido es texto-solo.
- Nuevo modelo intermedio instalado para comparar: `Qwen3.5-9B-MLX-4bit` (preset `mlx_local_mid`,
  puerto 8992) — generación más nueva que el Qwen3-8B ya instalado, tamaño en disco casi idéntico.
  FODA completo de candidatos en el ADR. Tool-calling confirmado funcionando.
- **Hallazgo real durante la comparación:** correr dos servers MLX generando al mismo tiempo (rápido +
  intermedio) crasheó el server rápido con un error real de Metal
  (`Insufficient Memory kIOGPUCommandBufferCallbackErrorOutOfMemory`) — memoria libre medida en el
  momento del crash: 0.06GB. El modelo intermedio queda instalado pero **apagado** (no arranca solo)
  hasta que se decida usarlo, para no competir por memoria con el rápido en uso normal.
- Bug real encontrado y arreglado: 4 tests de `test_orchestrator.py` asumían "sin credencial de pago
  configurada → LLM no disponible" — dejó de ser cierto con el nuevo default (`mlx_local_fast` no
  exige credencial), así que esos tests terminaban pegándole de verdad al server local real en vez de
  ejercitar el modo eco/corte duro que decían probar. Arreglados ruteando esos 4 casos a mano a un
  proveedor con credencial (borrada en tests). Suite completa: 952/952 tests.
- UI: overlay "Snarf se está conectando..." — pantalla completa, bloquea toda interacción mientras
  `/status` no responde; cubre arranque en frío y reconexión si el server se reinicia solo con la
  pestaña ya abierta. Verificado con Playwright contra el server real.
- Riesgo señalado, no resuelto hoy: la comparación cuantitativa rápido/intermedio/pesado sigue
  pendiente (no se completó por el tiempo que tomó diagnosticar el crash real); y el mismo patrón de
  tests no-herméticos del punto anterior puede seguir latente en otros tests que no fueron auditados.

## [2026-08-05] Epílogo: modelo intermedio probado en real y descartado, `mlx_local_fast` queda como decisión final

- Prueba real en producción, pedida explícitamente: server reiniciado con `orchestrator` + los 7
  Especialistas del board ejecutivo ruteados al modelo intermedio (`Qwen3.5-9B`), rápido apagado para
  evitar el crash de concurrencia ya documentado.
- Bug real encontrado y arreglado: `PUT /llm-routing` no mergeaba con el archivo ya guardado —
  cambiar UN rol desde Configuración reseteaba en silencio TODOS los demás a los defaults del código.
  `attempt_fallback` ya hacía el merge correcto; el endpoint era la única ruta rota. Test de regresión
  agregado.
- Hallazgo real: con el intermedio activo, una respuesta larga dejaba **todo el servidor sordo**
  (dashboard, `/status`, otra pestaña) hasta terminar de generar — explica el reporte de "el enlace no
  funciona" en medio de la prueba. Se agregó timestamp por línea al log real del server
  (`snarf/runtime/timestamp_lines.py`, pipeado desde el LaunchAgent) para poder medir esto con
  evidencia exacta.
- **Decisión final, con Activity Monitor real mostrando 31GB de RAM usada / 24.8GB de Python:** el
  fundador descartó el modelo intermedio ("todo el sistema crashea y se pone lento") — ni llegó a
  evaluarse su calidad real porque el fallback automático redirigió a `xai` antes. El rápido, en
  cambio, "funcionó bien" en el uso real de toda la sesión. `com.snarf.mlx-mid` queda instalado pero
  apagado; `mlx_local_fast` queda como default final en 23 de 24 roles, verificado en vivo (server
  reiniciado limpio, 17.96GB libres).
- Candidato de reemplazo del propio rápido mencionado pero NO perseguido: `Qwen3.5-4B-MLX-4bit` —
  riesgo real sin verificar de heredar el modo *thinking* por default de su hermano 9B.

## [2026-08-05] Cerebro local MLX: rol rápido en producción real, `orchestrator` se queda en el fallback automático

- Hallazgo real: la lentitud del modelo local no era solo presión de memoria/swap sino, en el caso
  típico, costo de **prefill en frío** — `mlx_lm.server` cachea el prefijo de tokens (system prompt +
  88 tools, ~15.630 tokens, casi idéntico en cada request), así que ese costo (~90-105s) se paga una
  vez por arranque del server. Con el prefijo caliente, la mayoría de las respuestas bajan a 5.5-33.6s
  — pero verificado en vivo contra producción real, la presión de memoria real de esta Mac (swap subió
  de 6.57GB a 10.7GB durante la sesión) todavía produce picos ocasionales (163.6s medido).
- `Qwen3-8B-4bit` reemplaza a `Qwen3-14B-4bit` como modelo pesado default — rinde igual en caliente
  pero usa ~la mitad de memoria residente.
- Nuevo preset `mlx_local_fast` (`Qwen3-4B-Instruct-2507-4bit`, otro puerto) — ganancia real y estable:
  3 roles chicos (`history_compaction`, `conversation_title`, `dashboard_curator`) corriendo en local
  sin costo de tokens, sin la misma variabilidad del modelo pesado.
- Dos LaunchAgents nuevos (`com.snarf.mlx-heavy`, `com.snarf.mlx-fast`), mismo patrón que
  `com.snarf.server`. Comandos de pausa/reanudación documentados en el ADR.
- `orchestrator` se probó en `mlx_local`/Qwen3-8B pero terminó revertido solo, dos veces, por el
  propio mecanismo de fallback automático ante picos que superaron incluso un timeout generoso
  (150s) — se deja en el estado real al que el fallback lo llevó (`xai`) en vez de forzarlo a local
  por tercera vez. El modelo pesado queda construido, probado y seleccionable a mano cuando el
  fundador quiera experimentar.
- Fix real: `openai.OpenAI()` reintentaba 2 veces en silencio ante un timeout — con proveedor local
  eso multiplicaba el timeout real. Ahora `local=True` fuerza `max_retries=0`.
- `LOCAL_TIMEOUT_SECONDS` subido de 90s a 150s — el valor anterior era más corto que el peor caso real
  de prefill en frío medido, y disparaba fallbacks falsos apenas arrancaba el server MLX.
- Modelos sin uso (`Qwen3-14B-4bit`, `Qwen3-30B-A3B-Instruct-2507-4bit`) borrados del cache de
  Hugging Face — libera 25.52GB de disco. 949/949 tests. Ver ADR 0118.

## [2026-08-05] Cerebro local vía MLX: infraestructura lista, `orchestrator` se queda en Anthropic

- Instalado `mlx-lm` nativo (nunca Docker/Colima — sin Metal ahí) y probados dos modelos vía
  `mlx_lm.server`: `Qwen3-30B-A3B-Instruct-2507-4bit` (MoE) crasheó por falta de memoria de GPU contra
  el contexto real de Snarf (88 tools, ~16.000 chars de system prompt); `Qwen3-14B-4bit` (denso) no
  crasheó pero pasó de 38.6s a 991s según la memoria libre real del momento, y 289.8s en una
  verificación end-to-end real contra producción.
- `snarf/runtime/llm_routing.py`: preset `mlx_local` (reusa `OpenAICompatibleLLM`, sin clase nueva) +
  fallback automático ahora también ante errores de **conexión** (no solo status HTTP) — necesario
  porque un proveedor local caído no devuelve ningún status HTTP. `openai_compatible_llm.py`: soporte
  de proveedor sin API key real, y timeout corto (90s, no los 10 minutos default de la SDK) para que
  un modelo local lento dispare el fallback rápido en vez de dejar el chat colgado.
- **`orchestrator` se revierte a `anthropic`/`claude-sonnet-5`** — la memoria real disponible en esta
  Mac durante uso normal no alcanza para sostener el cerebro local a velocidad usable, ni con el
  modelo más chico probado. Infraestructura queda lista y verificada para retomar sin trabajo de cero
  cuando haya más memoria libre disponible de forma sostenida.
- 946/946 tests (varios nuevos). Ver ADR 0117.

## [2026-08-05] Resumen real de historial reemplaza el truncamiento duro por caracteres

- `Orchestrator._capped_for_replay()`: una entrada de historial demasiado larga ahora se condensa con
  un resumen real (rol nuevo `history_compaction`, modelo barato) en vez de cortarse a lo bruto y
  perder contenido en silencio — cacheado en memoria para no re-resumir la misma entrada en cada
  turno. Si el resumen falla, cae al corte duro de siempre (nunca rompe el turno).
- 946/946 tests (3 nuevos). Ver ADR 0116.

## [2026-08-05] Notion: soporte de databases (query, crear registro, actualizar properties)

- Cuatro métodos/tools nuevos (`notion_get_database`/`notion_query_database`/
  `notion_create_database_item`/`notion_update_page_properties`) — hasta ahora la integración de
  Notion (ADR 0075) solo cubría páginas sueltas, sin ningún soporte de databases ni properties
  tipadas. `NOTION_API_KEY` confirmada configurada, a diferencia de ADR 0075.
- 946/946 tests (6 nuevos). Ver ADR 0115.

## [2026-08-05] Fix real: dos bugs de indexado de Drive (el pipeline en sí no estaba roto)

- Investigado a fondo un reporte de "el indexado se perdió": el pipeline real seguía funcionando
  (4658 archivos indexados, corrida real de esta misma madrugada) — dos bugs concretos explicaban por
  qué parecía roto. `drive_index_status` reportaba estado efímero en memoria (0 tras cada reinicio del
  server) en vez del progreso real persistido; `VectorStore.add()` no troceaba al límite de batch de
  chromadb, así que archivos con muchos chunks fallaban siempre.
- 946/946 tests (2 nuevos). Ver ADR 0114.

## [2026-08-05] Fix real: respuestas truncadas y audio incompleto (causa raíz común)

- `MAX_OUTPUT_TOKENS` de Anthropic (y proveedores compatibles) subido de 4096 a 16000, con streaming
  obligatorio arriba de ese tope y hasta 2 continuaciones automáticas si la respuesta se sigue
  cortando — antes solo se anotaba el corte, nunca se reintentaba. La misma causa explicaba el audio
  corto: el marcador de narración hablada va al final del texto, así que un corte por longitud nunca
  llegaba a escribirlo.
- Restaurado el botón "escuchar completo" (retirado en ADR 0063), que lee la respuesta íntegra en
  pantalla a pedido, sin depender de que el modelo haya marcado un entregable.
- Verificado en vivo contra producción: un plan de 18 pasos devolvió 4678 caracteres completos, sin
  ninguna nota de truncado.
- 946/946 tests. Ver ADR 0113.

## [2026-08-05] Cerebro de Snarf: visualiza los 9 Especialistas nuevos de la Fase I

- El backend (`brain.py::NODE_TIER`) ya conocía los 9 nodos `specialist_*` de la Fase I desde que se construyó cada rama, pero `web/index.html` mantiene sus propias seis tablas JS (posición en el anillo, label, ícono SVG, color, feed mini del HUD, familia visual) que nunca se habían actualizado — esos nodos existían en el backend pero jamás se dibujaban.
- Completadas las seis tablas con los 9 IDs reales, íconos nuevos dibujados a mano en el mismo lenguaje monolínea del resto (lupa para Research, lápiz para Content, mesa de directorio para Executive Board, llave inglesa para Skill Factory, etc.).
- Verificado en un navegador real (Playwright, no solo que compile) contra el server real de producción: los 32 nodos confirmados en el DOM real, los 9 tooltips y íconos nuevos confirmados con contenido real, cero errores de consola. Capturas reales confirmaron el feed en vivo mostrando actividad real con su ícono nuevo.
- 928/928 tests de Python (sin cambios de backend). Ver ADR 0112.

## [2026-08-05] Fix real: `drive_list_files` fallaba con texto libre como query

- Revisando `activity_log.jsonl` a pedido del fundador se encontró un 400 real recurrente (`HttpError ... "Invalid Value"`) cada vez que se pasaba texto libre ("vida es sueño", "Tommy") como query en vez de la sintaxis real de Drive — el fundador lo sufrió en vivo buscando contenido real, 3 intentos fallidos seguidos.
- `snarf/capabilities/google_drive.py::normalize_drive_query()`: si la query no parece sintaxis real de Drive, se envuelve automáticamente como `fullText contains '...'` — cubre todos los callers reales (`drive_list_files`, `drive_index_scan/start/catalog_unsupported`) desde un solo punto, sin tocarlos uno por uno. `get_or_create_folder()` (sintaxis real interna) sigue intacto.
- Verificado contra Drive real (no solo mocks): la búsqueda exacta que fallaba en producción ahora trae los 5 documentos reales correctos.
- 928/928 tests (11 nuevos). Ver ADR 0111.

## [2026-08-05] Fase I (Ops/Custom) de la expansión "Inteligencia Ejecutiva" — cierra la Fase I completa

- Vault Cleanup confirmado sin código nuevo (`data_backup.py` + purga de audio, ya existentes). Rama que el plan original marcaba con la captura de referencia parcialmente tapada — consultado al fundador, pidió que se generen las skills operativas reales que hacen falta hoy, con criterio propio.
- `snarf/runtime/ops_health.py::system_health()` (tool `ops_system_health`): diagnóstico real consolidado — disponibilidad de LLM/Google, llamadas y errores recientes reales, tamaño real en disco de `data/` — reúne señales ya existentes, nunca inventa una cifra. `data_backup.backup_now()` expuesto como tool (`ops_backup_now`) para backups a pedido, sin esperar hasta 6hs. Deliberadamente NO se expone `restore_latest()` — sobreescribe datos en vivo, queda manual.
- Bug real evitado: los paths default de `backup_now()` se resuelven al definirse la función, no en cada llamada — un test que monkeypercheaba solo la constante de módulo hubiera escrito un snapshot real durante la suite; corregido parcheando la función en sí.
- 917/917 tests (6 nuevos). Ver ADR 0110.
- **Cierra la Fase I completa** (las 9 ramas) y con eso el plan de expansión "Inteligencia Ejecutiva" completo (Fases A-I): mapa, gobernanza, Knowledge Layer, servidor MCP, los 7 roles asesores, el Harness, el Skill Framework, la Skill Factory operativa, y las 9 ramas de capacidades reales.

## [2026-08-05] Fase I (Agency) de la expansión "Inteligencia Ejecutiva"

- `ClientStatusSpecialist` (`snarf/specialists/agency/`), único código genuinamente nuevo de la rama: a diferencia de Sponsor Pitch Deck/Scope-of-Work/Deliverable QA/Retainer Renewal Brief (ya cubiertos sin código nuevo, mismo criterio que Proposal Drafts en Sales), parte de datos reales y estructurados de un Proyecto (`ProjectManager.get()`) — nunca inventa un avance no reflejado en tareas/notas reales. Tool nuevo `agency_client_status`.
- Client AIOS Builder sigue diferido, mismo motivo que el plan original (tamaño real, no bloqueo de vendor).
- Bug real encontrado y corregido: el wiring inicial instanciaba el specialist antes de que `self._projects` existiera en el constructor — detectado corriendo la suite completa.
- 911/911 tests (6 nuevos). Ver ADR 0109.

## [2026-08-05] Fase I (Community) de la expansión "Inteligencia Ejecutiva"

- `snarf/capabilities/discord.py::Discord` (vendor decidido en el plan, sin credencial real todavía): bot token + servidor/canal reales vía env vars, mismo patrón lazy-client que Notion/Tavily. `CommunityPulseSpecialist`: métricas reales (miembros, mensajes recientes, autores activos), determinístico, sin LLM.
- Tool nuevo de alto impacto `community_post_message` (postear como el fundador/marca, única acción de alto impacto real de la rama) — mismo protocolo `_pending()`/`confirmed` que `gmail_send_message`, excluido del allowlist MCP.
- `MemberOnboardingSpecialist`/`WeeklyQADigestSpecialist`/`CommentTriageSpecialist` diferidos explícitamente: necesitan un servidor real con actividad real para diseñarse honesto, no están bloqueados por falta de vendor — Discord ya está listo para que los use en cuanto el fundador conecte el bot.
- 905/905 tests (15 nuevos). Ver ADR 0108.

## [2026-08-05] Fase I (Finance v1) de la expansión "Inteligencia Ejecutiva"

- Confirmado sin código nuevo: `GoogleDrive.read_file_text()` ya exporta un Google Sheet real como CSV — la premisa del plan ("reusa GoogleDrive/Sheets, sin OAuth nuevo") se verificó real antes de escribir nada.
- `snarf/specialists/finance/transactions.py::parse_transactions_csv` (parseo real y tolerante, columnas en español o inglés), `BooksCategorizeSpecialist` (categoriza transacciones reales vía LLM), `MonthlyPnLSpecialist` (P&L determinístico, sin LLM, sobre transacciones ya categorizadas).
- Explícitamente diferidos, nombrados con motivo concreto (no bloqueados por vendor): `TaxPrepSpecialist` (necesita investigar la estructura real de Schedule C), `AnomalyScanSpecialist`/`SubsAuditSpecialist` (necesitan volumen real de transacciones para calibrar umbrales, no hay datos reales todavía), `ReceiptsTrackerSpecialist` (la extracción por visión ya existe, falta el flujo de asociación a una transacción real).
- 890/890 tests (18 nuevos). Ver ADR 0107.

## [2026-08-05] Fase I (Sales) de la expansión "Inteligencia Ejecutiva"

- Único código genuinamente nuevo: `SponsorInboxTriageSpecialist` (`snarf/specialists/sales/`), mismo patrón cache-first que `GmailDigestSpecialist` pero con una búsqueda de Gmail real y acotada a oportunidades de sponsor/partnership. Tool nuevo `sales_sponsor_inbox_triage`.
- Proposal Drafts y Lead Enrichment/Pipeline Review cerrados sin código nuevo — ya cubiertos por `drive_create_document` y por Proyectos (`project_list`/`project_get`/`project_search`) + `knowledge_search` como pipeline liviano, mismo criterio que la rama Memory. Un CRM dedicado (ej. HubSpot) queda nombrado como upgrade futuro, no como bloqueo de v1.
- 872/872 tests (8 nuevos). Ver ADR 0106.

## [2026-08-05] Fase I (Content) de la expansión "Inteligencia Ejecutiva"

- `snarf/specialists/content/`: `ContentSpecialist`, una sola clase real con tres configs (`blog_post`/`social_post`/`newsletter`, mismo patrón que Research/Inteligencia Ejecutiva) — redacta con `AnthropicLLM`, publica e indexa con `DocumentPublisher`. Disciplina de honestidad adaptada: solo las afirmaciones concretas sobre el fundador/su negocio tienen que basarse en `reference_material` real, el resto es trabajo creativo libre.
- Generación de imágenes queda fuera de esta ronda a propósito — `IMAGE_GENERATION_RESEARCH.md` ya investigó el espacio, sin decisión de vendor del fundador todavía.
- Tres tools nuevos (`content_write_blog_post`, `content_write_social_post`, `content_write_newsletter`), nodo `specialist_content`.
- 864/864 tests (6 nuevos). Ver ADR 0105.

## [2026-08-05] Fase I (Research) de la expansión "Inteligencia Ejecutiva"

- `snarf/capabilities/web_search.py::TavilySearch` (vendor decidido en el plan) + `GoogleYouTube.get_video_captions()` (real, pero limitado por la propia API de YouTube a videos que el fundador posee — un video de terceros devuelve `None`, tratado como "sin captions"). El fallback a ffmpeg+STT para videos de terceros del plan original NO se construyó — necesita una dependencia nueva (`yt-dlp`) con consideraciones reales de ToS, queda como decisión pendiente del fundador.
- `snarf/specialists/research/`: una sola clase real (`ResearchSpecialist`), tres configs (`deep_research`/`trend_scan`/`competitor_watch`, mismo patrón que los 7 roles de Inteligencia Ejecutiva) — junta fuentes reales, sintetiza con disciplina de honestidad, publica el informe con `DocumentPublisher` (ya lo indexa de inmediato, sin mecanismo nuevo). NotebookLM Bridge queda fuera de alcance: Google no publica ninguna API real para eso.
- **Hallazgo real de esta ronda**: se encontró un registro real (no de fixture) en `data/skill_proposals/` — un intento real de construir "Procesador de PDFs" vía la Skill Factory (Fase H), que falló por crédito real agotado de Claude Code (`Credit balance is too low`, separado del `ANTHROPIC_API_KEY` que usa Snarf para conversar). Confirma con datos reales de producción que el flujo completo de Fase H funciona de punta a punta, incluida la falla manejada con gracia. El propio test que lo encontró tenía un gap de aislamiento (`SkillFactorySpecialist._proposals_dir` sin neutralizar en la fixture `client`) — corregido.
- 858/858 tests (22 nuevos). Ver ADR 0104.

## [2026-08-05] Fase I (Memory + Productivity) de la expansión "Inteligencia Ejecutiva"

- **Memory**: cerrada sin código nuevo — las cuatro piezas que el mapa de referencia pedía ya existen con otro nombre (Knowledge Layer, Proyectos, FOUNDATION/CONSTITUTION/CHARACTER, EpisodicMemory). Documentado explícito en `KNOWLEDGE.md`.
- **Productivity**: primer skill real bajo el sub-paquete por rama (`snarf/specialists/productivity/`, que la Fase G dejó preparado sin usar todavía). `CalendarBriefSpecialist` interpreta la agenda real de Google Calendar en un resumen accionable, mismo patrón cache-first que `GmailDigestSpecialist`. Tool nuevo `calendar_brief`, widget nuevo `GET/POST /dashboard/widgets/calendar/brief`.
- `snarf/runtime/scheduler.py::next_run_at(hour, minute, tz)` (único código de infraestructura nuevo): los 3 loops periódicos de hoy son de intervalo fijo, no de hora de reloj — bug real encontrado y corregido en el propio test: comparar contra un `now` en otra zona horaria sin convertirlo primero a `tz` construía la hora de reloj equivocada.
- 842/842 tests (19 nuevos). Ver ADR 0103.

## [2026-08-05] Fase H de la expansión "Inteligencia Ejecutiva": Skill Factory, implementación real

- Primera vía real por la que Snarf puede modificar su propio código fuente — acotada, con confirmación explícita en dos pasos (ADR 0095), auditable. `snarf/capabilities/claude_code.py::ClaudeCode` invoca el CLI real `claude -p ... --output-format json` (versión 2.1.220 instalada, verificado campo por campo antes de escribir código), con `--allowedTools` acotado a editar/leer/correr tests — nunca red, nunca `git commit`/`git push`.
- `snarf/specialists/skill_factory.py::SkillFactorySpecialist`: toma un snapshot real de `git status --porcelain` antes y después de invocar a Claude Code — solo el delta cuenta como "tocado por esta construcción", robusto a que el working tree ya tenga cambios reales sin commitear de otra sesión en paralelo (el caso real de ahora mismo, ver ADR 0099). Si el delta toca un documento fundacional o cualquier archivo fuera del alcance esperado, la construcción se aborta sola; si la suite completa real no pasa después, queda `failed`, nunca se ofrece activar algo roto.
- Dos tools nuevos de alto impacto (`skill_factory_build`, `skill_factory_activate`), mismo protocolo `_pending()`/`confirmed` de dos pasos que `gmail_send_message`; un tercero de solo lectura (`skill_factory_status`). Los tres quedan excluidos del allowlist MCP — la Inteligencia Ejecutiva nunca puede construir, activar, ni siquiera consultar una construcción.
- `data/skill_proposals/` (nuevo): registro de auditoría real de cada intento, con endpoints de solo lectura `GET /skill_proposals` y `GET /skill_proposals/{id}`.
- Activar de verdad reinicia el server real (mismo procedimiento de CLAUDE.md) — nunca queda "caliente" sin reiniciar.
- Deliberadamente sin smoke test real de punta a punta esta vez (a diferencia de Fases C/D/E): invocar a Claude Code de verdad ahora mismo arriesgaría interferir con el trabajo real y sin commitear de la otra sesión en paralelo, y activar de verdad reiniciaría el server de producción sin necesidad. Recomendado para la primera vez que el working tree esté limpio.
- 823/823 tests (28 nuevos). Ver ADR 0102.

## [2026-08-04] Fase G de la expansión "Inteligencia Ejecutiva": Skill Framework — convención `INPUT_SCHEMA`/`OUTPUT_SCHEMA`

- De la propuesta original de 13 archivos por skill sobrevivió solo lo genuinamente nuevo: un dict `INPUT_SCHEMA`/`OUTPUT_SCHEMA` a nivel de módulo (misma forma que `orchestrator.TOOLS[i]["input_schema"]`), justificado porque la Skill Factory (Fase H) va a necesitar algo generable/validable por máquina.
- Documentada en `snarf/specialists/base.py` y retrofiteada en los 3 `Specialist` reales de hoy: `GmailDigestSpecialist`, `DashboardCuratorSpecialist`, `ExecutiveBoardSpecialist` (Fase E). `ProjectManager` queda fuera a propósito — no hereda de `Specialist`, sus 14 tools no comparten una sola forma de entrada/salida.
- `REGISTRY`/`register()` de `base.py` quedan documentados como deliberadamente sin usar: un dict a nivel de módulo no sostiene más de una instancia por proceso, y varios tests reales instancian más de un `Orchestrator` en el mismo proceso.
- Test de cobertura nuevo (`tests/test_specialist_schema_coverage.py`, mismo protocolo que `TOOL_TO_NODE`): itera sobre `Specialist.__subclasses__()` real, nunca una lista mantenida a mano.
- La restructuración de `snarf/specialists/` en sub-paquetes por rama (que el plan nombraba como el único cambio estructural real de esta fase) queda explícitamente diferida a la Fase I, cuando el primer skill real de una rama necesite un lugar donde vivir — mover archivos existentes ahora sería especulativo, y de alto riesgo real puntual (dos de los tres módulos están siendo editados en paralelo por otra sesión, ver ADR 0099).
- 795/795 tests (1 nuevo). Ver ADR 0101.

## [2026-08-04] Fase F de la expansión "Inteligencia Ejecutiva": Harness — nombrar el ciclo de vida real, más `compare()`

- El plan pedía un Harness con inyección de contexto por skill, validación/tests automáticos, comparación entre modelos y reintento ante falla de calidad. Revisando el código real antes de construir nada, casi todo ya existía repartido sin nombre común: prompt caching (ADR 0026/0036), confirmación en dos pasos (ADR 0015), `_bulk_read_gate` (ADR 0067), logs unificados, alerta de costo (ADR 0081), ruteo multi-proveedor (ADR 0068) y el reintento ya existente de `AnthropicLLM.generate()` al agotar rondas.
- `HARNESS.md` (nuevo): documenta ese ciclo de vida real, mapeando cada función pedida a su mecanismo real ya existente — sobre todo un ejercicio de nombrar, no de construir.
- Pushback deliberado, mismo criterio que otras ADRs de este repo: no se construye validación/tests automáticos por skill ni selección automática de "ganador" entre proveedores — no hay todavía un caso de falla real y concreto contra el cual diseñar eso (los consumidores serían las Skills de la Fase I, que todavía no existen).
- `snarf/runtime/harness.py::compare(system, messages, providers)` (único código nuevo): corre el mismo prompt contra N proveedores reales (`providers: {provider: model}`, elegido a propósito, nunca adivinado) y devuelve las N respuestas reales para inspección manual — sin juez-LLM automático. Deliberadamente independiente del trabajo de fallback automático que otra sesión está construyendo en paralelo sobre `llm_routing.py` (real mientras tanto en el working tree, pero todavía sin comitear) — usa solo primitivas ya comiteadas, para que este commit quede autocontenido.
- 794/794 tests (4 nuevos). Ver ADR 0100.

## [2026-08-04] Fallback automático entre proveedores de LLM

- El fundador vio `dashboard_curator` roto en el HUD por falta de crédito en Anthropic mientras `orchestrator` (cambiado a mano a xAI en una sesión anterior) seguía andando — preguntó por qué el sistema no cambiaba solo de proveedor. Confirmado: el ruteo es por rol (ADR 0068) y no existía ningún fallback automático en ningún punto del código.
- `snarf/runtime/llm_routing.py`: `is_provider_level_error` clasifica honestamente un error real de proveedor (crédito agotado, rate limit, credencial inválida, 5xx — vía `APIStatusError` real de los SDKs de anthropic/openai/google-genai) de un bug real nuestro, que nunca dispara fallback. `attempt_fallback` prueba el siguiente proveedor disponible en `FALLBACK_ORDER`, persiste el cambio como nuevo default del rol y deja un registro real en `data/llm_fallback_log.jsonl` — nunca inventa un éxito si todos fallan.
- Dos formas de conexión, por un límite de arquitectura real encontrado en el camino (`snarf/specialists`/`snarf/capabilities`/`snarf/knowledge` no pueden importar `snarf.runtime`, deben ser reusables fuera de Snarf): `build_resilient_llm(role)` (envoltorio auto-curable, usado por los 4 roles resueltos vía factory) para los Specialists, y una llamada inline en `Orchestrator.handle()`/`generate_conversation_title()` para sus 2 roles de instancia fija (envolverlos rompía ~20 tests reales que hacen `monkeypatch` directo sobre la Capacidad concreta).
- `GET /llm-routing/fallback_events` (nuevo) + poll cada 60s en `web/index.html`: cualquier fallback real se avisa como un mensaje más en el chat, en cualquier vista, nunca solo el historial completo en la primera carga.
- 790/790 tests (33 nuevos entre `test_llm_routing.py`/`test_orchestrator.py`/`test_app.py`). Requiere reiniciar el servidor de producción para que el fallback entre en vigencia en llamadas reales. Ver ADR 0099.

## [2026-08-04] Fase E de la expansión "Inteligencia Ejecutiva": los 7 roles, implementación real (`snarf/executive/`)

- Los 7 roles asesores (cto/coo/research/ceo/cfo/cmo/creative) corren de verdad, cada uno como un proceso separado: `snarf/executive/process.py::consult_role()` levanta `mcp_server.py` como subproceso stdio por consulta — el primer consumidor real del transporte MCP construido en la Fase D (ADR 0093/0097), no solo verificado con un smoke test aislado.
- `_MCPToolBridge` resuelve el cruce sync/async real: `AnthropicLLM.generate()` llama a `tool_handler()` síncronamente desde su propio loop de rondas, pero una sesión de cliente MCP es asincrónica de punta a punta — se corre en un hilo con su loop de asyncio activo y se expone un `call_tool()` síncrono que bloquea vía `run_coroutine_threadsafe`.
- `snarf/executive/roles.py` (`ExecutiveRoleConfig`, 7 configs, reusan sin duplicar `ROLE_TOOL_SUBSETS` de la Fase D), `snarf/executive/opinion.py` (`parse_opinions`: disciplina de honestidad verificada en código — una afirmación `BASIS='hecho'` sin el nombre EXACTO de un tool realmente invocado ese turno se degrada mecánicamente a `inferencia`, nunca se confía en el self-report del modelo), `snarf/executive/specialist.py` (`ExecutiveBoardSpecialist`, 7 roles en paralelo vía `ThreadPoolExecutor`, un rol fallando nunca tira abajo a los demás).
- Tool nuevo `executive_board_consult(question, roles=None)` en el Orchestrator (sin protocolo de confirmación — solo lectura/asesoría, ningún rol puede mutar nada); nodo nuevo `specialist_executive_board` en el cerebro; widget nuevo `GET/POST /dashboard/widgets/executive_board` (cache-first, mismo patrón que Gmail/Dashboard Curator).
- `llm_factory_for_role` usa `llm_routing.build_resilient_llm` (fallback automático entre proveedores, integrado en esta misma ronda al resto del wiring real de Snarf) en vez de `build_llm` a secas.
- Verificado con un smoke test real de punta a punta, fuera de la suite automatizada (gasta tokens reales): consulta real al rol `cto` — subproceso, sesión MCP y llamada a `knowledge_index_status` reales. El rol respondió honestamente que el dominio `code` todavía no tiene nada indexado en producción, en vez de fabricar una evaluación — la disciplina de honestidad funcionó con datos reales, no solo con fixtures.
- 790/790 tests (33 nuevos). Ver ADR 0098.

## [2026-08-04] Fase D de la expansión "Inteligencia Ejecutiva": servidor MCP real, cuarto punto de entrada

- Primer y único segundo consumidor real de las herramientas de Snarf (ver ADR 0093). El SDK `mcp` (oficial, `modelcontextprotocol.io`) no estaba instalado — se instaló y se inspeccionó campo por campo antes de escribir código: la versión real (2.0.0) resultó tener una API bastante distinta de lo asumido en el diseño original, con `MCPServer.add_tool()` construyendo el schema por introspección de función Python en vez de aceptar JSON Schema crudo.
- `snarf/core/orchestrator.py`: `HIGH_IMPACT_TOOLS`/`BULK_READ_GATED_TOOLS` (constantes nuevas, nombran lo que antes era conocimiento tribal repartido en los métodos que llaman a `_pending()`/`_bulk_read_gate()`) + tool nuevo `telemetry_cost_summary` (wrapper sobre `usage_tracker.summarize()` ya existente — sin esto el rol CFO de Inteligencia Ejecutiva iba a quedar sin ninguna competencia real).
- `snarf/mcp/tools.py` (allowlist positivo y explícito, 17 tools reales, dos ejes — nunca solo lectura cruda de contenido personal — más sub-allowlist por rol), `snarf/mcp/server.py` (genera wrappers tipados dinámicamente desde el `input_schema` real de cada tool, delega siempre a `Orchestrator._handle_tool()`, nunca una segunda implementación), `mcp_server.py` (cuarto punto de entrada, stdio).
- Verificado con un smoke test real de punta a punta: `mcp_server.py` como subproceso real, cliente MCP real conectado vía stdio, `list_tools`/`call_tool` contra el camino completo — sin mocks.
- Nueva dependencia pineada: `mcp==2.0.0`.
- 740/740 tests (8 nuevos). Ver ADR 0097.

## [2026-08-04] Fase C de la expansión "Inteligencia Ejecutiva": Knowledge Layer generalizada, dominio `code` real

- Primera pieza de código real de la expansión (Fases A/B fueron mapa y gobernanza puros). Contrato `KnowledgeSource` nuevo (`snarf/knowledge/source.py`) + `LocalRepoKnowledgeSource` (`snarf/knowledge/local_repo_source.py`, dominio `code` — indexa el propio repositorio: `snarf/**/*.py`, `tests/**/*.py`, `adr/*.md`, documentos de raíz) + `KnowledgeIndexer` (`snarf/knowledge/indexer.py`, motor genérico agnóstico de fuente, mismo pipeline real que `DriveIndexer` sin reemplazarlo).
- Cuatro tools nuevos y aditivos en el Orchestrator: `codebase_search`, `knowledge_search(domain=...)` (router explícito — `personal`/`code` reales hoy, el resto declara honestamente que no tiene fuente conectada en vez de inventar), `knowledge_index_start(domain='code')`, `knowledge_index_status(domain='code')`. Mapeados al nodo `knowledge` ya existente del cerebro — misma capacidad real, fuente nueva, no una subcapacidad distinta.
- Verificado en vivo contra el repositorio real (sin gastar Voyage): 242 ítems reales encontrados (138 `.py`, 104 `.md`), lectura de contenido confirmada.
- 732/732 tests (25 nuevos). Ver ADR 0096.

## [2026-08-04] Fase A/B de la expansión "Inteligencia Ejecutiva": mapa evolucionado, gobernanza fijada, primera Política real del proyecto

- El fundador pidió adaptar a Snarf el mapa de un video de referencia ("Claude Code as Your Personal AI Operating System"), sumando lo que el video no tiene: una Inteligencia Ejecutiva (board asesor de 7 roles que opinan, nunca ejecutan — el verdadero diferenciador del proyecto), una Knowledge Layer como infraestructura y un Harness de gobierno de ejecución. Tras revisión a fondo (91 ADRs previas, MASTER_MAP/CONSTITUTION/FOUNDATION/COGNITION reales), y dos rondas de feedback directo del fundador — rechazó dejar la Skill Factory como cola de propuestas ("la quiero totalmente funcional, que Snarf pueda construir y usar la skill en la misma conversación") y rechazó dejar Finance/Research/Community/Agency marcadas como bloqueadas por falta de vendor ("como no lo tenemos, lo construimos") — se planificó y arrancó una expansión de 10 fases (A-J). Esta entrada cubre las dos primeras, puramente de mapa y gobernanza, sin código nuevo.
- **MASTER_MAP.md**: Cognition gana el bullet de Inteligencia Ejecutiva (realiza, sin consumir, los slots ya reservados `DECISION_ENGINE`/`OPPORTUNITY_ENGINE`) y actualiza el párrafo de ADR 0010 para registrar su reapertura. Knowledge gana su primer documento real (`KNOWLEDGE.md`). Business documenta la arquitectura de datos ya decidida para Finance (Sheet/CSV real + recibos por visión, cero vendor nuevo en v1). Governance registra la primera Política real del proyecto — el hueco que el propio mapa señalaba desde la primera versión.
- **COGNITION.md**: nueva sección "Especialistas de proceso separado" — el contrato de Especialista Cognitivo es una propiedad conceptual, no de despliegue; la Inteligencia Ejecutiva lo satisface corriendo como procesos separados vía MCP en vez de llamado in-process. No es una cuarta capa.
- **KNOWLEDGE.md** (nuevo): contrato `KnowledgeSource`, modelo de namespacing (dominio = colección Chroma, sub-alcance = filtro `where`, mismo mecanismo que ya usa Proyectos), estado real por dominio (Personal/Código reales hoy; Negocio/Trading/Marketing/Finanzas reservados).
- **POLICY_HIGH_IMPACT_ACTIONS.md** (nuevo, v1.0): primera Política real del proyecto, conforme al mecanismo que el propio Artículo VII de Constitution anticipó. Nombra qué acción nueva de esta expansión requiere confirmación directa del fundador (conectar una cuenta financiera real, postear en nombre del fundador/marca, construir y activar una skill nueva) y cuál es competencia operativa ordinaria (leer/categorizar/reportar sobre datos ya provistos, buscar y indexar, generar un borrador).
- **ADR 0093, 0094, 0095** (nuevas — la numeración 0092 ya estaba tomada por el cambio de "globos de previsualización" que llegó en paralelo; renombradas antes de commitear para no pisarlo): 0093 reabre la política de "no MCP" de forma acotada al primer segundo consumidor real de las herramientas de Snarf (los procesos de Inteligencia Ejecutiva); 0094 fija el modelo de autoridad y honestidad de la Inteligencia Ejecutiva (cero autoridad inherente, Snarf como único sintetizador, disciplina `hecho/inferencia/hipótesis/estimación/opinión` verificada en código, no confiada al modelo); 0095 reabre la postergación de ADR 0010 (automodificación de Snarf vía Claude Code) — revisando Constitution/Foundation se confirmó que ningún artículo lo prohíbe, así que no se propone ninguna enmienda: una confirmación explícita caso por caso ya es la autoridad directa que el Artículo VII exige, mismo mecanismo que la confirmación en dos pasos de ADR 0015.
- **CLAUDE.md** actualizado: sección "Skills vs. MCP" registra la reapertura acotada; conteo de archivos de test corregido (31 → 54, estaba desactualizado).
- El código real (servidor MCP, procesos de Inteligencia Ejecutiva, Knowledge Layer generalizada, Skill Framework/Factory, las 9 ramas de capacidades) queda para las Fases C-I, todavía sin construir — esta entrada es solo mapa y gobernanza, sin una sola línea de código nueva.
- 707/707 tests (sin cambios — ningún archivo de código tocado en esta entrada).

## [2026-08-04] Globos de previsualización de documento, y barra de input a lo ancho del chat

- El fundador señaló, con un ejemplo real (plan del canal de deporte de Tommy en Drive), que un globo diciendo "leyendo plan de contenido..." sin mostrar nada del documento real "no se vuelve útil". Pidió título/resumen/miniatura visual clickeable hasta el archivo, estandarizado para Drive/Notion y extensible a futuro.
- `snarf/telemetry/detail.py`: campo nuevo `preview` (`{title, link, snippet}`), paralelo a `detalle` pero deliberadamente parcial — solo para tools que tocan un documento real (`drive_read_file`, `drive_update_document`, `drive_create_document/spreadsheet/presentation`, `notion_create_page`, `notion_read_page`). `link` siempre real (API o URL pública estable construida sin llamadas de red nuevas); `title` ausente a propósito en lectura/actualización (evita agregar latencia real solo para enriquecer un globo). Wireado en cascada hasta `data/telemetry_events.jsonl` (`events.py`/`activity_log.py`/`orchestrator.py`) y hasta `widget_summary.py` (`last_preview`/`recent_items[].preview`). Documentado en `TELEMETRY_SCHEMA.md`.
- `web/index.html`: tarjeta de preview (título+snippet+link real, acento ámbar) integrada en los slots de texto existentes de las 24 plantillas — nunca un slot/plantilla nueva. Barra de input del chat-dock ya no topeada a 480px, ocupa el ancho real del chat (`min(760px, 92vw)`).
- Bug real encontrado y corregido verificando con Playwright: `dashHudTransformFor` leía `pos.ring` antes de chequear la salida de un widget (`pos === null` a propósito ahí), tirando una excepción sin capturar que interrumpía el resto del render cada vez que un widget dejaba de ser relevante.
- Miniatura visual (thumbnail real de Drive) queda explícitamente diferida — necesita infraestructura nueva (proxy + cacheo de imágenes autenticadas, nunca construida hasta ahora).
- 707/707 tests (18 nuevos). Verificado con Playwright contra el servidor real de producción, sin disparar ninguna llamada real a Drive/Notion/LLM (widgets sintéticos solo en el navegador, nunca escritos a la telemetría real). Requiere reiniciar el servidor de producción para que `preview` empiece a viajar en llamadas reales — confirmar con el fundador antes. Ver ADR 0092.

## [2026-08-04] SNARF OS v2: 24 plantillas, profundidad 3D real, y el curador elige presentación

- Tras probar la v1 (ADR 0090) en producción, el fundador pidió una pasada mucho más profunda inspirada en el HUD de Iron Man: widgets más grandes con más información real, sensación 3D genuina (no solo el orbe — también el chat y los widgets entre sí), líneas de conexión entre la esfera y cada widget, jerarquía por transparencia, input siempre visible con un botón de foco sutil (no la barra grande de v1), posición configurable del chat, y un curador que elija activamente **cómo** presentar cada widget, no solo qué texto poner. También pidió delegarle crear/modificar otros agentes — contrastado contra `CONSTITUTION.md` (Art. III/V/línea 109: ninguna autoridad nace de una delegación general de fondo), se separó en Track A (este ciclo: el curador propone plantillas visuales, nunca ejecuta código) y Track B (crear/modificar Specialists de verdad, fuera de alcance, iniciativa aparte con su propia gobernanza).
- `snarf/telemetry/widget_templates.py` (nuevo): 24 plantillas, 3 tamaños × 8 variantes. El tamaño se asigna mecánicamente por ranking real (`assign_tier`, nunca el LLM); el curador solo elige la variante dentro de ese tamaño. `widget_summary.py` gana `recent_activity_buckets`/`recent_items` (histograma y lista real de actividad reciente, mecánicos, sin LLM) y `size_tier` por widget.
- `dashboard_curator.py`: el curador ahora elige plantilla + puede proponer una nueva (persistida en cola de solo lectura para el fundador, nunca aplicada sola); el nodo `cost` se cura como cualquier otro (antes solo aparecía como contexto).
- `web/index.html`: primera escena con perspectiva CSS real del archivo (`translate3d`/`perspective`) — widgets con profundidad por anillo, chat con burbujas alejándose hacia el fondo (`--depth`, acotado a Vista HUD); líneas de conexión SVG orbe→widget; chat-dock rediseñado (input siempre visible, botón de foco chico en vez de la barra grande, `openChatFocus`/`closeChatFocus` corregidos para funcionar desde cualquier vista); posición configurable del chat; drawer lateral de conversaciones/proyectos con pin.
- Seis bugs reales encontrados y corregidos verificando con Playwright, cuatro de ellos en el mismo problema (el layout radial, documentados en cadena porque cada uno solo se hizo visible tras corregir el anterior): dos colisiones de z-index nuevas contra modales existentes; alineación radial sistemática entre anillos; un radio circular que no cabe en un rectángulo angosto de escritorio (y una elipse que rompía la garantía de separación); un solver iterativo de pares que **no convergía** en grupos densos (reemplazado por completo por un empaquetado constructivo por espiral, que garantiza cero superposición por construcción); el dock de chat fijo, invisible para el cálculo de layout. Además, una regresión real de cache: el `template` elegido por el curador se validaba contra el tamaño que el nodo tenía al momento de curarlo, no el actual.
- 688/688 tests (28 nuevos). En el camino se encontró y corrigió una fuga real de test pollution (mismo tipo que ADR 0085): `test_app.py` nunca aislaba el `CACHE_DIR` de `dashboard_curator`, así que sus tests podían leer cache real de producción. Verificado con Playwright en servidor aislado, datos de actividad reales sembrados: cero superposiciones confirmadas programáticamente contra bounding boxes reales, curador probado con una llamada real al LLM, drawer/foco/posición/reversibilidad verificados de punta a punta, cero errores de consola. Ver ADR 0091.

## [2026-08-04] SNARF OS: dashboard radial con Especialista curador real, reversible por toggle

- El fundador pidió que el experimento del dock de globos (ADR 0089) deje de vivir dentro de un widget y se convierta en el dashboard principal: esfera central animada, widgets distribuidos por toda la pantalla que se reposicionan solos por relevancia real, con animación completa (entrada/salida/actualización), cada widget clickeable a un detalle, y el chat integrado como barra inferior colapsable. Pidió Especialistas de IA reales (no solo código) curando el dashboard, todo en un solo desarrollo — y, tras revisar el plan, un toggle real y persistido para volver a la versión clásica en cualquier momento si el rediseño no convence.
- `snarf/telemetry/widget_summary.py` (nuevo): agregación real por nodo (`summarize_node`/`all_widget_summaries`/`curation_snapshot`), mismo motor de datos que ya usa el dock de globos (ADR 0089) — cero contenido inventado, `None` cuando un nodo no tuvo actividad real.
- `snarf/specialists/dashboard_curator.py` (nuevo): `DashboardCuratorSpecialist`, mismo patrón cache-first que `GmailDigestSpecialist`. Nunca decide qué widgets existen (eso sigue siendo `relevance.dock_priority`, determinístico) — solo rephrasea datos reales ya agregados, con la misma frontera "nunca inventes" ya usada en `ProjectManager`. Refresca en un loop de backend cada 10 min o antes si la señal real cambió — nunca disparado por el poll del navegador.
- `snarf/runtime/dashboard_prefs.py`: nuevos campos aditivos (`dashboard_view`, `hud_widget_state` auto/pinned/hidden, `hud_widget_options`) — la Vista clásica (`visible_widgets`/`panel_order`/`widget_options`) no se tocó, sigue funcionando exactamente igual.
- `web/index.html`: toggle Vista clásica/HUD persistido (mismo componente visual que el del panel Cerebro); esfera central animada reaccionando a señales reales (curador corriendo de verdad); layout radial en anillos concéntricos con reposición real vía FLIP (nunca destruye/recrea un widget que sigue siendo relevante); drill-down genérico por nodo; barra de chat colapsable (`#chatDock`, solo Vista HUD, chat reparentado nunca clonado). Con el toggle en "clásica", cero cambios de comportamiento — todo lo nuevo es aditivo.
- Cuatro bugs reales encontrados y corregidos verificando con Playwright (no a ojo): colisión de `transform` real entre `.orb-wrap` y el nuevo selector del orb (mismo tipo de bug ya visto en ADR 0069/0078, el orb aparecía ~90px fuera de centro); el chat dock seguía visible al angostar a mobile; el parser de captions del curador fallaba contra una respuesta REAL del LLM (no un mock) porque el modelo repetía el `(score N.N)` del prompt; el layout radial amontonaba widgets en medio círculo por dividir el ángulo por la capacidad máxima del anillo en vez de su ocupación real.
- 660/660 tests (39 nuevos). Verificado con Playwright en servidor aislado: reversibilidad real (Vista clásica bit a bit igual que antes), reposición FLIP confirmada por identidad de elemento DOM, ciclo desktop→mobile→desktop sin duplicar el chat, y **el curador probado con una llamada real al LLM** (no mock) generando `headline` y captions correctos sobre datos reales sembrados. Ver ADR 0090.

## [2026-08-04] Globos contextuales: contenido real por nodo, y cobertura total del dock

- El fundador vio Dock v3 en producción y señaló el problema de fondo: "no está mostrando absolutamente nada... es un orbe que late... pero eso es todo lo que hace." Pidió, con un ejemplo concreto, que cada skill/capacidad/especialista tenga su propio widget mostrando contenido real (a quién se le mandó un mail, qué documento se creó, qué se buscó), apareciendo/desapareciendo por relevancia real. Rechazó un primer plan con cobertura parcial ("no veo... para cada skill capacidad o especialista, ni sus sub elementos") — este ciclo entrega cobertura completa.
- Causa raíz: el evento unificado nunca capturó contenido, solo identificadores. `snarf/telemetry/detail.py` (nuevo): un extractor de `detalle` real por cada uno de los 60 tools del Orchestrator (verificado, no 68 como se estimó al planear), leyendo `tool_input`/`result` reales — nunca inventado. Wireado en los tres chokepoints reales (`activity_log`, `usage_tracker` para LLM/STT/TTS, `input_log`), con cobertura total exigida por test.
- `DOCK_NODE_IDS` (antes 9 nodos elegidos a mano) ahora es `list(brain.NODE_TIER.keys())` — los 24 nodos reales completos. El frontend muestra el top-9 por relevancia real (ranking ya existente), no todos a la vez.
- `web/index.html`: capa de globos contextuales (`#hudBubbleLayer`), 9 familias visuales compartidas (scan/document/list/dispatch/voice/think/admin/system/input) ancladas al chip real de cada nodo, con TTL real (~20s) y prioridad por conversación activa al llegar al tope de simultáneos. Tabla de feed eliminada por completo (pedido explícito: "no aporta nada").
- Dos bugs reales de layout encontrados y corregidos verificando con Playwright (bounding box del hub contra `#brainPanel`, no a ojo): el hub se geometrizaba con un fallback 300×190 mientras la Vista HUD seguía oculta (hasta 130px fuera del panel); corregido el offset vertical del hub, insuficiente una vez sacada la tabla de feed.
- 621/621 tests (16 nuevos, cobertura total verificada). Verificado con Playwright en servidor aislado: 4 familias de globos con contenido real confirmado, expiración real por TTL de punta a punta, hub dentro del panel con margen real, cero errores de consola. Backend requiere reinicio de producción; capa de globos y layout son 100% frontend. Ver ADR 0089.

## [2026-08-03] La rueda como escenario principal, con reacción automática a eventos reales

- El fundador reportó el problema de fondo del dock v2: por default aparecía colapsado ("un orbe en standby") y sin click no mostraba nada — pidió que sea "una manifestación de los procesos de Snarf", ocupando el escenario principal.
- `web/index.html`: el dock arranca abierto por defecto (antes requería click), ocupa casi todo el panel (antes una franja de 190px), la tabla de texto se reduce a un renglón mínimo. Generalizado el "story moment" (antes solo la alerta de costo): cada evento real nuevo destella su chip y línea guía correspondiente, automáticamente, sin interacción.
- 605/605 tests. Verificado con Playwright sembrando un evento real mientras el panel estaba abierto y capturando el destello en vivo (~1.8s después, dentro de la ventana de poll). Cambio 100% frontend, no requiere reiniciar producción. Ver ADR 0088.

## [2026-08-03] Dock v2: glow volumétrico real (SVG) — el fundador rechazó la primera versión y autorizó reusar la estética literal de sus referencias

- El fundador rechazó el resultado anterior ("círculos horribles, sin luz volumétrica, sin efecto 3D") y autorizó explícitamente reusar la estética literal de sus referencias visuales, incluido un acento rojo — **supersede, solo para este componente**, el límite de "color literal no" de ADR 0006/0037 (aclarado: nunca fue una regla de FOUNDATION/CONSTITUTION, era un ADR de diseño ordinario, revisable con autoridad real del fundador).
- Reconstrucción real con SVG (no solo CSS): hub central con glow vía filtros `feGaussianBlur` reales, anillo de marcas rotando, líneas guía SVG desde el hub hasta cada chip (alineadas en píxeles reales, no aproximadas), chips en paralelogramo con glow en tres capas, etiquetas en el nuevo rojo `--hud-signal-red`.
- Dos bugs reales encontrados y corregidos verificando con Playwright (`elementFromPoint`, no solo mirando el render): un typo real (`position: relative` en vez de `absolute`) rompía el hit-test de todos los chips; el hitbox invisible del anillo de apertura/cierre seguía tapando al chip más cercano al centro (típicamente el de mayor prioridad) incluso con el dock abierto.
- 605/605 tests, cero errores de consola verificados en los tres estados (hover, select, cierre por click vacío). Ver ADR 0087.

## [2026-08-03] Dock rediseñado como anillo Omega, inspirado en cómo se construyó realmente el HUD de Iron Man

- El fundador compartió referencias visuales + la transcripción real de cómo The Orphanage construyó el HUD de Iron Man (2008). Se aplicó la lógica de diseño (nunca colores/branding literal, límite ya establecido en ADR 0006/0037): un solo anillo compacto ("widget Omega") que colapsa/expande bajo comando en vez de quedar siempre abierto, bordes con profundidad implícita (desvanecidos, nunca corte duro), y reacción real ("story moment") a una alerta genuina de costo — el dock se auto-abre una sola vez cuando el gasto del día cruza el umbral real (Fase 5), nunca de forma simulada.
- `web/index.html`: `#hudRingIdle` (nuevo), `#hudMiniDock[data-open]` controla colapsado/expandido, `setHudDockOpen()`. Cero cambios de backend.
- 605/605 tests. Verificado con Playwright contra un servidor real: colapsado por default, abre/cierra al click, auto-abre ante una alerta real sembrada, desvanecido de bordes confirmado en el DOM. No hizo falta reiniciar producción (cambio 100% frontend). Ver ADR 0086.

## [2026-08-03] Fuga real de test-pollution visible en producción: corregida y purgada

- El fundador reportó (con captura real) la Vista HUD inundada de filas sintéticas `gemini:gemini-3-pro-preview`. Causa real: `tests/test_gemini_llm.py` llamaba `.generate()` de verdad sin aislar `usage_tracker.DEFAULT_PATH`/`events.DEFAULT_PATH` — cada corrida de la suite completa escribía directo a los archivos reales del proyecto. Corrige además una atribución imprecisa de ADR 0077/0079: `test_llm_routing.py` nunca fue la fuente (nunca llama `.generate()`).
- Purgadas 605 entradas sintéticas de `data/usage_log.jsonl` y 11 de `data/telemetry_events.jsonl`, con huella exacta e inequívoca (defaults literales del fixture de test) — verificado que ninguna entrada real se tocó. Backup tomado antes de purgar.
- 605/605 tests, conteo de entradas sintéticas 605→605 tras correr la suite completa de nuevo (confirma la fuga cerrada, no solo una purga puntual). No hizo falta reiniciar el servidor de producción. Ver ADR 0085.

## [2026-08-03] Fase 0-1 del plan de HUD: esquema de telemetría, evento unificado, fix de vendors invisibles en el cerebro

### Arquitectura y código
- `TELEMETRY_SCHEMA.md` (Fase 0, sin ADR propio — solo diseño/documentación): esquema de evento unificado (`nodo`/`agente`/`skill`/`modelo`/`tokens_in`/`tokens_out`/`costo_usd`/`latencia_ms`/`estado`) y tabla determinística de verbo temático por nodo. `web/hud_design_tokens.css`: sistema de diseño holográfico (paleta cian reusada de `--glow`, ámbar nuevo reservado para atención/alerta, animación de materialización, tipografía monoespaciada para datos) — todavía sin enlazar a `web/index.html`.
- `snarf/telemetry/events.py` (nuevo): evento unificado emitido desde adentro de los tres logs reales ya existentes (`activity_log.record`, `usage_tracker.record`, `input_log.record`), sin agregar llamadas nuevas al modelo. `snarf/telemetry/verbs.py` (nuevo): la tabla de verbos, nunca generada por el LLM.
- Cerrado el gap de `estado="truncado"`: `anthropic_llm.py` ahora pasa el `stop_reason` real de cada respuesta hasta el evento unificado.
- Bug real encontrado y corregido en `brain.py`: los vendors `gemini`/`openai`/`xai`/`groq_llama`/`groq`/`local` (multi-proveedor de LLM y voz, ADR 0056/0067/0068) nunca tenían nodo mapeado — quedaban invisibles en el cerebro actual, no solo en la instrumentación nueva.
- 570/570 tests. Ver ADR 0077.

### Fase 2: dock radial HUD (prototipo)
- `web/hud_gestures.js` (nuevo): capa de gestos desacoplada del render — `HUDGestureController` traduce mouse/touch a eventos abstractos (`focus`/`select`/etc.), reemplazable por otra fuente (eye-tracking, Fase 9) sin tocar el componente visual.
- `web/hud_dock_prototype.html` (nuevo): arco de nodos con perspectiva 3D real (proyección cilíndrica, no `scale()` simulado), estados collapsed/focus/select, panel anclado con el verbo temático real de `verbs.py`. Datos mock, todavía sin backend.
- Tres bugs reales encontrados y corregidos verificando con Playwright: posición 3D pisada por la animación de estado (mismo patrón que ADR 0069 del cerebro), doble binding de gestos duplicando el toggle de selección, y un backdrop tapando el resto de nodos por un contexto de apilado no considerado. Ver ADR 0078.

### Fase 3: historial de costos por día/agente/sesión
- `snarf/telemetry/context.py` (nuevo): `conversation_id` real por thread (`threading.local()`, mismo criterio que ADR 0041), seteado por `Orchestrator.handle()` — el evento unificado lo lee solo, sin parámetro nuevo en ninguna función `record_*`.
- `snarf/telemetry/cost_history.py` (nuevo) + `GET /dashboard/cost_history`: agrega costo/tokens por día/agente/sesión desde el evento unificado. Costo desconocido nunca se cuenta como cero (mismo criterio que `usage_tracker.summarize()`).
- `web/hud_cost_history_prototype.html` (nuevo): historial visual en el lenguaje de Fase 0, fetch real al endpoint con fallback a mock de la misma forma.
- Gap real encontrado y corregido: `tests/test_app.py` no redirigía `events.DEFAULT_PATH`, seguía escribiendo al archivo real (corrige también una afirmación imprecisa del CHANGELOG/ADR 0077 anterior sobre el origen de esa fuga).
- 584/584 tests. Ver ADR 0079.

### Fase 4: Vista HUD del cerebro, en paralelo a la Vista clásica
- `GET /dashboard/telemetry_feed` (nuevo): el evento unificado de Fase 1 anotado con verbo temático y resumen recortado, listo para render directo.
- `web/index.html`: nuevo toggle "Vista clásica"/"Vista HUD" dentro del panel del cerebro — el grafo SVG/canvas existente queda **intacto, sin ningún cambio**, la Vista HUD es un feed de texto nuevo al lado, con poll propio en paralelo (cambiar de vista nunca pierde datos ni recarga nada).
- Bug real de CSS encontrado y corregido verificando contra la app real (no un prototipo): `el.hidden` no ocultaba nada porque `display: flex` de una regla de autor le ganaba al `[hidden]` del user-agent — las dos vistas quedaban superpuestas. Corregido con selectores `[hidden]` de mayor especificidad.
- Verificado de punta a punta contra un servidor real (datos aislados en un directorio temporal, cero riesgo para `data/` real): login, toggle entre vistas, evento real con `estado="truncado"` mostrando el modificador correcto ("conteniéndose en pontificando"), cero errores de consola.
- 586/586 tests. Ver ADR 0080.

### Fase 5: motor de relevancia contextual, conectado al dock radial
- `snarf/telemetry/relevance.py` (nuevo) + `GET /dashboard/dock_priority`: ranking real de nodos por recencia/frecuencia de actividad, boost por error reciente ("alerta"), y alerta de costo cuando el gasto del día cruza un umbral ($1.00/día, decisión de diseño nueva declarada como tal). "Tarea activa"/"alertas pendientes" del pedido original no tienen sistema real detrás en Snarf — interpretadas con honestidad (actividad más reciente / errores recientes), documentado en ADR.
- `web/hud_dock_prototype.html`: reemplaza el orden mock fijo de Fase 2 por `fetch('/dashboard/dock_priority')` (con el mismo fallback ya establecido). El nodo de mayor prioridad cae en el slot central real del arco — "sube de prioridad y se mueve al centro" es literal. Alerta de costo como nodo sintético nuevo, distinguido en ámbar.
- 598/598 tests. Ver ADR 0081.

### Fase 6: panel de optimización de entrada
- `snarf/telemetry/input_preprocessing.py` (nuevo) + `GET /dashboard/input_efficiency`: registra, por turno, lo que el fundador escribió vs. el tamaño real del bundle completo enviado al LLM (system + historial + input) — Snarf no reescribe el mensaje, la ineficiencia real está en lo que viaja alrededor. `overhead_ratio` (chars enviados / chars escritos) como métrica central, nunca tokens inventados.
- `web/hud_input_efficiency_prototype.html` (nuevo): tiles de resumen + tabla de turnos recientes, en el lenguaje de Fase 0, con overhead alto marcado en ámbar.
- 601/601 tests. Ver ADR 0082.

### Fase 7 (auditoría, en curso) — feedback real: verbos por tool + dock radial integrado en la Vista HUD
- `snarf/telemetry/verbs.py`: `VERB_BY_SKILL`, un verbo propio por cada una de las 68 tools reales (antes compartían el genérico del nodo) — pedido explícito tras ver poca variedad en la Vista HUD real.
- `web/index.html`: el dock radial de Fase 2/5 (nunca antes enlazado a la app real) se integra dentro de `#brainHudView` — datos reales de `/dashboard/dock_priority`, click en un nodo filtra el feed de texto al lado.
- Bug real encontrado y corregido verificando contra un servidor real: una llave de cierre faltante en JS rompía el parseo de todo el `<script>` inline, dejando el dashboard entero sin inicializar (degradaba a la vista de chat/grabación sin ningún widget).
- Servidor de producción (puerto 8002) reiniciado con el código corregido — mismo link de siempre.
- 605/605 tests. Ver ADR 0083.

### Fase 7/8, nodo Orchestrator: recorte de duplicación verificada en `SYSTEM_PREFIX`
- Medido (no asumido) el solapamiento real entre la prosa de `SYSTEM_PREFIX` y las `description` que cada tool ya tiene en el schema — varios pasajes resultaban duplicados casi palabra por palabra (ej. `measure_text_length`, la excepción de `drive_update_document`). Recortado solo lo verificado como duplicado; el protocolo de confirmación en dos pasos y el resto de guía única quedan intactos.
- `SYSTEM_PREFIX`: 15.385 → 13.211 caracteres (-14,1%). FOUNDATION/CONSTITUTION/CHARACTER evaluados y **no tocados** — ya económicos para lo que son, cortar hubiera arriesgado matiz real sin evidencia de grasa retórica.
- 605/605 tests. Servidor de producción reiniciado, actividad real confirmada post-cambio. Ver ADR 0084.

## [2026-08-01] Edición de Google Docs existentes, integración con Notion, widget de uso de APIs completo

### Arquitectura y código
- Nueva tool `drive_update_document`: reemplaza el contenido de un Google Doc ya existente (antes Snarf solo podía crear archivos nuevos). Confirmación una vez por documento por conversación, no en cada edición. Ver ADR 0074.
- Nueva Capacidad `Notion` (búsqueda, lectura, creación y append de páginas) — excepción acotada y logueada al gate de Capabilities de MASTER_MAP, confirmada explícitamente por el fundador. Inactiva hasta que exista `NOTION_API_KEY` real. Ver ADR 0075.
- Extractor de migración desde ChatGPT (`snarf/migration/chatgpt_export.py`): parsea el export completo (`conversations.json`, árbol `mapping`) a conversaciones en orden cronológico real. Probado solo contra fixtures del formato documentado — el fundador todavía no generó su export real. Ver ADR 0076.
- CHARACTER.md ("Memoria consistente") ampliado: detectar huecos reales de capacidad y proponerlos (nunca auto-construirlos, Art. III/IV de Constitution), extrapolar patrones de interacciones pasadas, y revisión de patrones repetidos solo a pedido explícito del fundador. Guía correspondiente agregada al `SYSTEM_PREFIX` del Orchestrator — sin tools ni ADR nuevos, apoyado en `search_memory`/`list_conversations`/`project_search` ya existentes.
- Fix del widget de uso de APIs (`web/index.html`): mostraba solo Anthropic/Voyage/ElevenLabs (allowlist fija); ahora itera todos los vendors que ya registra el backend (Gemini, OpenAI, xAI, Llama vía Groq, STT/TTS locales) — bug real desde que ADR 0068 sumó el ruteo multi-proveedor.

## [2026-07-31] Backlog de uso real: tools de fecha/longitud, grabación a un tap, convenciones de Proyectos

### Arquitectura y código
- Nuevas tools `get_current_datetime` y `measure_text_length` (Orchestrator) — nodo `utility` nuevo en el cerebro. Ver ADR 0073.
- Grabación de voz: reemplazado el gesto de mantener presionado + deslizar para bloquear (ADR 0049) por un tap simple, manos libres desde el primer instante, con waveform animado en vivo. Ver ADR 0073.
- Límite de prompt de Proyecto (`PROJECT_PROMPT_MAX_LENGTH`) subido de 4000 a 8000 caracteres, backend y frontend.
- Persona gramatical en mails a terceros, formatos nativos de Drive por defecto, links siempre en Markdown clicable, y convenciones de texto para tareas/notas de Proyectos (descartar sin perder motivo, dedup, trazabilidad de origen, dependencias, resumen + continuidad entre consolidados, plantilla de tarea tipo "especialista"): guía nueva en `SYSTEM_PREFIX`, sin cambios de schema.

## [2026-07-25] BUILD MODE 001 — Primera versión funcional

### Documentos
- CONSTITUTION.md: primera versión estable (v1.0), reemplaza al borrador candidato. Ver ADR 0001.
- CHARACTER.md: nuevo. Personalidad permanente de Snarf.
- COGNITION.md: nuevo, v0.1. Describe el razonamiento real implementado (walking skeleton).
- MASTER_MAP.md: actualizado para reflejar la existencia de Constitution, Character y Cognition, y para registrar la ausencia de un nivel de Políticas/Procedimientos en la jerarquía documental.

### Arquitectura y código
- Adoptado Python como stack técnico inicial. Ver ADR 0002.
- Implementada arquitectura de tres capas (Capacidades / Especialistas Cognitivos / Snarf). Ver ADR 0003.
- Construido el primer walking skeleton: canal de texto funcional de punta a punta (entrada → Core Cognitivo → memoria episódica → salida). Ver ADR 0004.
- Canal de voz (ElevenLabs) definido como interfaz, pendiente de credencial.

### Repositorio
- `git init` del repositorio.
- Estructura de carpetas creada: `snarf/` (core, capabilities, specialists, runtime), `adr/`, `data/`.

## [2026-07-25] Canal de voz real (ElevenLabs)

- `ElevenLabsTTS` y `ElevenLabsSTT` implementadas contra la API real (antes eran stubs). Nueva Capacidad `LocalAudioIO` para reproducción (`afplay`) y grabación de micrófono (`sounddevice`).
- Voz elegida por el fundador: Antonio - Confident, Gentle and Clear (`es-AR`).
- Verificado: síntesis + reproducción de audio real, y transcripción por round-trip (texto → audio → texto, coincide).
- Pendiente de verificación: captura de micrófono en vivo (requiere ejecución interactiva de `python3 main.py --voice`).
- Ver ADR 0005.

## [2026-07-25] Grabación manual e interfaz visual

- Primera prueba en vivo reveló dos problemas reales: grabación de duración fija desincronizada con el habla real, y un bug en `AnthropicLLM` (asumía que el primer bloque de respuesta siempre era texto; el modelo a veces antepone un bloque de razonamiento). Ambos corregidos.
- `LocalAudioIO` soporta grabación manual start/stop. `VoiceChannel` (terminal) actualizado a este esquema.
- Nuevo punto de entrada `app.py` (FastAPI) + `web/index.html`: interfaz visual con un orbe controlado a un click (escuchar / detener), diseño propio inspirado en el principio de HUD conversacional, sin reproducir ninguna interfaz de ficción con derechos de autor.
- Verificado de punta a punta vía HTTP: grabación real capturada, transcripta, razonada y respondida por voz correctamente.
- Ver ADR 0006.

## [2026-07-25] Grabación en el navegador, dos modos, chat y rediseño visual

- Captura de audio movida del servidor (`sounddevice`) al navegador (`MediaRecorder`) — necesario para que la interfaz tenga sentido desde cualquier dispositivo, no solo la Mac.
- Dos modos intercambiables: mantener presionado y soltar para enviar, o click/click con revisión de texto y envío manual.
- Historial de conversación tipo chat (usuario a la derecha, Snarf a la izquierda), persistente mientras la pestaña está abierta.
- Rediseño visual: fondo con degradé a negro, grilla técnica, línea de escaneo, orbe con rayos y anillos concéntricos.
- Servidor ahora en `0.0.0.0` (antes solo localhost); imprime la URL de red al iniciar.
- Verificado por API: `/transcribe` y `/send` funcionan de punta a punta. Pendiente de verificación manual en navegador (MediaRecorder no se puede probar por este medio).
- Limitación conocida y no resuelta: acceso al micrófono desde el celular vía red local requiere HTTPS (contexto seguro del navegador); pendiente de decisión sobre cómo resolverlo.
- Ver ADR 0007.

## [2026-07-25] Acceso remoto seguro vía Tailscale

- Instalado Tailscale en la Mac y el iPhone del fundador, mismo tailnet.
- `tailscale serve --bg 8000` expone `app.py` con HTTPS gestionado automáticamente en `https://macbook-pro-de-jeremas.tailb10c73.ts.net/`.
- Verificado: la URL responde 200. Pendiente: prueba manual de grabación de voz desde el iPhone.
- Ver ADR 0008.

## [2026-07-25] Correcciones de interfaz para iOS y layout móvil

- Diagnosticadas dos causas probables de que la voz no funcionara en iPhone: `MediaRecorder` etiquetaba el audio como `webm` sin verificar el formato real que graba Safari, y la reproducción de audio ocurría fuera de la ventana de gesto de usuario que exige iOS.
- Detección real de formato soportado (`MediaRecorder.isTypeSupported`) y patrón de "desbloqueo de audio" con un elemento compartido.
- Layout invertido: orbe y controles fijos abajo (alcance del pulgar), chat arriba creciendo hacia arriba.
- Corregidos los bordes blancos en Safari (`viewport-fit=cover`, fondo negro en `html`, `safe-area-inset-*`).
- Más efectos visuales: doble capa de rayos, nebulosas de fondo, partículas, marcas de esquina tipo HUD.
- Errores ahora muestran el detalle técnico en pantalla para poder diagnosticar sin acceso a la consola del dispositivo.
- No verificado contra un iPhone real en esta sesión — pendiente de confirmación del fundador.
- Ver ADR 0009.

## [2026-07-25] Conversaciones persistentes, Markdown y pulido de interfaz

- Memoria episódica agrupable por `conversation_id`; nuevos endpoints `GET /conversations` y `GET /conversations/{id}`.
- Barra lateral desplegable (☰) para listar, retomar y crear conversaciones — funciona igual desde la Mac o el iPhone porque ambos hablan con el mismo backend.
- Snarf ahora formatea sus respuestas en Markdown cuando corresponde (encabezados, listas, negrita, citas, código); el frontend incluye un renderer propio y liviano.
- Selector de modo reducido a un texto pequeño de bajo contraste (antes eran dos botones prominentes). Agregado indicador de "escribiendo" (tres puntos animados).
- Pospuesto explícitamente, a pedido del fundador: que Snarf pueda automodificarse conversando (código o documentos propios). Queda registrado como capacidad futura, no implementada.
- Verificado por API completo. Pendiente confirmación visual del fundador (renderer, barra lateral, animaciones).
- Ver ADR 0010.

## [2026-07-25] Memoria cruzada, modo de texto y orbe holográfico

- Snarf puede ahora buscar y recordar contenido de cualquier conversación pasada, no solo la actual, mediante herramientas (`list_conversations`, `get_conversation`, `search_memory`) que decide usar cuando hace falta. Verificado con un caso real cruzando dos conversaciones distintas.
- Nuevo modo de texto en el selector (click/mantener/texto): campo de texto + enviar, teclado automático en el celular.
- Orbe rediseñado: relleno translúcido tipo fresnel en vez de sólido, con anillos de wireframe 3D simulando un globo y parpadeo sutil — más holográfico, menos "bola sólida".
- Ver ADR 0011.

## [2026-07-25] Audio bajo demanda, selector de modo segmentado, arranque en conversación nueva

- El audio de Snarf ya no se reproduce solo; cada respuesta tiene un botón "▶ escuchar" que abre una ventanita flotante con control de velocidad (1x a 2x, y 0.75x) y botón de cierre para cortar antes de que termine.
- Selector de modo (Mantener / Toque / Texto) rediseñado como control segmentado grande y claro, en vez de un texto chico fácil de tocar por error cerca del orbe.
- La app ahora siempre arranca en una conversación nueva; retomar una anterior es una acción explícita desde la barra lateral.
- Ver ADR 0012.

## [2026-07-25] Autenticación de Google y primera Capacidad de Drive

- Proyecto de Google Cloud creado, credenciales OAuth (App de escritorio) configuradas.
- `GoogleAuth`: autenticación compartida (OAuth + caché/refresh de token) para todas las futuras Capacidades de Google. Un solo consentimiento cubre Drive, Gmail, Calendar y YouTube.
- `GoogleDrive`: listar y leer archivos. Verificado en vivo contra la cuenta real del fundador — trajo archivos reales de su Drive.
- Pendiente: extracción de contenido de PDFs, imágenes, audio y video (hoy solo texto/Google Docs/Sheets). Vectorización todavía no construida.
- Ver ADR 0013.

## [2026-07-25] Gmail, Calendar, YouTube conectados; tablas Markdown

- Nuevas Capacidades: `GoogleGmail`, `GoogleCalendar`, `GoogleYouTube`, todas sobre la autenticación ya aprobada.
- Snarf puede leer correo, agenda, suscripciones y videos que le gustaron al fundador — verificado en conversación real con datos reales.
- `send_message` y `create_event` existen pero no están expuestos como herramientas autónomas todavía: enviar o crear algo es una acción de alto impacto (Constitution, Artículo VII) que necesita un mecanismo de confirmación que todavía no se construyó.
- Corregido: el renderer de Markdown del frontend no soportaba tablas — se detectó en la primera respuesta real de Gmail (llegó como tabla) y se agregó soporte completo con estilo.
- Ver ADR 0014.

## [2026-07-25] Confirmación en dos pasos para acciones de alto impacto

- `gmail_send_message` y `calendar_create_event` ya son herramientas autónomas de Snarf, con protocolo obligatorio de confirmación: primero propone (vista previa, no ejecuta nada), y solo ejecuta de verdad tras una confirmación explícita del fundador en la conversación.
- Verificado en vivo contra el Calendar real: confirmado que el evento no existía antes de aprobar, y que sí existía después, con los datos correctos.
- Limitación conocida y documentada: la barrera depende de que el modelo siga el protocolo; no hay todavía un control independiente del modelo (por ejemplo, un botón de aprobación en la interfaz).
- Ver ADR 0015.

## [2026-07-25] Rendimiento: TTS bajo demanda real, calentamiento de conexión, fix de scroll

- `/send` ya no genera audio salvo que se pida; nuevo endpoint `/tts` bajo demanda. Como efecto secundario positivo, ahora también se puede escuchar el audio de mensajes de conversaciones pasadas.
- Calentamiento de la conexión con Anthropic al arrancar el servidor: primera consulta real bajó de ~10.8s a ~5s; consultas siguientes, ~1.5-2s (medido, no estimado).
- Velocidad de reproducción por defecto: 1.25x. Botón "escuchar" ahora siempre en su propia línea dentro del globo.
- Corregido bug de scroll en Chrome de escritorio tras respuestas largas (layout flexbox con `justify-content: flex-end` no scrolleaba bien con overflow) — reemplazado por el patrón robusto de wrapper interno.
- Ver ADR 0016.

## [2026-07-25] Gestión de calendarios, organización de Gmail/Drive, fixes de interfaz

- Corregido bug real: en modo "mantener presionado", un error dejaba el chat sin forma de recuperarse sin refrescar. Ahora cualquier interacción limpia el error y reintenta.
- `/transcribe` degrada con gracia (transcript vacío) en vez de tirar un 500 crudo.
- Corregido scroll horizontal: causado por links Markdown sin renderizar (URLs largas sin espacios); ahora los links se renderizan como `<a>` y se agregó `overflow-wrap` como cinturón de seguridad.
- Selector de modo reducido a un ícono chico en la esquina (antes tres botones siempre visibles) — más espacio para el chat.
- Nuevas Capacidades: gestión completa de calendarios (listar/crear/eliminar), organización de Gmail (etiquetas/carpetas) y Drive (crear carpetas, mover archivos, eliminar) — con el mismo protocolo de confirmación en dos pasos para lo irreversible.
- `Orchestrator._handle_tool` refactorizado de `if/elif` a un registro de handlers.
- Verificado en vivo, incluyendo un ciclo completo de creación y eliminación de un calendario real, confirmado independientemente en ambos sentidos.
- Ver ADR 0017.

## [2026-07-25] Gestión de eventos individuales de calendario

- Encontrada y corregida la causa de una contradicción aparente: se había construido gestión de *calendarios* (ADR 0017), no de *eventos individuales* dentro de un calendario — eran cosas distintas, mal comunicadas como si fueran lo mismo.
- Hallazgo adicional real: `calendar_list_upcoming_events` no muestra eventos pasados, por lo que un evento que ya ocurrió parecía "no existir". Se agregó `calendar_search_events` (busca sin restricción de fecha) y se instruyó a Snarf a usarla en vez de asumir que algo no existe.
- Nuevas herramientas: `calendar_search_events` (lectura), `calendar_delete_event` y `calendar_move_event` (alto impacto, con confirmación).
- Resuelto en vivo, a través del chat, el caso real que expuso el problema: encontrado un evento pasado, borrado un duplicado de prueba, y movido el evento correcto entre calendarios — todo confirmado explícitamente y verificado de forma independiente contra la API real.
- Ver ADR 0018.

## [2026-07-27] Auditoría técnica completa y base de calidad (tests, CI, dependencias fijadas)

- Primera auditoría técnica de arquitectura del repositorio completo (no de gobernanza/identidad, esa fue Architecture Review 0001): documento `ARCHITECTURE_AUDIT.md`, 22 secciones, cada hallazgo anclado a archivo y línea. Confirmó que el código es limpio (sin dependencias circulares, sin imports sueltos) pero con cero madurez operacional: sin tests, sin CI, sin versiones fijadas, sin logging estructurado.
- Identificados con evidencia de código, sin haber tocado nada todavía: causa más probable de que las respuestas largas se corten (`max_tokens=1024` fijo en `AnthropicLLM.generate`, sin chequear `stop_reason`), causa más probable de que el push-to-talk deje de andar en iPhone tras el primer uso (el `MediaStream` del navegador se cachea para siempre y nunca se revalida), y causa más probable del botón de enviar cortado en mobile (`min-height: 100vh` conviviendo con `height: 100dvh` en el mismo `body`). Ninguno corregido todavía — quedan para la siguiente fase de trabajo.
- Se fijaron las versiones exactas de todas las dependencias en `requirements.txt` (antes sin pinear); nuevo `requirements-dev.txt` para dependencias de test.
- Primera suite de tests automatizados del proyecto (27 tests, `pytest`): memoria episódica, dispatch de herramientas del Orchestrator, y — el más importante — que las 8 herramientas de alto impacto (Artículo VII de Constitution) nunca ejecutan la acción real sin `confirmed=true`, para las ocho, una por una.
- Primer pipeline de CI (`GitHub Actions`): corre la suite completa en cada push y pull request.
- Ver ADR 0019.

## [2026-07-27] Corrección de los tres bugs reportados

- Respuestas largas cortadas: `max_tokens` fijo en 1024 sin chequear `stop_reason`, subido a 4096, y ahora se agrega una nota visible cuando una respuesta se trunca en vez de devolverla en silencio como si estuviera completa. Verificado con test unitario (cliente falso) y con una llamada real a la API de Anthropic.
- Push-to-talk muerto en iPhone tras el primer uso: el `MediaStream` del micrófono se cacheaba para siempre; en iOS, backgrounding/bloqueo de pantalla suele matar esos tracks sin avisar, produciendo grabaciones vacías. Ahora se pide un stream nuevo en cada grabación y se libera al terminar. **Confirmado por el fundador en su iPhone real**, tanto en modo "mantener presionado" como en modo "toque".
- Botón de enviar cortado en mobile: dos hipótesis iniciales (conflicto `min-height:100vh`/`height:100dvh`; falta de `min-width:0` en el input de texto) resultaron necesarias pero no suficientes, descartadas con evidencia real de capturas de pantalla del fundador. La causa real: la página completa renderizaba más ancha que el viewport del iPhone en todos los modos (no solo en modo texto), y Safari permitía pellizcar para hacer zoom en vez de ajustarla — solo haciendo zoom-out manual se veía todo encuadrado. Corregido agregando `overflow-x: hidden` a `html` y deshabilitando el zoom táctil (`user-scalable=no`), coherente con que esta es una interfaz tipo HUD fija.
- **Los tres bugs confirmados como resueltos por el fundador en su iPhone real.**
- Ver ADR 0020.

## [2026-07-27] Login por contraseña y credenciales de Google por usuario

- Verificado y descartado un temor real del fundador: sus credenciales de Google nunca estuvieron públicas en GitHub (chequeado contra la historia completa de git y el remoto real), pero la arquitectura sí asumía un único usuario implícito, sin forma de que un segundo usuario conectara su propio Google sin pisar el token del fundador.
- `GoogleAuth` ahora recibe `user_id` y guarda el token en `credentials/tokens/<user_id>.json` (antes un único archivo global); `Orchestrator` recibe `user_id` explícitamente (`DEFAULT_USER_ID = "fundador"` por ahora).
- Nuevo login real: página `web/login.html`, cookie de sesión firmada con `itsdangerous`, contraseña en `SNARF_ACCESS_PASSWORD`, falla cerrado (no abierto) si falta configuración. `/send`, `/transcribe`, `/tts` y `/conversations*` ahora exigen sesión válida — antes la única barrera era la red (Tailscale/LAN).
- Evaluado y pospuesto a propósito: login con Google (el camino correcto para cuando haya multi-usuario real, ya que Snarf ya pide ese mismo consentimiento) y con Apple (no es simple como se asumió, y no destraba nada hoy).
- 11 tests nuevos de autenticación; en el camino se encontró y corrigió un bug real en dos tests existentes que disparaban una llamada real a la API de Anthropic vía el hook de arranque, detectado por duración anómala de la suite.
- Confirmado por el fundador en su navegador real, contra el servidor de producción reiniciado.
- Ver ADR 0021.

## [2026-07-27] Dashboard v1 y plan por fases

- Antes de construir nada, se documentó en ADR 0022 el alcance real y un plan por fases: la visión original del fundador (paneles de Trading, Mercado, GitHub, MCP, y una visualización de red neuronal tipo "Jarvis brain") no tiene todavía ninguno de esos subsistemas construidos, así que la v1 se limita a datos 100% reales, y el resto queda registrado como fases futuras explícitas en `MASTER_MAP.md` (Roadmaps).
- Nuevo endpoint `GET /dashboard/summary`: estado de capacidades (LLM/STT/TTS, y si el usuario actual tiene a Google conectado vía `credentials/tokens/<user_id>.json`) y estadísticas reales de memoria episódica (`EpisodicMemory.stats()`, nuevo: total de mensajes y conversaciones, fecha más antigua/reciente, actividad de los últimos 14 días).
- Nueva vista Dashboard en `web/index.html`, alternable con el Chat por botón (📊) y por swipe táctil horizontal, con layout en grilla responsive (una columna en mobile, varias en desktop aprovechando el ancho disponible). Tres widgets: Estado del sistema, Conversaciones (con gráfico de barras de actividad reciente) y Memoria episódica.
- Nuevo menú de usuario en el sidebar (usuario actual + desplegable con "cerrar sesión" y un placeholder de "configuración, próximamente"), reemplazando al botón de cerrar sesión suelto.
- Explícitamente pospuesto y documentado en ADR 0022: widgets de Capacidades que no existen todavía (Fase 2), y aplicación de escritorio nativa multi-ventana junto con la visualización de red neuronal (Fase 3) — esta última requiere antes un registro real de eventos del `Orchestrator` que hoy no existe.
- 6 tests nuevos (47/47 en total). Verificado por API real contra una instancia aislada en el puerto 8001 (misma práctica que ADR 0020/0021, sin tocar el servidor real del fundador en el puerto 8000) y el JavaScript validado sintácticamente. Pendiente de confirmación visual del fundador en su navegador real — no hay navegador ni motor de automatización disponible en este entorno de desarrollo.
- Ver ADR 0022.

## [2026-07-27] Íconos propios, widgets de Google, configuración de widgets y layout Jarvis en desktop

- Reemplazados todos los íconos de emoji de la interfaz (menú, alternar dashboard/chat, modos de entrada, configuración, cerrar sesión) por SVG propios de trazo delgado, coherentes con la estética HUD ya existente — sin librería externa ni CDN.
- Cuatro widgets nuevos con datos reales, de solo lectura: Google Drive (últimos 5 archivos modificados), Gmail (últimos 5 mensajes), Calendar (próximos 5 eventos), YouTube (últimas 5 suscripciones). Corrige un error de alcance de ADR 0022: estas Capacidades ya existían desde ADR 0013/0014, no eran hipotéticas — no debieron quedar pospuestas a "Fase 2".
- Nuevo panel de configuración (reemplaza el placeholder "próximamente" del menú de usuario): un interruptor por widget para elegir qué mostrar, persistido por usuario en `data/dashboard_prefs/<user_id>.json` (nuevo módulo `snarf/runtime/dashboard_prefs.py`, endpoints `GET`/`PUT /dashboard/preferences`).
- Paneles reordenables arrastrando: mouse en desktop (arrastre inmediato desde un asa dedicada), mantener presionado ~350ms y arrastrar en mobile (mismo mecanismo con Pointer Events para ambos). El orden se guarda junto con la visibilidad.
- Layout "Jarvis" en desktop ancho (`min-width: 900px`) con el Dashboard activado: el chat queda centrado (mismo componente, no una copia) y los widgets rodean alrededor — arriba (actividad de conversaciones), izquierda (lista de conversaciones siempre visible + estado del sistema), derecha (memoria, Drive, Gmail, Calendar, YouTube, estos sí reordenables). En mobile, o en desktop sin el Dashboard activado, se mantiene el comportamiento de ADR 0022 (una vista a la vez).
- Corregida una vulnerabilidad real encontrada en el camino: los datos de Gmail y Calendar no los controla el fundador (el asunto de un email lo define quien se lo envía) — insertarlos sin escapar en el HTML habría sido XSS real. Se agregó `escapeHtml()` y se aplicó a todo campo de origen externo, y por defensa en profundidad también al título de conversación de la lista lateral.
- 21 tests nuevos (68/68 en total). Verificado por API real contra una instancia aislada (puerto 8001) incluyendo los cuatro widgets de Google contra la cuenta real del fundador; JavaScript validado sintácticamente y HTML verificado con balance de tags. **Pendiente crítico:** ni el layout Jarvis ni el arrastre para reordenar fueron vistos en un navegador real — se pide explícitamente confirmación visual del fundador antes de seguir construyendo sobre este layout.
- Ver ADR 0023.

## [2026-07-27] Fixes de layout Jarvis, CI y arrastre; widgets más útiles

- **Layout Jarvis roto en desktop, corregido:** faltaba `position: relative; z-index: 2` en `#appRoot` — los fondos fijos de la interfaz pintaban por encima de las tres zonas nuevas (arriba/izquierda/derecha), que estaban geométricamente bien ubicadas pero invisibles. Encontrado con `document.elementFromPoint` usando Playwright (Chromium headless), instalado en este entorno por primera vez para poder verificar visualmente en vez de a ciegas.
- **CI roto en GitHub Actions, corregido:** `pythonpath = .` agregado a `pytest.ini` — el workflow corre `pytest` a secas (no `python -m pytest`), que nunca agregó el directorio del proyecto a `sys.path`. Bug preexistente, no introducido por el trabajo de hoy; encontrado revisando el run fallido que el fundador vio pasar por el widget de Gmail.
- **Arrastre para reordenar paneles, roto en celular real, corregido:** se cancelaba el gesto si el dedo se movía más de 6px durante los 350ms de espera — umbral irreal para un toque humano. Eliminada esa cancelación (el asa ya bloquea el scroll nativo con `touch-action: none`, así que no protegía nada) y agrandada el área táctil del asa.
- **Widgets con más contexto:** subtítulo corto en cada uno explicando qué muestra; Drive ahora enlaza a cada archivo real y muestra fecha/tamaño; Gmail enlaza a cada mensaje real; Calendar enlaza a cada evento real; YouTube enlaza a cada canal real. Nuevo selector dentro del propio widget de Gmail para elegir cuántos mensajes ver (5/10/20), persistido por usuario.
- 5 tests nuevos (73/73). Primera verificación con navegador real del proyecto: capturas de pantalla de desktop y mobile después de cada fix, y una simulación de arrastre táctil con jitter realista.
- Ver ADR 0024.

## [2026-07-27] Interpretación de Gmail: primer Especialista Cognitivo real

- Nuevo `snarf/specialists/gmail_digest.py` (`GmailDigestSpecialist`): primer Especialista Cognitivo real del proyecto (la capa existía documentada desde ADR 0004 pero vacía). Razona sobre la bandeja de entrada de Gmail con su propio system prompt (agrupa por categoría, señala qué conviene revisar y por qué), reutilizando las Capacidades `GoogleGmail` y `AnthropicLLM` ya existentes.
- Nueva herramienta de chat `gmail_summarize_inbox`: Snarf puede interpretar el correo cuando se le pida, sin necesitar confirmación (es de solo lectura). Por defecto devuelve la interpretación ya cacheada; `force_refresh=true` genera una nueva.
- Nuevo refresco automático en segundo plano: primer componente de Snarf que actúa sin que medie un pedido del fundador — un loop de `asyncio` en `app.py` reinterpreta la bandeja cada `GMAIL_DIGEST_REFRESH_MINUTES` (30 por defecto), solo si hay Google conectado y LLM disponible.
- Widget de Gmail del dashboard ampliado con un botón "interpretar bandeja" y el texto de la última interpretación, en Markdown.
- 18 tests nuevos (91/91 en total).
- Ver ADR 0025.

## [2026-07-27] Refresco de Gmail bajo demanda, reusabilidad de Capacidades/Especialistas, costo de tokens

- **Corregido a pedido del fundador:** eliminado el loop de refresco en segundo plano de ADR 0025. Ahora es 100% impulsado por el navegador — se dispara al abrir el dashboard (comparando barato el último mensaje contra la interpretación cacheada) y se repite cada 5 minutos solo mientras el dashboard sigue abierto y visible (pausado con la Page Visibility API). Cero costo cuando no se está usando.
- **Bug real corregido:** arrastrar paneles en el navegador de escritorio no funcionaba — el mousedown disparaba selección de texto nativa, y los listeners de arrastre estaban en el asa (chica) en vez de en `document`, así que dejaban de recibir eventos en cuanto el cursor se alejaba. Verificado esta vez con un arrastre de mouse real (no sintético).
- **Bug real corregido:** el botón de modo de entrada (mantener/toque/texto) no hacía nada — un bug latente de ADR 0023: al reemplazar emojis por íconos SVG, un chequeo de `e.target !== modeFab` dejó de funcionar porque el clic ahora aterriza en el `<svg>` hijo, no en el botón.
- Tipografía monoespaciada reemplazada por la pila de San Francisco (`-apple-system`/`system-ui`) — más legible, mismo estilo Jarvis.
- **Reusabilidad de Capacidades/Especialistas garantizada con un test** (`tests/test_architecture_boundaries.py`): nunca importan `snarf.core`, `snarf.runtime` ni `app.py` — ya era cierto por diseño, ahora queda fijo para que no se erosione.
- **Primera optimización real de costo de tokens:** el system prompt de Snarf (idéntico en cada llamada, en cualquier conversación) ahora usa prompt caching de Anthropic. La interpretación de Gmail pasa a usar `claude-haiku-4-5` (más barato) en vez del modelo principal de Snarf — es una tarea de categorización acotada, no conversación con identidad.
- 3 tests nuevos (93/93 en total).
- Ver ADR 0026.

## [2026-07-27] Panel superior movible y transparencia de paneles/burbujas

- El panel de arriba (Conversaciones) ya no está fijo — se fusionó con la columna derecha en un solo grupo reordenable: el primer widget del orden ocupa la franja superior, el resto la columna derecha. La columna izquierda (conversaciones + estado del sistema) sigue fija, a pedido explícito del fundador.
- `makeReorderable` generalizada para reordenar entre varios contenedores a la vez, no solo dentro de uno.
- Paneles y burbujas de chat pasan de un tinte plano a un degradé radial (centro más visible, bordes más oscuros) con vidrio esmerilado, coherente con el resto de la estética Jarvis — confirmado que la línea de escaneo de fondo sigue pasando por detrás.
- Verificado con Playwright (arrastre de mouse real, promoviendo un widget a la franja superior) y con captura de pantalla.
- Ver ADR 0027.

## [2026-07-27] Textura de paneles, tipografía y modos de entrada simplificados a dos

- Degradé más marcado (centro claro, bordes oscuros) con resplandor cian interior en paneles y burbujas de chat; títulos de widget menos pesados visualmente (peso 400 en vez de 500, tamaño levemente mayor).
- Selector de modo de entrada simplificado de tres modos a dos: **toque** (orbe, ahora más chico, ~133px en vez de 180px) y **teclado** (ahora el modo por defecto en desktop y en mobile). Se eliminó "mantener presionado".
- El modo teclado tiene un botón de micrófono embebido junto al campo de texto: graba, transcribe y coloca el texto para revisar antes de enviar, sin una vista previa separada. Botón de enviar rediseñado como flecha hacia arriba.
- Pospuesto explícitamente a una ronda dedicada: ancho variable por widget, zona izquierda flexible, y posición reubicable del módulo de chat — es, en los hechos, un editor de layout tipo grilla genérico, no un ajuste de CSS.
- Verificado con Playwright, incluyendo el flujo completo de grabar-transcribir-completar el campo con un dispositivo de audio falso y una llamada real a la API de transcripción.
- Ver adenda de ADR 0027.

## [2026-07-27] Vidrio esmerilado real en paneles y burbujas (aún sin commitear, a pedido del fundador)

- El primer ajuste de degradé subía la opacidad en vez de bajarla — corregido: menos opacidad en todo el degradé, `backdrop-filter` de 15px + saturación, para que la línea de escaneo y las partículas de fondo se vean difuminadas *a través* de paneles y burbujas, en vez de tapadas.
- Verificado con capturas de pantalla reales.
- Ajuste posterior, misma jornada: el fundador pidió aún más transparencia y *menos* difuminado (para disfrutar la línea con nitidez, no perderla en el blur) — `backdrop-filter` bajado de 15px a 4px y opacidad del degradé reducida más todavía en `.dash-widget`, `.msg.user` y `.msg.snarf`. Verificado con Playwright contra el servidor real.
- Suite completa: 93/93 sin cambios (CSS puro).
- Sin ADR de cierre todavía: el fundador pidió frenar el commit/push hasta terminar de ajustar el look visual.

## [2026-07-28] Vectorización de Google Drive y panel de costo de API en tiempo real

- Nuevo panel "Costo de API" en el dashboard (`snarf/telemetry/`): estima en tiempo real el gasto de Anthropic, ElevenLabs y Voyage a partir de cada llamada real (nunca inventado), con desglose por proveedor y aclaración explícita de que es una estimación según tarifa pública, no el saldo real de cada cuenta.
- Construida la extracción de contenido por tipo de archivo que faltaba desde ADR 0013/0014 (PDF, imagen, audio, video) y el pipeline completo de vectorización de Google Drive (`snarf/knowledge/`): extracción → chunking → embeddings (Voyage AI, `voyage-4-lite`) → `chromadb` local, con progreso reanudable por archivo.
- Cinco herramientas nuevas para Snarf: `drive_index_scan` (solo lectura, cuenta archivos/tamaño por tipo sin gastar nada), `drive_index_start`/`drive_index_status`/`drive_index_stop` (indexación en segundo plano, siempre disparada a pedido explícito, nunca automática) y `drive_search_knowledge` (búsqueda semántica sobre lo ya indexado).
- Evaluada y pospuesta a propósito una infraestructura multi-usuario para esto: no existe todavía un segundo usuario real: los datos quedaron namespaced por `user_id` desde el día uno para que agregarlo, cuando corresponda, sea pasar otro `user_id`, no rediseñar el pipeline.
- `drive_index_scan` corrido en vivo contra el Drive real del fundador (37.479 archivos indexables + 5.251 carpetas, ~820GB): el mayor consumidor de espacio es video (1.824 archivos, ~576GB), seguido de una categoría "other" sin extractor hoy (9.854 archivos, ~230GB) — PDF, imagen, audio y texto/Google Docs juntos son una fracción menor del total (~20GB).
- Nuevo `drive_index_catalog_unsupported` + alias `query='free_tier'`, y corrido en vivo también: de los ~230GB de "other", ~212GB son software (instaladores ZIP, artefactos de un proyecto Unity) sin valor de conocimiento personal; el resto son robots/indicadores de trading reales en `.zip`/`.rar`/`.dll` (identificables por nombre, no extraíbles como texto) y, sin buscarlo, 95 `.docx` + 41 `.epub` + otros documentos personales genuinamente valiosos que hoy no tienen extractor — candidatos claros para una próxima ronda.
- Corregido un bug real encontrado en el camino: un archivo marcado `error` en el manifest (por ejemplo, por falta de `VOYAGE_API_KEY`) quedaba descartado para siempre en vez de reintentarse en la próxima corrida.
- 67 tests nuevos (160/160 en total). Encontrado y corregido durante la construcción: un fallo real en el extractor (no solo un tipo no soportado) tiraba abajo el thread de indexación entero en silencio, sin registrar nada — cubierto con test de regresión.
- Ver ADR 0028.

## [2026-07-28] Extractores de Office, registro real de actividad, y visión de negocio registrada

- Nuevos `DocxExtractor`/`PptxExtractor`/`XlsxExtractor` (`.docx`/`.pptx`/`.xlsx`) sumados al tier gratuito de vectorización de Drive — los documentos personales reales que aparecieron en el catálogo de "other" (planes de negocio, etc.) ahora sí tienen extractor, sin costo de API.
- Nuevo registro real de actividad del Orchestrator (`snarf/telemetry/activity_log.py`, `GET /dashboard/activity`): qué herramienta se ejecuta, cuándo, y con qué resultado — la base de datos real que pedía el fundador antes de construir cualquier visualización tipo "cerebro de Snarf". Sin widget visual todavía, a propósito.
- El fundador planteó una visión mucho más amplia (dashboard de costos/ingresos/mercados/campañas de negocio, reemplazo de sus chatbots externos con migración de "Proyectos" de ChatGPT, arquitectura de Especialistas por dominio, creación/exportación de documentos, onboarding). Se registró completa en `MASTER_MAP.md` con el orden de ejecución acordado, sin construir las piezas grandes todavía — varias necesitan una fuente de datos real (costos, ingresos, mercado) que hoy no existe, y este proyecto no muestra datos inventados.
- 23 tests nuevos (183/183 en total).
- Ver ADR 0029.

## [2026-07-28] Snarf crea, recibe y vectoriza archivos reales; corregido rate limit de Voyage; piloto de video verificado

- **Vectorización de Drive corriendo de verdad**: `VOYAGE_API_KEY` configurada, con método de pago agregado por el fundador para destrabar el límite de 3 requests/minuto de las cuentas nuevas de Voyage (bug real corregido: `VoyageEmbeddings` no pasaba `max_retries` al SDK, así que la mayoría de los embeddings fallaban directo en vez de esperar y reintentar). También se corrigió el alcance real de `query='free_tier'`: `contains 'text/'` traía miles de archivos de código fuente/configuración de un backup de Python/Unity que Drive clasifica como texto — acotado a `text/plain` exacto.
- **Piloto de video verificado en vivo**: 19 archivos reales (carpeta "Grabaciones", 10.4GB) — transcripción + vectorización, 0 errores, **$2.03 de costo real medido** (no estimado). Extrapolación a los ~576GB de video totales: ~$40 y ~18 horas, basada en la proporción real GB→minutos del piloto, no en una suposición a ciegas.
- **Snarf puede crear archivos reales**: `DocumentBuilder` (Markdown/PDF/PPTX/XLSX, todo local) + `GoogleDrive.upload_file` (con conversión real a Google Doc/Sheet/Slide nativo al subir, sin necesitar la API de Google Docs aparte) + `DocumentPublisher`. Tres herramientas nuevas: `drive_create_document`, `drive_create_spreadsheet`, `drive_create_presentation` — devuelven el link real de Drive y quedan indexados al instante.
- **Snarf puede recibir archivos**: nuevo `POST /files/upload` + botón de adjuntar en la interfaz. Todo lo subido se guarda en la carpeta `Snarf - Archivos` y se indexa de inmediato; si es una imagen, la descripción que genera la visión se devuelve directo al chat.
- Reorganizado el roadmap en `MASTER_MAP.md` a pedido del fundador: **Fundación técnica** (vectorización de Drive, archivos, migración a un VPS Linux, segundo usuario de prueba) tiene que cerrarse antes de sumar **Capacidades** nuevas (mercado, ChatGPT, cerebro Jarvis, negocio). La migración a VPS pasó de "buena idea" a "primero de lo que sigue": el fundador reportó que la interfaz se sentía lenta incluso antes de la indexación, accediendo desde el celular a través de un túnel hacia la Mac — la ruta de red completa es la causa raíz más probable, no solo la carga del indexado.
- 33 tests nuevos (216/216 en total). Verificado en vivo contra el Drive real: un Markdown, un Google Doc (por conversión real) y un Excel, los tres creados, indexados, y encontrados con una búsqueda semántica real inmediatamente después.
- **Adenda, misma jornada**: el fundador preguntó cómo evitar que los archivos que Snarf crea queden duplicados (el real en Drive + una copia local desperdiciando espacio en el futuro VPS). Aclarado y verificado: nunca hubo duplicación — lo local siempre fue el índice vectorial (texto+embeddings), nunca el archivo.
- **Segunda adenda, misma jornada**: el fundador pidió una distinción más fina — además de Drive, poder mandar un archivo directo a su propio dispositivo (con el diálogo nativo de "Guardar como" de su sistema operativo), y reservarse solo para él la opción de usar el disco del propio servidor como carpeta de trabajo. `destination` pasa a tener tres valores: `drive`, `device` (nuevo endpoint `GET /files/local/<user_id>/<archivo>`, con su link de descarga real) y `server` (mismo mecanismo, sin link, exclusivo del fundador — `allow_server_storage` gateado en código y en el prompt). 19 tests nuevos (235/235 en total). Verificado en vivo: `device` y `server` ambos crean el archivo real en disco, indexado, sin ninguna llamada a Drive; `device` con su `download_url` real y funcional.
- Ver ADR 0030.

## [2026-07-29] Indexación desacoplada de la sesión, runbook de VPS, y cookie de sesión endurecida

- El proceso de vectorización del tier gratuito se relanzó como proceso desacoplado de verdad (`nohup` + `disown`, reparentado a `init`) — antes moría si se cerraba la sesión de Claude Code; ahora sobrevive, incluida la propia Mac quedando sin esa terminal abierta.
- Nuevo `VPS_MIGRATION.md`: runbook completo (sin ejecutar) para el ítem 4 de la Fundación técnica. Recomienda seguir usando Tailscale desde el VPS en vez de montar un dominio público — mismo mecanismo ya probado (ADR 0008), que además resulta ser el "túnel" que el fundador no identificaba al describir la lentitud de la interfaz.
- Corregido un detalle de seguridad real encontrado al preparar el runbook: la cookie de sesión no tenía `secure=True`. Agregado — defensa en profundidad, no depender de que Tailscale sea la única capa de HTTPS. Los `TestClient` de los tests pasaron a `base_url="https://testserver"` para poder seguir probando el login con la cookie marcada `Secure`.
- 1 test nuevo (236/236 en total).

## [2026-07-29] Cerebro de Snarf — visualización tipo Jarvis del Orchestrator

- El fundador reordenó el plan del día: antes de migrar a VPS o seguir indexando Drive, construir la visualización "cerebro de Snarf" — el prerrequisito (registro real de actividad, ADR 0029) ya estaba listo y es lo que más necesita ahora para entender el estado del sistema.
- Relevadas todas las fuentes de datos reales antes de diseñar: `activity_log.jsonl` (el prerrequisito nombrado) estaba en la práctica vacío (cero eventos desde que se instrumentó); la fuente rica en datos reales hoy es `usage_log.jsonl` (4.126 líneas, de la corrida de indexación con Voyage) y el manifiesto de indexación ya persistido (4.618 archivos). El diseño combina las tres fuentes.
- Nuevo `snarf/telemetry/brain.py`: mapea las 35 herramientas reales del Orchestrator y los 3 vendors reales (Anthropic/ElevenLabs/Voyage) a 9 nodos de Capacidad + el nodo central Orchestrator, con un test de regresión que impide que una herramienta nueva quede sin mapear en silencio. Nuevo endpoint `GET /dashboard/brain`.
- Nuevo widget "Cerebro" en el dashboard: mini-grafo con tamaño de nodo real (nunca vacío), que se expande a pantalla completa con el grafo grande + un feed de actividad en vivo. Pulsos de luz animados (SVG `animateMotion`) viajan del centro a cada nodo en cada evento real, con el mismo patrón de polling 100% impulsado por el navegador que el digest de Gmail (solo mientras la pantalla está abierta y visible).
- 17 tests nuevos (253/253 en total). Verificado en vivo con Playwright (login real, desktop y mobile, sin errores de consola ni requests fallidos) — capturas confirman nodos de tamaño real distinto y el feed mostrando actividad real.
- Ver ADR 0031.
- **Bug real encontrado al verificar en vivo, corregido en el momento**: `secrets.compare_digest` no acepta `str` con caracteres no-ASCII (tildes, ñ) — el login del fundador tiraba un 500 en vez de comparar la contraseña. Corregido codificando ambos lados a bytes antes de comparar (1 test nuevo, 254/254).

## [2026-07-29] PDF con fuentes Type3 + fallback de OCR; cerebro de Snarf con dos capas y latido diferenciado

- **Bug real reportado por el fundador**: ciertos PDFs (exportados desde apps móviles/navegadores) usan fuentes Type3 embebidas — el texto es seleccionable/copiable en cualquier visor real, pero `PdfExtractor` (basado en `pypdf`) devolvía texto vacío o basura. Reescrito sobre PyMuPDF (`fitz`), que resuelve el CMap/ToUnicode de Type3 de forma nativa. Decisión de licencia explícita con el fundador: PyMuPDF es AGPL-v3 (elegida sobre la alternativa MIT `pdfplumber`, con Type3 menos confiable) — sin problema para uso interno, a revisar si Snarf se ofrece como servicio a terceros a futuro.
- Nuevo fallback de OCR con Tesseract (`spa+eng`, paquete de idioma español instalado en el entorno del fundador) para PDFs sin ninguna capa de texto real — rasterizado con la misma librería, sin dependencia extra. Si ninguna estrategia encuentra texto usable, ahora se declara explícito (`skipped_reason`) en vez de indexar contenido vacío en silencio.
- **Cerebro de Snarf, con capturas de referencia de Jarvis (Iron Man) como guía**: pasa de un anillo plano de 9 nodos a dos anillos — Especialistas Cognitivos (interno, hoy solo el digest de Gmail) y Capacidades (externo) — reflejando la arquitectura real de tres capas del proyecto (COGNITION.md, ADR 0003) en vez de una lista arbitraria. El nodo "voz" se separó en `stt`/`tts` (dato que `usage_log` ya distinguía, antes escondido).
- Cada nodo late distinto según su estado real: latido rápido y brillante si tuvo actividad en los últimos 60 segundos, latido lento de espera si no — nunca apagado del todo, nunca inventando actividad que no ocurrió. Un edge activo suma además un flujo continuo de luz (CSS puro) sobre el pulso puntual por evento que ya existía.
- 15 tests nuevos (264/264 en total). Verificado en vivo con Playwright: los 12 nodos renderizan sin recortes de etiqueta (el viewBox del SVG se ajustó de 400×400 a 500×500 para el nuevo layout de dos anillos), en desktop y mobile, sin errores de consola; el estado activo/idle confirmado inyectando un snapshot controlado.
- Ver ADR 0032.

## [2026-07-29] Cerebro de Snarf: anillo de entrada, paleta real de marca, nodos fantasma

- Con capturas de referencia del cerebro de Jarvis en *Avengers: Age of Ultron*, tercera vuelta sobre el cerebro: nodos de entrada (texto/voz/archivo), múltiples niveles de profundidad, y una paleta de colores saturados estilo Iron Man/neón. Límite puesto explícitamente antes de construir: se distingue por tipo real de archivo (imagen/audio/video/documento, `categorize_mime`), no por género semántico (canción vs. podcast) — eso el sistema no lo sabe, y mostrarlo sería inventar un dato.
- **Paleta no inventada**: se buscó en el Drive ya indexado del fundador y se encontró el documento real `PALETA DE COLORES JERE MASIH TRADER` — su paleta de marca de trading, con los hex exactos que pidió (Magenta, Aqua, Violeta, Verde, sobre negro/violeta oscuro). Usada tal cual, sumando rojo/blanco/gris/amarillo para los estados que faltaban.
- Nuevo `snarf/telemetry/input_log.py`: primera instrumentación real de los tres puntos de entrada a Snarf (`/send`, `/transcribe`, `/files/upload`) — ninguno emitía ningún evento hasta ahora. Nuevo anillo "Entrada" en el cerebro (el más interno), con `input_text`/`input_voice`/`input_file`.
- Nuevo estado "fantasma" (gris, sin animación) para nodos que nunca tuvieron actividad real — distinto de "en espera" (sí tiene historia, no reciente).
- **Bug real encontrado y corregido en la propia verificación en vivo**: la regla base de nodos/pulsos traía un color por defecto que, por orden de declaración en la hoja de estilos, pisaba siempre a la clase de color real de cada nodo — todo se veía aqua sin importar el tier. Corregido quitando ese default; cada nodo real ya lleva su propia clase de color explícita.
- 19 tests nuevos (273/273 en total). Verificado en vivo con Playwright, incluida una inyección de snapshot con actividad en todos los tiers para confirmar la paleta completa funcionando junta (magenta, violeta, blanco, aqua).
- Ver ADR 0033.

## [2026-07-29] `drive_read_file` extrae de verdad; el cerebro gana partículas, resplandor y cámara

- **Bug real reportado por el fundador**: probó el fix de PDF con un archivo real (`Peso_16-07-2026.pdf`, composición corporal con fuentes Type3) y Snarf seguía devolviendo bytes crudos. Causa real: `drive_read_file` (la herramienta de lectura en el chat) nunca pasaba por `ContentExtractor`/`PdfExtractor` — llamaba directo a `GoogleDrive.read_file_text()`, que decodifica cualquier binario como UTF-8 a lo bruto. El fix de ADR 0032 solo tocaba el camino de indexación, no este.
- `Orchestrator._read_drive_file` ahora reusa `ContentExtractor` — un solo camino de verdad para extraer contenido de Drive, con OCR automático para PDF escaneado, visión para imagen, transcripción para audio/video. **Verificado en vivo**: el PDF real del fundador ahora extrae el análisis de composición corporal completo y legible.
- **Instancia real del fundador (puerto 8002) reiniciada**: corría desde el lunes con el código viejo en memoria — Python no recarga solo. Relanzada con `nohup`/`disown` (mismo patrón que el indexado), confirmada contra el mismo entorno virtual.
- **Cerebro de Snarf, cuarta vuelta**: nueva capa `<canvas>` de partículas — ambiente con resplandor real (blending aditivo, no un blur simulado), estallido de partículas por cada evento real (coloreado según el nodo o rojo si fue error), y una cámara que hace zoom hacia el nodo que se activa (~1.55x, ~2.4s) y vuelve sola a la vista general. SVG y canvas se mueven siempre juntos (un solo transform compartido) para que el zoom nunca desalinee las dos capas. Primera vez que el proyecto usa canvas — todo lo anterior sigue siendo SVG/CSS.
- **`/send` degrada con gracia ante un fallo real del LLM**: encontrado al cerrar la jornada — la cuenta de la API de Anthropic del fundador (separada de su suscripción de Claude Pro) se quedó sin crédito, y `/send` tiraba un HTTP 500 crudo en vez de un mensaje entendible. `Orchestrator.handle()` ahora envuelve la llamada al LLM en `try/except`, mismo criterio que ya usaba `/transcribe` para fallos de STT.
- 3 tests nuevos (276/276 en total). Verificado en vivo con Playwright: partículas con resplandor real en desktop y mobile, cámara confirmada en zoom real inyectando un evento controlado, loop de animación confirmado apagado tras cerrar (sin fugas). Instancia real reiniciada dos veces en la jornada, la segunda con este último fix.
- Ver ADR 0034.

## [2026-07-29] Grilla de dashboard unificada y redimensionable, modo enfoque, tres bugs de UI

- **Tres bugs reales corregidos**: texto redundante en modo teclado ("escribí tu mensaje", cuando el placeholder ya decía lo mismo); la app abría el teclado nativo en mobile al arrancar sin que el usuario tocara nada (`textInput.focus()` disparándose solo); y "escuchar" a veces no generaba audio — en realidad sí lo generaba, pero `sharedAudio.play()` fallaba en silencio (política de autoplay, o una carga interrumpida por otro click) y el reproductor flotante igual se mostraba como si estuviera sonando. Los tres corregidos, el último con el error ahora visible en vez de tragado.
- **Grilla de dashboard unificada (solo desktop, ≥900px)**: reemplaza las tres zonas fijas de antes por una sola grilla de 12 columnas donde todo bloque —incluidos el historial de conversaciones y el chat con Snarf, antes fijos y fuera del sistema de widgets— se puede arrastrar para reposicionar y redimensionar (ancho y alto) libremente, con la posición/tamaño guardados por usuario. Reordenamiento actualizado de comparar solo altura a comparar altura y ancho (necesario con bloques de tamaño variable). Nuevo mecanismo de resize, mismo estilo que el de reordenar ya existente.
- **Bug real corregido de paso**: `_normalize()` de las preferencias del dashboard reconstruía `widget_options` a mano, hardcodeado solo a la clave de Gmail — cualquier otro dato ahí (por ejemplo, el tamaño de otro widget) se perdía en silencio al guardar. Generalizado a todos los widgets, con validación real.
- **Modo enfoque**: el chat se expande a pantalla completa con la misma barra lateral que ya existía para el menú hamburguesa de mobile (historial, nueva conversación, usuario/configuración) — reusada, no duplicada.
- Desktop arranca siempre en el Dashboard (antes: Chat), con la distribución guardada la última vez.
- **"Proyectos" registrado, no construido**: el fundador pidió, en la misma ronda, que Snarf tenga su propia versión de "Proyectos" al estilo Claude/ChatGPT (prompt de proyecto, archivos organizados en Drive con vectorizado, propuesta automática de carpetas). Es una Capacidad nueva entera — queda registrada en `MASTER_MAP.md`, con su propio ciclo de diseño pendiente, no mezclada con este cambio.
- 10 tests nuevos (285/285 en total). Verificado en vivo con Playwright, incluido contra el archivo real de preferencias del fundador (de antes de este cambio): migró sin intervención manual, con las Capacidades que ya tenía ocultas manualmente siguiendo ocultas. Resize y modo enfoque confirmados con interacciones reales (arrastrar y recargar; enviar un mensaje real y recibir respuesta real dentro del modo enfoque). Mobile confirmado sin ningún cambio.
- Ver ADR 0035.

## [2026-07-29] Análisis de eficiencia de tokens: cacheo del historial de conversación, TTL de 1h, CLAUDE.md

- El fundador pasó tres transcripciones sobre metodología de ahorro de tokens en Claude/Claude Code y pidió analizar la eficiencia real del proyecto. Confirmado contra código y datos reales (`data/usage_log.jsonl`, 53 llamadas del día): el cacheo de system+tools ya funcionaba (`cache_read_tokens` fijo en 14.895 en casi toda llamada real), pero el array de `messages` no tenía ningún punto de cacheo — se reprocesaba entero, a tarifa completa, en cada llamada y en cada ronda del loop de herramientas.
- `AnthropicLLM.generate()` gana un segundo punto de cacheo: el último mensaje de cada llamada (y de cada ronda del loop de herramientas) se marca con `cache_control`, sin mutar nunca la lista original que pasa el llamador. Ambos puntos de cacheo (system+tools, y este nuevo) pasan de TTL default de 5 minutos a 1 hora explícito — Snarf llama a la API directa, no a la suscripción de Claude, así que corría bajo el TTL corto pese a que el patrón real de uso del fundador (entradas y salidas espaciadas, digest de Gmail cada 5 min) se beneficia del TTL largo.
- Nuevo `CLAUDE.md`: índice liviano para sesiones de Claude Code futuras (apunta a `MASTER_MAP.md` y las convenciones ya establecidas, no las repite) — aplicando a las propias sesiones de trabajo el mismo hábito que recomiendan las transcripciones.
- 3 tests nuevos (288/288 en total).
- Ver ADR 0036.

## [2026-07-29] Orden default del dashboard, legibilidad a 1920×1080, y malla volumétrica del cerebro

- **Orden default del dashboard de escritorio**, pedido concreto del fundador: historial a la izquierda (alto completo), cerebro arriba centrado, sistema/costo al lado del cerebro, chat debajo, y conversaciones/memoria/Drive/Gmail/Calendar/YouTube formando una columna a la derecha que sigue bajando. Logrado reordenando `WIDGET_IDS` y ajustando `DEFAULT_SPANS` (backend + espejo en frontend) — el auto-flow disperso de la grilla (ADR 0035) hace el resto. El archivo real de preferencias del fundador se regeneró directamente al nuevo orden (cambiar el default de Python no alcanza para una preferencia ya guardada), preservando su elección manual de ocultar YouTube.
- **Legibilidad a 1920×1080**: `rem` es siempre relativo al `<html>` raíz, no al ancestro más cercano — el tamaño de fuente base del modo escritorio sube de 16px (default del navegador, sin ajustar hasta ahora) a 18px dentro del mismo breakpoint de ancho ya existente, sin tocar cada clase suelta. Mobile no se toca.
- **Cerebro de Snarf, quinta vuelta, con capturas reales de la escena de creación de Ultron** (*Avengers: Age of Ultron*): nueva capa de malla de filamentos sobre el canvas de partículas ya existente — satélites alrededor de cada nodo real, coloreados con el color real de ese nodo/tier, enlazados con sus vecinos más cercanos (incluso entre nodos distintos, para que lea como una masa conectada y no triángulos sueltos). Nueva aura volumétrica (gradiente radial con respiración lenta) y viñeta de fondo, más brillo en el nodo central y el latido activo. Ninguna lógica real de datos se tocó — es pura atmósfera, igual que las partículas ambiente ya existentes. Se aclaró explícitamente el límite de ADR 0006 (no reproducir el esquema de color literal de la franquicia): se toma el estilo, no los colores azul/dorado — la paleta real Jere Masih Trader se mantiene.
- De paso, el fundador preguntó por qué Snarf no usa MCP y pidió una política Skills-vs-MCP para este repo — respondido y registrado en `CLAUDE.md` (es una convención de cómo trabajamos con Claude Code en este proyecto, no una decisión de arquitectura de Snarf-producto).
- 288/288 tests (sin tests nuevos — cambio mayormente visual/frontend). Verificado en vivo con Playwright a 1920×1080 (orden de bloques, tamaño de fuente, cero errores de consola) y en mobile (390×844, sin cambios, tamaño de fuente vuelve a 16px). Cerebro verificado a pantalla completa en ambos anchos, loop de animación confirmado apagado al cerrar.
- Ver ADR 0037.

## [2026-07-29] Mensaje honesto cuando el STT falla de verdad (no cuando no se escuchó nada)

- **Bug real reportado por el fundador**: el botón de micrófono "no transcribía". Causa real, encontrada en el log del servidor real: la cuenta de ElevenLabs se quedó sin crédito (`quota_exceeded`, 0 créditos restantes) — el STT (Scribe v1) fallaba en cada intento. `/transcribe` ya degradaba con gracia (nunca un error crudo), pero devolvía siempre `{"transcript": ""}`, indistinguible de un silencio genuino — la interfaz le decía "no se escuchó nada, probá de nuevo" aunque el micrófono hubiera funcionado perfecto y reintentar no fuera a cambiar nada.
- `/transcribe` ahora suma un campo `error` solo cuando el STT en sí lanzó una excepción (nunca en los casos de audio corto o sin credenciales, que siguen siendo `{"transcript": ""}` sin más). El frontend (los dos flujos de grabación, modo tap y modo teclado) muestra ese mensaje real en vez del genérico cuando está presente.
- Aclarado aparte, a pedido del fundador: cambiar la *voz* de ElevenLabs no ahorra crédito (la tarifa de TTS depende del modelo — `eleven_multilingual_v2` hoy — no de qué voz premade se elige); y el STT (`scribe_v1`) no tiene tiers de calidad para elegir, así que no hay ningún ajuste de configuración que resuelva una cuota agotada — solo cargar crédito o esperar la renovación del plan.
- 1 test nuevo (289/289 en total). Verificado en vivo con Playwright interceptando `/transcribe` para simular el fallo real sin gastar crédito.

## [2026-07-29] TTS pasa a eleven_turbo_v2_5 (mismo costo que Flash, mejor calidad)

- El fundador preguntó cómo abaratar ElevenLabs. Confirmado contra la documentación oficial (no una suposición): `eleven_multilingual_v2` (el modelo que usábamos) cuesta 1 crédito/carácter; `eleven_turbo_v2_5` y `eleven_flash_v2_5` cuestan la mitad (0.5 créditos/carácter) — mismo precio entre sí, Turbo con mejor calidad/profundidad emocional que Flash a cambio de ~200ms más de latencia (250-300ms vs ~75ms), diferencia irrelevante para Snarf porque la síntesis ocurre después de que el LLM ya generó la respuesta completa, no en streaming en vivo.
- `ElevenLabsTTS.DEFAULT_MODEL` pasa de `eleven_multilingual_v2` a `eleven_turbo_v2_5` — la mitad de costo por el mismo texto, sin resignar calidad frente a la alternativa igual de barata (Flash).

## [2026-07-29] Cerebro: sin recorte de etiquetas al hacer zoom, menos aspecto de diagrama

- **Bug real reportado por el fundador**: al hacer zoom hacia un nodo (o "en algunas ocasiones"), el texto de otros nodos desaparecía. Causa real, confirmada con un barrido automatizado (no solo mirando capturas): el zoom de cámara escalaba el grafo entero con el origen puesto exactamente en el nodo activo a 1.55x, empujando el lado opuesto del grafo (sobre todo el par diametralmente opuesto Memoria/Calendar) fuera del área visible recortada. Corregido bajando el zoom a 1.14x y mezclando el origen de escala solo 32% hacia el nodo activo (antes 100%) — verificado con Playwright sobre los 15 nodos reales: cero etiquetas recortadas en ningún foco (antes, 7 casos reales).
- **Menos "diagrama de red", más "entidad de luz"**: el fundador señaló que los círculos y las líneas rectas centro-nodo (un literal asterisco) seguían dominando sobre la malla orgánica nueva, con aspecto "rústico". Bajada la opacidad/grosor de esas líneas rectas (siguen existiendo, las necesita el pulso puntual) y sumado un resplandor permanente a los nodos — se sienten orbes de luz fundidos con la malla, no círculos de diagrama técnico.
- 289/289 tests (cambio puramente visual). Ver ADR 0038.

## [2026-07-29] CHARACTER v0.2: ingenio seco, responsabilidad propia, registro y cercanía

- El fundador pasó un prompt de personalidad pensado como imitación directa de J.A.R.V.I.S. (nombrando a Marvel/Iron Man, con "Señor Masih" como eco literal del personaje). Señalado antes de tocar nada: `CHARACTER.md` v0.1 ya tenía, escrita dos veces, la regla contraria explícita — tomar los principios de trato, nunca imitar al personaje por nombre o forma superficial (mismo criterio de ADR 0006 para el cerebro visual). El fundador confirmó mantener esa regla y adoptar solo el espíritu del prompt.
- `CHARACTER.md` pasa a v0.2: nuevo rasgo **ingenio seco** (humor sutil al servicio de un propósito, nunca gratuito); nuevo rasgo **responsabilidad propia** (reconocer un error propio directo, sin sobreactuar); **pensamiento crítico** ampliado (ejecutar con el mismo profesionalismo aunque el fundador no siga una objeción ya señalada); nueva sección **Registro y cercanía** (predominantemente por nombre de pila, más formal ante decisiones críticas o de alto impacto — la formalidad vive en la estructura de la respuesta, nunca en un honorífico; la cercanía puede profundizarse con el historial compartido).
- Deliberadamente no incorporados los marcos de tipificación del prompt original (MBTI/Eneagrama) — etiquetas decorativas para rasgos ya cubiertos de forma conductual, inconsistentes con la voz ya establecida del documento.
- 289/289 tests (cambio de documento, no de código — aplica al reiniciar el servidor real, `load_identity()` lee `CHARACTER.md` de disco al construir el Orchestrator).
- Ver ADR 0039.

## [2026-07-29] Cerebro sin ningún recorte real, reproductor con pausa y siempre visible

- **Bug real, persistente**: el fundador seguía viendo la primera letra de algunas etiquetas del cerebro (Memoria, Conocimiento, Documentos, Orchestrator, Voz, Texto) cortada "en algunos casos". El fix de ADR 0038 (zoom 1.14x) reducía el recorte pero no lo eliminaba del todo — verificado con el mismo barrido automatizado sobre los 15 nodos reales, esta vez exigiendo cero recorte (no solo <50%): quedaban ~15-20 casos de recorte chico, concentrados en las etiquetas más largas de los nodos cercanos al eje horizontal del anillo externo. Zoom bajado a 1.07x, mezcla de cámara a 18% — verificado: cero recorte, ni parcial, en ningún foco.
- **Bug real, causa encontrada con Playwright**: el reproductor de audio flotante tenía `z-index: 9`, por debajo del panel de configuración, el cerebro a pantalla completa y el modo enfoque (10 a 15) — quedaba literalmente tapado e inaccesible detrás de cualquiera de esos paneles mientras el audio sonaba. Subido a `z-index: 20` (por encima de todo lo demás). Confirmado con `elementFromPoint` que el botón ahora sí recibe el click estando el modo enfoque abierto encima.
- **Pausa/reanudar**: nuevo botón en el reproductor, sincronizado con los eventos reales `play`/`pause` del audio (no solo con su propio click) — la etiqueta también pasa a decir "en pausa" en vez de seguir diciendo "reproduciendo" cuando está pausado.
- 289/289 tests. Ver ADR 0040.

## [2026-07-29] Gmail resiliente ante fallos transitorios, uso real por API, y dashboard con tamaños más justos

- **Bug real, causa encontrada inspeccionando el server en vivo**: el widget de Gmail devolvía `[SSL] record layer failure` — la conexión `googleapiclient` cacheada como singleton en `GoogleDrive`/`GoogleGmail`/`GoogleCalendar`/`GoogleYouTube` puede quedar rota en un proceso de larga vida. Nuevo decorador `retry_once_with_fresh_client`: reintenta una sola vez con el cliente reconstruido ante cualquier fallo, sin ocultar un fallo real y persistente. Aplicado solo a lecturas idempotentes, nunca a `upload_file`/`send_message`/mutaciones (riesgo de duplicar el efecto en un reintento).
- Fechas y enlaces reales en Gmail: la lista de mensajes ya tenía el dato (`date`) pero no se mostraba; el digest interpretado por el LLM ahora viene acompañado de una referencia estructurada real (id/asunto/de/fecha) por mensaje, en vez de depender de que la prosa libre del LLM mencione fechas o links (que sería inventar datos).
- Nuevo widget "Uso real de APIs": consumo trackeado localmente (llamadas, tokens, caracteres, segundos) por Anthropic/ElevenLabs/Voyage, más el cupo real de la cuenta de ElevenLabs (`GET /v1/user/subscription`, en vivo) — el panel de costo existente es una estimación en dólares, nunca fue un saldo real, por eso cargar crédito en ElevenLabs no lo movía.
- Tamaños de widgets del dashboard recalibrados usando como evidencia los tamaños que el propio fundador ya había elegido a mano en su layout guardado (no una preferencia estética a ciegas) — solo cambia el default para instalaciones nuevas, el layout ya guardado no se tocó.
- `#textInput` pasa de `<input>` de una línea a un `<textarea>` que crece hasta ~6 líneas visibles antes de scrollear internamente; `Shift+Enter` inserta salto de línea real, `Enter` solo sigue enviando. Mismo tratamiento en el cuadro de revisión de transcripción por voz.
- 305/305 tests. Ver ADR 0041.

## [2026-07-29] Respaldo automático de `data/`

- **Incidente real durante esta sesión**: al verificar en vivo el widget de uso, Claude Code escribió datos de prueba en el `data/usage_log.jsonl` real por error, y al intentar revertirlo con una sintaxis de `head` no soportada en macOS terminó sobreescribiendo el archivo real completo con uno vacío — perdiendo sin posibilidad de recuperación las 4304 líneas de historial real de uso acumulado. No estaba en git (gitignored a propósito), no había snapshot ni backup de ningún tipo.
- Nuevo `snarf/runtime/data_backup.py`: respalda automáticamente memoria episódica, logs de actividad/uso/entrada, preferencias del dashboard, caché del digest de Gmail y archivos locales (no el índice de Drive, regenerable desde la fuente real) a `data_backups/`, con los últimos 14 snapshots. Se dispara al arrancar el server y cada 6 horas mientras corre.
- 305/305 tests. Ver ADR 0042.

## [2026-07-29] Desktop usable de verdad: reintento triple, widgets que no se cortan, Gmail reordenado

- **Bug real, confirmado en vivo**: el reintento único de ADR 0041 no alcanzaba — el mismo `[SSL] record layer failure` podía pegarle también al reintento (falla de red genuinamente intermitente). `retry_once_with_fresh_client` pasa a `retry_with_fresh_client`, con 3 intentos en total y una pausa corta entre cada uno.
- **Bug real de CSS**: al achicar un widget arrastrando su esquina, el título y subtítulo podían recortarse junto con el contenido. Corregido con `flex-shrink: 0` — ahora solo el cuerpo del widget se comprime/scrollea, título y subtítulo quedan siempre completos.
- Gmail: la interpretación de la bandeja ahora va primero, la lista de mensajes (con su selector de cantidad) queda debajo — antes era al revés.
- **Bug real preexistente, no de esta sesión**: en modo desktop, el botón que abre el menú de usuario (configuración del dashboard, cerrar sesión) estaba oculto sin ningún reemplazo — quedaban completamente inalcanzables en escritorio. Restaurado.
- El toggle de modo Toque/Teclado se oculta en desktop (redundante ahí: la caja de texto ya tiene su propio botón de micrófono).
- Confirmado (no es un bug nuevo): los widgets de costo y uso mostrando $0.00/0 caracteres son la consecuencia directa y esperada del incidente de ADR 0042 — el cupo real de ElevenLabs sí se muestra correctamente.
- 305/305 tests. Ver ADR 0043.

## [2026-07-29] El fallo SSL de Google era una condición de carrera, no la red

- **Diagnóstico corregido**: el reintento triple de ADR 0043 no eliminó el error `[SSL] record layer failure` en producción — seguía apareciendo bajo uso real del dashboard. Reproducido a voluntad: 24 llamadas concurrentes reales (`ThreadPoolExecutor`) contra Gmail/Calendar/Drive, compartiendo el `self._service` cacheado de cada Capacidad, producían fallos SSL reales consistentemente; la misma API llamada secuencialmente nunca fallaba. Causa real: FastAPI corre cada endpoint en un thread del pool, el dashboard dispara varios widgets en paralelo, y `httplib2` (la base de `googleapiclient`) no es thread-safe para compartir un cliente entre threads — dos threads leyendo/escribiendo el mismo socket TLS corrompen la conexión.
- `GoogleDrive`/`GoogleGmail`/`GoogleCalendar`/`GoogleYouTube` pasan a cachear su cliente en `threading.local()` — cada thread tiene el suyo, nunca comparte el socket de otro. Verificado: el mismo escenario de 24 llamadas concurrentes reales, ahora con 0 fallos.
- 313/313 tests (8 nuevos verificando aislamiento real entre threads). Ver ADR 0044.

## [2026-07-29] Capacidad "Proyectos" (Mark I)

- Nueva Capacidad completa, registrada desde ADR 0035 y nunca construida hasta hoy: cada Proyecto es una carpeta propia en Drive (con subcarpetas propuestas por un modelo barato según el tipo de proyecto), un prompt/instrucciones propias, y sus propias listas de tareas y notas.
- Prerrequisito resuelto en el camino: "Snarf - Archivos" y la nueva carpeta de Proyectos se unificaron bajo una sola carpeta raíz "Snarf" en el Drive del fundador (migración real verificada: mismos archivos, mismos ids, solo cambió el padre), separada de sus carpetas propias.
- `GoogleDrive` suma `rename_file` (bajo riesgo) y `share_file` (alto impacto, gateado por confirmación — da acceso real a otra persona o vía link público).
- Búsqueda semántica acotada a un proyecto puntual (`project_search`): `POST /files/upload` acepta un `project_id` opcional que sube a la carpeta de ESE proyecto y etiqueta el índice — sin esto, la búsqueda por proyecto habría quedado vacía para siempre.
- 11 herramientas nuevas para el chat (`project_create`, `project_list`, `project_get`, tareas, notas, `project_search`, `project_delete` con confirmación), más endpoints REST para la barra lateral (que ahora tiene un switcher Conversaciones/Proyectos) y un panel de detalle con prompt editable, tareas, notas y link real a Drive.
- 348/348 tests. Verificado con un proyecto real creado y borrado contra el Drive real, y con Playwright de punta a punta en una copia aislada del repo. Ver ADR 0045.

## [2026-07-29] Dial de "Ingenio seco"/sarcasmo configurable

- CHARACTER.md v0.2 → v0.3: el rasgo permanente "Ingenio seco" (ADR 0039, antes fijo y discreto) declara ahora un eje configurable de intensidad — mismo criterio que ya usaba "Registro y cercanía" para variar la formalidad situacionalmente sin dejar de ser un rasgo permanente. El invariante no negociable en ningún nivel: nunca reemplaza la seriedad ante crisis, riesgo de alto impacto o corrección importante.
- Nueva escala 0-10 (medio punto de precisión), con default **7.5** — a pedido explícito del fundador, la única preferencia de este repo donde "sin configurar" es una intensificación deliberada, no "igual que antes". Configurable desde un slider nuevo en el panel de ajustes (primer control deslizante de esta UI) o pidiéndoselo a Snarf directamente por mensaje ("subime/bajame el sarcasmo") vía la tool nueva `personality_set_sarcasm`.
- El nivel se relee en cada turno de conversación (no se cachea como la identidad) — un cambio a mitad de charla se refleja sin reiniciar Snarf. El comportamiento más serio ante una crisis es puro criterio del modelo en el momento: nunca toca el número guardado, para no quedar "pegado" abajo si la conversación corta abrupto a mitad de una situación difícil.
- 369/369 tests. Verificado con Playwright contra una instancia real aislada. Ver ADR 0046.

## [2026-07-29] Proyectos Mark II: conversaciones formalmente asociadas a un proyecto

- Nueva fuente de verdad persistente (`data/conversation_projects.json`, en `EpisodicMemory`) para "a qué proyecto pertenece esta conversación" — reemplaza el enfoque más simple de Mark I.5 (project_id como parámetro por mensaje, nunca persistido), que no alcanzaba para asignar una conversación recién creada o reasignarla más tarde. El tag histórico por-entrada del log se mantiene intacto como auditoría, nunca se reescribe retroactivamente.
- Tools nuevas sin gate de confirmación (reversibles, no tocan terceros): `project_assign_conversation`, `project_unassign_conversation`, `project_list_conversations`. Nuevos endpoints REST: `PUT`/`DELETE /conversations/{id}/project`, `GET /projects/{id}/conversations`.
- `GET /projects/{id}` se enriquece con estadísticas reales (`file_count`, `pending_task_count`, `conversations`) y un resumen generado por Snarf (`cached_summary`, mismo patrón que el digest de Gmail) — completa lo que había quedado pausado de Mark I.5.
- El modal chico de detalle de proyecto se retira: entrar a un proyecto desde la barra lateral ahora la escala para mostrar solo sus conversaciones, y el área de chat muestra el "home" del proyecto (estadísticas, resumen, prompt con contador de caracteres, tareas, notas) mientras no haya ninguna conversación abierta.
- Dos bugs reales encontrados con Playwright y corregidos: `file_count` contaba las propias subcarpetas del proyecto como archivos; volver a "todos los proyectos" cerraba la barra lateral entera en vez de solo la lista.
- 398/398 tests. Verificado de punta a punta con Playwright contra una instancia real aislada (Drive/LLM reales), limpiado sin dejar rastro en producción. Ver ADR 0047.

## [2026-07-29] Proyectos usable de verdad en escritorio, menú contextual, copiar y cerebro vivo

- **Bug raíz encontrado usando la interfaz real**: entrar a un proyecto en escritorio dejaba "una pantalla sin nada" — `enterProject()` llamaba `showChat()`, que apaga el modo Jarvis; en escritorio eso oculta la grilla donde vive reparentado el chat y muestra el `#viewChat` original, vacío desde el arranque. Corregido: `showChat()` solo se llama fuera de escritorio.
- El cajón del hamburguesa en escritorio ya no duplica el historial de conversaciones/proyectos (redundante con el bloque fijo de la grilla) — queda solo para configuración y cerrar sesión.
- Nuevo botón fijo "🏠 home del proyecto" para volver sin salir de la conversación.
- El icono suelto 📁/✕ se reemplaza por un menú contextual (⋮, mismo patrón visual que el menú de usuario) — suma "mover a otro proyecto" dentro de la vista de un proyecto, que antes faltaba.
- Título "(nueva conversación)" que se quedaba pegado para siempre: `sendText()` ahora refresca las listas al completar el primer mensaje.
- Botones de copiar en las respuestas de Snarf: la respuesta completa, y cada bloque de código/entregable por separado (sin arrastrar el comentario alrededor).
- El widget colapsado del cerebro de Snarf ahora hace poll propio cada 4s (antes una foto fija) — se siente vivo sin tener que abrir la pantalla completa. Cada nodo del grafo reemplaza su título de texto por un ícono, con el nombre completo como tooltip.
- 398/398 tests (sin cambios de backend esta ronda). Verificado con Playwright en escritorio contra una instancia real aislada. Ver ADR 0048.

## [2026-07-29] Grabación estilo WhatsApp, cerebro con íconos propios, y más pulido de Proyectos

- **Regresión de ADR 0048 corregida**: el modo enfoque en escritorio se quedaba sin nada al costado — la regla que oculta las pestañas del cajón del hamburguesa no distinguía el estado en que esa misma barra se reutiliza como panel fijo del modo enfoque.
- Grabación de voz en modo texto: se retira el toggle de click (mic en rojo confundible con la flecha de enviar, que en realidad dejaba la grabación colgada sin transcribir) y se reemplaza por el patrón de WhatsApp/Telegram/ChatGPT — mantener presionado graba, soltar transcribe y envía directo, deslizar a la izquierda cancela, deslizar hacia arriba bloquea para grabar manos libres.
- El cerebro de Snarf reemplaza los emoji de la ronda anterior por íconos propios dibujados en el mismo lenguaje visual monolínea del resto de la interfaz, con el mismo pulso de luz de los nodos activos aplicado también al ícono.
- Nuevo indicador de en qué proyecto está una conversación abierta (antes no existía ningún rastro salvo en el home).
- Se retira el swipe lateral chat↔dashboard en mobile — interfería con el scroll horizontal real dentro de bloques de código/tablas en los globos de chat.
- "+ nueva conversación" ahora también disponible en la barra lateral dentro de un proyecto (antes solo en el home); "borrar proyecto" se reubica al final del home, lejos de una acción de uso diario.
- Backlog real de "Incubadora de Ideas" revisado en Drive — sin conflictos con el trabajo de esta sesión.
- 398/398 tests (sin cambios de backend). Verificado con Playwright en escritorio y en mobile (con micrófono falso). Ver ADR 0049.

## [2026-07-29] Notas de voz reproducibles (estilo WhatsApp) y caché de audio de Snarf

- Nuevo `snarf/memory/audio_store.py`: las notas de voz del usuario ahora se guardan como archivos reales (`data/audio/`, nunca en el log de texto) y quedan reproducibles en el chat como una nota de voz — botón de reproducir + transcripción disponible debajo como desplegable, en vez de mostrarse siempre.
- Las respuestas de Snarf siguen mostrándose como texto igual que siempre (sin cambio de interfaz ahí) — lo que cambia es que escucharlas varias veces ya no vuelve a pagar ni esperar una síntesis nueva de ElevenLabs: `/tts` cachea por contenido del texto.
- Protocolo de limpieza real: las transcripciones y respuestas de texto se guardan para siempre como siempre; los archivos de audio en sí (notas de voz + caché de TTS) se purgan solos a los 7 días — a pedido explícito del fundador, priorizando espacio sobre "replay histórico" de audios viejos.
- Nuevo endpoint `GET /audio/{id}` (con validación estricta contra path traversal).
- 414/414 tests (16 nuevos). Verificado con Playwright contra una instancia real aislada: guardado/servido de audio real, 404 ante ids inválidos, render del bubble de nota de voz con su desplegable, y caché de TTS confirmada con un contador real de llamadas a síntesis. Ver ADR 0050.

## [2026-07-29] Reproductor de nota de voz embebido por burbuja (reemplaza el reproductor flotante)

- El reproductor flotante único de siempre (pausa/velocidad/cerrar, pero sin forma real de volver a darle play tras pausarlo) se retira por completo. Reemplazado por un reproductor embebido propio por burbuja — el mismo componente para la nota de voz del usuario y para la de Snarf — con play/pausa real (confirmado que reanudar funciona), progreso seekable, velocidad, y un menú ⋮ con **compartir** (Web Share API, pensado para iPhone) y **descargar**.
- El botón de las respuestas de Snarf pasa de "▶ escuchar" a "🎙️ generar nota de voz": genera (o recupera de caché, instantáneo) y reemplaza el propio botón por el reproductor real, en vez de reproducir directo en el reproductor flotante de un solo uso.
- 414/414 tests. Verificado con Playwright: pausar/reanudar de verdad con un audio real de ~16 segundos, seek por click en la barra, ciclo de velocidad, y el menú de descargar. Ver ADR 0051.

## [2026-07-29] Cerebro: pulso de activación suave y haces de luz reales

- El "latido" de un nodo activo era un doble golpe con salto de escala grande (hasta 1.2×) — se veía como un "tac-tac" feo, sobre todo con varios nodos activos a la vez. Ahora es un solo pulso suave (máximo 1.05×), con la diferenciación real llevada a la luminosidad/glow. El ícono de cada nodo ya no escala nada al activarse — pulsa solo brillo y opacidad.
- Los haces de luz que viajan entre nodos activos se ven más gruesos, brillantes y con segmentos más largos — se leen como un haz real, no una línea punteada genérica.
- **Bug real encontrado en el camino**: el grosor de esos haces nunca se aplicaba de verdad — una regla de CSS declarada en el orden equivocado lo pisaba en silencio desde que existe el efecto.
- El feed de eventos del cerebro ahora muestra el mismo ícono real de cada nodo junto al texto de cada fila (había quedado sin ninguno tras retirar los emoji).
- 414/414 tests (sin cambios de backend). Verificado con Playwright. Ver ADR 0052.

## [2026-07-29] Cerebro: flujo de partículas orgánico y más niebla volumétrica

- El "haz de luz" entre nodos era una línea de guiones en movimiento — mecánico, "tac tac tac" según el fundador. Reemplazado por un flujo real de partículas que viajan del orquestador a cada nodo activo, con velocidad y deriva propias (nunca sincronizadas entre sí, nunca sobre rieles).
- Más niebla de luz volumétrica (partículas grandes, lentas y tenues, distintas de las puntuales de siempre) y más partículas en general.
- El zoom de cámara al enfocar un nodo activo ya no es siempre el mismo valor exacto — varía dentro de un rango en cada evento.
- 414/414 tests (sin cambios de backend). Verificado con Playwright: el edge activo ya no anima guiones, y dos capturas separadas por 600ms muestran las partículas de flujo en posiciones distintas. Ver ADR 0053.

## [2026-07-29] Proyectos se separa en 3 nodos reales del cerebro (sin costo nuevo)

- Las 14 herramientas de Proyectos caían todas en un único nodo del cerebro — de lejos el más cargado, y el más opaco (no se veía qué parte estaba realmente activa). Usando el mismo `tool_name` que `activity_log` ya registraba sin costo nuevo, se separan en 3 nodos reales: gestión, tareas y notas, y conversaciones (Proyectos Mark II).
- 414/414 tests (1 actualizado para cubrir los 3 nodos con tool_names reales distintos). Verificado con Playwright contra el snapshot real del backend. Ver ADR 0054.

## [2026-07-29] Protocolo de crecimiento del cerebro + más nodos (Gmail/Calendar)

- Se establece un protocolo permanente (comentario al inicio de `snarf/telemetry/brain.py`, referenciado desde la "Regla de crecimiento" de MASTER_MAP.md): cada tool/Capacidad/Especialista/canal nuevo evalúa en el mismo cambio si merece nodo propio en el cerebro, en vez de encajarlo por comodidad en uno ya existente — con un test nuevo que pone un techo real de tools por nodo "specialist" para que la decisión no se posponga para siempre.
- Aplicado como segundo caso real: Gmail (7 tools → leer/organizar/enviar) y Calendar (8 tools → ver/editar) se separan igual que Proyectos, usando datos que ya se registraban sin costo nuevo.
- El cerebro pasa de 17 nodos reales (al empezar esta sesión) a 22.
- 415/415 tests. Verificado con Playwright contra el snapshot real. Ver ADR 0055.

## [2026-07-30] Capa de voz con proveedores intercambiables (Groq/Kokoro) + split texto/habla

- ElevenLabs quedaba cableado para toda la voz (STT del audio grabado, TTS de cada respuesta completa) — nuevo `snarf/voice/` con `STTProvider`/`TTSProvider` detrás de un router, proveedor activo elegido en `voice/config.yaml`, nunca en código.
- STT: Groq (`whisper-large-v3-turbo`, ~USD 0.04/hora) como primario, con fallback 100% local y gratis (`faster-whisper`) cuando no hay red o Groq falla.
- TTS: nuevo tier "local" con Kokoro-FastAPI corriendo en Docker (CPU, gratis) como default de toda conversación cotidiana — ElevenLabs pasa a ser tier "premium" exclusivo, nunca usado en silencio.
- La optimización de mayor impacto real: cada respuesta ahora se separa en versión completa (a pantalla) y versión hablada breve (a voz, <400 caracteres, sin markdown, nunca oculta un riesgo o dato faltante) — ya no se lee en voz alta la respuesta entera con formato.
- En la burbuja de cada respuesta: si el turno vino por voz, el resumen hablado se genera y aparece listo para tocar solo, sin click (nunca se reproduce automático) — si vino por texto, sigue siendo un botón manual. Nuevo botón separado y más discreto ("🔊 completa") para escuchar la respuesta larga entera, siempre a pedido.
- Docker instalado y usado desde el día uno (Colima) — el mismo contenedor de Kokoro va a correr igual en el futuro VPS.
- 444/444 tests (30 nuevos). Verificado con Kokoro real en Docker (3 voces en español reales probadas), con Playwright (mensaje de chat real, nota de voz generada y reproducida con audio real, auto-audio por turno de voz) y con `GROQ_API_KEY` real: 6 audios reales ya grabados transcriptos en rioplatense correcto, sin artefactos. Ver ADR 0056.

## [2026-07-30] Bug real corregido: 4 llamadores de generate() rotos + refinamiento de la burbuja de audio

- **Bug real en producción**: el cambio de `AnthropicLLM.generate()` para devolver texto+habla (entrada anterior de este mismo día) rompió en silencio otros 4 puntos que llamaban a `generate()` esperando un string plano — el digest de Gmail del dashboard tiraba un error real (`Object of type LLMResponse is not JSON serializable`), y lo mismo afectaba el resumen de Proyectos y la descripción por visión de imágenes al indexar Drive. Ningún test lo agarró porque los tests de esos 3 módulos usan su propio `FakeLLM` de juguete, no el real — corregidos los 4 llamadores y los 3 fakes.
- En la burbuja de audio: la duración total ahora se ve ANTES de tocar play (no solo durante), los reproductores de audio quedan siempre arriba del texto completo (nunca abajo, mezclados con los botones), y tocar "escuchar resumen" o "escuchar completa" ahora reproduce automático apenas está listo (tocar el botón ya es la confirmación de que se lo quiere escuchar).
- Íconos SVG propios (mic / parlante) en los botones de audio, mismo estilo que el resto de la interfaz — nunca emoji.
- 444/444 tests. Verificado con Playwright: orden correcto de la burbuja, duración visible y correcta en todo momento, autoplay real, y dos reproductores con duraciones reales distintas (12s vs 38s) confirmando que resumen y completa son contenido genuinamente distinto. Ver ADR 0056 (actualizado).

## [2026-07-30] Multibotón mic/enviar y envío combinado texto+voz

- El botón de grabar y el de enviar estaban siempre los dos visibles, sin ningún criterio — se leía como dos botones sueltos en vez de uno. Ahora se muestran según el estado real: solo mic si no hay nada escrito, mic+flecha si hay un borrador (a propósito: permite grabar una nota de voz encima de texto ya escrito), solo mic mientras se graba sin bloquear, tachito+flecha si la grabación quedó bloqueada en manos libres.
- Si había texto escrito antes de grabar, se perdía en silencio al enviar la nota de voz — ahora se manda todo junto, texto + transcripción, como un solo mensaje.
- 444/444 tests (sin cambios de backend). Verificado con Playwright simulando el gesto completo (mantener presionado, deslizar arriba para bloquear, soltar el dedo, tocar enviar) y el envío combinado con una transcripción de prueba. Ver ADR 0057.

## [2026-07-30] Cerebro: flujo de partículas en ambos sentidos, dos colores

- El flujo de partículas entre nodos viajaba en un solo sentido (orquestador → nodo). Ahora hay partículas en ambas direcciones a la vez mientras un nodo está activo: las que van usan el color propio del nodo, las que vuelven son blancas — se lee como ida y vuelta real de información, no un solo flujo.
- 444/444 tests (sin cambios de backend). Verificado con Playwright: partículas en ambas direcciones, exactamente 2 colores distintos en pantalla, confirmado también visualmente. Ver ADR 0058.

## [2026-07-30] Ronda de bugs reales: audio duplicado, scroll, grabación mobile

- El audio de "resumen" podía salir idéntico al de "completa" en respuestas largas e importantes (un plan de negocio) — el modelo a veces ignoraba el límite de 400 caracteres del resumen. Reforzada la instrucción y sumado un tope de seguridad real en el código (nunca vuelve a pasar, sin importar qué decida el modelo).
- Nueva instrucción: si una respuesta no entra en el límite de un mensaje, Snarf genera un archivo Markdown con el contenido completo en vez de truncar en silencio.
- Barras de desplazamiento ocultas por default en toda la interfaz — aparecen solo mientras se hace scroll de verdad, nunca permanentes (resuelve también el textarea de una sola línea mostrando una barra sin necesidad real).
- El scroll del chat ya no "se escapa" hacia el resto de la página al llegar al final.
- Bug real en mobile: un toque rápido en el micrófono podía dejar la interfaz grabando sin ninguna forma de pararla (race real entre el permiso de micrófono y el toque). Ahora hace falta mantener presionado de verdad para que arranque a grabar, y mientras graba el ícono cambia a un cuadrado rojo de stop.
- 445/445 tests. Verificado con Playwright y micrófono simulado. Ver ADR 0059.

## [2026-07-30] Mini-cerebro clickeable durante "pensando", vuelta automática al chat

- El indicador de "pensando" (tres puntitos) suma una mini-animación real del cerebro (mismos datos de `/dashboard/brain`) — clickeable, abre el cerebro completo mientras se espera una respuesta.
- Al llegar la respuesta, si el cerebro se había abierto desde acá, se cierra solo y vuelve al chat — sin que haga falta cerrarlo a mano.
- 445/445 tests (sin cambios de backend). Verificado con Playwright: la mini-animación aparece, el click abre el cerebro completo, y se cierra solo apenas llega la respuesta real. Ver ADR 0060 — nota: usa el mismo overlay flotante existente en mobile y desktop; la versión "contenida dentro de la caja de chat" específica de escritorio queda pendiente.

## [2026-07-30] Identidad real del usuario, nunca inventada

- Corrige un bug real: Snarf le empezó a decir "Andi" al fundador sin que nadie se lo dijera — una alucinación de identidad. Nuevo `snarf/runtime/user_profile.py` (mismo patrón que `personality_prefs.py`), atado al `user_id` real de cada usuario.
- System prompt releído en cada turno: si hay nombre guardado, Snarf se dirige siempre por ese nombre; si no, tiene instrucción explícita de nunca inventar uno y preguntarlo si surge naturalmente. Tool nueva `profile_set_name` (sin gate de confirmación) para que lo guarde en cuanto la persona lo diga.
- Endpoints `GET`/`PUT /profile` + campo de nombre en el panel de configuración del frontend.
- 459/459 tests (7 nuevos de `user_profile`, 5 de `orchestrator`, 2 de endpoints REST). Verificado con Playwright: persistencia real vía HTTP y reflejada en la UI tras un reload. Ver ADR 0061.

## [2026-07-30] Entrada en remolino del mini-cerebro, coherente con los tres puntitos

- El mini-cerebro clickeable durante "pensando" (ADR 0060) ahora aparece al lado de los tres puntitos (mismo renglón, antes quedaba debajo) con una entrada en remolino real (escala + rotación, 0.7s) en vez de aparecer de golpe.
- Los tres puntitos se mantienen sin cambios — señal inmediata sin depender de la red; el cerebro se materializa al lado apenas llegan sus datos reales, ambas señales conviven en vez de reemplazarse.
- 459/459 tests (sin cambios de backend). Verificado con Playwright: orden de aparición correcto, animación aplicada (`brain-swirl-in`), click sigue abriendo el cerebro completo. Ver ADR 0062.

## [2026-07-30] "Escuchar" vs "escuchar entregable" reemplaza resumen/completa

- Rediseño de fondo del audio de las respuestas: ya no hay "resumen" (acortado) vs "completa" (texto crudo) — hay "escuchar" (narración hablada fiel de la respuesta completa en pantalla, sin tope de longitud artificial) y, solo cuando corresponde, "escuchar entregable" (nuevo marcador `---ENTREGABLE---`, aparece solo si la respuesta trae un plan/documento/copia puntual pedido explícitamente — lee solo eso, sin la charla alrededor).
- Bug real encontrado y corregido en la propia verificación: cuando el modelo encadenaba el marcador de entregable sin cerrar el de habla antes, el entregable no se extraía y los marcadores quedaban crudos en el audio — `split_speech()` ahora es robusto a ese caso.
- 467/467 tests. Verificado con Playwright + llamadas reales a Anthropic: mensaje conversacional → solo "escuchar"; pedido de un plan de negocios → aparecen ambos botones, el entregable limpio y completo. Ver ADR 0063.

## [2026-07-30] Fix: carrera del permiso de micrófono en mobile + íconos del reproductor

- Bug real reportado desde un teléfono real: el diálogo nativo de permiso de micrófono cortaba el toque en curso (`pointercancel` mientras `getUserMedia()` seguía pendiente) y, al otorgar el permiso, la grabación arrancaba igual sin que quedara ningún gesto real que pudiera cortarla — quedaba "grabando" para siempre, solo se arreglaba refrescando la página.
- `pointercancel` ahora limpia el pointer activo siempre (no solo si ya estaba grabando), y `beginActualRecording` vuelve a chequear que el gesto siga vivo apenas `getUserMedia()` resuelve — si no, descarta el stream y pide un gesto nuevo, en vez de arrancar a grabar sin forma de pararlo.
- Los íconos ▶/⏸ del mini reproductor de audio (antes glifos de texto/emoji) pasan a ser SVG propios, coherentes con el resto del branding.
- 467/467 tests (sin cambios de backend). Verificado con Playwright simulando la carrera exacta del permiso. Ver ADR 0064.

## [2026-07-30] Reintentar nota de voz, pull-to-refresh del historial, título automático

- Bug real reportado: una nota de voz que falla con "Load failed" (error de red real) ya no se pierde — un botón "reintentar" reenvía el mismo audio grabado (o la transcripción, si ya se había obtenido) sin forzar a grabar todo de nuevo. Aplica también, de yapa, a mensajes de texto que fallan al enviarse.
- El historial de conversaciones (barra lateral y dashboard) ahora se puede refrescar deslizando hacia abajo desde arriba del todo del listado.
- Cada conversación se nombra sola apenas ocurre su primer intercambio real (LLM barato, en background, sin sumarle latencia a la respuesta) — reemplaza el substring crudo de los primeros 60 caracteres.
- 475/475 tests. Verificado con Playwright: falla de red real simulada + reintento exitoso con el mismo audio, y gesto de pull-to-refresh disparando un nuevo `GET /conversations`. Ver ADR 0065 — incluye un hallazgo operativo urgente sin relación con el código: la cuenta real de Anthropic se quedó sin crédito.

## [2026-07-30] Fix: el botón "reintentar" quedaba visible siempre

- Mismo bug ya conocido del repo (ver ADR 0059): `display: flex` de autor le ganaba al `[hidden]` del navegador — el botón de reintentar quedaba visible en todos los chats sin importar si había algo real para reintentar, y clickearlo no hacía nada.
- De paso, cambiar de conversación ahora limpia un reintento pendiente de la conversación anterior (antes podía quedar reintentando contra la conversación equivocada).
- 475/475 tests. Verificado con Playwright: `display: none` real tanto al cargar como después de un envío exitoso. Ver ADR 0066.

## [2026-07-30] Protocolo de costos: confirmar lecturas masivas + tope de repetición en el historial

- Análisis real de costos (`data/usage_log.jsonl`): una sola llamada costó $1.09 (22% de un día) porque un pedido sin tope de "mil correos" quedó embebido en el historial y se re-transmitía/re-cacheaba entero en cada turno futuro. `gmail_list_messages`, `calendar_list_upcoming_events`, `calendar_search_events`, `youtube_list_subscriptions`, `youtube_list_liked_videos` y `drive_list_files` ahora preguntan antes de traer más de 50 resultados — pero si el fundador confirma, se ejecuta la cantidad exacta pedida, nunca se recorta en silencio.
- El historial de una conversación ya no re-transmite indefinidamente una respuesta gigante turno a turno — se recorta lo que se re-manda al LLM (no lo guardado ni lo que se ve en la UI) una vez que un resultado ya fue entregado.
- 496/496 tests. Verificado con una llamada real (crédito recién cargado): pedir 200 correos generó la pregunta de confirmación esperada; confirmado, trajo los 200 reales. Ver ADR 0067.

## [2026-07-30] LLM multi-proveedor, configurable por rol

- Investigación real de precios (Gemini, OpenAI, xAI, Llama): ningún proveedor ofrece hoy "tan inteligente como Sonnet" y notablemente más barato a la vez — el nivel Gemini Pro cuesta prácticamente lo mismo que Sonnet 5; el 25x más barato real es clase Haiku, no un reemplazo. Con esa realidad sobre la mesa, se construyó igual el soporte multi-proveedor real.
- Nuevas Capacidades `OpenAICompatibleLLM` (cubre OpenAI, xAI/Grok y Llama vía Groq, mismo formato de tool-calling los tres) y `GeminiLLM`, con la misma interfaz que `AnthropicLLM` — verificadas campo por campo contra los SDKs reales instalados.
- `snarf/runtime/llm_routing.py`: qué proveedor/modelo usa cada rol (conversación principal, Gmail, visión de Drive, resumen de proyectos, título de conversación) — default = exactamente el comportamiento de siempre, configurable desde un selector nuevo en configuración ("LLM por rol"), con los proveedores sin credencial real marcados como tales.
- 529/529 tests. Verificado con Playwright: los 5 roles muestran su default correcto, los proveedores sin API key aparecen deshabilitados, y un cambio persiste tras un reload. Ver ADR 0068 — los adaptadores nuevos todavía no tienen un smoke-test con una llamada real (faltan las credenciales).

## [2026-07-30] Paneo 3D: profundidad real entre los anillos del cerebro

- Pendiente de varias rondas: el núcleo del cerebro (Orchestrator) y cada anillo (Entrada/Especialistas/Capacidades) ahora reaccionan con intensidad distinta al mismo desvío orbital de cámara — lo "cercano" se mueve más que el "fondo", dando sensación de volumen real en vez de un dibujo plano. Sin WebGL, con SVG puro.
- Encontrado y resuelto un choque técnico real: los nodos ya pulsan con animaciones CSS propias sobre `transform`, que le ganan a un `transform` puesto por JS — se resolvió envolviendo cada nodo en su propio `<g>` para que el paralaje y el pulso convivan sin pisarse.
- 529/529 tests (sin cambios de backend). Verificado con Playwright: desplazamiento real medido (núcleo ~31 unidades vs. ~3.6 en el anillo externo, más de 8x de diferencia), cero errores de consola, el zoom-foco existente intacto. Ver ADR 0069.

## [2026-07-30] Credenciales reales de LLM: fix de nombres de modelo + ruteo dinámico sin reinicio

- Con las credenciales reales de Gemini/OpenAI/xAI cargadas, el smoke-test real encontró y corrigió: nombres de modelo desactualizados (`gemini-2.5-flash-lite` da 404, reemplazado por `gemini-3.1-flash-lite`; `grok-4.1-fast` con puntos da 400, la nomenclatura real de xAI usa guiones); y un bug real donde cambiar el ruteo de un rol desde la interfaz no tenía ningún efecto hasta reiniciar el servidor — corregido con `Orchestrator.refresh_llm_routing()`, disparado desde `PUT /llm-routing`.
- Los 4 roles acotados (Gmail, visión de Drive, resumen de proyectos, título) se movieron a los proveedores más baratos ya verificados de punta a punta. El rol principal de conversación queda en Sonnet 5 — Haiku ya está disponible en el selector, pero esa decisión (afecta la personalidad/calidad de Snarf) queda para que el fundador la tome, no para decidirla en silencio.
- Encontrada y corregida de paso una fuga real de aislamiento en los tests: las credenciales nuevas en `.env` no se borraban antes de cada test.
- 529/529 tests. Verificado con llamadas reales de punta a punta a través del Orchestrator real (no solo la Capacidad aislada): título generado por Gemini real, respuesta real de xAI en el rol principal, visión real confirmada con Gemini. Ver ADR 0070.

## [2026-07-30] Fix: `.warmup()` faltante en las Capacidades LLM no-Anthropic

- El fundador ruteó `orchestrator` a xAI Grok manualmente; `OpenAICompatibleLLM`/`GeminiLLM` nunca implementaron `.warmup()` (a diferencia de `AnthropicLLM`), así que cualquier rol ruteado a un proveedor no-Anthropic hacía crashear el arranque del servidor con `AttributeError` en el próximo reinicio real.
- 529/529 tests. Se corrige de paso un test que no aislaba `ROUTING_PATH` y leía el archivo real en disco. Ver ADR 0071.

## [2026-07-30] Cerebro: rotación 3D real (no paralaje simulado) + fix de desincronización + partículas mejoradas

- El paralaje 2D del ADR 0069 no se sentía como una cámara rotando y tenía un bug real: las partículas de flujo entre nodos se desincronizaban de las líneas de los edges (dos fuentes de verdad distintas para la misma geometría). Se reemplaza todo por una única función de proyección de perspectiva 3D (`project3D`), calculada una sola vez por frame antes de dibujar SVG o canvas — elimina la clase de bug por construcción.
- Rotación de cámara continua y lenta con eje Z real entre anillos (orquestador más cerca, capacidades más al fondo). Partículas de flujo reescritas: entrada/salida tipo "humo de luz" (radio variable), órbita tipo electrón alrededor del nodo al llegar, y color que interpola entre el núcleo y el nodo según de dónde vienen y hacia dónde van.
- 529/529 tests (sin cambios de backend). Verificado con Playwright: rotación real que avanza con el tiempo, un nodo del anillo de Capacidades desplazándose notablemente más en X que el núcleo ante la misma rotación (el eje Z participa de verdad), radios variando con la profundidad, cero errores de consola. Ver ADR 0072.

## [2026-07-31] Fix real de timeout de voz + investigación de lag reportado en el cerebro

- El fundador reportó voz fallando; el log real mostró un timeout de 30s contra el contenedor Kokoro tras un cold-start — se sube a 60s, verificado con 5 llamadas reales seguidas post-fix.
- Investigación a fondo del "se traba" reportado en el cerebro: se corrigieron dos ineficiencias reales (lectura de DOM en cada frame en vez de coordenadas cacheadas; un `stroke()` de canvas por link de malla en vez de uno por color), pero instrumentando tiempos reales contra producción, ninguna explicaba el costo medido — deshabilitando el cerebro entero el lag no bajó. No se encontró la causa raíz; queda pendiente si el fundador confirma que persiste. Ver ADR 0071 (adenda de voz) y 0072 (adenda de investigación).
