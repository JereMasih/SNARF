# ADR 0054 — Proyectos se separa en 3 nodos reales del cerebro (sin costo nuevo)

**Fecha:** 2026-07-29
**Estado:** Aceptado

## Contexto

El fundador pidió revisar si el cerebro podía mostrar más subcapacidades/nodos encendiéndose, **sin aumentar el costo**. Revisando `TOOL_TO_NODE` contra `activity_log` (que ya registra el `tool_name` real de cada llamada, sin ninguna llamada nueva a ningún vendor), el caso más claro es Proyectos: 14 herramientas distintas —de lejos las más numerosas de cualquier nodo— caían todas en un único nodo `specialist_projects`, dejando invisible CUÁL parte de Proyectos estaba realmente activa en un momento dado. `calendar` (8 tools) y `gmail` (7) son candidatos menores para el futuro, no tan desproporcionados como para justificar tocarlos ahora.

## Decisión

`specialist_projects` se reemplaza por 3 nodos reales, agrupados por lo que un usuario reconocería como subcapacidades distintas (no por detalle de implementación interna), usando el mismo `tool_name` que ya se registraba:

- **`specialist_projects_manage`** (6 tools): `project_create`, `project_list`, `project_get`, `project_delete`, `project_set_prompt`, `project_search`.
- **`specialist_projects_tasks`** (5 tools): `project_add_task`, `project_complete_task`, `project_delete_task`, `project_add_note`, `project_delete_note`.
- **`specialist_projects_conversations`** (3 tools): `project_assign_conversation`, `project_unassign_conversation`, `project_list_conversations` (Proyectos Mark II, ADR 0047/0048).

Los 3 nuevos nodos quedan en el mismo tier `"specialist"` que `specialist_gmail` (ahora 4 especialistas en ese anillo, no 2), mismo color de marca (magenta, distinguidos por posición/ícono/tooltip como ya pasaba entre gmail y proyectos). Cada uno suma su propio ícono monolínea (gestión reusa el ícono de carpeta ya existente; tareas es un checklist nuevo; conversaciones reusa el ícono de chat ya usado en el resto de la interfaz) y su propia etiqueta ("Proyectos: gestión" / "Proyectos: tareas y notas" / "Proyectos: conversaciones").

## Verificado

- 414/414 tests (`test_snapshot_routes_project_tools_to_specialist_nodes_not_drive_or_knowledge` actualizado para cubrir los 3 nodos nuevos con 3 tool_names reales distintos).
- Playwright contra una instancia real aislada: `GET /dashboard/brain` real confirma que los 3 nodos nuevos existen en el snapshot y que el nodo único viejo ya no aparece; el grafo renderiza 19 íconos (orquestador + 18 nodos, antes 17); los 3 tooltips muestran las etiquetas correctas.

## Consecuencias

- `calendar` y `gmail` quedan como candidatos futuros para el mismo tratamiento (lectura vs escritura) si el fundador lo pide — no implementado ahora, señalado nada más.
- Cualquier tool nueva de Proyectos que se agregue en el futuro debe elegir explícitamente uno de estos 3 nodos (o proponer un cuarto) — `test_tool_to_node_covers_every_orchestrator_tool` sigue siendo la red de seguridad que evita que quede sin mapear.
