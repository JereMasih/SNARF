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
- CHARACTER (vigente, v0.2 desde el 2026-07-29 — ver ADR 0039: ingenio seco, responsabilidad propia y registro/cercanía, manteniendo explícitamente la regla anti-imitación de personajes de ficción de v0.1)
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

Desde el 2026-07-28 (ADR 0029): sumados `DocxExtractor`/`PptxExtractor`/`XlsxExtractor` (`.docx`/`.pptx`/`.xlsx`, todos locales y sin costo) al tier gratuito de indexación (`query='free_tier'`). Nuevo `snarf/telemetry/activity_log.py`: registro real de qué herramienta ejecuta el Orchestrator y cuándo (`data/activity_log.jsonl`, `GET /dashboard/activity`) — prerrequisito de la futura visualización "cerebro de Snarf", todavía sin construir.

Desde el 2026-07-28 (ADR 0030): Snarf puede crear archivos reales (`DocumentBuilder` + `GoogleDrive.upload_file` con conversión a Google Doc/Sheet/Slide nativo + `DocumentPublisher`, tres herramientas nuevas: `drive_create_document`/`drive_create_spreadsheet`/`drive_create_presentation`) y recibir archivos subidos por el fundador (`POST /files/upload`, botón de adjuntar en la interfaz) — todo queda indexado de inmediato, sin esperar la próxima corrida de background (`DriveIndexer.index_file`). Verificado en vivo contra el Drive real: Markdown, Google Doc por conversión y Excel, los tres creados y ya buscables.

`drive_index_start(query='free_tier')` ya corrió de verdad — `VOYAGE_API_KEY` configurada por el fundador, con método de pago agregado en Voyage para destrabar el límite de 3 requests/minuto que tienen las cuentas nuevas sin pago cargado (bug real encontrado y corregido: `VoyageEmbeddings` no pasaba `max_retries` al SDK). También se verificó en vivo un piloto de video (19 archivos, 10.4GB, carpeta "Grabaciones"): $2.03 de costo real medido, 0 errores.

Desde el 2026-07-29 (ADR 0031): construida la visualización "cerebro de Snarf" estilo Jarvis (Fase 3 del roadmap de dashboard) sobre el registro real de actividad del Orchestrator (ADR 0029) combinado con `usage_log.jsonl` y el manifiesto de indexación de Drive — nuevo `snarf/telemetry/brain.py` mapea las 35 herramientas reales y los 3 vendors reales a nodos de Capacidad + el Orchestrator, y nuevo endpoint `GET /dashboard/brain`. Widget nuevo en el dashboard (`brain`) que se expande a pantalla completa: grafo de nodos con tamaño real (nunca vacío) + feed de actividad en vivo, con pulsos de luz animados (SVG) viajando del centro a cada nodo en cada evento real, solo mientras la pantalla está abierta (mismo patrón de polling browser-driven que el digest de Gmail, ADR 0026).

Desde el 2026-07-29 (ADR 0032): `PdfExtractor` reemplaza `pypdf` por PyMuPDF (`fitz`) — resuelve de forma nativa el CMap/ToUnicode de fuentes Type3 embebidas (un bug real: PDFs exportados desde apps móviles/navegadores, con texto seleccionable en cualquier visor, que `pypdf` no extraía). Fallback de OCR con Tesseract (`spa+eng`) para PDFs sin ninguna capa de texto real (escaneos puros), rasterizando con la misma librería. Si ninguna estrategia encuentra texto usable, `ContentExtractor` lo declara explícito en vez de indexar contenido vacío en silencio.

Desde el 2026-07-29 (ADR 0032): el cerebro pasa a dos anillos — Especialistas Cognitivos (anillo interno, hoy solo `specialist_gmail`) y Capacidades (anillo externo), reflejando la arquitectura real de tres capas de COGNITION.md/ADR 0003 en vez de una lista plana. El nodo "voz" se separó en `stt`/`tts` (dato ya distinguible en `usage_log`, antes escondido). Cada nodo late distinto según tenga actividad real reciente (latido rápido y brillante) o no (latido lento de espera) — nunca apagado del todo, nunca simulando actividad inexistente — y un edge activo suma un flujo continuo de luz (CSS puro) además del pulso puntual por evento de ADR 0031.

