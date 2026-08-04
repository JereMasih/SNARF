# ADR 0086 — Rediseño del dock ("la rueda") como anillo Omega, inspirado en cómo se construyó realmente el HUD de Iron Man

**Fecha:** 2026-08-03
**Estado:** Aceptado

## Contexto

El fundador compartió 6 referencias visuales (mockups tipo HUD "Mark III
Omega": anillos concéntricos, arcos segmentados, profundidad en capas) y
una transcripción completa de un video que documenta cómo el estudio The
Orphanage construyó realmente el HUD de Iron Man (2008) — pidiendo aplicar
esos principios a la "rueda" del dock de Snarf, que hasta ahora era una
fila plana de nodos siempre expandida (Fase 2/5, integrada a la app real
en ADR 0083).

**Límite de gobernanza ya establecido, reafirmado acá (ADR 0006/0037):**
"estilo sí, colores literales de la franquicia no". De la transcripción se
tomó la **lógica real de diseño e interacción**, nunca paleta ni branding.

## Principios reales extraídos de la transcripción, y su aplicación

1. **El "widget Omega" (Mark III):** un solo anillo compacto (inspirado en
   el click-wheel del iPod) que se "desbloquea" (metáfora de llave girando)
   y abre en abanico hacia los sub-widgets, volviendo a colapsarse solo
   cuando la tarea termina — reemplaza al Mark II (todo expandido tipo
   escritorio de computadora, más lento de usar). **Aplicado:** el dock
   ahora arranca colapsado en un anillo (`#hudRingIdle`), se abre en abanico
   al click (revela `#hudMiniDockArc`, ya existente de Fase 2/5), y el
   mismo anillo (encogido) cierra de nuevo.
2. **Profundidad implícita en los bordes:** el HUD real nunca corta duro —
   sus extremos quedan justo afuera de cámara, dejando que el cerebro
   infiera espacio no visible. **Aplicado:** `mask-image` en
   `.hud-mini-dock` desvanece los bordes izquierdo/derecho del arco en vez
   de cortarlo.
3. **"Story moments" — el HUD reacciona a eventos reales de la trama, nunca
   decorativo.** **Aplicado con datos reales, no simulados:** si
   `GET /dashboard/dock_priority` (Fase 5) reporta una alerta real de
   costo, el dock se auto-abre UNA vez (no en cada poll) y el anillo pasa a
   ámbar con un pulso distinto — reacciona a un umbral de gasto real
   cruzado, no a un guión.
4. **Minimalismo tipo iPhone:** cada elemento se gana su lugar, nada
   "flashy" porque sí. **Aplicado:** no se agregó ningún elemento
   decorativo sin función — el anillo cierra Y abre (doble función), la
   alerta reusa el mismo token ámbar ya establecido en Fase 0/5.
5. **Tres modos de interacción del HUD original** (voz, mirada, IA
   proactiva) — Snarf ya cubre los tres de forma real: voz/texto (chat),
   mouse hoy con la capa de gestos ya desacoplada para eye-tracking a
   futuro (Fase 2/9), y el motor de relevancia (Fase 5) como el
   "Jarvis proactivo" que decide qué es relevante sin que se le pida.
   **No requirió cambio de código** — ya estaba resuelto por decisiones de
   fases anteriores.

## Decisión técnica

- `#hudRingIdle` (nuevo): anillo con dos bordes concéntricos (`::before`/
  `::after`) + núcleo pulsante, reusa `--glow`/`--hud-amber` existentes,
  ningún token nuevo.
- `#hudMiniDock[data-open]` controla el estado: `"0"` (default) oculta
  `#hudMiniDockArc` (opacity+pointer-events) y muestra el anillo a tamaño
  completo; `"1"` invierte — anillo encogido a escala 0.42, arco visible.
- `setHudDockOpen()`/`isHudDockOpen()` (nuevas funciones JS) — el click en
  el anillo alterna. Se resetea a cerrado al cerrar el panel del cerebro
  (`closeBrainFullscreen`).
- `hudDockHadAlert` (flag nuevo): evita reabrir el dock en cada poll
  mientras la alerta sigue activa — el "story moment" ocurre una vez, en
  el momento real en que la alerta aparece, no se repite molestando.

## Verificado

- `.venv/bin/python -m pytest -q` — 605/605 passed (cambio 100% frontend,
  sin tests Python nuevos).
- Playwright contra un servidor real en directorio temporal (datos
  aislados): (1) sin alerta — dock colapsado por default, click abre el
  arco (opacity 0→1), click de nuevo cierra; (2) con una alerta de costo
  real sembrada — el dock se auto-abre solo, el anillo queda marcado
  `data-alert="1"`, el nodo `cost` visible en ámbar dentro del arco
  abierto; (3) `mask-image` de desvanecido en los bordes confirmado en el
  DOM real. Cero errores de consola en los tres escenarios.
- No hizo falta reiniciar el servidor de producción — cambio 100%
  frontend, `web/index.html` se sirve fresco del disco en cada request.

## Consecuencias

- `web/hud_dock_prototype.html` (Fase 2/5, standalone) no se actualizó con
  este mismo rediseño — sigue mostrando el arco siempre expandido. Si el
  fundador quiere el mismo anillo Omega ahí, es un cambio aparte, menor,
  reusando el mismo patrón.
- El feed de texto al lado del dock sigue mostrando el resumen mock del
  verbo/skill — sin cambios de esta ADR.
