# MASTER_MAP

## El Plano Maestro del Ecosistema Snarf

**Versión:** 0.1 (Candidate)

## Propósito

Este documento representa el mapa conceptual completo del proyecto Snarf. No contiene el conocimiento; contiene la estructura donde ese conocimiento vivirá.

Todo nuevo documento, capacidad, agente, sistema o unidad de negocio deberá encontrar primero su lugar dentro de este mapa antes de incorporarse al proyecto.

## Dominios principales

- Identity
- Governance
- Cognition
- Knowledge
- Canon
- Architecture
- Capabilities
- Business
- Infrastructure
- History
- Roadmaps
- Archive

## Identity

Define quién es Snarf.

Documentos:

- FOUNDATION (vigente)
- PROJECT_CONTEXT (vigente)
- CHARACTER (vigente, v0.1)
- CONSTITUTION — nota: constitucionalmente pertenece a Governance (define autoridad, no identidad), pero vive en Identity por ahora al no existir todavía una carpeta propia; ver nota de Governance.

Documentos previstos, sin crear todavía:

- EVOLUTION
- VISION
- PURPOSE

## Governance

Define autoridad, delegación, permisos, auditoría y gestión del riesgo.

Documentos:

- CONSTITUTION (vigente, v1.0) — nivel constitucional: quién tiene poder, cómo se transfiere, cómo se limita.

**Vacío detectado en la auditoría constitucional de Constitution Design 0001:** este dominio necesita, a futuro, dos niveles adicionales que hoy no existen como tipo de documento distinto:

- **Políticas** — posturas operativas revisables (ej. qué acciones requieren aprobación explícita, delegado vigente). Cambian con más fricción que un ajuste de código, pero sin necesidad de reabrir Constitution.
- **Procedimientos** — pasos concretos de ejecución (ej. protocolo de verificación de sucesión, mecánica de notificación). Cambian con la menor fricción de los tres niveles.

No se crean todavía por no existir contenido real que los justifique (Regla de crecimiento). Se registran aquí para que la próxima Política o Procedimiento real encuentre dónde vivir sin necesidad de reabrir esta discusión.

## Cognition

Describe cómo piensa Snarf.

Documentos:

- COGNITION (vigente, v0.1) — describe la arquitectura de tres capas (Capacidades / Especialistas / Snarf) y el razonamiento realmente implementado, no uno aspiracional. Desde el 2026-07-27 (ver ADR 0025), registra el primer Especialista Cognitivo real: `GmailDigestSpecialist`, que interpreta la bandeja de Gmail (categoriza, señala qué revisar) y es también el primer componente de Snarf que actúa de forma autónoma, con un refresco propio en segundo plano.

Documentos previstos, sin crear todavía:

- MEMORY
- LEARNING
- REASONING
- DECISION_ENGINE
- OPPORTUNITY_ENGINE
- FOUNDER_MODEL
- CONTEXT_ENGINE

**Capacidad futura, pospuesta explícitamente por el fundador (2026-07-25):** que Snarf pueda conversar para automodificar su propio código o documentos (equivalente a operar sobre sí mismo a través de una herramienta tipo Claude Code). No implementada — se prioriza terminar interfaz y funcionamiento base primero. Ver ADR 0010.

## Knowledge

Todo el conocimiento operativo (negocios, trading, marketing, tecnología, filosofía, etc.).

## Canon

Fuentes fundacionales que orientan el razonamiento del sistema.

## Architecture

Describe la arquitectura lógica y técnica.

Implementado:

- Arquitectura de tres capas (Capacidades / Especialistas Cognitivos / Snarf) — ver ADR 0003.
- Runtime de interacción multicanal, con contrato `Channel` único y canales concretos agregados por extensión — ver ADR 0004.
- Tres puntos de entrada equivalentes en capacidad, sobre el mismo Orchestrator: `main.py` (texto), `main.py --voice` (voz por terminal, start/stop manual), `app.py` (voz con interfaz visual HUD en `web/index.html`, grabación del lado del navegador, accesible en red local) — ver ADR 0006 y ADR 0007.

## Capabilities

Todo aquello que Snarf puede hacer.

