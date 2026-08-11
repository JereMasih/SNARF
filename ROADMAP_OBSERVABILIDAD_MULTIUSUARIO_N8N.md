# Evolución de Snarf hacia un AI Operating System observable, multi-usuario y Jarvis-style

> **Por qué este documento vive acá y no solo en un plan de Claude Code:** un plan guardado por
> `ExitPlanMode` queda en `~/.claude/plans/`, fuera del repo — una sesión nueva de Claude Code no tiene
> garantía de poder leerlo (pasó de verdad: una sesión que retomó la Fase 5 no pudo acceder al texto
> original y tuvo que reconstruir el alcance desde ADR 0139, dejándolo anotado como nota de honestidad
> en el CHANGELOG). Este archivo es la copia autoritativa, versionada en git, que cualquier sesión futura
> puede leer siempre — indexado desde `CLAUDE.md`.

## Estado actual (retomar una sesión nueva desde acá)

**Última actualización:** 2026-08-10. **Hechas: Fases 0-6** (más un adelanto real de la Fase 9.1) —
Fase 6 (Prompt Registry, `adr/0141-*`) hecha y testeada, **todavía sin commitear** — ver "Trabajo
pendiente de commit" abajo. Fases 0-5 commiteadas, sin pushear a `origin/master` en este momento —
confirmar `git push` con el fundador antes de asumirlo hecho. Suite completa en verde: 1233/1233 tests
(`.venv/bin/python -m pytest -q`).

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

**Trabajo pendiente de commit:** Fase 6 (Prompt Registry, `adr/0141-*`) — hecha, testeada (1233/1233),
sin commitear todavía. Archivos: `snarf/runtime/prompt_registry.py` (nuevo),
`tests/test_prompt_registry.py` (nuevo), `adr/0141-*.md` (nuevo), más cambios en
`snarf/core/orchestrator.py`, `app.py`, `CHANGELOG.md`, este documento, y los ~13 archivos de
`snarf/specialists/`/`snarf/knowledge/` wireados (ver ADR 0141 para el detalle completo). **No
commitear sin pedido explícito del fundador.**

**Estado real de infraestructura en esta Mac** (verificar que sigue así al retomar, puede haber
cambiado):
- Colima corriendo (`colima start --cpu 2 --memory 2 --disk 20` — perfil acotado a propósito).
- Contenedor `snarf-n8n` corriendo (`docker ps`), n8n real en `http://127.0.0.1:5678/` — el fundador ya
  completó el "Set up owner account" y tiene un workflow activo con un nodo Webhook (**en POST, no el
  GET por default** — gotcha real documentado en ADR 0139).
- `.env` tiene `N8N_WEBHOOK_URL` y `N8N_CONTROL_TOKEN` reales seteados — integración verificada
  funcionando (`POST` a la Production URL devuelve `200 {"message":"Workflow was started"}`).
- **Ninguno de los dos (Colima/n8n) sobrevive un reboot de la Mac todavía** — si al retomar no
  responden, es esperable, hay que levantarlos de nuevo (`colima start` + `docker compose -f
  docker-compose.n8n.yml up -d`), no es un bug nuevo.
- Puede haber quedado una conversación de prueba real ("ping de verificación real, ignorar") en
  `data/episodic_memory.jsonl` del fundador — inofensiva, generada verificando el flujo de `/send`.

**Recomendación de VPS ya dada, sin decisión tomada todavía**: esquema híbrido (VPS aloja FastAPI/
orquestación, la inferencia local sigue viajando a esta Mac por Tailscale) — no migración completa,
porque MLX es específico de Apple Silicon y una migración completa perdería el costo ~$0 de inferencia
local. Pendiente de que el fundador decida si/cuándo.

