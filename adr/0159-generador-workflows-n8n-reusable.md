# ADR 0159 — Generador de workflows n8n reusable (reemplaza el trabajo manual de ADR 0154)

**Fecha:** 2026-08-12
**Estado:** Aceptado

## Contexto

ADR 0154 (Fase 14) construyó el mapa navegable de n8n — 13 workflows reales — mediante llamadas HTTP
sueltas hechas a mano contra la API de n8n durante una sesión de Claude Code. Funcionó, pero dejó dos
deudas reales, señaladas explícitamente en ese ADR y en el pedido del fundador que originó esta serie de
fases: (1) no quedó ningún módulo committeado y reusable — regenerar el mapa exige repetir el trabajo
manual desde cero; (2) los nodos son snapshots de texto fijo (`notes` escritas a mano), nunca se
actualizan solos cuando cambia la receta real de un rol — exactamente lo que hace que el mapa hoy se
sienta "un nodo que dispara una lista sin sentido, sin trazabilidad" en vez de un espejo vivo de la
arquitectura real.

Con el Agent/Capability Registry (Fase 16, ADR 0157) y el motor de stages (Fase 17, ADR 0158) ya
construidos, esta fase cierra el círculo: un generador que lee el estado real (nunca datos escritos a
mano) y lo empuja a n8n de forma idempotente.

## Decisión

**`snarf/runtime/n8n_generator.py`** — dos funciones separadas a propósito:

- `build_executive_board_workflow(editar_prompt_workflow_id)`: **pura**, sin I/O, testeable sin n8n
  corriendo. Reconstruye la rama "Snarf - Executive Board" (un `noOp` por rol + un edge hacia "Snarf -
  Editar prompt") leyendo `agent_registry.get_agent_recipe()` (Fase 16) para el texto de cada nodo
  (prompt_id, tools activas, modelo/routing — recalculado en cada corrida, nunca un snapshot fijo) y
  `agent_graph_registry` (vía el mismo `agent_registry`) para las conexiones: sin overrides, fan-out plano
  idéntico al de ADR 0154 (cero regresión); con stages configuradas, una stage conecta a la siguiente en
  el propio canvas — esto es lo que resuelve el pedido original de "trazabilidad visual, orden correcto".
  n8n no tiene un concepto nativo de "barrera" entre grupos de nodos: encadenar desde el primer nodo de
  una stage hacia todos los de la siguiente alcanza para la trazabilidad visual pedida — quien ejecuta de
  verdad las stages sigue siendo `snarf/executive/specialist.py` (Fase 17), n8n solo lo representa. Esto
  reafirma el invariante de ADR 0156: n8n nunca se convierte en un motor de ejecución, solo en un espejo
  visual del estado real.
- `push_workflow(workflow, workflow_id, base_url, api_key)`: la mitad con red — `POST`/`PUT
  /api/v1/workflows` (mismo endpoint que ya usó ADR 0154 a mano). Idempotente por diseño: con el mismo
  `workflow_id`, correrlo dos veces sin cambios deja el mismo resultado en n8n. Levanta `RuntimeError`
  explícito si falta `N8N_API_KEY`, nunca intenta una llamada sin credencial real.
- `sync_executive_board()`: punto de entrada real — lee `n8n_workflows/ids.json`, arma el workflow, lo
  empuja, y actualiza el `id` en `ids.json` si es la primera vez.

**Ajuste de alcance respecto al plan original (documentado acá, no silencioso):** el plan inicial de esta
serie de fases asumía que cada nodo del board tendría un `httpRequest` "Ver receta actual" contra `GET
/n8n/agent/{role}` — un endpoint que originalmente estaba planeado para la Fase 19. Se adelantó a esta
Fase 18 (agregado en `app.py`, solo lectura, mismo patrón que `GET /n8n/prompts`) porque es de solo
lectura y de bajo riesgo — no tiene sentido demorar un endpoint seguro solo para mantener una numeración
de fases que no aporta nada acá. La Fase 19 sigue siendo la que agrega el camino de **escritura** con
confirmación de dos pasos (`propose`/`apply`), que es donde vive la verdadera preocupación de gobernanza
de ADR 0156.

**Alcance honesto, explícito:** esta fase cubre solo la rama del Executive Board. Las otras 8 ramas de
Specialists (agency/community/content/finance/productivity/research/sales/raíz) siguen el patrón manual de
ADR 0154 — migrarlas a este generador es trabajo de seguimiento, no bloquea esta fase ni el pedido
original del fundador (que se centró en poder editar la construcción de agentes, y el único patrón real de
"agente con receta completa" hoy es el board).

**Empaquetado también como Skill** (`.claude/skills/n8n-map-sync/SKILL.md`) — mismo criterio que
`os-audit`: "regenerar el mapa" pasa a ser un comando explícito invocable en cualquier sesión futura, no
una instrucción que se pierde releyendo este ADR.

## Verificado

- 10 tests nuevos en `tests/test_n8n_generator.py`: comportamiento idéntico al workflow de ADR 0154 sin
  overrides (fan-out plano completo, cada rol conectado a su propio "Editar prompt"), el texto de cada
  nodo refleja el `tool_subset`/routing activo real, las conexiones reflejan stages reales cuando hay
  overrides, idempotencia entre dos corridas sin cambios, `push_workflow` usa `POST` sin id existente y
  `PUT` con id existente, y rechaza sin `N8N_API_KEY`.
- Nuevo endpoint `GET /n8n/agent/{agent_id}` en `app.py` (solo lectura, `require_n8n_token`), 3 tests
  nuevos en `tests/test_app.py`.
- **No se ejecutó `push_workflow`/`sync_executive_board` contra la instancia real de n8n en esta ronda** —
  requiere Colima + el contenedor `snarf-n8n` corriendo y `N8N_API_KEY` real, ninguno disponible en esta
  sesión. Queda para la Fase 21 (verificación end-to-end) o para cuando el fundador corra la Skill
  `n8n-map-sync` con su entorno real levantado.
- 1355/1355 tests de la suite completa (`.venv/bin/python -m pytest -q`), 1342 previos (post ADR 0158,
  cifra corregida ahí — ver nota de honestidad en ese ADR) + 13 nuevos de esta fase (10 + 3, verificado con
  `git diff` contra HEAD, no solo contado a mano).
