# ADR 0186 — OAuth de Notion por usuario

**Fecha:** 2026-08-20
**Estado:** Aceptado

## Contexto

Fase B1 del plan Second Brain (`ROADMAP_SECOND_BRAIN_NOTION.md`, ver ADR 0179). Notion es hoy una
integración global — un solo `NOTION_API_KEY` para todo el workspace del fundador, sin OAuth por usuario
(a diferencia de Google, que lo tiene desde ADR 0137). El plan de negocio del fundador ("conectá tu Notion
con el plan de $10") exige que cualquier usuario pueda conectar su propio Notion.

Se ejecuta después de A1-A3/A7 (con el core de Notion ya verificado contra el `NOTION_API_KEY` global)
para aislar el riesgo del flujo OAuth nuevo.

## Decisión

**`snarf/capabilities/notion_auth.py` (nuevo)**: Notion no tiene SDK propio de OAuth para Python (a
diferencia de `google-auth-oauthlib` que usa `google_auth.py`) — el intercambio de código
(`exchange_code`) es un `POST` directo a `https://api.notion.com/v1/oauth/token` con Basic Auth
(`client_id:client_secret`), siguiendo la doc real de la API. A diferencia de Google, el token de Notion
no expira y no trae `refresh_token` — `NotionAuth` no tiene ningún mecanismo de refresh, a propósito.
Tokens guardados en `credentials/notion_tokens/<user_id>.json`, namespaced desde el día uno (mismo
criterio que A2/B2).

**Prerequisito manual real, no automatizable**: la integración de Snarf tiene que estar registrada como
**pública** en el panel de developers de Notion (`https://www.notion.so/my-integrations`), con
`NOTION_OAUTH_CLIENT_ID`/`NOTION_OAUTH_CLIENT_SECRET` reales y el redirect URI real dado de alta —
mismo tipo de gotcha ya documentado en `CLAUDE.md` para Google Cloud Console/permisos de TCC de macOS.
**Sin este paso del fundador, el flujo entero está construido y testeado pero no puede ejercitarse en
vivo.** Documentado en `.env.example`.

**`Notion` (capability) gana `notion_auth` opcional**, mismo patrón de inyección que
`GoogleDrive(google_auth)` — `_resolve_token()` prioriza el token OAuth real de `notion_auth.access_token()`
si existe; si no (usuario nunca conectó OAuth, o no se inyectó ningún `NotionAuth`), cae de vuelta al
`NOTION_API_KEY` global. `DEFAULT_USER_ID` (el fundador) sigue funcionando exactamente igual que antes de
este ADR mientras no conecte OAuth explícito.

**Endpoints REST** (`app.py`, mismo patrón que `/google/connect`/`/google/oauth/callback`):
`GET /auth/notion/start` (requiere sesión ya iniciada — Notion OAuth acá es solo "conectar", nunca un
mecanismo de login como sí lo es para Google) y `GET /auth/notion/callback`, con el mismo protocolo de
`state` firmado + cookie de corta vida para CSRF real.

**Diferido explícitamente, no construido en esta fase: ningún botón "Conectar Notion" en la UI.**
Investigado antes de construirlo: el endpoint equivalente de Google (`GET /google/connect`, ya real desde
ADR 0137) **tampoco tiene ningún botón en `web/index.html`** — ni un link, ni un `onclick`, nada (grep
exhaustivo sin resultados). No hay ningún precedente real de UI para "conectar" (a diferencia de "login
con Google", que sí tiene botón). Construir uno para Notion ahora sería inventar un patrón de UI que ni
siquiera Google tiene todavía, en vez de esperar al panel real de configuración del Second Brain (Fase C5
o el propio onboarding de A4), que es su lugar natural.

## Verificado

- `.venv/bin/python -m pytest -q` — 1604/1604 (1587 previos + 17 nuevos: 12 en `tests/test_notion_auth.py`
  — credenciales requeridas, URL de autorización real, intercambio con Basic Auth real, namespacing por
  usuario — y 5 en `tests/test_app.py` — requiere autenticación, requiere credenciales de cliente
  configuradas, rechaza cookie de estado faltante/alterada, redirige ante error real de Notion, flujo
  completo real (mockeado) guarda el token del usuario correcto — más 3 en `tests/test_notion.py` para el
  fallback OAuth→key global en `Notion._resolve_token()`.
- No se probó contra un client_id/secret reales de Notion — el fundador todavía no completó el registro
  manual de la integración pública. Queda como verificación en vivo pendiente para cuando ese paso esté
  hecho.

## Consecuencias

- Fase A4 (onboarding) es el punto natural donde SÍ va a hacer falta una superficie real de "conectar
  Notion" en la UI — ahí se construye, junto con el resto del flujo de onboarding, no antes.
- Multi-usuario real de Second Brain queda desbloqueado a nivel de código — falta el paso manual del
  fundador (registro de la integración pública) para que sea real en producción.
