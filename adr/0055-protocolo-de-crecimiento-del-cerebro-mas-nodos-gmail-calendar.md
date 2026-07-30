# ADR 0055 — Protocolo de crecimiento del cerebro + más nodos (Gmail/Calendar)

**Fecha:** 2026-07-29
**Estado:** Aceptado

## Contexto

Tras ADR 0054 (Proyectos separado en 3 nodos), el fundador preguntó si se podían desplegar más nodos, y pidió algo más de fondo: un **protocolo permanente** para que cada vez que se agregue algo nuevo a Snarf (tool, Capacidad, Especialista, canal de entrada/salida) el cerebro se actualice al máximo detalle posible **sin tener que encararlo como tarea aparte cada vez** — que quede establecido de una vez cómo va a seguir creciendo.

## Decisión

### 1. Protocolo escrito, con dientes reales (no solo un comentario)

Al inicio de `snarf/telemetry/brain.py` queda un bloque de comentario permanente ("PROTOCOLO DE CRECIMIENTO DEL CEREBRO") que establece: toda tool/Capacidad/Especialista/canal nuevo evalúa en el MISMO cambio si merece nodo propio, con el criterio real ("¿un usuario reconocería esto como una subcapacidad distinta?"), no solo "mapearlo a lo que ya existe por comodidad". Referenciado desde MASTER_MAP.md ("Regla de crecimiento"), que ya tenía el mismo principio general para el mapa del ecosistema.

**El diente real**: `test_no_specialist_node_absorbs_too_many_tools` (nuevo) pone un techo de 8 tools por nodo del tier "specialist" — si se agrega una tool nueva y algún nodo lo supera, el test falla y obliga a decidir conscientemente si toca dividir, en vez de que se acumule en silencio otra vez (como pasó con Proyectos antes de ADR 0054). El tier "capability" no tiene techo automático a propósito: ahí puede haber operaciones legítimamente parecidas (CRUD de un mismo recurso), el criterio queda a juicio, no a un número.

### 2. Gmail y Calendar aplicados como segundo caso real

Mismo criterio que Proyectos, con datos que `activity_log` ya registraba sin costo nuevo:
- **Gmail** (7 tools → 3 nodos): `gmail_read` (listar/leer mensajes, listar labels), `gmail_manage` (crear/borrar labels, modificar labels de un mensaje), `gmail_send` (enviar — la única acción con efecto real hacia afuera).
- **Calendar** (8 tools → 2 nodos): `calendar_view` (listar calendarios/eventos, buscar eventos), `calendar_edit` (crear/borrar/mover eventos y calendarios).

Ambos quedan en el tier "capability" (son Capacidades crudas, no Especialistas Cognitivos) — mismo color de marca que tenían antes (aqua, por default), distinguidos por posición/ícono/tooltip. Cada nodo nuevo suma su propio ícono monolínea (envelope/tag/avión de papel para Gmail; grilla de calendario simple vs. grilla con un "+" para Calendar).

## Verificado

- 415/415 tests (2 tests viejos actualizados para los nuevos node ids de Gmail; 1 test nuevo — el techo de tools por especialista).
- Playwright contra el snapshot real (`GET /dashboard/brain`): confirma que los 5 nodos nuevos existen, que `gmail`/`calendar` (los ids viejos) ya no aparecen, y que el total de nodos reales pasó de 17 (antes de esta sesión) a 22. El grafo renderiza 22 íconos con sus 22 tooltips correctos, cero errores de consola.

## Consecuencias

- El techo de 8 tools por nodo "specialist" es una elección razonable, no un número que pidió el fundador — ajustable si en el uso real resulta muy bajo o muy alto.
- La próxima vez que se agregue una tool a Snarf, el protocolo de brain.py es el punto de partida — no hace falta releer este ADR ni el anterior para saber qué hacer.
