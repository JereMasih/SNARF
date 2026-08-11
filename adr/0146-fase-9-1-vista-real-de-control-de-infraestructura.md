# ADR 0146 — Fase 9.1: vista real de control de infraestructura en la UI

**Fecha:** 2026-08-11
**Estado:** Aceptado

## Contexto

ADR 0138 dejó `ops_process_status`/`ops_process_restart` "vive en el chat, no en una vista de dashboard
todavía — falta: vista visual real en `web/index.html`, ver logs desde la UI, asistente guiado de
migración a VPS." Esta ADR cierra la primera de esas tres deudas.

## Decisión

**Dos endpoints HTTP nuevos, `app.py`, reusando `snarf/runtime/process_control.py` tal cual (nunca una
segunda implementación):**

- `GET /ops/processes` → `process_control.status()`.
- `POST /ops/processes/{label}/restart` → mismo protocolo `confirmed` en dos pasos que ya usan
  `HIGH_IMPACT_TOOLS`/`BULK_READ_GATED_TOOLS` (`_pending`), delegando a `process_control.restart()`.

**Gate de founder a nivel HTTP, primera vez que hace falta**: hasta ahora el gate `user_id ==
DEFAULT_USER_ID` solo existía dentro de cada `_tool_ops_process_*` de `orchestrator.py` (porque el chat
es el único punto de entrada que existía). Como esta es la primera vez que se expone fuera del chat, se
agrega el mismo chequeo a nivel de endpoint (403 para cualquier `user_id` que no sea el fundador).

**Nueva sección "Control de infraestructura" en el panel de Configuración** (`web/index.html`, junto a
"LLM por rol") — se oculta por completo (`display: none`) si `GET /ops/processes` devuelve 403, en vez
de asumir de antemano quién está logueado: el propio backend decide, mismo criterio en todo el resto de
esta feature. Cada fila muestra nombre real, estado (●verde/gris), PID y RAM real cuando corre. El botón
"Reiniciar" usa `window.confirm()` como la confirmación real que exige el backend (`?confirmed=true`) —
mismo patrón exacto ya usado para borrar un proyecto (`projectHomeDeleteBtn`), nunca un componente de
confirmación nuevo. `com.snarf.server` nunca muestra el botón (`restartable_via_tool: false`, ya
calculado por `process_control.status()` — el frontend no reinventa esa regla).

**Fuera de alcance, con motivo**: "ver logs desde la UI" y el "asistente guiado de migración a VPS"
(las otras dos deudas de ADR 0138) no se tocaron acá — son features genuinamente distintas (leer
archivos de log del servidor de forma segura la primera; una migración a un VPS que todavía no existe
la segunda), cada una merece su propia ronda.

## Verificado

- 5 tests nuevos en `tests/test_app.py`: `GET /ops/processes` devuelve el estado real, 403 para un
  usuario que no es el fundador, `POST .../restart` sin confirmar devuelve `pending_confirmation` sin
  llamar a `process_control.restart`, confirmado sí lo llama exactamente una vez, y el intento sobre
  `com.snarf.server` devuelve 400 con el mensaje real de por qué no se puede.
- **Verificado con Playwright en un servidor aislado (puerto 8001, nunca el 8002 de producción)**: login
  real, panel de Configuración abierto, sección "Control de infraestructura" visible con los 6 procesos
  reales de esta Mac (PIDs/RAM reales — `com.snarf.server` con su PID real, los 3 servers MLX, Kokoro
  TTS, el watchdog), 5 botones de "Reiniciar" (todos menos el servidor principal, confirmando el gate
  `restartable_via_tool`), el diálogo de confirmación real disparado con el mensaje esperado al hacer
  click — **descartado a propósito, nunca aceptado**, para no reiniciar un proceso real de producción
  sin una decisión explícita del fundador de hacerlo en el momento. Cero errores de consola.
- 1282/1282 tests de la suite completa (`.venv/bin/python -m pytest -q`), 1277 previos (post reapertura
  de n8n) + 5 nuevos.
