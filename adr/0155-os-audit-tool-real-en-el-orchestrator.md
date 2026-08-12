# ADR 0155 — `os_audit` como tool real de Snarf, además de la Skill de Claude Code

**Fecha:** 2026-08-12
**Estado:** Aceptado

## Contexto

Se creó primero una Skill de Claude Code (`.claude/skills/os-audit/SKILL.md`, adaptada de una skill
genérica externa) para auditar drift/frescura/organización de este repo desde una sesión de Claude Code.
El pedido explícito del fundador fue "añadila a Snarf" — pero probarla escribiéndole a Snarf en su propia
ventana de chat del navegador no hizo nada, porque son dos sistemas de tools completamente distintos:

- Una **Skill de Claude Code** solo la puede invocar Claude Code — vive en `.claude/skills/`, la lee el
  harness de Claude Code al iniciar sesión, nunca la ve el Orchestrator de Snarf.
- **Snarf-el-producto** corre como su propio proceso (Orchestrator, puerto 8002) con su propio sistema de
  tools nativo de Anthropic (`TOOLS` + `_tool_handlers` en `snarf/core/orchestrator.py`), sin ninguna
  integración con las Skills de Claude Code (ver CLAUDE.md, "Skills vs. MCP" — política explícita de que
  esa distinción es sobre cómo trabaja Claude Code en este repo, no arquitectura de Snarf).

Para que el fundador pueda pedirle una auditoría del repo a Snarf desde su chat normal, hacía falta un
tool real nuevo en el Orchestrator — no reusar el `SKILL.md` (que es prosa para que un LLM de Claude Code
siga paso a paso), sino reimplementar la lógica mecánica de los checks en Python puro.

## Decisión

**Módulo nuevo `snarf/runtime/os_audit.py`**, mismo criterio que `introspection.py`: funciones puras que
devuelven señales crudas y estructuradas (dicts), nunca un reporte narrado ya armado — el modelo (Snarf)
es quien arma el reporte final a partir de estos datos, igual que `system_snapshot()`. Cubre los checks de
la Skill que son verificables mecánicamente, sin juicio semántico:

- `routing_check`: extrae paths reales (spans entre backticks) de `CLAUDE.md`/`MASTER_MAP.md` y verifica
  cuáles existen en disco (rutas repo-relativas) o fuera del repo (`~/...` o absolutas largas tipo
  `/opt/homebrew/bin/docker`); y a la inversa, qué carpetas reales de primer nivel el manual ni menciona.
- `freshness_check`: último ADR real (por nombre + `git log` de esa ruta), última entrada de
  `CHANGELOG.md`, y fechas/snippet de "Estado actual" de cada `ROADMAP*.md`.
- `root_hygiene_check`: archivos sueltos en la raíz que no son ni manual ni gobernanza ni config estándar
  (allowlist explícita + patrones para `ROADMAP*.md`/`docker-compose*.yml`/`requirements*.txt`), y el
  conteo de palabras de `CLAUDE.md` (peso real de lo que se carga siempre).
- `git_hygiene_check`: archivos trackeados que matchean patrones de secretos (`.env`, credenciales,
  `service-account*.json`, claves privadas — nunca `.env.example`, el template sancionado), y si
  `.gitignore` cubre `.env` de verdad.
- `skills_and_agents_check`: carpetas de `.claude/skills/*` sin `SKILL.md` exacto o con frontmatter
  incompleto (`name`/`description` vacíos) — nunca cargan, nunca fallan visiblemente.

**Fuera de alcance a propósito, delegado al modelo**: los checks semánticos de la Skill (misroutes reales
vs. solo un path muerto, duplicados por significado, el "gut check" de intuitividad, ubicación de
contexto expertise/situacional) requieren juicio de lenguaje natural — no se reimplementan en Python.
`run_audit()` le da al modelo las señales objetivas; la síntesis narrada (veredictos, tags de modo de
falla, batches de arreglo) queda para el propio Snarf al responder, no para este módulo.

**Sin escritura de archivo**: a diferencia de la Skill (que guarda `audits/os-audit-YYYY-MM-DD.md`), este
tool es puramente de lectura — no existe hoy ningún tool que escriba archivos de texto al propio repo de
Snarf (confirmado al investigar: `drive_create_document` solo apunta a Drive/servidor de documentos del
fundador, nunca al filesystem del repo). Agregar un write-to-repo genérico es una decisión aparte, no
necesaria para que el fundador reciba el reporte narrado en el chat.

**Registro completo del protocolo de crecimiento** (mismo patrón que ADR 0152): tool nuevo en `TOOLS` +
dispatch dict (`snarf/core/orchestrator.py`), nodo `utility` en `TOOL_TO_NODE` (`brain.py`), verbo propio
en `VERB_BY_SKILL` (`verbs.py`), extractor en `DETAIL_EXTRACTORS` (`detail.py`), y sumado a
`MCP_EXPOSED_TOOLS` + `ROLE_TOOL_SUBSETS["cto"]` (`snarf/mcp/tools.py`) — es puramente de lectura y
acotado, mismo criterio que `system_introspect`, útil para que el rol `cto` de Inteligencia Ejecutiva
también pueda consultar la salud real del repo.

## Verificado

- `tests/test_os_audit.py`: cada check probado contra repos sintéticos en `tmp_path` (paths muertos vs.
  existentes, URLs/rutas HTTP cortas ignoradas, paths absolutos largos tratados como externos, carpeta
  oculta nunca confundida con marcador `./` relativo — bug real encontrado y corregido durante el
  desarrollo, ver commit de este ADR —, secretos trackeados vs. `.env.example` nunca falso positivo,
  skill rota vs. bien formada).
- `tests/test_orchestrator.py::test_os_audit_tool_delegates_to_os_audit_run_audit`: dispatch real vía
  `Orchestrator._handle_tool("os_audit", {})`.
- Cobertura genérica existente (`test_brain.py`, `test_verbs.py`, `test_mcp_server.py` con sus tests de
  cobertura total sobre `orchestrator.TOOLS`) confirma automáticamente que `os_audit` quedó registrado en
  los 4 puntos del protocolo de crecimiento, sin ningún test nuevo dedicado a eso.
- 1310/1310 tests de la suite completa (18 nuevos: 17 de `test_os_audit.py` + 1 de dispatch en
  `test_orchestrator.py`).
