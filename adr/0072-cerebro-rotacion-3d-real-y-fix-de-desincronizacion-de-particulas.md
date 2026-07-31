# ADR 0072 — Cerebro: rotación 3D real (no paralaje simulado) + fix de desincronización + partículas mejoradas

**Fecha:** 2026-07-30
**Estado:** Aceptado

## Contexto

El "paneo 3D" del ADR 0069 era en realidad paralaje 2D: cada nodo se movía una fracción distinta del mismo desvío de cámara, sin rotación ni eje Z genuinos. El fundador probó el resultado y reportó, con razón, que (a) no se siente como una cámara rotando alrededor del cerebro, y (b) un bug real: las partículas de flujo (que van y vienen entre nodos) quedaban desincronizadas de las líneas de los edges, porque las partículas calculaban su posición contra las coordenadas SVG estáticas mientras los edges ya se recalculaban cada frame con el offset de paralaje — dos fuentes de verdad distintas para la misma geometría.

Pedido explícito, además del fix: (1) rotación 3D real con eje Z genuino entre los anillos; (2) que las partículas de luz tengan entrada/salida más orgánica ("humo de luz"); (3) que al llegar a un nodo orbiten alrededor de él como electrones; (4) que su color refleje de dónde vienen y hacia dónde van.

## Decisión

Proyección de perspectiva real, una sola fuente de verdad para SVG y canvas — todo (nodos/edges en SVG, partículas/malla/aura en canvas) lee su posición en pantalla de la misma función `project3D(x, y, z)`, calculada una sola vez por frame antes de dibujar nada. Esto elimina la clase de bug de desincronización por construcción, no como parche puntual.

- **Mundo 3D**: cada nodo mantiene su x/y del layout radial existente + un z fijo según su anillo (`BRAIN_RING_Z`: orquestador +90, entrada +40, especialistas -20, capacidades -110 — el anillo más externo es el más "atrás").
- **Cámara**: `brainCamera3D` con rotación continua y lenta en Y (una vuelta completa cada ~45s) e inclinación fija en X, trigonometría cacheada una sola vez por frame (`brainRotTrig`).
- **Orden del frame, la clave del fix**: `renderBrainFrame` incrementa la rotación, actualiza la trigonometría y proyecta el SVG (`applyBrain3DProjection`) ANTES de dibujar nada en el canvas — así partículas, malla y aura del mismo frame usan la proyección ya actualizada, nunca una desfasada un frame.
- **Partículas de flujo**: reescritas como máquina de dos fases (`travel` → `orbit`). En `travel` se interpola posición en coordenadas de mundo (x, y, z) y color entre blanco (núcleo) y el color del nodo según avance — así el color literalmente refleja origen/destino en ambos sentidos. El radio varía (más grande y difuso en los extremos de vida, más chico y brillante a mitad de camino) para el efecto de humo pedido. Al llegar, entra ~0.8s en una órbita elíptica achatada alrededor del punto de llegada antes de apagarse — el efecto "electrón alrededor de un núcleo".
- Partículas ambiente/niebla, ráfagas y la malla satelital de cada nodo también suman y proyectan su propio z, para que participen del mismo volumen 3D.

## Verificado

- 529/529 tests (sin cambios de backend — el cambio es 100% frontend).
- Playwright en instancia aislada: `brainCamera3D.rotY` avanza genuinamente con el tiempo (no es un temblor fijo); un nodo del anillo de Capacidades (z muy negativo) se desplaza notablemente más en X que el núcleo ante la misma rotación (evidencia real de que el eje Z participa, no un truco 2D); el radio de cada círculo varía según su profundidad proyectada; cero errores de consola; capturas en distintos momentos de la rotación confirman un cerebro reconocible y prolijo en todos los ángulos, sin glitches.

## Consecuencias

- El paralaje 2D del ADR 0069 queda reemplazado por este mecanismo — ese ADR sigue documentando el hallazgo del choque CSS-animation-vs-transform-JS (envolver cada nodo en su propio `<g>`), que esta ronda reutiliza sin cambios.

## Adenda — investigación de lag reportado (sin causa encontrada en este código)

El fundador reportó que el panel "se traba o tarda en cargar" (Mac e iPhone). Se investigó a fondo contra producción real (Playwright + instrumentación de tiempos):

- Se encontraron y corrigieron dos ineficiencias reales de todos modos: `applyBrain3DProjection` leía `cx`/`cy` del DOM (`getAttribute`+`parseFloat`) en cada uno de los ~60 frames/segundo, intercalado con escrituras — un patrón de layout thrashing evitable. Se cachean las coordenadas base una sola vez al construir el esqueleto (`brainNodeBasePos`). `drawBrainMesh` hacía un `beginPath()`/`stroke()` por cada uno de hasta ~500 links de la malla por frame — se agrupan por color una sola vez en `initBrainMesh` (`brainMeshLinksByColor`) y se dibuja un solo `stroke()` por color.
- Instrumentando tiempos reales: ninguna de las dos correcciones, ni el resto de las funciones del cerebro (`renderBrainFrame` completo incluido, con partículas/malla/aura reales) explica el costo medido — `renderBrainFrame` completo mide ~0.5ms por llamada. Deshabilitando por completo el cerebro (incluso antes de abrir el panel) el frame time medido en el navegador no bajó de forma significativa — evidencia de que la causa, si es real, no está en este código.
- No se encontró la causa raíz — queda como pendiente de investigación aparte si el fundador confirma que persiste tras este deploy (candidatos: algo del dashboard más amplio, no específico del cerebro).
