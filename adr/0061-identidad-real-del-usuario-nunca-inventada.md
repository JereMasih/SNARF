# ADR 0061 — Identidad real del usuario, nunca inventada

**Fecha:** 2026-07-30
**Estado:** Aceptado

## Contexto

Snarf empezó a llamar al fundador "Andi" en medio de una conversación real — un nombre que nadie le dio, una alucinación de identidad directa (Principio VI de FOUNDATION.md: nunca presentar como cierto lo que no se puede justificar). El fundador pidió que Snarf sepa quién es su usuario real, que si no lo sabe lo pregunte en vez de inventar, y que esto quede atado de forma sólida al mismo `user_id` que ya identifica sus credenciales de Google — pensando explícitamente en que esto no debe confundir a ningún usuario, ni siquiera en un futuro multi-usuario.

## Decisión

Nuevo módulo `snarf/runtime/user_profile.py`, mismo patrón exacto que `personality_prefs.py`/`dashboard_prefs.py`: `data/user_profile/<user_id>.json`, `{"name": str | None}`, normalización defensiva (`_normalize_name` descarta no-strings, recorta whitespace, trunca a `NAME_MAX_LENGTH = 80`). Namespaced por `user_id` desde el día uno — satisface arquitectónicamente el pedido de "ni ningún usuario nunca a futuro" sin construir todavía un onboarding multi-usuario que no existe.

`profile_identity_instruction(name)` en `orchestrator.py` inyecta una de dos instrucciones de sistema, releída en cada turno (mismo criterio que `sarcasm_level`, nunca cacheada en `__init__`): si hay nombre guardado, instruye a Snarf a dirigirse siempre por ese nombre real y nunca cambiarlo por su cuenta; si no hay nombre, instruye explícitamente a NUNCA inventar ni asumir uno, preguntarlo si surge naturalmente, y guardarlo con la tool nueva `profile_set_name` en cuanto la persona lo diga.

`profile_set_name` es una tool sin gate de confirmación (igual que `personality_set_sarcasm`) — es un dato que la propia persona acaba de decir en el intercambio, reversible al instante, sin tocar terceros.

REST: `GET`/`PUT /profile`, mismo patrón que `/personality/preferences`. Frontend: campo de texto simple en el panel de configuración ("Tu nombre"), debajo del cual sigue el slider de sarcasmo — se persiste en `change` (blur o Enter), no en cada tecla.

## Verificado

- 459/459 tests (7 nuevos en `test_user_profile.py`, 5 nuevos en `test_orchestrator.py` cubriendo ambas ramas de `profile_identity_instruction` más la tool, 2 nuevos en `test_app.py` para el endpoint REST).
- Playwright en instancia aislada: `PUT /profile` persiste, `GET /profile` y la UI reflejan el valor tras un reload real de la página.
- `profile_set_name` mapeada en `snarf/telemetry/brain.py` al nodo `personality` (mismo dominio que `personality_set_sarcasm`) — sin esto, `test_tool_to_node_covers_every_orchestrator_tool` falla por diseño (cualquier tool nueva sin mapear rompe ese test a propósito).

## Consecuencias

- El nombre nunca se infiere de las credenciales de Google (email, nombre de cuenta) — deliberado: el fundador pidió específicamente que Snarf pregunte, no que asuma, incluso cuando ya tiene datos de auth disponibles. Si en el futuro se quiere ofrecer el nombre de Google como sugerencia prellenada (no autoasignada), es una extensión explícita, no lo que se construyó acá.
- No hay todavía un flujo de onboarding dedicado que pida el nombre en el primer uso — la instrucción de sistema le permite a Snarf preguntarlo "cuando le parezca natural" dentro de la conversación normal, no en un paso obligatorio previo. Si el fundador prefiere un onboarding explícito más adelante, es un refinamiento a pedido, no lo decidido acá.