Hoy, todas reales y verificadas: `AnthropicLLM` (razonamiento), `ElevenLabsTTS`/`ElevenLabsSTT` (voz, voz elegida: Antonio, es-AR), `LocalAudioIO` (reproducción y grabación local), `GoogleAuth` (OAuth compartido, alcance completo de Drive) + `GoogleDrive`, `GoogleGmail`, `GoogleCalendar`, `GoogleYouTube`. Lectura y organización reversible (etiquetas, carpetas, mover archivos) son herramientas directas; enviar correo, crear/eliminar calendarios, eliminar etiquetas o archivos exigen el protocolo de confirmación en dos pasos de ADR 0015. El despacho de herramientas en `Orchestrator` es un registro (`_tool_handlers`), no una cadena `if/elif`. Nuevas capacidades se agregan implementando el contrato `Capability` en `snarf/capabilities/`.

Desde el 2026-07-27: la interfaz web exige login (`web/login.html`, cookie de sesión firmada, `SNARF_ACCESS_PASSWORD`) y las credenciales de Google se guardan por usuario (`credentials/tokens/<user_id>.json`, no un único archivo global) — `GoogleAuth` y `Orchestrator` ya reciben `user_id` explícito, aunque hoy solo exista uno (`"fundador"`). Ver ADR 0021.

Desde el 2026-07-27: dashboard v1 dentro de `web/index.html` (endpoint `GET /dashboard/summary`), con tres widgets sobre datos 100% reales — estado del sistema (LLM/STT/TTS/Google conectado), conversaciones (totales + actividad de los últimos 14 días vía `EpisodicMemory.stats()`) y memoria episódica (entradas guardadas, fecha de la más antigua). Navegación Chat/Dashboard por botón y por swipe táctil; nuevo menú de usuario en el sidebar (reemplaza al botón de cerrar sesión suelto) con desplegable para cerrar sesión y un placeholder de configuración futura. Ver ADR 0022 y Roadmaps para el plan de fases siguientes.

Desde el 2026-07-27 (misma jornada, ver ADR 0023): íconos de la interfaz reemplazados por SVG propios (sin emojis, sin librería externa). Cuatro widgets nuevos sobre Capacidades reales ya existentes (`GET /dashboard/widgets/{drive,gmail,calendar,youtube}`) — corrigiendo a ADR 0022, que había clasificado por error estos widgets como "Fase 2" cuando esas Capacidades ya existían. Preferencias de dashboard persistidas por usuario (`snarf/runtime/dashboard_prefs.py`, `data/dashboard_prefs/<user_id>.json`): qué widgets mostrar y en qué orden, editable desde un panel de configuración nuevo y reordenable arrastrando (mouse en desktop, mantener presionado en mobile). En desktop ancho (`min-width: 900px`) con el Dashboard activado, layout "Jarvis": el chat queda centrado y los widgets rodean alrededor (arriba, izquierda con la lista de conversaciones, derecha) en vez de reemplazar la vista de chat como en mobile.

Desde el 2026-07-27 (ADR 0024): corregido un bug real de stacking CSS que rompía por completo el layout Jarvis (invisible aunque bien ubicado), un bug preexistente en CI (pytest sin `pythonpath`, roto desde antes de hoy) y el arrastre para reordenar en celular (umbral de jitter irreal para un dedo real). Widgets de Drive/Gmail/Calendar/YouTube ahora con más contexto (subtítulo, fecha/tamaño) y cliqueables (abren el recurso real de Google). Primera verificación de este proyecto con navegador real (Playwright/Chromium headless, instalado en el entorno de desarrollo, no es dependencia del proyecto).

Desde el 2026-07-27 (ADR 0025, corregido por ADR 0026): primer Especialista Cognitivo real, `GmailDigestSpecialist` — interpreta la bandeja de Gmail (categoriza, señala qué revisar), invocable por Snarf en el chat (`gmail_summarize_inbox`) o preguntando "¿qué tenemos para hoy?". El refresco automático en segundo plano de ADR 0025 se corrigió en ADR 0026: es 100% impulsado por el navegador (al abrir el dashboard y cada 5 min mientras sigue abierto y visible), nunca del lado del servidor sin uso real. Usa su propia Capacidad de LLM más barata (`claude-haiku-4-5`), distinta a la de Snarf.

