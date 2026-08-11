# ADR 0145 — Reapertura: n8n puede escribir prompts/config directo, sin aprobación humana

**Fecha:** 2026-08-11
**Estado:** Aceptado

## Contexto

ADR 0144 (Fase 9.3) cerró la mitad "cockpit" de la escritura real de Prompt Registry/Configuración
dinámica y dejó la mitad "n8n" explícitamente sin resolver: *"darle a n8n poder de escritura real sobre
los prompts/config de Snarf es una autoridad categóricamente distinta de lo que n8n tiene hoy... necesita
su propia decisión de gobernanza explícita con el fundador, no algo que esta ronda decida
unilateralmente."*

Se le presentó la decisión al fundador con tres opciones reales (solo lectura como hoy; n8n propone +
HITL vía el protocolo de Fase 8; n8n escribe directo con su propio token) — **eligió la tercera:** n8n
puede escribir directo, con su propio `N8N_CONTROL_TOKEN`, sin aprobación humana de por medio.

**Esto reabre, para esta superficie puntual, el principio "n8n observa y propone, nunca decide"** fijado
en ADR 0093 (MCP) y reafirmado en ADR 0139 (n8n self-hosted) — mismo patrón real de gobernanza ya usado
antes en este repo (ADR 0028 reabierta explícitamente por el fundador para multi-usuario, citado en
`MASTER_MAP.md`): un principio de diseño anterior sigue vigente en todo lo demás, pero el fundador tiene
autoridad real (Constitution Art. II) para reabrirlo puntualmente cuando lo pide de forma explícita e
informada — no es una reinterpretación silenciosa de esta sesión.

## Decisión

**Seis endpoints nuevos, `/n8n/prompts` y `/n8n/generation-config`** (mismas rutas que los del founder,
prefijadas `/n8n/`, gateadas por `require_n8n_token` en vez de `require_user`) — `GET`/`PUT {id}`/
`POST {id}/rollback` para ambos. **Nunca una segunda implementación**: `app.py` extrae la lógica real de
cada operación a seis funciones privadas (`_prompts_snapshot`, `_put_prompt`, `_rollback_prompt`,
`_generation_config_snapshot`, `_put_generation_config`, `_rollback_generation_config`) que las rutas de
founder y de n8n comparten — un cambio escrito por n8n es indistinguible, en el storage real
(`data/prompts.json`/`data/generation_config.json`), de uno escrito por el founder desde el cockpit.

**`refresh_llm_routing()` real, mismo motivo que ADR 0144**: el camino de n8n no tiene una sesión de la
que sacar un `user_id` real — usa `DEFAULT_USER_ID` (mismo criterio ya establecido por
`GET /n8n/status`, que ya resuelve `_google_connected(DEFAULT_USER_ID)` de la misma forma).

**Por qué no HITL (segunda opción presentada, no elegida)**: hubiera reusado el protocolo de Fase 8
(`approval.requested`/`granted`) pero necesitaba un mecanismo nuevo de "aplicar tras aprobar" que no
existe todavía (Fase 8 solo observa el protocolo `confirmed` YA existente de los tools del Orchestrator,
no generaliza una cola de cambios pendientes de aplicar). El fundador decidió no construir eso ahora.

## Riesgo real, explícito

Un flujo de n8n mal configurado (o el propio `N8N_CONTROL_TOKEN` filtrado) puede sobreescribir el prompt
o la configuración de generación de cualquier rol sin que el founder lo apruebe en el momento — mismo
nivel de exposición que ya existe hoy para `N8N_CONTROL_TOKEN` en general (ver ADR 0139: "nunca la cookie
de sesión del founder", pero ya es la llave real de `GET /n8n/status`/`introspect`). Mitigación real ya
vigente, sin cambios: nada se pierde nunca (`rollback` real sobre el historial completo, ninguna versión
se borra), y el propio founder puede revertir cualquier cambio de n8n desde `/prompts`/
`/generation-config` con su propia sesión en cualquier momento.

## Verificado

- 6 tests nuevos en `tests/test_app.py`: `/n8n/prompts` y `/n8n/generation-config` rechazan sin token
  (401), escriben y leen de vuelta correctamente, rollback real reactiva el default original, y un
  cambio escrito por el camino de n8n es visible de inmediato desde el camino del founder (mismo
  storage, nunca dos implementaciones).
- 1277/1277 tests de la suite completa (`.venv/bin/python -m pytest -q`), 1271 previos (post Fase 9.3) +
  6 nuevos.
