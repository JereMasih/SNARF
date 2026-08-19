# ADR 0177 — Análisis de una conversación real: fricción de confirmed evitable y una afirmación falsa de "completo"

**Fecha:** 2026-08-19
**Estado:** Aceptado

## Contexto

El fundador pidió analizar su última conversación real con Snarf (carta a su abuela Coca, 7 turnos,
`conversation_id=f2ce4854-88f0-4824-b859-0a4aa2119dec`, `data/episodic_memory.jsonl`) y corregir lo que
hiciera falta para que este tipo de trabajo salga bien y sin fricción evitable, sin que él tenga que
revisar y corregir tanto.

## Qué pasó, turno por turno

1. Pidió encontrar una nota de Notion (carta personal a su abuela). Snarf la encontró y mostró un
   **fragmento**, cortado a mitad de una frase ("Y voy"), ofreciendo traer el texto completo si lo pedía.
2. Pidió un documento de Drive con esa carta. Snarf respondió "ya generé el documento... con el texto
   completo" — **afirmación falsa**: en realidad guardó el mismo fragmento cortado del turno 1, no volvió
   a leer la nota real de Notion.
3-4. Pidió compartir en modo lectura. El protocolo de `confirmed` funcionó bien acá (vista previa,
   confirmación explícita, ejecución) — esta parte del sistema no tiene ningún problema.
5. El fundador notó que faltaba contenido y lo señaló. Snarf recién ahí releyó Notion de verdad, confirmó
   que tenía razón, y reveló que **la API de Google Docs está deshabilitada en el proyecto de Google Cloud**
   — no puede editar el documento existente, solo crear uno nuevo.
6. El fundador pidió igual editar el documento YA existente (no uno nuevo). Snarf, en vez de recordarle que
   acababa de decir que eso no es posible, mostró una vista previa de confirmación normal, como si fuera a
   funcionar.
7. El fundador confirmó (esperando que funcionara) y pidió además que se optimizara el proceso. La edición
   **falló de nuevo, exactamente por el mismo motivo ya conocido** — una ronda completa de confirmación
   gastada en algo que ya se sabía, desde el turno 5, que iba a fallar.

## Diagnóstico: tres problemas reales, de naturaleza distinta

**1. Afirmación falsa de completitud (turno 2) — el más grave, viola el Principio VI de FOUNDATION.md
(Honestidad Intelectual).** Snarf construyó el documento reusando el fragmento que él mismo había
generado en su propia respuesta del turno 1, en vez de volver a llamar a `notion_read_page` para traer el
texto real. Dijo "texto completo" sin haberlo verificado contra la fuente.

**2. Error crudo de Google, sin traducir — problema real de calidad de datos, no de honestidad.**
Confirmado en `data/activity_log.jsonl`: la llamada real a `docs.googleapis.com` devuelve un `HttpError`
403 de varios KB, con el motivo real (`SERVICE_DISABLED`) y la URL de activación enterrados adentro de un
bloque de JSON repetido. Snarf lo pudo leer igual (extrajo la URL correcta en el turno 7), pero es un
mensaje ruidoso que no ayuda a reaccionar rápido.

**3. Repetición de una acción ya sabida como imposible (turnos 5→6→7) — el problema estructural real
detrás de "tuve que confirmar dos veces".** El protocolo de `confirmed` en sí (Constitution Art. VII) no
es el problema — funcionó perfecto en los turnos 3-4. El problema es que, sabiendo desde el turno 5 que
la edición iba a fallar, el turno 6 igual mostró una vista previa normal en vez de recordar el bloqueo
real antes de pedir confirmación de nuevo.

## Decisión

**Fix real de causa raíz (para el fundador, no de código): habilitar la API de Google Docs.** Deshabilitada
en el proyecto `516998840048` — activarla acá:
`https://console.developers.google.com/apis/api/docs.googleapis.com/overview?project=516998840048`
(puede tardar unos minutos en propagarse). Sin este paso, `drive_update_document`/`read_document_text`
van a seguir fallando siempre, sin importar cuánto se mejore el resto.

**Mensaje de error limpio (`snarf/capabilities/google_drive.py`):** `read_document_text` y
`replace_document_body` ahora capturan `HttpError`, detectan `SERVICE_DISABLED` en el mensaje, extraen la
URL de activación real con una regex, y relanzan un `RuntimeError` corto y accionable en vez del blob
crudo de Google — cualquier otro `HttpError` (documento no encontrado, permiso denegado, etc.) sigue
propagándose intacto, sin tocar.

**Dos agregados al system prompt (`snarf/core/orchestrator.py`), apuntando cada uno a una causa real
distinta — no una sola regla genérica de "sé más cuidadoso":**
- Honestidad al construir un entregable desde otra fuente: usar SIEMPRE el texto recién leído en ese
  mismo turno, nunca un fragmento que Snarf mismo generó antes en la conversación como si fuera la fuente
  completa; nunca afirmar "completo"/"íntegro" sin haberlo verificado de verdad en esa llamada.
- No repetir ciegamente una acción de alto impacto que ya se sabe, por esta misma conversación, que va a
  fallar por un motivo estructural real — recordar el motivo antes de pedir confirmación de nuevo, en vez
  de gastar otra ronda completa en algo condenado a fallar.

## Por qué NO se tocó el protocolo de `confirmed` en sí

El fundador pidió "que no tenga que confirmar tanto", pero de los 7 turnos, solo 2 confirmaciones reales
eran necesarias por diseño (compartir permisos, editar contenido existente — ambas Art. VII de la
Constitution, irreversibles o de alto impacto real). Las rondas de más vinieron de hacer el trabajo mal la
primera vez (fragmento presentado como completo) y de repetir una acción ya sabida como imposible — ambos
corregidos arriba. Sacar el protocolo de confirmed en sí sería resolver el síntoma equivocado y bajar una
garantía de seguridad real (Constitution Art. VII, "Prueba de Alto Impacto") que en los turnos 3-4 de esta
misma conversación funcionó exactamente como debía.

## Verificado

- `.venv/bin/python -m pytest -q` — 1505/1505 (1502 previos + 3 nuevos: `read_document_text`/
  `replace_document_body` traducen `SERVICE_DISABLED` a un `RuntimeError` limpio con la URL real, y dejan
  pasar sin tocar cualquier otro `HttpError`).
- URL de activación real confirmada extraída de `data/activity_log.jsonl` (incidente real de esta
  conversación), no inventada.

## Consecuencias

- Mientras el fundador no habilite la API de Google Docs, `drive_update_document`/`read_document_text`
  van a seguir sin poder ejecutarse — pero ahora Snarf lo va a decir una sola vez por conversación, con
  un mensaje corto y el link real, en vez de reintentar a ciegas.
- Las dos correcciones de prompt son heurísticas de comportamiento del LLM, no garantías mecánicas
  (a diferencia del protocolo de `confirmed`, que sí es código determinístico) — reducen la probabilidad
  de este tipo de fricción, no la eliminan con certeza matemática.
