# ADR 0083 — Verbos por tool real y dock radial integrado dentro de la Vista HUD

**Fecha:** 2026-08-03
**Estado:** Aceptado

## Contexto

Feedback real del fundador tras usar la Vista HUD construida en Fase 4:
(1) muy poca variedad de verbos — varias tools distintas dentro del mismo
nodo compartían el mismo verbo genérico; (2) "la rueda" (el dock radial de
Fase 2/5) no aparecía en ningún lado — la Vista HUD solo mostraba la tabla
de texto, nunca se integró el componente visual del dock a la app real.

## Decisión

### `snarf/telemetry/verbs.py` — `VERB_BY_SKILL`, verbo propio por tool

Nueva tabla de 68 entradas, una por cada tool real de
`snarf.core.orchestrator.TOOLS` (`drive_delete_file` ≠ `drive_list_files`
aunque compartan nodo). `verbo_tematico()` ahora prioriza `skill` >
`nodo` > `agente`. `test_verb_by_skill_covers_every_orchestrator_tool`
(mismo patrón que `test_tool_to_node_covers_every_orchestrator_tool` de
`test_brain.py`) garantiza que ninguna tool real quede sin verbo propio.
Las llamadas de vendor (`anthropic:claude-sonnet-5`, sin nombre de tool)
siguen cayendo al verbo de nodo — no hay más granularidad real posible ahí
sin inventar sub-acciones que no existen.

### Dock radial real, integrado dentro de `#brainHudView`

El prototipo de Fase 2/5 (`web/hud_dock_prototype.html`) seguía sin
enlazarse a la app real — decisión explícita de esa fase, revisada ahora a
pedido del fundador. Se portó (no se enlazó el archivo — mismo motivo de
ADR 0080, `web/index.html` no tiene mecanismo de estáticos) la lógica
esencial directo al `<script>` existente:

- `HUDGestureControllerMini` — copia funcional de `HUDGestureController`
  (Fase 2), renombrada para no colisionar si en el futuro se decide cargar
  el archivo original también.
- `buildHudMiniDock`/`hudMiniCenterOutPositions` — mismo arco con
  perspectiva real y "el de mayor prioridad cae al centro" de Fase 5,
  escalado al espacio del panel (150px de alto vs. los ~320px del
  prototipo standalone).
- Poll propio (`pollBrainHudDock`, mismo intervalo que el feed de texto)
  contra `GET /dashboard/dock_priority` (Fase 5) — datos reales, nunca
  mock, coherente con que esta es la primera vez que ese endpoint se
  consume desde la app real (antes solo desde el prototipo aislado).
- **Integración nueva, no pedida explícitamente en el plan original pero
  con sentido real:** click en un nodo del mini-dock atenúa (opacity 0.25)
  las filas del feed de texto que no correspondan a ese nodo — conecta
  visualmente el dock con el feed en vez de ser dos widgets sin relación
  en la misma pantalla.

## Bug real encontrado y corregido: llave de cierre faltante rompía TODO el dashboard

Al insertar el bloque nuevo de JS, `pollBrainHudDock()` quedó con el
`catch` sin cerrar (`}` faltante) — un error de sintaxis en un `<script>`
inline rompe el parseo de **todo** el bloque, no solo la función nueva:
el dashboard entero dejaba de inicializar y degradaba a un estado sin
JS (la vista de chat/grabación default, sin ningún widget). Encontrado
verificando con Playwright contra un servidor real (`pageerror:
"Unexpected end of input"`) — nunca se hubiera visto solo mirando el
diff. Corregido agregando la llave faltante.

## Verificado

- `.venv/bin/python -m pytest -q` — 605/605 passed (1 test corregido en
  `test_app.py` por el cambio de verbo esperado, 4 tests nuevos en
  `test_verbs.py`).
- Playwright contra un servidor de prueba real en directorio temporal
  (datos aislados, cero riesgo para `data/` real — el fundador estaba por
  generar actividad real propia): login, toggle a Vista HUD, 10 nodos
  reales en el mini-dock (incluida la alerta de costo, en ámbar, con
  datos sembrados que cruzan el umbral), verbos ricos y distintos por tool
  en el feed (`hojeando el Drive` / `borrando el archivo` / `creando la
  carpeta` / `curando la bandeja`, antes todos hubieran sido el mismo
  verbo genérico de nodo), click en un nodo atenuando correctamente las
  filas no relacionadas, cero errores de consola.
- Servidor real de producción (puerto 8002) reiniciado con el código
  corregido — mismo link de siempre
  (`https://macbook-pro-de-jeremas.tailb10c73.ts.net`). `data/` real
  verificado sin cambios de conteo antes/después del reinicio.

## Consecuencias

- Ninguna decisión de Fase 7 (auditoría del nodo Orchestrator) se tocó en
  este cambio — sigue pendiente de la aprobación explícita del fundador.