Desde el 2026-07-27 (ADR 0026): `snarf/capabilities/` y `snarf/specialists/` quedan garantizados reusables desde un futuro agente/proyecto — nunca importan `snarf.core` ni `snarf.runtime` ni `app.py`, reciben todo por inyección en el constructor. Garantía fijada con un test (`tests/test_architecture_boundaries.py`), no con una extracción a paquete separado (prematura sin un segundo consumidor real). Primera optimización real de costo de tokens: el system prompt de Snarf (idéntico en cada llamada) usa prompt caching de Anthropic.

Desde el 2026-07-28 (ADR 0028): construida la extracción de contenido por tipo de archivo (PDF vía `pypdf`, imagen vía Claude Haiku 4.5 con visión, audio vía `ElevenLabsSTT`, video extrayendo la pista de audio con `ffmpeg` y transcribiéndola) y el pipeline completo de vectorización de Drive (`snarf/knowledge/`: extracción → chunking → embeddings de Voyage AI `voyage-4-lite` → `chromadb` local), con progreso reanudable por archivo y seis herramientas nuevas para Snarf (`drive_index_scan`, `drive_index_catalog_unsupported`, `drive_index_start`, `drive_index_status`, `drive_index_stop`, `drive_search_knowledge`, esta última todavía sin usar hasta que haya algo indexado). Mismo ADR: panel de costo en tiempo real (`snarf/telemetry/`) que estima el gasto real de Anthropic/ElevenLabs/Voyage a partir de cada llamada real, nunca inventado.

Desde el 2026-07-28 (ADR 0029): sumados `DocxExtractor`/`PptxExtractor`/`XlsxExtractor` (`.docx`/`.pptx`/`.xlsx`, todos locales y sin costo) al tier gratuito de indexación (`query='free_tier'`). Nuevo `snarf/telemetry/activity_log.py`: registro real de qué herramienta ejecuta el Orchestrator y cuándo (`data/activity_log.jsonl`, `GET /dashboard/activity`) — prerrequisito de la futura visualización "cerebro de Snarf", todavía sin construir. **Pendiente real, no resuelto:** `drive_index_start(query='free_tier')` todavía no se corrió de verdad — hace falta que el fundador configure `VOYAGE_API_KEY` (ver `.env.example`) antes de poder embeber contenido.

Planificado, todavía sin construir: interfaz genérica de "fuente de conocimiento" para que Drive, Notion y archivos subidos a mano compartan un mismo motor de vectorización (hoy el pipeline es específico de Drive); reforzar la confirmación de acciones de alto impacto con un control independiente del modelo (por ejemplo, un botón en la interfaz) si el uso escala más allá de un solo usuario; login con Google (reemplazando o complementando la contraseña) y flujo real de un segundo usuario conectando su propia cuenta y vectorizando su propio Drive, cuando exista multi-usuario real — evaluado explícitamente en ADR 0028 y pospuesto a propósito (los datos de indexación ya están namespaced por `user_id` desde el día uno, así que agregar el segundo usuario es pasar otro `user_id`, no rediseñar el pipeline).

## Business

Unidades económicas, productos, servicios y empresas.

## Infrastructure

Repositorios, Git, IA, servidores, automatizaciones y herramientas.

Repositorio Git local inicializado el 2026-07-25, publicado el 2026-07-27 en `https://github.com/JereMasih/SNARF` (público; secretos excluidos por `.gitignore`). Estructura de código bajo `snarf/` (core, capabilities, specialists, runtime); memoria episódica en `data/`; credenciales externas (Google OAuth) en `credentials/`, fuera de git.

Desde el 2026-07-27: dependencias fijadas a versión exacta en `requirements.txt` (antes sin pinear); `requirements-dev.txt` para dependencias de test; primera suite de tests automatizados en `tests/` (27 tests, `pytest`) cubriendo memoria episódica, dispatch de herramientas y — el más importante — que ninguna de las 8 herramientas de alto impacto ejecuta su acción real sin `confirmed=true`; CI en `.github/workflows/tests.yml` que corre la suite en cada push/PR. Ver ADR 0019 y `ARCHITECTURE_AUDIT.md` (auditoría técnica completa del repositorio, distinta de la auditoría de gobernanza de Architecture Review 0001).

