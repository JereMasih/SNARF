# ADR 0070 — Credenciales reales, fix de nombres de modelo, ruteo dinámico sin reinicio

**Fecha:** 2026-07-30
**Estado:** Aceptado

## Contexto

El fundador cargó las tres credenciales reales (`GEMINI_API_KEY`, `OPENAI_API_KEY`, `XAI_API_KEY`) construidas en el ADR 0068. El smoke-test real con cada una encontró tres problemas concretos que el código escrito "verificado contra la documentación" no podía anticipar sin una llamada real.

## Decisión

**Tres hallazgos reales, corregidos:**

1. **Nombres de modelo desactualizados**: `gemini-2.5-flash`/`gemini-2.5-flash-lite` responden 404 ("no longer available to new users") — se reemplaza el preset default por `gemini-3.1-flash-lite` (confirmado funcionando, tool-calling incluido). `grok-4.1-fast` (con puntos) responde 400 "Model not found" — la nomenclatura real de xAI usa guiones (`grok-4-1-fast`), corregido en `pricing.py` y en los presets del frontend.
2. **OpenAI**: el código funciona (la request llega, se autentica, responde un error estructurado), pero la cuenta no tiene crédito cargado (`insufficient_quota`) — no es un bug, es un pendiente de billing del lado del fundador.
3. **Bug real de arquitectura, encontrado probando el propio ADR 0068 en vivo**: cambiar el ruteo del rol `conversation_title` a Gemini desde la interfaz no tenía ningún efecto — el título seguía cayendo al fallback en silencio. Causa: `Orchestrator._llm`/`_title_llm` se resolvían una sola vez en `__init__`, nunca de nuevo. Se agrega `Orchestrator.refresh_llm_routing()`, llamado desde `PUT /llm-routing` en `app.py` apenas se guarda un cambio — así el próximo turno ya usa el proveedor nuevo, sin reiniciar el servidor. Los otros 3 roles (`gmail_digest`, `drive_vision`, `project_summary`) NO tenían este problema: `GmailDigestSpecialist`/`ProjectManager`/`ContentExtractor` pasan a recibir una **factory** (`lambda: llm_routing.build_llm(role)`) en vez de una instancia fija, así que ya eran dinámicos por diseño — no necesitaron el mismo fix.

`self._llm`/`self._title_llm` del Orchestrator se mantienen como atributos fijos (no una factory) a propósito: gran parte de la suite de tests existente hace `monkeypatch.setattr(orchestrator._llm, "_client", ...)` contra el objeto ya construido — una factory que resuelve distinto en cada acceso hubiera roto ese patrón establecido. El refresco es explícito (`refresh_llm_routing()`), disparado solo cuando el ruteo cambia de verdad, no en cada turno.

**Ruteo aplicado en producción tras el smoke-test real**: los 4 roles acotados y mecánicos (Gmail, visión de Drive, resumen de proyectos, título) se movieron del Haiku por defecto a lo más barato ya verificado de punta a punta — visión a Gemini 3.1 Flash-Lite (xAI rechazó una imagen de prueba por tamaño mínimo, sin verificar con una imagen real todavía), el resto a xAI Grok 4.1 Fast. El rol `orchestrator` (conversación principal, 96% del gasto real) se deja en Sonnet 5 — Haiku queda ofrecido como opción lista en el selector, pero cambiarlo es una decisión sobre la calidad/personalidad de Snarf que le corresponde al fundador, no algo para decidir en silencio dentro de un barrido de optimización.

## Verificado

- 529/529 tests. Se encontró y corrigió además una fuga real de aislamiento: las 3 credenciales nuevas en `.env` no se borraban en `conftest.py` (a diferencia de `ANTHROPIC_API_KEY`/etc.) — cualquier test que construyera una Capacidad con el ruteo default podría haber disparado una llamada real. Se suman las 3 nuevas más `GROQ_API_KEY` (mismo criterio, ahora también usada por el rol `groq_llama`) a la lista ya existente de variables borradas antes de cada test.
- Smoke-test real de punta a punta contra el Orchestrator real (no solo la Capacidad aislada): cambiar el rol `conversation_title` a Gemini vía `PUT /llm-routing` y mandar un mensaje real generó un título real en español ("Prueba del sistema con modelo Gemini"), confirmando que el refresco dinámico funciona. Mismo resultado cambiando `orchestrator` a xAI Grok 4.1 Fast — respuesta real y coherente.
- Visión real verificada con Gemini (una imagen PNG real generada a mano, sin librerías externas) — xAI rechazó por tamaño mínimo de imagen (512px), no se insistió con una imagen más grande dado que Gemini ya cubre el rol.

## Consecuencias

- Las claves reales quedan solo en `.env` (gitignored), nunca en el repo ni en ningún commit.
- `drive_vision` en xAI queda sin verificar todavía con una imagen de tamaño real — si en algún momento se rutea ahí, conviene un smoke-test dedicado antes de confiar en el resultado para indexación real.
- La decisión de mover `orchestrator` (el rol de mayor impacto en costo) queda deliberadamente en manos del fundador — el selector ya está listo y probado (Haiku 4.5 es la opción de menor riesgo, mismo SDK, revertible con un clic).
