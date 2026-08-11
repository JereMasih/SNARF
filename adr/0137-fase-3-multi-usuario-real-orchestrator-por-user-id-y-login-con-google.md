# ADR 0137 — Fase 3 del plan de multi-usuario: Orchestrator por user_id + login real con Google

**Fecha:** 2026-08-10
**Estado:** Aceptado

## Contexto

Plan aprobado con el fundador (ver `/Users/jeremiasabdelmasih/.claude/plans/vengo-pensando-hace-unos-mighty-treehouse.md`):
el objetivo inmediato es empezar a tener usuarios de prueba reales, no seguir siendo un sistema de un
solo usuario en una Mac. Antes de tocar cualquier UI de onboarding, la Fase 3 exigía auditar si Snarf
ya soportaba un segundo usuario real o si había una asunción de usuario único enterrada (flag explícito
dejado en ADR 0135/0136).

**Veredicto real de la auditoría, con evidencia de código** (no de documentos viejos): Snarf era
single-user de punta a punta pese a tener scaffolding per-usuario parcial y real (perfiles,
preferencias, credenciales de Google por `user_id` desde ADR 0021). Concretamente:

1. `app.py` instanciaba un único `Orchestrator(user_id=DEFAULT_USER_ID)` a nivel de módulo — **toda**
   sesión logueada, sin importar qué `user_id` real tuviera la cookie, operaba sobre el mismo objeto:
   misma `EpisodicMemory`, mismas credenciales de Google, mismos proyectos, mismos indexers.
2. `EpisodicMemory()` se construía sin argumentos dentro de `Orchestrator.__init__` — ni siquiera
   usaba el `user_id` que sí recibía el constructor. Dos `Orchestrator` de dos usuarios distintos
   habrían compartido el mismo archivo de conversaciones.
3. El login (`POST /login`) mintaba `DEFAULT_USER_ID` en la sesión sin importar quién ingresara la
   contraseña — no existía ningún mecanismo para que un segundo usuario real obtuviera un `user_id`
   propio.
4. La conexión a Google (`google_auth.py`) usaba `InstalledAppFlow.run_local_server()` — abre un
   navegador y un servidor HTTP temporal **en la máquina que corre Snarf**. Funciona solo para quien
   tiene acceso directo a esa Mac (el fundador operándola a mano); estructuralmente imposible para un
   usuario remoto conectando su propia cuenta desde su propio navegador.

ADR 0021 (el intento original de credenciales por usuario) ya lo decía explícitamente: diseñado "para
un solo usuario hoy pero listo para multi-usuario después", con "aislar la memoria episódica por
usuario" y "flujo de un segundo usuario conectando su propio Google" listados a propósito como
pendientes, no como hechos.

## Decisión

### 1. Registro de Orchestrator por `user_id` (`app.py`)

`get_orchestrator(user_id)` — lazy + cacheado en un dict de proceso, protegido por lock. `orchestrator`
(el nombre de módulo) queda como alias de `get_orchestrator(DEFAULT_USER_ID)`, así:
- `warmup()`/`GET /status` (sin `user_id` de request) siguen operando sobre la instancia del fundador.
- Los ~40 usos de `orchestrator.X` en las ~30 rutas HTTP que ya tenían `user_id: str =
  Depends(require_user)` en su firma pasan a `get_orchestrator(user_id).X` — cada handler resuelve
  la instancia real de QUIEN hizo la request, nunca la del fundador por default.
- La suite de tests existente (`tests/test_app.py`, que monkeypatchea `app_module.orchestrator`
  directo en decenas de tests) sigue funcionando sin ningún cambio: como `orchestrator` puebla el
  registro bajo `DEFAULT_USER_ID` en el mismo objeto, `get_orchestrator(DEFAULT_USER_ID)` siempre
  resuelve exactamente esa misma instancia.

### 2. `EpisodicMemory` per-usuario real (`snarf/core/orchestrator.py`)