## History

Registro permanente de decisiones, cambios y aprendizaje.

Hoy implementado mediante `adr/` (decisiones de arquitectura y gobernanza) y `CHANGELOG.md` (registro legible de cambios del proyecto). Ambos son el mecanismo real del Artículo VIII de Constitution mientras no exista un dominio History más amplio.

## Roadmaps

Planificación de la evolución del sistema.

**Dashboard, plan por fases (2026-07-27, ver ADR 0022 y ADR 0023):**

- Fase 1 (construida): dashboard con widgets sobre datos 100% reales — estado del sistema, conversaciones, memoria episódica, y (corrección de ADR 0023 a la Fase 2 original) Drive, Gmail, Calendar y YouTube, porque esas Capacidades ya existían y no eran hipotéticas. Menú de usuario, panel de configuración (qué widgets mostrar), reordenamiento persistido por usuario, navegación Chat/Dashboard por swipe o botón en mobile, y layout "Jarvis" (chat centrado + paneles alrededor) en desktop ancho. Ver Capabilities y Architecture para el detalle.
- Fase 2 (futura, sin fecha): cada Capacidad genuinamente nueva que se agregue (Trading, GitHub, MCP, lo que se decida — subsistemas que hoy no existen) suma su propio widget al dashboard, opt-in por el usuario.
- Fase 3 (futura, sin fecha): aplicación de escritorio nativa multi-ventana (múltiples monitores) y visualización tipo "Jarvis brain" de los flujos del sistema — requiere antes un registro real de eventos/actividad del `Orchestrator` que hoy no existe (`episodic_memory.jsonl` solo guarda input/response, no qué herramienta se ejecutó).

**Vectorización de conocimiento, plan por fases (2026-07-28, ver ADR 0028):**

- Fase 1 (construida): extracción por tipo de archivo + pipeline de vectorización específico de Google Drive, un solo usuario (el fundador), con progreso reanudable e indexación siempre disparada a pedido explícito, nunca automática.
- Fase 2 (futura, sin fecha): interfaz genérica de "fuente de conocimiento" para que Notion y archivos subidos a mano compartan el mismo motor que hoy es específico de Drive.
- Fase 3 (futura, sin fecha, requiere multi-usuario real): un segundo usuario conectando su propia cuenta de Google y vectorizando su propio Drive — los datos ya están namespaced por `user_id`, falta el resto de la infraestructura multi-usuario (login con Google, aislamiento de sesión) que también sigue en Planificado.

**Visión ampliada del dashboard y de Snarf, registrada sin construir (2026-07-28):** el fundador planteó una visión mucho más grande, todavía sin priorizar ni diseñar — se registra acá completa para no perderla (Foundation, Principio VIII), no como compromiso de construcción inmediata. Ver conversación del 2026-07-28 para el pedido textual completo.