Desde el 2026-07-29 (ADR 0033): el cerebro suma un tercer anillo, Entrada (`input_text`/`input_voice`/`input_file`, el más interno), sobre un nuevo `snarf/telemetry/input_log.py` que instrumenta por primera vez los tres puntos reales de entrada a Snarf (`/send`, `/transcribe`, `/files/upload`) — antes ninguno emitía ningún evento. Nuevo estado "fantasma" (gris, sin animación) para nodos que nunca tuvieron actividad real, distinto de "en espera" (tiene historia, no reciente). Paleta de color real por tier (magenta para Especialistas, violeta para voz, aqua para Capacidades, blanco/violeta para el centro, colores reales por tipo de archivo en los pulsos) — tomada tal cual del documento real `PALETA DE COLORES JERE MASIH TRADER`, encontrado en el propio Drive indexado del fundador en vez de inventada.

Desde el 2026-07-29 (ADR 0035): el dashboard de escritorio (≥900px) reemplaza las tres zonas fijas (arriba/izquierda/derecha, columnas de ancho fijo) por una grilla unificada de 12 columnas donde **todo** bloque —incluidos el historial de conversaciones y el chat con Snarf, antes fuera del sistema de widgets— se puede arrastrar para reposicionar y redimensionar (ancho y alto) libremente, con la posición/tamaño persistidos por usuario. Nuevo modo enfoque: el chat se expande a pantalla completa con la barra lateral del menú hamburguesa de mobile (historial, nueva conversación, usuario/config) reusada, no duplicada. Desktop arranca siempre en el Dashboard (antes: Chat). Mobile queda completamente afuera de este cambio, sin resize, mismo comportamiento de siempre. También corregidos tres bugs reales de UI: texto redundante en modo teclado, la app abriendo el teclado nativo en mobile al arrancar sin que el usuario tocara nada, y "escuchar" fallando en silencio cuando la reproducción de audio se bloqueaba (política de autoplay o una carga interrumpida). "Proyectos" (prompt + archivos por proyecto, organización en Drive) quedó registrado como pedido explícito del fundador, sin construir — es una Capacidad nueva entera, con su propio ciclo de planificación pendiente.

Desde el 2026-07-29 (ADR 0034): `drive_read_file` (la herramienta que Snarf usa para leer un archivo en el chat) reusa `ContentExtractor` en vez de decodificar bytes crudos como UTF-8 — un bug real encontrado con un PDF real del fundador (Type3, ver ADR 0032) que devolvía glifos ilegibles porque la lectura en vivo nunca pasaba por el extractor arreglado, solo la indexación. Un solo camino de verdad ahora para "extraer contenido de un archivo de Drive". El cerebro suma una capa de `<canvas>` (partículas ambiente con resplandor real por blending aditivo, estallido de partículas por evento real, cámara que hace zoom hacia el nodo que se activa) sobre el SVG/CSS ya construido — primera vez que el proyecto usa canvas, con la misma disciplina de nunca correr sin la pantalla completa abierta y visible.

Desde el 2026-07-29 (ADR 0036): segundo punto real de cacheo de tokens en `AnthropicLLM.generate()` — además del system prompt+tools (ADR 0026), ahora el último mensaje de cada llamada (y de cada ronda del loop de herramientas) se marca con `cache_control`, aprovechando que el historial reconstruido desde `EpisodicMemory` es idéntico turno a turno. Ambos puntos de cacheo pasan de TTL default de 5 minutos a 1 hora — Snarf llama a la API directa de Anthropic (no la suscripción de Claude), así que corría bajo el TTL corto pese a que el patrón real de uso del fundador se beneficia del largo. Análisis motivado por tres transcripciones sobre metodología de ahorro de tokens que el fundador pasó; también sumó `CLAUDE.md` (índice liviano para sesiones de Claude Code futuras).