**Qué preguntar/confirmar apenas se retome:** (1) ¿se commitea el trabajo de Fase 6 tal cual está? (2)
¿seguimos con la Fase 7 (Configuración dinámica), o el fundador quiere reordenar/saltar a otra fase? La
instrucción vigente de sesiones anteriores fue "continuá con las fases siguientes, no hace falta que
preguntes" — sigue aplicando salvo que el fundador diga lo contrario, pero **no** cubre commits (esos
siempre se piden explícitamente) ni gasto real/infraestructura paga.

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

## Fase 6 — Prompt Registry ✅ HECHO PERO SIN COMMITEAR (`adr/0141-*`)

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

## Fase 7 — Configuración dinámica

Extiende el patrón de `llm_routing.py` a `MAX_OUTPUT_TOKENS`, temperatura (hoy ni se pasa), timeout/retry por rol. Versionado igual que el Prompt Registry.

---

## Fase 8 — Aprobación humana genérica (HITL) + decisión de stack de observability

**HITL:** generaliza el protocolo de dos pasos ad-hoc de `HIGH_IMPACT_TOOLS` (ADR 0015) en un evento reusable (`ApprovalRequested`/`Granted`/`Rejected`) sobre el event bus de Fase 2, consumible desde n8n sin que n8n pase a decidir nada.

**Stack de observability**, evaluado con el rollout de usuarios de prueba como driver real:
- **Grafana + Prometheus**: postergados — ese problema lo crea el VPS multiplicando procesos, no la cantidad de usuarios de prueba.
- **OpenTelemetry**: postergado hasta que haga falta interoperar con un tercero externo real.
- **Langfuse**: el candidato a adelantar, gratis en su versión self-hosted. Se evalúa en paralelo a la Fase 6, cuando arranque el rollout de usuarios de prueba.

---

## Fase 9 — Cockpit del fundador: control de infraestructura + cerebro rediseñado

### 9.1 — Control de infraestructura ⚠️ ADELANTADO PARCIALMENTE, ya hecho (`adr/0138-*`)

Lo que ya existe: tools `ops_process_status`/`ops_process_restart` (solo founder, confirmación de dos
pasos, `com.snarf.server` excluido de auto-reinicio), nombres de proceso reales en Activity Monitor/`ps`
(`setproctitle`). Vive en el chat, no en una vista de dashboard — **falta**: vista visual real en
`web/index.html`, ver logs desde la UI, asistente guiado de migración a VPS.

### 9.2 — Cerebro rediseñado ("entidad cognitiva digital"), founder-preview primero

Evolución de `brain.py`/vista HUD (mismo protocolo de crecimiento de nodos), gateado por
`is_founder`/rol (mismo mecanismo del toggle clásico/HUD, ADR 0090), promovido a todos cuando el
fundador apruebe.

### 9.3 — Escritura desde n8n hacia agentes existentes

Cierra el caso de uso de la Fase 4: desde el cockpit o desde un flujo de n8n, el founder puede abrir el
prompt/config activo de un agente (Fase 6/7), editarlo, y activar la nueva versión, con historial y
rollback.

---

## Fase 10 — Streaming de voz como canal principal (estilo Jarvis)

Hoy la voz es grabar → transcribir → Snarf responde → sintetizar (turnos discretos). El objetivo de largo plazo es un canal continuo, bidireccional. Se construye sobre lo que ya existe (ElevenLabs/Groq STT, Kokoro TTS nativo con MPS) en vez de reemplazar el stack de voz entero. Fase de diseño propio cuando le toque el turno.

---

## Fase 11 — Extensión Claude Code / MCP

El servidor MCP ya existe y ya expone un allowlist a un segundo consumidor real. Sumar tools de introspección de solo lectura (Fase 5) a `MCP_EXPOSED_TOOLS`, evaluando un subset de rol propio para Claude Code — siempre delegando a `Orchestrator._handle_tool()`.

---

## Fase 12 — Replay y debugging

Sobre la persistencia de Redis Streams (Fase 2) + `EpisodicMemory` + versiones de prompt/config (Fases 6-7): seleccionar una ejecución pasada por `trace_id` y reproducirla. Diseño explícito para no-determinismo de LLM.

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