- **Dashboard, información de negocio (requiere fuentes de datos reales que hoy no existen — Foundation Principio VI, nunca dato inventado):** costo total de operar Snarf en tiempo real (la Fase 1 del panel de costo ya lo hace para APIs; falta hosting/servidores), costos de publicidad por unidad de negocio, ingresos (diario/semanal/mensual), cantidad de proyectos activos/en desarrollo, cosas que requieren atención del fundador, campañas activas por unidad de negocio. Nada de esto puede mostrarse sin antes construir (o conectar) la fuente real: un sistema de costos/contabilidad, integraciones con plataformas de ads, y un tracking real de proyectos/unidades de negocio — hoy el dominio Business de este mapa está vacío.
- **Dashboard, datos de mercado:** precio de Bitcoin, petróleo, oro, S&P 500, Dow Jones, Nasdaq. Requiere una Capacidad nueva (`MarketData` o similar) contra un proveedor de datos de mercado — vendor nuevo, a elegir.
- **Visualización "cerebro de Snarf" estilo Jarvis:** el fundador confirmó el orden — primero el registro real de actividad del Orchestrator (qué herramienta se ejecuta y cuándo, hoy inexistente), después la visualización sobre ese dato real.
- **Interfaz de configuración** para todo lo anterior, y un **onboarding** — tanto para que el propio fundador termine de conectar todo dentro de Snarf hoy, como (a futuro, multi-usuario) para que un usuario nuevo conecte sus propias cuentas. Nota de gobernanza: ADR 0028 (misma jornada, antes de este pedido) evaluó explícitamente construir infraestructura multi-usuario ahora y decidió posponerla por no existir todavía un segundo usuario real — este pedido la vuelve a poner sobre la mesa; queda pendiente de decisión explícita con el fundador si se reabre esa decisión o se mantiene.
- **Capacidad de crear y exportar documentos** (Google Docs, Sheets, PDF) — hoy `GoogleDrive` solo lee, nunca escribe contenido de documentos.
- **Reemplazo de los chatbots externos del fundador** (ChatGPT es el más usado, también Claude): migrar el historial y contexto de "Proyectos" existentes fuera de Snarf (ej. "Alimentación y Workout", "High Value Men", con mucha conversación acumulada) hacia adentro de Snarf.
- **Capacidad de "Proyectos"/Especialistas por dominio:** que Snarf mantenga contexto general pero delegue en un Especialista Cognitivo propio (con su propia metodología/contexto, ver arquitectura de tres capas en COGNITION.md) para dominios específicos como alimentación/workout — el fundador siempre habla con Snarf, nunca directamente con el Especialista, mismo patrón que `GmailDigestSpecialist`.

**Orden acordado con el fundador (2026-07-28), "el más eficiente posible":**

1. (construido, ver ADR 0029) Extractores `.docx`/`.pptx`/`.xlsx` sumados al tier gratuito de Drive. Falta todavía correr `drive_index_start(query='free_tier')` de verdad (pendiente de `VOYAGE_API_KEY`, ver Capabilities).
2. (construido, ver ADR 0029) Registro real de actividad del Orchestrator (`data/activity_log.jsonl`, `GET /dashboard/activity`) — qué herramienta se ejecuta y cuándo. Prerrequisito de (6), todavía sin visualización.
3. Crear/exportar documentos (Google Docs, Sheets, PDF) — capacidad nueva; hoy `GoogleDrive` solo lee. Elegido antes que lo demás porque desbloquea que un futuro Especialista (5) pueda producir un entregable real, y porque es en sí mismo uno de los pedidos directos del fundador ("trabajar con Snarf").
4. Datos de mercado (Bitcoin, petróleo, oro, S&P 500, Dow Jones, Nasdaq) — el más autocontenido: una Capacidad nueva contra un proveedor de datos de mercado (a elegir), sin depender de nada de lo anterior. Valor visible rápido mientras se diseña lo más grande.
5. Migración de "Proyectos" externos (ChatGPT: Alimentación y Workout, High Value Men) + arquitectura de Especialistas por dominio dentro de Snarf — el más grande y novedoso arquitectónicamente; se beneficia de (3) ya existente y del patrón de logging de (2).
6. Visualización "cerebro de Snarf" estilo Jarvis, sobre el registro real de (2).
7. Fuente real de costos/ingresos/campañas de negocio — no es trabajo de código todavía, es una conversación pendiente con el fundador: qué sistema contable/de ads conectar. Puede pasar en paralelo, en cualquier momento, sin bloquear el resto.
8. Interfaz de configuración + onboarding (para el propio fundador primero) — tiene más sentido una vez que existan varias piezas conectadas (Drive, mercado, Docs, Especialistas, negocio) que consolidar.

Multi-usuario (login con Google, onboarding de un segundo usuario real) sigue explícitamente pospuesto — decisión de ADR 0028 ratificada por el fundador el mismo día, no reabierta.

## Archive

Conocimiento histórico que deja de estar vigente pero nunca se elimina.

## Relaciones

- Identity gobierna todo.
- Governance protege todo.
- Cognition utiliza Knowledge.
- Canon orienta Cognition.
- Capabilities consumen Knowledge.
- Business utiliza Capabilities.
- Infrastructure soporta todo.
- History registra todo.
- Roadmaps planifican todo.

## Regla de crecimiento

Si un nuevo elemento no encuentra lugar dentro del mapa, primero deberá evolucionar el mapa y después incorporarse el nuevo elemento.