Desde el 2026-07-29 (ADR 0037): orden default del dashboard de escritorio rehecho a pedido concreto del fundador — historial a la izquierda, cerebro arriba centrado, sistema/costo al lado del cerebro, chat debajo, y conversaciones/memoria/Drive/Gmail/Calendar/YouTube en una columna a la derecha. Tamaño de fuente base del modo escritorio subido de 16px a 18px (pensado para 1920×1080 real). El cerebro suma una malla de filamentos (satélites por nodo, coloreados con el color real de su tier, enlazados entre nodos vecinos) y una aura volumétrica sobre el canvas de partículas ya existente — pura atmósfera, ninguna lógica de datos tocada; se aclaró el límite de ADR 0006 (estilo sí, colores literales de la franquicia no).

Desde el 2026-07-29 (ADR 0041, diagnóstico corregido por ADR 0044): `GoogleDrive`/`GoogleGmail`/`GoogleCalendar`/`GoogleYouTube` reintentan ante un fallo de conexión (solo en lecturas idempotentes) — pero la causa real del `[SSL] record layer failure` visto en producción no era una falla transitoria de red, era una condición de carrera: FastAPI corre cada endpoint en un thread del pool, el dashboard dispara varios widgets en paralelo, y el `self._service` cacheado como singleton de cada Capacidad se compartía entre threads — `httplib2` no es thread-safe para eso. Reproducido el fallo a voluntad con llamadas concurrentes reales, y confirmado resuelto pasando el cliente a `threading.local()` (cada thread el suyo). Gmail ahora muestra fecha real por mensaje, y el digest interpretado por el LLM viene acompañado de una referencia estructurada real (no inventada) de los mensajes que resume, arriba de la lista de mensajes en sí (antes al revés). Nuevo widget `usage`: consumo real por vendor (llamadas/tokens/caracteres/segundos) más el cupo real de la cuenta de ElevenLabs consultado en vivo — distinto del panel `cost`, que siempre fue una estimación en dólares, nunca un saldo real. Tamaños default de los widgets del dashboard recalibrados con evidencia real (los tamaños que el propio fundador ya había elegido a mano), y ya no se recortan al achicarlos. Cuadro de texto de envío pasa de una sola línea a un textarea que crece. Acceso a perfil/configuración restaurado en modo desktop (estaba oculto sin reemplazo, bug preexistente).

Desde el 2026-07-29 (ADR 0045): construida la Capacidad "Proyectos", registrada desde ADR 0035 y pospuesta hasta hoy. Cada Proyecto es una carpeta propia dentro de "Snarf/Proyectos" en Drive (con subcarpetas propuestas por un modelo barato según el tipo de proyecto), un prompt/instrucciones propias, y sus propias listas de tareas y notas — persistidos en `data/projects/{id}.json`. Prerrequisito resuelto en el camino: "Snarf - Archivos" y "Proyectos" se unificaron bajo una única carpeta raíz "Snarf" en el Drive del fundador (migración real verificada, mismos archivos y ids, solo cambió el padre), separada de sus carpetas propias. `GoogleDrive` sumó `rename_file` y `share_file` (alto impacto, gateado). Búsqueda semántica acotada a un proyecto puntual vía `project_id` opcional en la subida de archivos, reusando el vectorizado ya existente (no un motor paralelo). Nuevo nodo `specialist_projects` en el cerebro (mismo tier que `specialist_gmail`). Barra lateral con switcher Conversaciones/Proyectos y panel de detalle (prompt editable, tareas, notas, link a Drive) — reusa el mismo `#sidebar` de ADR 0035 en las tres superficies (mobile, modo enfoque, hamburguesa desktop), sin nav nueva.

