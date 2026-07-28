# ADR 0025 — Interpretación de Gmail: primer Especialista Cognitivo real

**Fecha:** 2026-07-27
**Estado:** Aceptado

## Contexto

Al revisar el widget de Gmail del dashboard (ADR 0023/0024), el fundador pidió que Snarf no solo liste correos recientes, sino que los interprete: categorizarlos, señalar cuáles son importantes y por qué, sin tener el pedido completamente definido de antemano ("no lo tengo bien definido, pero algo así"). Antes de construir nada se ofrecieron tres alcances posibles, de menor a mayor infraestructura: (1) una herramienta que Snarf invoca en el chat cuando se le pide; (2) lo anterior más un botón en el propio widget del dashboard; (3) lo anterior más un refresco automático en segundo plano, aclarando explícitamente que esto último requiere construir infraestructura de scheduling que hoy no existe en Snarf (nada corre en background todavía). El fundador eligió la tercera opción, de forma informada.

Esta funcionalidad — razonar sobre un dominio acotado (una bandeja de entrada) con metodología propia, sin ser Snarf ni hablarle directamente al fundador — es exactamente lo que `COGNITION.md` define como un **Especialista Cognitivo**, la capa intermedia que existía documentada (`snarf/specialists/base.py`) pero vacía desde el walking skeleton original (ADR 0004). Es, además, el primer componente de Snarf que actúa de forma autónoma, sin que medie una conversación o un pedido explícito del fundador.

## Decisión

1. **`GmailDigestSpecialist`** (`snarf/specialists/gmail_digest.py`), primer Especialista real: recibe una Capacidad `GoogleGmail` y una Capacidad `AnthropicLLM` ya existentes (inyectadas por el `Orchestrator`, no instanciadas por el propio Especialista) y un `user_id`. Su método `refresh()` trae los últimos N correos, arma un listado y le pide al modelo de lenguaje, con un system prompt propio (no el de Snarf), que los agrupe por categoría y señale qué conviene revisar. Cachea el resultado en `data/gmail_digest/<user_id>.json` (gitignorado). `cached_digest()` lee esa caché sin disparar ningún trabajo nuevo. Degrada con claridad, sin inventar nada: si no hay correos, lo dice; si no hay LLM configurado, lo dice.

2. **Herramienta de chat**: `gmail_summarize_inbox`, registrada en `Orchestrator._tool_handlers` como cualquier otra herramienta de lectura (no es de alto impacto, no requiere confirmación). Snarf puede invocarla cuando el fundador pregunte algo sobre su correo; por defecto devuelve la interpretación cacheada si existe, o la genera si no; acepta `force_refresh=true` para cuando el fundador pida explícitamente una versión actualizada ahora mismo.

3. **Refresco en segundo plano**: `app.py` lanza, al arrancar el servidor (`asyncio.create_task` dentro del hook de `startup`, ahora `async`), un loop que cada `GMAIL_DIGEST_REFRESH_MINUTES` (variable de entorno, 30 por defecto) llama a `orchestrator.gmail_digest.refresh()` en un hilo aparte (`asyncio.to_thread`, para no bloquear el loop de eventos con la llamada de red), solo si el usuario tiene Google conectado y hay LLM disponible — si no, no hace nada y reintenta en el siguiente ciclo. Cualquier excepción se loguea y el loop sigue vivo (un fallo puntual no lo mata). Un hook de `shutdown` cancela la tarea prolijamente al apagar el servidor — necesario para que los tests que instancian `TestClient` no dejen tareas de `asyncio` colgadas.

4. **Widget de Gmail, ampliado**: sección nueva debajo de la lista de mensajes con un botón "interpretar bandeja" (dispara `POST /dashboard/widgets/gmail/digest/refresh`, síncrono, con estado de carga visible) y el texto de la última interpretación disponible (`GET /dashboard/widgets/gmail/digest`, lectura de caché, rápido), renderizado con el mismo motor de Markdown que ya usa el chat.

5. **Excepción documentada en `COGNITION.md`**: en el dashboard, la salida del Especialista se muestra directamente, sin pasar por la voz de Snarf — consistente con que el resto del dashboard (ADR 0022) ya muestra datos crudos de Capacidades sin filtrar. En el chat, en cambio, la salida del Especialista vuelve a Snarf como resultado de herramienta, y es Snarf quien decide cómo presentarla.

## Verificado

- 18 tests nuevos (91/91 en total): el Especialista en aislamiento (sin mensajes, sin LLM disponible, con LLM, cacheo real, `handle()`), la herramienta de chat (caché, sin caché, `force_refresh`), los dos endpoints nuevos (conectado/no conectado, éxito, degradación), y la función de refresco en segundo plano en sus tres ramas (Google no conectado, LLM no disponible, listo para refrescar) — esta última invocada directamente con `asyncio.run()`, no simulando el loop infinito completo.
- Sin tareas de `asyncio` colgadas al cerrar `TestClient` en ningún test (se agregó el hook de `shutdown` específicamente por esto).

## Descartado explícitamente en esta ronda

- Especialistas para otros dominios (Drive, Calendar, YouTube): no pedidos todavía: se construyen si y cuando el fundador los pida, siguiendo el mismo patrón.
- Multi-usuario en el refresco de segundo plano: el loop hoy solo refresca `DEFAULT_USER_ID` ("fundador"), coherente con que ese sigue siendo el único usuario real del sistema.

## Consecuencias

- Primer costo real y recurrente de infraestructura: cada refresco en segundo plano es una llamada real a la API de Gmail y una llamada real a la API de Anthropic, cada 30 minutos por defecto, corran o no haya conversación activa. Vale la pena que el fundador tenga esto presente si nota consumo de cuota inesperado.
- `snarf/specialists/` deja de estar vacío: el próximo Especialista que se agregue tiene ahora un ejemplo real de cómo integrarse (recibir Capacidades ya construidas por inyección, no crearlas; exponerse como herramienta de Snarf; opcionalmente engancharse a un refresco en segundo plano si corresponde).
- `data/gmail_digest/` es nuevo y queda fuera de git, igual que `credentials/`, `data/dashboard_prefs/` y la memoria episódica real.
