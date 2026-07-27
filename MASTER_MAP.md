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

- COGNITION (vigente, v0.1) — describe la arquitectura de tres capas (Capacidades / Especialistas / Snarf) y el razonamiento realmente implementado, no uno aspiracional.

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
