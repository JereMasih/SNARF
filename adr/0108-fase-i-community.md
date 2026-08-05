# ADR 0108 — Fase I: rama Community (Discord)

**Fecha:** 2026-08-05
**Estado:** Aceptado

## Contexto

Séptima rama de la Fase I. Vendor decidido en el plan: Discord. Sin credencial real todavía (el
fundador no creó el bot aún) — mismo patrón que toda credencial nueva en este repo (Google/Voyage/
Groq/Tavily): se construye completo, degrada honesto sin la credencial, el último paso es que el
fundador la provea.

## Decisión

1. **`snarf/capabilities/discord.py::Discord`**: bot token real vía `DISCORD_BOT_TOKEN` +
   servidor/canal reales vía `DISCORD_GUILD_ID`/`DISCORD_CHANNEL_ID` — mismo patrón lazy-client que
   `Notion`/`TavilySearch`. `send_message`, `list_recent_messages`, `guild_member_count` sobre la API
   REST real de Discord (`discord.com/api/v10`).
2. **`CommunityPulseSpecialist`**: métricas reales (miembros, mensajes recientes, autores activos) —
   determinístico, sin LLM, mismo criterio que `MonthlyPnLSpecialist` (contar cosas reales no
   necesita interpretación). Nunca inventa una cifra si Discord no está configurado — reporta el
   motivo explícito.
3. **Postear en Discord como el fundador/marca es la única acción de alto impacto real de la rama**
   (confirmado en el plan) — tool nuevo `community_post_message`, mismo protocolo
   `_pending()`/`confirmed` de dos pasos que `gmail_send_message`, sumado a `HIGH_IMPACT_TOOLS`
   (queda automáticamente excluido del allowlist MCP).

## Explícitamente diferido en esta ronda

- **`MemberOnboardingSpecialist`**, **`WeeklyQADigestSpecialist`**, **`CommentTriageSpecialist`**:
  los tres necesitan un servidor de Discord real y con actividad real para diseñarse honesto (qué
  mensaje de onboarding real, qué cadencia real de digest, qué patrón real de comentarios a
  triagear) — construirlos ahora, sin ese contexto real, sería adivinar la forma en vez de
  construirla sobre necesidad real. Se construyen en cuanto el fundador conecte el bot y haya
  actividad real para diseñar contra eso.

Ninguno de los tres está bloqueado por falta de vendor — Discord ya está decidido y `discord.py` ya
está listo para que los usen.

## Verificado

- 12 tests nuevos: `tests/test_discord.py` (7), `tests/test_community_pulse.py` (5).
- 905/905 tests de la suite completa (incluida cobertura de orchestrator/MCP).

## Consecuencias

- En cuanto el fundador cree el bot, lo invite a su servidor, y provea las tres variables de
  entorno reales, la rama queda operativa de punta a punta sin ningún cambio de código.
