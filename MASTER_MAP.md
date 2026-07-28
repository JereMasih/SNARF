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

Planificado: extracción de contenido por tipo de archivo (PDF, imagen, audio, video) para poder vectorizar Drive completo; interfaz genérica de "fuente de conocimiento" para que Drive, Notion y archivos subidos a mano compartan un mismo motor de vectorización; reforzar la confirmación de acciones de alto impacto con un control independiente del modelo (por ejemplo, un botón en la interfaz) si el uso escala más allá de un solo usuario; login con Google (reemplazando o complementando la contraseña) y flujo real de un segundo usuario conectando su propia cuenta, cuando exista multi-usuario real.

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