Planificado, todavía sin construir: interfaz genérica de "fuente de conocimiento" para que Drive, Notion y archivos subidos a mano compartan un mismo motor de vectorización (hoy el pipeline es específico de Drive); reforzar la confirmación de acciones de alto impacto con un control independiente del modelo (por ejemplo, un botón en la interfaz) si el uso escala más allá de un solo usuario; login con Google (reemplazando o complementando la contraseña) y flujo real de un segundo usuario conectando su propia cuenta y vectorizando su propio Drive, cuando exista multi-usuario real — evaluado explícitamente en ADR 0028 y pospuesto a propósito (los datos de indexación ya están namespaced por `user_id` desde el día uno, así que agregar el segundo usuario es pasar otro `user_id`, no rediseñar el pipeline).

## Business

Unidades económicas, productos, servicios y empresas.

## Infrastructure

Repositorios, Git, IA, servidores, automatizaciones y herramientas.

Repositorio Git local inicializado el 2026-07-25, publicado el 2026-07-27 en `https://github.com/JereMasih/SNARF` (público; secretos excluidos por `.gitignore`). Estructura de código bajo `snarf/` (core, capabilities, specialists, runtime); memoria episódica en `data/`; credenciales externas (Google OAuth) en `credentials/`, fuera de git.

Desde el 2026-07-27: dependencias fijadas a versión exacta en `requirements.txt` (antes sin pinear); `requirements-dev.txt` para dependencias de test; primera suite de tests automatizados en `tests/` (27 tests, `pytest`) cubriendo memoria episódica, dispatch de herramientas y — el más importante — que ninguna de las 8 herramientas de alto impacto ejecuta su acción real sin `confirmed=true`; CI en `.github/workflows/tests.yml` que corre la suite en cada push/PR. Ver ADR 0019 y `ARCHITECTURE_AUDIT.md` (auditoría técnica completa del repositorio, distinta de la auditoría de gobernanza de Architecture Review 0001).

Desde el 2026-07-28: `VPS_MIGRATION.md` — runbook preparado (no ejecutado) para mudar Snarf de la Mac del fundador a un VPS Linux, reusando Tailscale (ADR 0008) en vez de montar un dominio público. Ver Roadmaps, ítem 5 de la Fundación técnica.

Desde el 2026-07-29 (ADR 0042): respaldo automático de `data/` (`snarf/runtime/data_backup.py`) a `data_backups/` (gitignored, últimos 14 snapshots), disparado al arrancar el server y cada 6 horas mientras corre — memoria episódica, logs, preferencias del dashboard, caché de Gmail, archivos locales (no el índice de Drive, regenerable desde la fuente real). Agregado tras un incidente real en esta misma sesión: un error de Claude Code sobreescribiendo por accidente el `usage_log.jsonl` real durante una verificación en vivo, sin backup ni forma de recuperarlo.

## History

Registro permanente de decisiones, cambios y aprendizaje.

Hoy implementado mediante `adr/` (decisiones de arquitectura y gobernanza) y `CHANGELOG.md` (registro legible de cambios del proyecto). Ambos son el mecanismo real del Artículo VIII de Constitution mientras no exista un dominio History más amplio.

## Roadmaps

Planificación de la evolución del sistema.

**Dashboard, plan por fases (2026-07-27, ver ADR 0022 y ADR 0023):**