`DEFAULT_USER_ID` sigue usando las rutas globales de siempre (`data/episodic_memory.jsonl` y
compañía) — compatibilidad real con los 180+ intercambios ya en disco del fundador, sin ninguna
migración. Cualquier otro `user_id` recibe rutas propias bajo `MEMORY_DATA_DIR = Path("data/users")`
(`data/users/<user_id>/episodic_memory.jsonl`, etc.) — nunca comparte archivo con nadie.

### 3. Login real con Google (`snarf/capabilities/google_auth.py`, `snarf/runtime/google_identity.py`, `app.py`)

Reemplaza `InstalledAppFlow` por el flujo web real de OAuth (`google_auth_oauthlib.flow.Flow`,
Authorization Code + redirect):

- `GET /login/google` (público) y `GET /google/connect` (autenticado) arman la URL real de
  consentimiento de Google y la guardan en una cookie de estado firmada de corta vida (10 min) —
  protección CSRF real vía el mismo `state` que Google devuelve, verificado byte a byte en el
  callback antes de hacer nada.
- `GET /google/oauth/callback` intercambia el código real por credenciales, y decide qué hacer según
  el `purpose` codificado en el estado firmado:
  - `"login"`: llama a la API real de userinfo de Google (`google_identity.fetch_email`), deriva un
    `user_id` real y estable del email (`google_identity.user_id_for_email` — sanitizado para nunca
    poder reconstruir un path traversal, ver "Riesgos" abajo), guarda el token para ESE `user_id`, y
    mintea una sesión real. **Conectar Google ES el login** para cualquiera que no sea el fundador —
    en el mismo consentimiento ya se piden los scopes de Drive/Gmail/Calendar/YouTube (`SCOPES`) junto
    con los de identidad (`openid`, `userinfo.email`), así que un usuario nuevo sale del flujo con su
    cuenta conectada de una sola vez, sin un segundo paso de "ahora conectá Drive".
  - `"connect:<user_id>"`: un usuario ya logueado (por contraseña o por Google) reconecta o renueva su
    propio token, sin tocar su sesión.
- `web/login.html` suma un botón real "Iniciar sesión con Google" — verificado con Playwright contra
  un server de prueba real (puerto 8000, nunca 8002): el click navega hasta la pantalla real de
  Google ("Sign in — to continue to Snarf"), cero errores de consola.

### 4. Bug real corregido de paso

`GoogleAuth.credentials()` nunca volvía a persistir el token tras un refresh silencioso (`creds.refresh(Request())` sin `write_text` después) — cada reinicio del proceso forzaba un refresh de más contra Google. Se persiste ahora en el mismo punto.

## Riesgos / trade-offs / lo que queda deliberadamente sin resolver en esta fase

1. **`google_identity.user_id_for_email` — hallazgo real durante el propio desarrollo de esta fase**:
   la primera versión dejaba pasar `.` como carácter "seguro" (válido en un email) — un email
   adversarial con `/../` sobrevivía como `_.._`, reconstruyendo un path traversal real, porque
   `user_id` se usa directo como segmento de path de disco (`MEMORY_DATA_DIR / user_id`,
   `KNOWLEDGE_DATA_DIR / user_id`, etc.). Detectado por un test propio antes de mergear, no en
   producción — corregido sacando `.` del allowlist (se reemplaza por `_` como cualquier otro
   carácter no seguro), verificado con `Path(...).resolve()` que nunca escapa el directorio padre.
2. **El cliente OAuth de Google Cloud Console del fundador es el mismo de ADR 0013** (originalmente
   pensado para `InstalledAppFlow`). Verificado en vivo contra `http://127.0.0.1:8000/google/oauth/
   callback` — Google acepta el request y muestra la pantalla real de consentimiento, así que el
   cliente actual sirve al menos para desarrollo local. **Para producción real (dominio/Tailscale
   HTTPS), el fundador tiene que dar de alta ese redirect_uri exacto en "URI de redireccionamiento
   autorizados" de Google Cloud Console** — acción manual real, ningún cambio de código la reemplaza.
