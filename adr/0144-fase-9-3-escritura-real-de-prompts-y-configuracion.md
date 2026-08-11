# ADR 0144 — Fase 9.3: escritura real de Prompt Registry y Configuración dinámica

**Fecha:** 2026-08-11
**Estado:** Aceptado

## Contexto

`ROADMAP_OBSERVABILIDAD_MULTIUSUARIO_N8N.md`, Fase 9.3: *"Cierra el caso de uso de la Fase 4: desde el
cockpit o desde un flujo de n8n, el founder puede abrir el prompt/config activo de un agente (Fase 6/7),
editarlo, y activar la nueva versión, con historial y rollback."* Fase 6 (Prompt Registry, ADR 0141) y
Fase 7 (Configuración dinámica, ADR 0142) construyeron el motor completo (`get_active_text`/
`save_new_version`/`rollback`/`history` en ambos módulos) pero deliberadamente sin ningún endpoint HTTP
— esta ADR es la que lo expone de verdad.

## Decisión

**Seis endpoints nuevos en `app.py`, mismo patrón que `GET/PUT /llm-routing`:**

- `GET /prompts` / `PUT /prompts/{prompt_id}` / `POST /prompts/{prompt_id}/rollback`
- `GET /generation-config` / `PUT /generation-config/{role}` / `POST /generation-config/{role}/rollback`

**`snarf/core/orchestrator.py::PROMPT_DEFAULTS`** (nuevo): mapeo completo de los 20 `prompt_id` reales a
su texto default — este módulo ya importaba los 19 que usa para wirear cada Specialist (Fase 6); se sumó
el import de `DASHBOARD_CURATOR_SYSTEM_PROMPT` (el único que faltaba, porque `DashboardCuratorSpecialist`
se construye en `app.py`, no acá) solo para completar este mapeo — un test nuevo
(`test_prompt_defaults_covers_every_prompt_registry_id`) garantiza que nunca queda desalineado con
`prompt_registry.PROMPT_IDS`.

**`snarf/runtime/llm_routing.py::default_generation_config(provider)`** (nuevo, extraído de `_build()`
sin cambiar su comportamiento): el default real de generación depende del PROVEEDOR actual de un rol
(`timeout_seconds` solo tiene default real para locales) — expuesto para que `GET/PUT/rollback
/generation-config` puedan calcular el mismo default que `_build()` ya usa, nunca una segunda fórmula.

**Refresco real, mismo bug ya corregido una vez para `/llm-routing`**: `self._llm`/`self._title_llm`
(roles `orchestrator`/`conversation_title`) se resuelven UNA sola vez al construir el `Orchestrator`, no
por factory — sin llamar a `orch.refresh_llm_routing()` después de un `PUT`/rollback de
`/generation-config`, un cambio ahí no tendría ningún efecto hasta el próximo reinicio del servidor
(exactamente el bug que motivó ese mismo refresh en `PUT /llm-routing`, ADR de ronda anterior).
`/prompts` no lo necesita: el texto se lee vía `prompt_registry.get_active_text()` en cada llamada real,
nunca cacheado en la instancia.

**Auth: solo `require_user` (founder), no `require_n8n_token` — decisión explícita, no un olvido.**
Darle a n8n poder de ESCRITURA real sobre los prompts/config de Snarf es una autoridad categóricamente
distinta de lo que n8n tiene hoy (leer estado vía `/n8n/status`/`/n8n/introspect`, Fases 4/5) — mismo
principio ya aplicado en `CONSTITUTION.md` Art. III/V/línea 109 al Track B del dashboard curator
(SESSION_STATE.md, 2026-08-04): ninguna autoridad de ese tipo nace de una delegación general de fase,
necesita su propia decisión de gobernanza explícita con el fundador. El texto del plan dice "desde el
cockpit **o** desde un flujo de n8n" — esta ADR resuelve el "cockpit" (el founder, autenticado, puede
editar/hacer rollback ya mismo vía estos endpoints); la mitad "n8n" queda pendiente de esa decisión.

## Fuera de alcance, explícito

- **UI real en `web/index.html`** para estos endpoints — no se tocó el frontend en esta ronda (mismo
  criterio que `ops_process_status`/`restart`, ADR 0138: "vive en el chat/API, no en una vista de
  dashboard todavía"). Los endpoints son consumibles ya mismo (curl, un cliente HTTP, o una vista futura).
  9.2 (cerebro rediseñado) es la fase que trae cambios de frontend — no se adelantó acá.
- **Escritura desde n8n** — ver "Decisión" arriba. Requiere su propia ADR de gobernanza, no esta.

## Verificado

- 11 tests nuevos en `tests/test_app.py`: roundtrip completo de `/prompts` (default real, PUT, rollback,
  400 en texto vacío, 404 en `prompt_id` desconocido, 400 en versión inexistente) y de
  `/generation-config` (default real por proveedor actual, override parcial sin resetear otros campos,
  400 en campo desconocido, 404 en rol desconocido, rollback real).
- 1 test de cobertura en `tests/test_orchestrator.py`: `PROMPT_DEFAULTS` nunca se desalinea de
  `prompt_registry.PROMPT_IDS`.
- `snarf/runtime/llm_routing.py::default_generation_config` extraído sin cambiar el comportamiento de
  `_build()` — toda la suite de `test_llm_routing.py`/`test_generation_config.py` sigue en verde sin
  tocarse.
- 1271/1271 tests de la suite completa (`.venv/bin/python -m pytest -q`), 1259 previos (post Fase 8/1) +
  12 nuevos.