- Fase 1 (construida): dashboard con widgets sobre datos 100% reales — estado del sistema, conversaciones, memoria episódica, y (corrección de ADR 0023 a la Fase 2 original) Drive, Gmail, Calendar y YouTube, porque esas Capacidades ya existían y no eran hipotéticas. Menú de usuario, panel de configuración (qué widgets mostrar), reordenamiento persistido por usuario, navegación Chat/Dashboard por swipe o botón en mobile, y layout "Jarvis" (chat centrado + paneles alrededor) en desktop ancho. Ver Capabilities y Architecture para el detalle.
- Fase 2 (futura, sin fecha): cada Capacidad genuinamente nueva que se agregue (Trading, GitHub, MCP, lo que se decida — subsistemas que hoy no existen) suma su propio widget al dashboard, opt-in por el usuario.
- Fase 3: la visualización "Jarvis brain" de los flujos del sistema está construida (2026-07-29, ver ADR 0031 y Capabilities). Queda futura, sin fecha, la aplicación de escritorio nativa multi-ventana (múltiples monitores) que originalmente compartía esta fase.

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
- **Reemplazo de los chatbots externos del fundador** (ChatGPT es el más usado, también Claude): migrar el historial y contexto de "Proyectos" existentes fuera de Snarf (ej. "Alimentación y Workout", "High Value Men", con mucha conversación acumulada) hacia adentro de Snarf. La Capacidad "Proyectos" en sí ya existe (ADR 0045, ver Capabilities) — esto es migrar contenido puntual hacia ella, no construirla.
- **Especialistas por dominio dentro de un Proyecto:** que Snarf mantenga contexto general pero delegue en un Especialista Cognitivo propio (con su propia metodología/contexto, ver arquitectura de tres capas en COGNITION.md) para dominios específicos como alimentación/workout — el fundador siempre habla con Snarf, nunca directamente con el Especialista, mismo patrón que `GmailDigestSpecialist`. Distinto de la Capacidad "Proyectos" (ADR 0045, ya construida): esto es un Especialista por dominio corriendo *dentro* de un Proyecto puntual, todavía sin construir.

**Fundación técnica vs. modo Capacidades (2026-07-28):** a pedido del fundador, se separa el roadmap en dos etapas explícitas — mientras la Fundación no esté cerrada, no se suman Capacidades nuevas (mercado, negocio, Especialistas) salvo las tres ya en curso/acordadas. El objetivo es no seguir construyendo infraestructura por debajo de capacidades que ya se agregaron.

**Fundación técnica (tiene que estar lista antes de seguir sumando capacidades):**

1. (construido, ver ADR 0029) Extractores `.docx`/`.pptx`/`.xlsx` sumados al tier gratuito de Drive.
2. (construido, ver ADR 0029) Registro real de actividad del Orchestrator (`data/activity_log.jsonl`, `GET /dashboard/activity`) — qué herramienta se ejecuta y cuándo.
3. (en curso, ver ADR 0028) Vectorización real de Drive corriendo — tier gratuito + piloto de video verificado ($2.03 reales por 19 videos/10.4GB). Base de conocimiento que el resto de la Fundación y las Capacidades futuras van a usar.
4. (construido, ver ADR 0030) Snarf puede crear, recibir y exportar archivos. `DocumentBuilder` genera Markdown/PDF/PPTX/XLSX localmente; `GoogleDrive.upload_file` los sube y, con `convert_to`, los convierte a Google Doc/Sheet/Slide nativo editable (verificado en vivo, sin necesitar la API de Google Docs aparte); `DocumentPublisher` orquesta todo y deja el resultado indexado al instante (`DriveIndexer.index_file`). Nuevo endpoint `POST /files/upload` + botón de adjuntar en la interfaz: cualquier archivo subido queda guardado en la carpeta `Snarf - Archivos` e indexado; si es una imagen, la descripción de la visión se devuelve de inmediato al chat. **Nunca se duplica el archivo original**: lo local es solo el índice vectorial (texto + embeddings), no una copia del archivo — verificado y explicado al fundador. Además, `destination='drive'|'device'|'server'` en las tres herramientas de creación: `device` guarda en `data/local_files/<user_id>/` (`LocalFileStore`) y devuelve un `download_url` real (`GET /files/local/<user_id>/<archivo>`) que el navegador resuelve con el diálogo nativo de "Guardar como" del sistema operativo de quien lo use; `server` usa el mismo mecanismo pero sin link, como carpeta de trabajo — **exclusivo del fundador** (`allow_server_storage`, gateado en código y en el prompt). Los tres destinos quedan igual de indexados y buscables (`DriveIndexer.index_local_text` para device/server, metadato `location` en cada chunk). Snarf pregunta cuál destino prefiere antes de crear, salvo que ya se lo hayan dicho.
5. (preparado, sin ejecutar — ver `VPS_MIGRATION.md`) Migración de Snarf de la Mac del fundador a un VPS **Linux** (no Windows — todo el stack, incluido `ffmpeg`, corre nativo ahí, y sale más barato) — que Snarf esté disponible 24/7 sin depender de que la Mac esté prendida. El túnel que el fundador no identificaba en su momento es Tailscale (ADR 0008, ya en uso) — se recomienda seguir usándolo desde el VPS (mismo mecanismo, cero curva nueva) en vez de montar un dominio público todavía. La causa más probable de la lentitud reportada es la Mac funcionando como servidor casero (subida residencial + trabajo pesado compitiendo en la misma máquina), no Tailscale en sí. Runbook completo, con checklist paso a paso, en `VPS_MIGRATION.md` — a ejecutar recién cuando el fundador tenga el VPS.
6. (siguiente, decisión reabierta el 2026-07-28) Base multi-usuario mínima: un segundo usuario de prueba real conectando sus propias cuentas en paralelo al fundador, para validar que el namespacing por `user_id` (ya presente en credenciales, preferencias de dashboard, digest de Gmail e índice de Drive desde el día uno de cada pieza) funciona de punta a punta con dos usuarios reales simultáneos. **Corrige a ADR 0028**: esa ADR había pospuesto multi-usuario por no existir un segundo usuario real; el fundador la reabrió explícitamente hoy, condicionada a que primero exista el VPS (5).

