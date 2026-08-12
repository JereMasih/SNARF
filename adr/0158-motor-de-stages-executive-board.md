# ADR 0158 — Motor de ejecución con stages reales en el Executive Board

**Fecha:** 2026-08-12
**Estado:** Aceptado

## Contexto

ADR 0157 (Fase 16) construyó `agent_graph_registry.py` — un registro versionado de "stages" (listas de
roles que corren en paralelo entre sí, en secuencia entre stages) — pero deliberadamente sin ningún motor
que lo lea: `ExecutiveBoardSpecialist.consult()` seguía siendo 100% fan-out paralelo, ignorando cualquier
override guardado. Esta fase cierra esa brecha: el registro empieza a tener efecto real en cada consulta
al board.

## Decisión

**`snarf/executive/specialist.py::consult()`** pasa de un único `ThreadPoolExecutor` sobre todos los roles
seleccionados a un loop `for stage in stages:` — paralelo dentro de cada stage (mismo patrón
`contextvars.copy_context()` ya resuelto, sin tocarlo), secuencial entre stages. Nuevo método
`_stages_for(selected)`: recorta las stages guardadas a los roles pedidos en esta consulta puntual
(`roles=` de `consult()`), y agrega como stage extra al final cualquier rol pedido que el grafo guardado no
mencione en ninguna stage — **nunca se pierde un rol seleccionado** solo porque la configuración guardada
no lo cubre explícitamente. Sin ninguna versión guardada en el registro, `_stages_for` devuelve una única
stage con los roles pedidos — comportamiento byte-a-byte idéntico al fan-out de siempre.

El resultado de cada stage (solo los roles que sí respondieron, nunca los fallidos) se acumula en un
`upstream: dict[str, dict]` que se pasa a `_consult_one()` de la stage siguiente. `consult_role()`
(`snarf/executive/process.py`) gana un parámetro nuevo, opcional, `upstream_context: str | None = None`:
si está presente, se antepone al system prompt real (nunca al mensaje de usuario) como bloque de texto —
"Postura previa de {rol}: {headline}...". Sin `upstream_context`, el comportamiento es idéntico a antes de
esta ADR.

**Invariante explícito, reafirmado de ADR 0094:** esto da más **información** a un rol en una stage
posterior, nunca **autoridad** — ningún rol pasa a decidir por otro, y Snarf sigue siendo el único
sintetizador final de todas las posturas, sin importar el orden interno de ejecución. El propio texto
anteponer al system prompt lo deja explícito ("información adicional, nunca autoridad sobre tu propia
postura, opiná con tu propio criterio").

## Verificado

- 4 tests nuevos en `tests/test_executive_specialist.py`: sin stages configuradas el comportamiento es
  idéntico a antes (nadie recibe `upstream_context`); con stages, una stage posterior recibe de verdad el
  texto de la anterior; un rol pedido que el grafo guardado no cubre corre igual, en una stage extra; un
  rol fallido nunca se reenvía como si fuera una postura real.
- 2 tests nuevos en `tests/test_executive_process.py`: `upstream_context` se antepone de verdad al system
  prompt real con el que se llama al LLM; sin `upstream_context`, el system prompt no se toca.
- Corregidos 2 tests preexistentes (`tests/test_app.py`,
  `test_dashboard_executive_board_consult_persists_and_the_widget_reflects_it`, y el fake de
  `test_executive_specialist.py`) cuyos dobles de `consult_role` tenían la firma vieja de 4 argumentos —
  sin el `upstream_context=None` agregado a su firma, la llamada real desde `_consult_one()` fallaba con
  `TypeError`, capturado silenciosamente por el `except Exception` del ThreadPoolExecutor y reportado como
  "no se pudo consultar" en vez de la respuesta real. Detectado corriendo la suite completa, no solo los
  tests nuevos — deja como recordatorio real que cualquier cambio de firma de `consult_role` necesita
  auditar todos los dobles de test, no solo los del módulo que se está tocando.
- 1342/1342 tests de la suite completa (`.venv/bin/python -m pytest -q`), 1336 previos (post ADR 0157) + 6
  nuevos (los 2 tests corregidos no suman, ya contaban). Corrección de honestidad sobre esta misma cifra:
  la primera corrida completa de esta ronda reportó "1 failed, 1341 passed" (el bug de `test_app.py` de
  arriba) — 1341 es ese número de la corrida CON el fallo, no el total real tras corregirlo; el total real
  con los 6 tests nuevos y sin fallos es 1342, verificado con `git diff` contra HEAD (4 nuevos en
  `test_executive_specialist.py` + 2 en `test_executive_process.py`) antes de escribir esta cifra acá.
