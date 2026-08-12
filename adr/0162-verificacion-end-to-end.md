# ADR 0162 — Verificación end-to-end del ciclo completo

**Fecha:** 2026-08-12
**Estado:** Aceptado

## Contexto

Cierra las Fases 15-21 (n8n como control-plane completo de agentes, ADR 0156-0161) con verificación real
contra la instancia real de n8n y el server real de producción — no solo tests unitarios, mismo estándar
ya usado por ADR 0139/0154. A diferencia de las Fases 18/19/20, esta vez Colima y el contenedor `snarf-n8n`
estaban corriendo (`docker ps` confirmó `snarf-n8n` up 43h, `N8N_API_KEY`/`N8N_CONTROL_TOKEN` ya en
`.env`), así que la verificación pudo hacerse de punta a punta real, no quedar pendiente como en las fases
anteriores.

## Verificación realizada (real, contra infraestructura real)

1. **Generador → n8n real:** `n8n_generator.sync_executive_board()` corrido contra la instancia real —
   `PUT` sobre el workflow existente `Snarf - Executive Board` (`3Qewxl21NTY4Q9LO`, mismo id, confirma
   idempotencia). Leído de vuelta vía la API real: 15 nodos, cada `noOp` con notas que ya reflejan
   `prompt_id`/tools/modelo reales (antes eran texto fijo escrito a mano en ADR 0154).
2. **Tres workflows nuevos creados en n8n real** (`POST /api/v1/workflows`, IDs nuevos persistidos en
   `n8n_workflows/ids.json`): `Snarf - Proponer cambio de agente`, `Snarf - Confirmar cambio de agente`,
   `Snarf - Ver trazas`. Enlazados también desde `Snarf - Mapa` (el workflow raíz, `LmND41v00r1kG4dN`,
   ahora 16 nodos — antes 13) para que sean navegables desde el mapa principal, no solo accesibles por
   ID directo.
3. **Reinicio real del server de producción (puerto 8002, LaunchAgent `com.snarf.server`)** — confirmado
   explícitamente con el fundador antes de hacerlo (CLAUDE.md lo exige sin excepción). Procedimiento real:
   `launchctl bootout gui/501/com.snarf.server` + `launchctl bootstrap gui/501 <plist>` (primer intento dio
   "address already in use" por el propio proceso todavía liberando el puerto; el `KeepAlive` del
   LaunchAgent lo reintentó solo y el segundo arranque quedó limpio, confirmado con tráfico real de
   dispositivos del fundador vía Tailscale sirviendo `/status`/`/dashboard/brain`/etc. con 200 OK inmediatamente
   después).
4. **Ciclo real n8n → Snarf de producción, desde dentro del contenedor** (`docker exec snarf-n8n wget`,
   mismo criterio de verificación que ADR 0139/0154):
   - `GET /n8n/agent/cto` → 200, receta real completa (prompt/tools/routing/stages).
   - `GET /n8n/traces` → 200, trazas reales del founder (`kind: "turn"`, timestamps reales).
   - `POST /n8n/agent/cto/propose` con un prompt de prueba → 200, `change_id` real y diff real calculado
     contra el prompt real vigente del CTO.

## Decisión deliberada: no se corrió `apply` contra producción

El `propose` de arriba generó un `change_id` real — **no se confirmó con `apply`**. Aplicarlo habría
escrito un prompt de texto de prueba (sin ningún valor real) como el prompt vigente del CTO del board
ejecutivo del fundador, visible en su próxima consulta real. Aunque es reversible (rollback real, ver ADR
0157), no vale la pena mutar el comportamiento de un agente real de producción solo para demostrar que el
endpoint funciona — la lógica de `apply()` ya está cubierta por 10 tests reales en
`tests/test_agent_change_proposals.py` (incluido un ciclo `propose`→`apply` real que sí escribe a los
cuatro registros, contra rutas aisladas) y por el ciclo HTTP completo en `tests/test_app.py`. La propuesta
de prueba expira sola por TTL (15 min, ver ADR 0160) sin dejar rastro.

**Pendiente real, explícito** (mismo espíritu que el "clic de Test workflow" que ADR 0154 dejó para el
fundador): la primera vez que el fundador use `Snarf - Editar agente` (los dos workflows nuevos) para un
cambio real que sí quiera aplicar, ese va a ser el primer `apply` real de este camino — funciona (probado
en tests + la mitad `propose` probada en vivo), pero nadie completó todavía el círculo con una escritura
real intencional.

## Verificado

- 1384/1384 tests de la suite completa (`.venv/bin/python -m pytest -q`) — sin cambios de código en esta
  fase (fue pura verificación de infraestructura), mismo número que al cierre de la Fase 20.
- Cinco fases (15-21) completas, siete ADRs (0156-0162), sin romper ningún test preexistente en todo el
  recorrido, con dos bugs reales de honestidad de cifras corregidos en el camino (ver notas en ADR 0158/
  0160) y dos bugs reales de mapeo de campos corregidos en `replay.py` (ADR 0161) — todos detectados por
  los propios tests antes de mergear, nunca reportados como "andando" sin haberlo verificado.
- Puerto 8002 (producción) reiniciado UNA vez, con confirmación explícita del fundador antes de hacerlo, y
  verificado sano después (tráfico real de sus dispositivos sirviendo 200 OK). Ninguna otra acción de esta
  serie de fases tocó producción sin confirmación — todo lo demás (workflows de n8n, propose de prueba) es
  aditivo/reversible por diseño.
