# ADR 0036 — Cacheo del historial de conversación y TTL extendido de 1h

**Fecha:** 2026-07-29
**Estado:** Aceptado

## Contexto

El fundador pasó tres transcripciones de video sobre metodología de ahorro de tokens en Claude/Claude Code (el artículo de Anthropic sobre "code execution" con MCP, la mecánica de prompt caching y TTLs, y una lista de hábitos por nivel) y pidió analizar la eficiencia real de todo el proyecto y la viabilidad de aplicar esos ahorros.

El análisis, hecho contra el código real (`snarf/capabilities/anthropic_llm.py`) y datos reales (`data/usage_log.jsonl`, 53 llamadas reales del día), confirmó que el cacheo de system+tools ya funcionaba (`cache_read_tokens` fijo en 14.895 en casi todas las llamadas), pero encontró dos brechas reales:

1. El array `messages` (el historial reconstruido en cada turno vía `EpisodicMemory.recent(10, ...)`, y la conversación creciente dentro del loop de herramientas de una misma llamada, `MAX_TOOL_ROUNDS=5`) no tenía ningún punto de cacheo — se reprocesaba entero, a tarifa completa, en cada llamada y en cada ronda.
2. `AnthropicLLM` llama a la API directa (`anthropic.Anthropic(api_key=...)`), no a la suscripción de Claude — por lo que corre bajo el TTL default de 5 minutos, no el de 1 hora. Dado el patrón real de uso del fundador (entra y sale del dashboard, el digest de Gmail chequea cada 5 minutos), esto es un riesgo concreto de perder el cache justo en el borde.

## Decisión

### 1. Segundo punto de cacheo: el último mensaje de cada llamada

`_mark_cache_breakpoint()` (nueva función en `anthropic_llm.py`) marca `cache_control` en el último bloque de contenido del último mensaje, justo antes de cada `messages.create()` — nunca mutando la lista original (`EpisodicMemory.recent()` puede ser reusada por quien llama). Esto cachea dos cosas distintas con el mismo mecanismo:

- **Entre llamadas del mismo turno de conversación**: el historial reconstruido (idéntico turno a turno, salvo el mensaje nuevo al final) ahora es reusable desde cache.
- **Entre rondas del loop de herramientas, dentro de una misma llamada**: antes, si Snarf necesitaba 2-3 rondas de herramientas para responder, cada ronda reprocesaba toda la conversación acumulada sin cachear nada — ahora cada ronda marca su propio último mensaje (el resultado de la herramienta, en las rondas después de la primera).

Verificado con las tres formas reales de contenido de mensaje que existen en el código (string plano, lista de bloques con imagen+texto del path de visión de Drive, lista de bloques `tool_result`) — nunca se intenta marcar un mensaje de assistant con bloques del SDK (`response.content`), porque ese mensaje nunca es el último antes de una llamada (siempre lo sigue un mensaje de `tool_result`).

### 2. TTL extendido a 1 hora

Ambos puntos de cacheo (system+tools, y el mensaje marcado) pasan de TTL default (5 min) a `"ttl": "1h"` explícito. Confirmado que la SDK instalada (`anthropic==0.120.0`) soporta el campo `ttl` sin necesitar ningún header beta (el viejo `anthropic-beta: extended-cache-ttl-2025-04-11` está retirado). El orden de breakpoints (system antes que messages, ambos con el mismo TTL) respeta la restricción real de la API de no tener un TTL más corto antes que uno más largo en la misma request.

## Verificado

- 288 tests (285 anteriores + 3 nuevos en `tests/test_anthropic_llm.py`): el mensaje marcado lleva `cache_control` con TTL de 1h; la lista de mensajes original que pasa el llamador no se muta; cada ronda del loop de herramientas marca su propio último mensaje sin filtrar el marcado entre rondas ni tocar el mensaje de assistant intermedio.

## Consecuencias

- Costo de escritura de cache más alto por byte (TTL de 1h cuesta más que el de 5 min al crear el cache), pero dado que el fundador ya reusa el cache de system+tools en casi el 100% de las llamadas reales del día, el costo extra de escritura es raro (solo ocurre cuando el cache expira) frente al ahorro constante de lectura.
- Si en el futuro se agrega un tercer punto de cacheo, respetar el orden largo-antes-que-corto de TTLs o la API rechaza la request.
- Se agregó `CLAUDE.md` (índice liviano para sesiones de Claude Code futuras — apunta a `MASTER_MAP.md` y las convenciones ya establecidas, no las repite) como parte de la misma ronda de optimización, aplicando el hábito recomendado por las transcripciones para las propias sesiones de trabajo.
