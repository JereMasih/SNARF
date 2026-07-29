# CLAUDE.md

Índice para sesiones de Claude Code en este repo. No repite contenido — apunta a dónde mirar.

## Antes de tocar código

- `MASTER_MAP.md` es el plano maestro del ecosistema — leelo primero para ubicar en qué Dominio cae el pedido (Identity, Governance, Cognition, Knowledge, Architecture, Capabilities, Business, Infrastructure, Roadmaps). Su "Regla de crecimiento": si algo nuevo no encaja en el mapa, primero evoluciona el mapa.
- `FOUNDATION.md` / `CONSTITUTION.md` / `CHARACTER.md` / `COGNITION.md`: identidad y gobernanza del proyecto. Principio VI de FOUNDATION.md (Honestidad Intelectual) rige también el propio trabajo de Claude en este repo: nunca presentar datos inventados como reales — construir el cerebro de Snarf, por ejemplo, se hizo estrictamente desde telemetría real (`activity_log`, `usage_log`, `input_log`), nunca con datos de relleno.
- `adr/` tiene una decisión por archivo, numeradas; `CHANGELOG.md` tiene una entrada por ADR con conteo de tests. Todo cambio de arquitectura real (no un fix trivial) se documenta en ambos.

## Convenciones de este repo

- Tests con `.venv/bin/python -m pytest -q` (31 archivos en `tests/`, suite completa corre en segundos). Correr la suite completa antes de dar por terminado cualquier cambio de backend.
- Cambios de frontend (`web/index.html`, un solo archivo grande): no alcanza con que compile — verificar en un navegador real (Playwright) antes de reportar terminado, especialmente drag/resize/reparentado de DOM vivo.
- DOM con estado (chat, historial de conversaciones, sidebar de mobile): reparentar (`appendChild` sobre el nodo existente) en vez de reconstruir por HTML — reconstruir pierde listeners y estado.
- Gotcha real de Python ya mordido una vez: `bool` es subclase de `int` — cualquier validación de `isinstance(x, int)` sobre un valor que puede venir de un payload externo necesita excluir `bool` explícitamente (ver `snarf/runtime/dashboard_prefs.py`).
- Mensajes de commit: en español, breves, sin firma manual del asistente salvo el trailer `Co-Authored-By` ya estándar de Claude Code. Ver `git log` para el tono real.
- Server real de producción corre en el puerto 8002 vía `nohup`+`disown` (persiste entre sesiones) — no confundir con instancias de prueba en 8000/8001. Si hace falta reiniciarlo, confirmar con el fundador primero.

## Costo/tokens de esta sesión

- `snarf/capabilities/anthropic_llm.py` ya cachea system+tools (breakpoint fijo) y el último mensaje de cada llamada/ronda del loop de herramientas (breakpoint móvil, TTL de 1h). Si se toca ese archivo, no romper ninguno de los dos breakpoints — hay tests dedicados en `tests/test_anthropic_llm.py`.
- Preferencia del fundador: sesiones largas y continuas están bien, pero al cerrar una tanda grande de features (varios ADRs seguidos) es buen momento para `/clear` antes de arrancar la siguiente, en vez de seguir acumulando contexto indefinidamente.
