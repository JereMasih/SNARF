# ADR 0121 — Streaming para el LLM local (timeout de inactividad), timeout más alto, y revert automático del fallback tras un cooldown

**Fecha:** 2026-08-05
**Estado:** Aceptado

## Contexto

El fundador reportó, en producción real, que el rol `orchestrator` seguía saltando a `xai` (Grok) por
timeout con el server local ya caliente y sano — no un crash, solo una generación genuinamente lenta
(varias rondas de tool-calling en un turno complejo). Pidió tres cosas juntas: acelerar el proceso local,
estirar la paciencia antes de saltar de proveedor, y — la parte que faltaba por completo — algo que
vuelva al modelo local después de resolverse el motivo del timeout. Investigación de esta ronda confirmó
que `attempt_fallback()` (`snarf/runtime/llm_routing.py`, ADR previo) persiste el proveedor de reemplazo
**para siempre** en `data/llm_routing.json` — no existía ningún mecanismo de expiración en todo el repo.

## Decisión 1: streaming para llamadas locales — el timeout pasa a ser de inactividad, no de duración total

`LOCAL_TIMEOUT_SECONDS` (`snarf/capabilities/openai_compatible_llm.py`) se pasa como `timeout` al cliente
de la SDK de OpenAI, que internamente es un timeout de **lectura** de `httpx` — pero con una request
no-streaming, el server (`mlx_lm.server`) computa la respuesta COMPLETA antes de mandar el primer byte,
así que ese timeout de lectura terminaba cubriendo, en la práctica, la generación entera. Confirmado en
vivo contra el server real (`mlx_local_fast`, puerto 8991): con `stream=True` el contenido llega
token por token (62 chunks para una respuesta de dos oraciones) y los `tool_calls` llegan ya completos
en un solo delta por índice (no fragmentados como en la API real de OpenAI, pero el código de
reensamblado quedó genérico para ese caso igual).

Con esto, `LOCAL_TIMEOUT_SECONDS` deja de ser "cuánto puede tardar la generación entera" y pasa a ser
"cuánto puede pasar sin que llegue NINGÚN byte nuevo" — una generación lenta pero que sigue progresando
ya no choca contra el límite; solo un cuelgue real (el server no responde nada en absoluto) sigue
disparando el timeout, que es exactamente el caso que debe seguir disparando fallback.

Aplicado solo a `local=True` (`OpenAICompatibleLLM._complete_once`) — los proveedores cloud (xai, groq,
openai) siguen sin streaming, sin motivo real para tocar un camino ya probado en producción.

## Decisión 2: `LOCAL_TIMEOUT_SECONDS` sube de 150s a 240s

Con streaming ya cubriendo el caso de "lento pero progresando", este número queda como red de seguridad
adicional (un cuelgue real que ni siquiera manda el primer chunk) — no como el mecanismo principal. 240s
da más margen sin significar una espera silenciosa larga, porque el streaming ya haría que el fundador
vea la respuesta llegar en pantalla mucho antes si el modelo está generando de verdad.

## Decisión 3: revert automático tras un cooldown

`attempt_fallback()` ahora estampa cada entrada nueva con `fallback_expires_at` (`FALLBACK_COOLDOWN_SECONDS
= 600`, 10 minutos). Nueva función `maybe_revert_expired_fallback(role, entry, **generate_kwargs)`: si el
cooldown venció, reintenta el proveedor **local por defecto** del rol con una llamada real — mismo
criterio de honestidad que `attempt_fallback`, nunca revierte a ciegas, solo si el intento tuvo éxito. Si
falla (el local sigue sin responder), extiende el cooldown en vez de reintentar en cada turno.

Se consulta al principio de `_ResilientLLM.generate()` (los 4 roles que ya pasan por ahí) y, en línea,
en `Orchestrator.handle()`/`generate_conversation_title()` (los 2 roles de instancia fija que llaman
`attempt_fallback` directo, sin `_ResilientLLM` — ver comentario ya existente en ese código sobre por qué
no están envueltos). El chequeo es barato en el caso común (un compare de timestamps, sin red) — solo
intenta una llamada real cuando de verdad corresponde reintentar.

**Nunca toca una elección manual del fundador**: `fallback_expires_at` es lo único que distingue "esto
quedó así por un fallback automático" de "el fundador lo eligió a mano desde Configuración" — un `PUT
/llm-routing` manual nunca manda ese campo, así que se pierde solo al elegir a mano (comportamiento
correcto: una elección real del fundador nunca debe revertirse sola). `_normalize()` (`llm_routing.py`)
se ajustó para preservar el campo al guardar/cargar routing — antes lo descartaba silenciosamente.

## Verificado

- `.venv/bin/python -m pytest -q` — suite completa (ver CHANGELOG para el conteo final).
- Streaming (contenido, `reasoning`/pensamiento, tool_calls reensamblados, truncamiento por longitud con
  continuación automática) probado en vivo contra el server real `mlx_local_fast` antes de escribir el
  código de producción, no solo con mocks.
- `maybe_revert_expired_fallback`: no revierte antes del cooldown, no toca una elección manual sin el
  flag, revierte y persiste limpio cuando el local vuelve a responder, extiende el cooldown sin dejar
  rastro en el log de fallbacks cuando el local sigue caído.

## Consecuencias

- Un rol que cayó a un proveedor pago por un timeout puntual vuelve solo al modelo local dentro de los
  10 minutos siguientes, apenas éste vuelve a responder — ya no queda "pegado" en Grok/Anthropic
  indefinidamente sin que nadie lo note.
- El streaming local agrega una responsabilidad nueva de reensamblado (`_consume_stream`,
  `_StreamedToolCall`) — más código que antes, pero acotado a un solo método (`_complete_once`) y
  cubierto por tests que simulan el shape real de chunks de `mlx_lm.server`.
- `FALLBACK_COOLDOWN_SECONDS` (600s) es un valor de partida razonable, no medido en producción real
  todavía — ajustable si en la práctica revierte demasiado seguido (reintentos innecesarios) o demasiado
  tarde (se queda mucho tiempo en el proveedor pago sin necesidad).