**Reordenamiento puntual (2026-07-29):** el fundador adelantó la visualización "cerebro de Snarf" (originalmente en Modo Capacidades, ver abajo) por delante del cierre de la Fundación — antes de migrar a VPS (5) o seguir indexando Drive (3, video/imágenes/audio/"other" pendientes), porque es lo que más necesita ahora para entender el estado del sistema y su prerrequisito (ítem 2) ya estaba listo. Construida y verificada el mismo día, ver ADR 0031. No reabre la regla general de la línea de arriba — es una excepción puntual, no una habilitación general para adelantar Capacidades.

**Modo Capacidades (recién después de cerrar la Fundación):**

- Datos de mercado (Bitcoin, petróleo, oro, S&P 500, Dow Jones, Nasdaq) — Capacidad nueva contra un proveedor a elegir, autocontenida.
- **Construida el 2026-07-29 (ADR 0045):** la Capacidad "Proyectos" en sí — prompt de proyecto, tareas y notas propias, carpeta (y subcarpetas propuestas) en Drive, búsqueda semántica acotada al proyecto, barra lateral con switcher Conversaciones/Proyectos. Queda pendiente, sin fecha: migración de "Proyectos" externos (ChatGPT: Alimentación y Workout, High Value Men) hacia adentro de un Proyecto real de Snarf, y arquitectura de Especialistas por dominio corriendo dentro de un Proyecto puntual (ver Capabilities).
- ~~Visualización "cerebro de Snarf" estilo Jarvis, sobre el registro real del ítem 2 de la Fundación.~~ Construida fuera de orden el 2026-07-29 — ver ADR 0031 y el reordenamiento puntual de arriba.
- Fuente real de costos/ingresos/campañas de negocio — no es código, es decidir con el fundador qué sistema contable/de ads conectar.
- Interfaz de configuración + onboarding (del propio fundador primero, después de un segundo usuario real).
- Modelo multi-usuario gratis/pago (cómo se traslada el costo real de vectorizar al usuario que lo pide) — sigue en los planes a pedido explícito del fundador, sin decidir todavía; ver borrador de tiers registrado en el briefing visual de esta jornada.

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
