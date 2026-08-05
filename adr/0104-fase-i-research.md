# ADR 0104 — Fase I: rama Research

**Fecha:** 2026-08-05
**Estado:** Aceptado

## Contexto

Tercera rama de la Fase I. El plan nombraba 3 capacidades distintas (Deep Research, Trend Scan,
Competitor Watch) más búsqueda web real y transcripciones de YouTube — sin dejar ninguna marcada
como bloqueada por falta de vendor (pedido explícito del fundador en la ronda de feedback que
originó este plan).

## Decisión

1. **Vendor de búsqueda web: Tavily**, ya decidido en el plan — `snarf/capabilities/web_search.py::TavilySearch`,
   mismo patrón lazy-client-desde-env-var que `Notion` (`TAVILY_API_KEY`). Sin la credencial real,
   `available` es `False` y ningún research se inventa una fuente.
2. **`GoogleYouTube.get_video_captions(video_id)`** (nuevo): intenta la descarga real de un caption
   track vía `captions().list()`/`captions().download()`. Limitación real de la API de YouTube,
   verificada contra su documentación (no asumida): solo se puede descargar el contenido de un
   caption track si el usuario autenticado es dueño del video — para un video de terceros, la API
   devuelve un `HttpError` real (403), tratado igual que "sin captions disponibles" (nunca
   distingue "no existe" de "no autorizado" de cara al llamador).
3. **Explícitamente NO se construye el fallback a ffmpeg+STT para videos de terceros** que el plan
   original sugería ("si un video no tiene captions, cae al pipeline ffmpeg+STT que Drive ya usa").
   Motivo real encontrado al diseñar esto: ese pipeline extrae audio de un archivo YA DESCARGADO
   (Drive); un video de YouTube arbitrario para research necesitaría descargarse primero, lo que
   requiere una herramienta nueva (`yt-dlp` o similar) — una dependencia nueva con consideraciones
   reales de ToS de YouTube que no corresponde decidir unilateralmente. Queda nombrado como decisión
   pendiente del fundador, no como código a medio construir.
4. **`ResearchSpecialist`** (`snarf/specialists/research/`): una sola clase real, tres configs
   (`ResearchModeConfig`, mismo patrón que `ExecutiveRoleConfig` de la Fase E) — `deep_research`
   (Sonnet, informe estructurado), `trend_scan` (Haiku, patrones repetidos entre fuentes),
   `competitor_watch` (Haiku, análisis de actores de mercado). Comparten el mismo mecanismo real:
   junta fuentes reales (Tavily + captions de YouTube si se pasan URLs), sintetiza con disciplina de
   honestidad (nunca completa el vacío si las fuentes son insuficientes), publica el informe con
   `DocumentPublisher` — que ya lo indexa de inmediato (ver KNOWLEDGE.md, "Reportes como insumo") sin
   mecanismo nuevo.
5. **LightRAG Query del video de referencia = `knowledge_search`** con otro nombre — no se adopta
   LightRAG como framework, mismo criterio "cero framework" que ya aplica a Inteligencia Ejecutiva.
   **NotebookLM Bridge queda fuera de alcance**: Google no publica ninguna API real para eso, no es
   cautela de planificación.
6. Tres tools nuevos (`research_deep_dive`, `research_trend_scan`, `research_competitor_watch`),
   nodo nuevo `specialist_research` (los tres tools caen ahí — misma clase real, mismo criterio que
   Inteligencia Ejecutiva con sus 7 roles en un solo nodo).

## Hallazgo real durante esta ronda: la Skill Factory (Fase H) ya se usó en producción

Escribiendo el test de aislamiento del endpoint `GET /skill_proposals`, se encontró un registro
REAL en `data/skill_proposals/` (no de fixture): un intento real de construir una skill
"Procesador de PDFs" (rama `productivity`), que falló con `Credit balance is too low` del lado de
Claude Code (el CLI necesita su propio saldo/credencial, separado de `ANTHROPIC_API_KEY` que usa
Snarf para conversar). Confirma, con datos reales de producción (no un smoke test aislado), que el
flujo completo de Fase H funciona de punta a punta: confirmación real, invocación real de Claude
Code, `session_id` real registrado, y una falla real manejada con gracia (`status: "failed"`,
motivo real persistido, cero archivos tocados). El propio test que encontró esto tenía un gap de
aislamiento real (`SkillFactorySpecialist._proposals_dir` no estaba neutralizado en la fixture
`client` de `test_app.py`, a diferencia de `dashboard_curator`/`executive_board` que sí lo estaban)
— corregido en esta misma ronda.

## Verificado

- 22 tests nuevos: `tests/test_web_search.py` (5), `tests/test_google_youtube_captions.py` (3),
  `tests/test_research_specialist.py` (7), más cobertura de orchestrator/schema/telemetría (7).
- 858/858 tests de la suite completa.

## Consecuencias

- Con `TAVILY_API_KEY` real (pendiente de que el fundador la provea), la rama queda 100% operativa
  sin ningún cambio de código adicional.
- El fallback ffmpeg+STT para YouTube de terceros queda como decisión real pendiente del fundador:
  sumar `yt-dlp` (o vendor equivalente) como dependencia nueva, con sus propias consideraciones de
  ToS.
