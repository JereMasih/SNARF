# ADR 0067 — Protocolo de costos: confirmar lecturas masivas + tope de repetición en el historial

**Fecha:** 2026-07-30
**Estado:** Aceptado

## Contexto

Con crédito real recién cargado en Anthropic, el fundador pidió con urgencia resolver la eficiencia de costos de LLM. Antes de tocar código se analizaron los datos reales (`data/usage_log.jsonl`, nunca estimados — Principio VI de FOUNDATION.md): el gasto real de ~25hs fue $5.09, 96% ($4.92) en el modelo principal de conversación (220 llamadas). El "ruteo de modelos por especialista" planeado como Parte 2 del plan original **ya estaba hecho** (Gmail digest, resumen de proyectos, visión de Drive y título de conversación ya usan Haiku) — no era ahí donde estaba el problema.

Dos hallazgos concretos:
1. Una sola llamada costó $1.09 (22% del día): `cache_creation_tokens: 523.869` en la conversación real donde el fundador pidió "un barrido de más de 30 correos... el último mil correos". `gmail_list_messages` no tenía ningún tope — el resultado gigante quedó embebido en `entry["response"]` y se re-transmitía/re-cacheaba entero en cada turno futuro de esa misma conversación.
2. 4 llamadas pegaron justo en `MAX_OUTPUT_TOKENS=4096` y se cortaron a mitad de camino.

## Decisión

**Confirmación previa para lecturas masivas, nunca un bloqueo permanente**: 6 tools sin tope real (`gmail_list_messages`, `calendar_list_upcoming_events`, `calendar_search_events`, `youtube_list_subscriptions`, `youtube_list_liked_videos`, `drive_list_files`) pasan por `Orchestrator._bulk_read_gate()`, que reusa el mecanismo ya existente (`_pending()`, Constitution Artículo VII, hoy en `gmail_send_message`/`drive_delete_file`) — cero cambios de frontend, es comportamiento guiado por el system prompt. Corrección explícita del fundador durante el diseño: "preguntar antes" nunca es "prohibir para siempre" — por encima de `BULK_READ_CONFIRM_THRESHOLD = 50` se pregunta, pero si el fundador confirma, se ejecuta la cantidad EXACTA que pidió, sin ningún recorte silencioso. `SYSTEM_PREFIX` suma un párrafo nuevo, mismo protocolo de 3 pasos que las tools de alto impacto pero framed en costo, no irreversibilidad.

**Nunca re-pagar un resultado ya obtenido**: `_capped_for_replay(text)` recorta a `HISTORY_REPLAY_MAX_CHARS = 8000` (~2000 tokens, generoso para una respuesta larga normal) lo que se RE-transmite al LLM al reconstruir `messages` desde `EpisodicMemory.recent(10, ...)` en cada turno nuevo. Solo afecta la replay — el JSONL, `GET /conversations/{id}` y las tools `list_conversations`/`get_conversation`/`search_memory` siguen mostrando el original completo sin tocar. El mensaje nuevo del turno actual nunca se cappea.

**Sin relación con lo vectorizado**: `drive_search_knowledge`/`drive_index_*` (ADR 0028) no están entre las 6 tools gateadas y corren sobre `VectorStore`/`VoyageEmbeddings`, camino totalmente separado — ni su calidad ni su alcance se tocan.

## Verificado

- 496/496 tests (18 nuevos para el gate de lecturas masivas — bajo el umbral ejecuta directo, sobre el umbral sin confirmar nunca llama a la capacidad real, confirmado ejecuta con la cantidad exacta pedida — más 3 nuevos para `_capped_for_replay` y su aplicación en `handle()`).
- Verificado con una llamada real a Anthropic + Gmail real (crédito recién cargado): pedir "traeme los últimos 200 correos" hizo que Snarf explicara el costo real y preguntara antes de ejecutar; al confirmar, trajo los 200 reales (no un número recortado) y, con buen criterio propio, los resumió en vez de tirar un muro de 200 líneas.

## Consecuencias

- El umbral (50) y el tope de replay (8000 caracteres) son constantes centralizadas, fáciles de ajustar si la experiencia real muestra que conviene otro número.
- Detectada y corregida contaminación real de datos de producción (`data/episodic_memory.jsonl`) de rondas de verificación anteriores de esta sesión donde un servidor "aislado" se lanzó sin `cd` al directorio correcto — ya reportado y limpiado en el ADR 0065, sin repetirse en esta ronda (verificado explícitamente que la nueva instancia aislada escribió en su propio `data/`, no en el real).
