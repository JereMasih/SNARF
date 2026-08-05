# ADR 0113 — Fix real: respuestas truncadas y audio incompleto (causa raíz común)

**Fecha:** 2026-08-05
**Estado:** Aceptado

## Contexto

El fundador reportó dos síntomas que parecían distintos: respuestas de Snarf cortadas a mitad de
camino, y el audio generado dando "una partecita nomás cortita" en vez de la información completa —
además de que el botón para escuchar el audio completo de una respuesta ya no estaba disponible.

Investigando el código real se encontró una única causa raíz para ambos síntomas:
`MAX_OUTPUT_TOKENS = 4096` en `snarf/capabilities/anthropic_llm.py` era un tope demasiado bajo para
el uso real de Snarf (planes, documentos largos), reusado tal cual por `openai_compatible_llm.py` y
`gemini_llm.py`. Cuando una respuesta larga chocaba contra ese tope (`stop_reason == "max_tokens"`),
Snarf solo agregaba una nota visible al final, sin reintentar. Como el marcador de habla
(`---HABLA---`) va al *final* del texto generado, un corte por longitud significaba que ese marcador
nunca se alcanzaba a escribir — `split_speech()` caía al fallback mecánico de
`FALLBACK_SPEECH_MAX_CHARS = 400`, exactamente el síntoma de audio corto reportado.

Por separado, ADR 0063 (2026-07-30) había retirado a propósito el botón "escuchar completa" del
diseño original (ADR 0056), en favor de "escuchar" (narración) + "escuchar entregable" (condicional
a que el modelo decida emitir el bloque `---ENTREGABLE---`). Ninguno de los dos garantiza audio
completo en todos los casos — es lo que el fundador recordaba como "esa opción estaba antes".

## Decisión

- `MAX_OUTPUT_TOKENS` subido de 4096 a 16000 en `anthropic_llm.py` (heredado automáticamente por
  `openai_compatible_llm.py`/`gemini_llm.py`, que lo importan de ahí).
- `AnthropicLLM._create()`: toda llamada a `messages.create` pasa a hacerse vía
  `client.messages.stream(...) + get_final_message()` — la propia SDK de Anthropic arriesga timeout
  HTTP en requests no-streaming con `max_tokens` alto, y con el nuevo tope streaming deja de ser
  opcional.
- Red de seguridad nueva: `MAX_CONTINUATIONS = 2`. Si pese al tope más alto la respuesta se sigue
  cortando por longitud, se le pide al modelo continuar EXACTO desde donde cortó (nunca reescribir
  desde cero) y se concatena — tanto en `AnthropicLLM.generate()` como en
  `OpenAICompatibleLLM.generate()` (mismo criterio, usa `finish_reason == "length"`). Recién si se
  agotan los reintentos se admite el corte con la nota visible de siempre.
- `web/index.html`: restaurado un botón **"escuchar completo"** que sintetiza `text` (la respuesta
  íntegra en pantalla) a pedido, sin depender de `speech` ni de que el modelo haya decidido incluir
  un entregable — coexiste con "escuchar" y "escuchar entregable", no los reemplaza.

## Verificado

- 946/946 tests de la suite completa (`tests/test_anthropic_llm.py`,
  `tests/test_openai_compatible_llm.py` con tests nuevos de continuación automática).
- Verificado en vivo contra el server real de producción (Playwright, vía `fetch` autenticado a
  `/send`): un pedido real de un plan detallado de 18 pasos numerados devolvió 4678 caracteres de
  texto y 1312 de narración hablada, sin ninguna nota de truncado, en 25.3s.

## Consecuencias

- Costo por turno más alto en el peor caso (hasta 3 llamadas si se agotan las continuaciones), pero
  acotado por `MAX_CONTINUATIONS` — nunca un loop sin límite.
- Requiere reiniciar el server real de producción para que el fix entre en vigencia — hecho en esta
  misma sesión, confirmado con el fundador antes.