3. **Verificación de la app OAuth ante Google, límite de 100 testers**: Google exige que una app en
   modo "Testing" liste explícitamente cada cuenta de prueba (hasta 100) en Google Cloud Console antes
   de que esa cuenta pueda completar el consentimiento — y exige un proceso de verificación real
   (incluida revisión de scopes sensibles como Drive/Gmail) para pasar a "In production" sin ese
   límite. Esto es un bloqueo operativo real para escalar más allá de un puñado de usuarios de
   prueba cercanos al fundador, independiente de todo el código de esta fase — el fundador necesita
   resolverlo en Google Cloud Console antes de invitar a alguien que no sea él mismo.
4. **Notion sigue siendo global, no per-usuario** (`snarf/capabilities/notion.py`, una sola
   `NOTION_API_KEY` de entorno) — a diferencia de Google, no hay ningún flujo OAuth de Notion
   construido todavía. Un segundo usuario real no puede conectar su propio Notion hoy; queda
   explícitamente fuera de esta fase (sería una integración nueva completa, no una extensión de lo que
   ya existe).
5. **La capa de telemetría/dashboard sigue sin particionar por usuario**: `activity_log.jsonl`,
   `usage_log.jsonl` y el `dashboard_curator` global son archivos compartidos entre TODOS los
   usuarios — un segundo usuario real viendo el dashboard/HUD hoy vería actividad/costo mezclados con
   los del fundador (potencial fuga de privacidad real: `detalle`/`preview` de eventos de telemetría
   a veces contiene contenido real como asuntos de mail o títulos de documento). `telemetry_events.jsonl`
   sí carga `user_id` por evento desde Fase 1 (ADR 0135) — ahora derivado correctamente del `Orchestrator`
   real de cada usuario en vez de siempre "fundador" — pero ningún endpoint de dashboard filtra
   todavía por ese campo. **Recomendación explícita: el dashboard/HUD no debería exponerse a usuarios
   de prueba hasta que este gap se cierre** (partición real de los tres logs, o al menos filtrado por
   `user_id` en los endpoints que ya lo tienen disponible) — no se resuelve en esta fase por su
   tamaño real (toca Fases 1-2 completas) y el riesgo de un fix apurado dejando una fuga más sutil sin
   detectar.
6. **`FOUNDER_TIMEZONE` sigue hardcodeada** (`snarf/core/orchestrator.py`) — usada para agregar costo
   por día en el dashboard. Bajo impacto (solo afecta a qué "día" se le atribuye un gasto cerca de
   medianoche), no bloqueante para chat, no resuelto acá.
7. **`allow_server_storage` sigue reservado al fundador** (`user_id == DEFAULT_USER_ID`) — decisión
   preexistente de ADR previa, no tocada: guardar un documento en el disco del propio servidor (sin
   subir a Drive) sigue siendo una herramienta exclusiva del fundador, correcto para un usuario de
   prueba que no debería tener esa capacidad.

## Verificado

- 25 tests nuevos: `tests/test_google_identity.py` (6, incluido el hallazgo real de path traversal),
  `tests/test_google_auth.py` (7: URL de autorización real, intercambio de código, persistencia de
  token, el nuevo error honesto de "no conectado" reemplazando el flujo interactivo viejo),
  `tests/test_app.py` (10: registro `get_orchestrator` real —mismo objeto para el mismo usuario,
  objetos distintos para usuarios distintos—, las 3 rutas nuevas de OAuth con sus casos de error
  reales —CSRF, callback incompleto, Google rechazando el consentimiento—, y un flujo de login
  completo que termina en una sesión real para un usuario nuevo con su propio token guardado),
  extensión de `tests/test_orchestrator.py` (+2: un segundo `user_id` real recibe su propia ruta de
  memoria, dos usuarios reales conversando en paralelo nunca terminan en el mismo archivo).
- 1179/1179 tests de la suite completa (`.venv/bin/python -m pytest -q`).
- Verificado con Playwright contra un servidor de prueba real (puerto 8000, nunca 8002 — protocolo
  de este repo respetado): la página de login renderiza el botón de Google sin errores de consola, y
  clickearlo navega de punta a punta hasta la pantalla real de "Sign in — to continue to Snarf" de
  Google (client_id, redirect_uri, scopes y PKCE correctos) — confirma que el flujo real llega hasta
  donde la automatización puede verificar sin completar un login real con una cuenta de Google.
