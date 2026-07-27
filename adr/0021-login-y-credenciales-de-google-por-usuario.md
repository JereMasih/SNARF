# ADR 0021 — Login por contraseña y credenciales de Google por usuario

**Fecha:** 2026-07-27
**Estado:** Aceptado — verificado por el fundador en su navegador real

## Contexto

Tras publicar el repositorio en GitHub (público, para que un asesor lo revise), el fundador planteó una preocupación: que sus credenciales de Google (Drive/Gmail/Calendar) estuvieran expuestas junto con el resto del código público. Se verificó exhaustivamente contra el remoto real y toda la historia de git (`git log --all --full-history`, `git ls-tree -r origin/master`): **nunca se commiteó** `credentials/google_client_secret.json`, `credentials/google_token.json` ni `.env` con valores reales — el `.gitignore` los excluyó desde el primer commit. Lo único público es `.env.example` (nombres de variables, sin valores) y el código que sabe *cómo* usar esas credenciales, no las credenciales en sí.

Corregida esa confusión puntual, quedó en pie una limitación real de arquitectura: `GoogleAuth` asumía un único usuario implícito, con un solo `credentials/google_token.json` global — no había forma de que un segundo usuario conectara su propio Google sin pisar el token del fundador. El fundador pidió resolver esto con una interfaz de login, pensada para un solo usuario hoy pero lista para multi-usuario después (opción elegida explícitamente sobre "solo vos" y "multi-usuario real ya").

## Decisión

1. **Distinción explicada y preservada en el diseño:** `google_client_secret.json` identifica a la aplicación Snarf ante Google (un solo archivo, compartido por cualquier usuario futuro); el token de acceso sí es por-usuario. Solo el segundo necesitaba dejar de ser global.

2. **`GoogleAuth(user_id)`** (`snarf/capabilities/google_auth.py`): el token ahora vive en `credentials/tokens/<user_id>.json` en vez de un único `credentials/google_token.json`. Migrado el token real existente a `credentials/tokens/fundador.json`. `credentials/` ya estaba excluido completo del `.gitignore`, así que `tokens/` queda cubierto sin cambios ahí.

3. **`Orchestrator(user_id=DEFAULT_USER_ID)`** (`snarf/core/orchestrator.py`, `DEFAULT_USER_ID = "fundador"`): recibe el usuario explícitamente en vez de asumirlo. `main.py` y `app.py` lo pasan explícitamente.

4. **Login real** (`snarf/runtime/web_auth.py`, nuevo): cookie de sesión firmada con `itsdangerous` (`URLSafeTimedSerializer`, expira a los 30 días), verificada con `secrets.compare_digest` contra `SNARF_ACCESS_PASSWORD`. **Falla cerrado, no abierto**: si `SESSION_SECRET` o `SNARF_ACCESS_PASSWORD` no están configuradas, el login y las rutas protegidas devuelven 503/401 en vez de dejar pasar todo sin autenticación.

5. **Endpoints protegidos** (`app.py`): `/send`, `/transcribe`, `/tts`, `/conversations`, `/conversations/{id}` ahora exigen `Depends(require_user)` — antes de esto, la única barrera de acceso era la topología de red (Tailscale/LAN), hallazgo ya señalado en `ARCHITECTURE_AUDIT.md` sección 20. `GET /` redirige a `/login` si no hay sesión válida. `/status` se dejó público (no expone datos sensibles, solo booleanos de configuración).

6. **`web/login.html`** (nuevo): página de login con la misma estética HUD del resto de la interfaz. Botón "cerrar sesión" agregado al sidebar de `web/index.html`. Nueva función `apiFetch()` en el frontend: cualquier respuesta 401 de un endpoint protegido redirige automáticamente a `/login`.

7. **Nueva dependencia:** `itsdangerous==2.2.0` — librería estándar del ecosistema Starlette/FastAPI para firmar cookies, en vez de reinventar criptografía a mano.

## Descartado explícitamente en esta ronda

El fundador propuso sumar "Iniciar sesión con Google" y "con Apple". Se evaluó y se decidió no implementarlo todavía (ver memoria de proyecto `snarf-login-google-oauth-future`):

- **Google** es el camino correcto para cuando exista multi-usuario real — Snarf ya pide consentimiento OAuth de Google para funcionar, y ese mismo consentimiento puede servir como login, evitando mantener dos sistemas de autenticación en paralelo. No se construye ahora porque reemplazaría el login por contraseña recién hecho, no convive con él sin definir cuál manda.
- **Apple** se descarta: requiere Apple Developer Program (u$s99/año), Service ID y verificación de dominio — no es "fácil" como se asumió inicialmente — y no destraba ninguna funcionalidad real de Snarf hoy.

Queda como compromiso explícito que el arquitecto (yo) proponga el login con Google activamente cuando se retome el trabajo de multi-usuario, sin esperar a que el fundador lo pida de nuevo.

## Verificado

- Suite completa de tests (41/41): incluye `tests/test_web_auth.py` (login correcto/incorrecto, logout, cookie falsificada rechazada, fail-closed sin `SESSION_SECRET`/`SNARF_ACCESS_PASSWORD`, roundtrip de firma de token) además de los tests existentes, ahora corriendo autenticados vía un login real dentro del propio fixture.
- Durante la implementación se encontró y corrigió un problema real en los propios tests: dos de ellos instanciaban `TestClient` sin haber forzado antes `orchestrator._llm._client = None`, y el hook de `startup` (`warmup()`) disparaba una llamada real a la API de Anthropic en cada uno — se detectó por la duración anómala de la suite (19s en vez de <1s), no por inspección visual. Corregido reordenando el monkeypatch antes de instanciar el cliente de test.
- Verificado extremo a extremo contra una instancia real de `app.py` (puerto de prueba aislado): redirect a `/login` sin sesión, 401 sin cookie, 401 con contraseña incorrecta, 200 y cookie con la correcta, acceso real a `/send`, 401 tras `/logout`.
- **Confirmado por el fundador en su propio navegador real**, contra el servidor de producción reiniciado con la contraseña definitiva.

## Consecuencias

- Nueva variable de entorno obligatoria para que la interfaz web funcione: `SNARF_ACCESS_PASSWORD`. `SESSION_SECRET` generada una vez (aleatoria, no memorizable, no necesita rotarse salvo sospecha de compromiso).
- El servidor real tuvo que reiniciarse para tomar los cambios; quedó una conversación de prueba (`test-auth`) en la memoria episódica real durante la verificación manual, movida a `data/manual_verification_log.jsonl` siguiendo la práctica de ADR 0020.
- Explícitamente fuera de esta ronda (quedan para cuando haya multi-usuario real, no antes): registro de nuevos usuarios, flujo de un segundo usuario conectando su propio Google, aislar la memoria episódica por usuario, y el propio login con Google.
