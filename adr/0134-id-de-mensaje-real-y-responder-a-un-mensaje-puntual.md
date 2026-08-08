# ADR 0134 — Id real por turno + "responder a un mensaje" puntual

**Fecha:** 2026-08-08
**Estado:** Aceptado

## Contexto

Pedido explícito del fundador, dentro de una ronda más amplia de rediseño de la interfaz de chat
(iconos para las acciones de una burbuja, una sola versión de audio, y una función nueva de
"responder a este mensaje" que permita referenciar puntualmente algo que Snarf dijo).

Investigación previa (sin tocar código): `EpisodicMemory.append()` nunca generó un `id` propio por
entrada — el único dato temporal era `timestamp`, compartido por el par input+response de un mismo
turno, y **no estable entre cliente y servidor**: en vivo, cada burbuja usaba su propio
`Date.now()/1000` generado en el navegador; al recargar, el backend devolvía el `timestamp` real del
turno persistido, que nunca coincidía con el del cliente. Sin un id real y persistente, "responder a
un mensaje puntual" no tenía nada estable a lo que apuntar.

## Decisión

**Un solo id por turno, generado en el cliente, reusado en dos roles.** El frontend ya generaba
`request_id` (`crypto.randomUUID()`) por cada `POST /send`, para la cancelación real (ver ADR 0132).
Ese mismo id se reusa ahora como identidad persistente del turno — sin sumar un campo nuevo al
payload de `/send` ni duplicar generación de uuids:

- `EpisodicMemory.append()` gana `id: str | None = None` (si no se provee, se genera server-side con
  `uuid.uuid4().hex` — cubre llamadas internas sin turno de usuario real: digest de Gmail, resumen de
  proyecto, etc.) y `reply_to_id: str | None = None`, ambos persistidos en cada entrada nueva.
- `EpisodicMemory.get_entry(conversation_id, message_id)` resuelve una entrada puntual por id —
  usado para citar el texto REAL de un mensaje anterior, nunca lo que el frontend diga que Snarf dijo.
- `SendRequest` gana `reply_to_id: str | None = None`. `orchestrator.handle()` gana el mismo parámetro,
  resuelve el texto citado contra la memoria real (degrada en silencio si el id no existe — mensaje
  viejo sin id, carrera, id inválido) y lo inyecta **solo en el mensaje que el LLM ve ese turno**
  (nunca en lo que se persiste como `input` — evita que un replay futuro de la conversación repita la
  cita en cada turno posterior, inflando tokens sin sentido).
- `POST /send` pasa `payload.reply_to_id` a `orchestrator.handle()` sin cambios adicionales.

**Frontend**: `addMessage()` gana `messageId`/`replyToPreview`. El botón "responder" (ícono, ver
`ICONS.reply`) solo aparece cuando hay un `messageId` real — nunca sobre un mensaje viejo cargado sin
`id` (conversaciones de antes de este ADR) ni sobre una respuesta cancelada. Al responder, un banner
sobre el renglón de escritura (`#replyContext`, reusa el mismo lenguaje visual que el resto de la
interfaz) muestra la cita con botón de cancelar. Al recargar una conversación, la cita se resuelve
DENTRO del mismo tramo ya cargado (`replyPreviewFor`, sin fetch aparte) — si el mensaje referenciado
quedó en una página más vieja no cargada, se degrada a un texto genérico honesto ("mensaje anterior"),
nunca inventa el contenido citado.

**Consolidación de audio (mismo pedido, parte de la misma ronda)**: antes convivían tres botones
("escuchar" con `speech`, "escuchar completo" con `text`, "escuchar entregable" con `deliverable")
sobre el mismo mecanismo de backend (`POST /tts`, sin ningún branching real — la única variable era
qué string de texto se sintetizaba). Ahora un solo botón, siempre lee `text` completo. Los botones de
escuchar/copiar/responder pasan a ser solo ícono (SVG monolínea, mismo lenguaje del resto de la app),
con el nombre completo como tooltip nativo.

## Riesgos/trade-offs

1. **Mensajes viejos (de antes de este ADR) no tienen `id`** — no pueden citarse (el botón "responder"
   no aparece). No hay migración retroactiva del JSONL existente; se acepta como límite conocido en
   vez de reescribir el historial persistido.
2. **El texto citado se resuelve con una lectura lineal de la conversación** (`get_entry` reusa
   `get_conversation`, que ya lee y filtra el archivo completo) — mismo costo que operaciones
   existentes similares (`search`), aceptable al volumen actual.
3. Un bug real encontrado y corregido durante la verificación: `addMessage()` pisaba con
   `div.textContent = text` cualquier `.msg-reply-ref` ya insertado en mensajes de texto plano del
   usuario — corregido a `appendChild(document.createTextNode(text))`.

## Verificado

- 12 tests nuevos: `tests/test_episodic_memory.py` (7: `id` explícito/generado, `reply_to_id`
  persistido/default, `get_entry` con match/sin match/scoping por conversación),
  `tests/test_orchestrator.py` (3: `id` persistido como `request_id`, cita inyectada en el mensaje al
  LLM sin tocar lo persistido, degradación silenciosa con `reply_to_id` inválido), `tests/test_app.py`
  (2: `/send` persiste `id`, `reply_to_id` viaja de punta a punta hasta el LLM).
- 1094/1094 tests de la suite completa.
- Verificado con Playwright contra una instancia de prueba (puerto 8000): burbujas de Snarf con
  exactamente un botón de audio (antes hasta 3), copiar sin texto visible (solo ícono), botón de
  responder ausente en mensajes viejos sin id y presente en un turno nuevo; click en "responder"
  despliega el banner con la cita, cancelar lo oculta, y el turno enviado lleva `reply_to_id` real en
  el `POST /send` y muestra la cita persistente en su propia burbuja — cero errores de consola en todo
  el flujo.
