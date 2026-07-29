# ADR 0040 — Cerebro sin recorte real, reproductor con pausa y por encima de cualquier panel

**Fecha:** 2026-07-29
**Estado:** Aceptado

## Contexto

Tras ADR 0038, el fundador reportó que las etiquetas de algunos nodos (Memoria, Conocimiento, Documentos, Orchestrator, Voz, Texto) todavía se cortaban en la primera letra "en algunos casos". Verificado con el mismo barrido automatizado pero con un umbral mucho más estricto (cualquier recorte, no solo >50%): el zoom de cámara de ADR 0038 (1.14x) todavía dejaba un recorte real, chico, en las etiquetas más largas de los nodos ubicados cerca del eje horizontal del anillo de Capacidades (Conocimiento, Documentos, Razonamiento) — exactamente donde el margen entre el radio del anillo y el borde del contenedor es más angosto.

Además, el fundador pidió: (1) que el reproductor de audio sume pausa/reanudar, y (2) que sus controles no se pierdan al pasar de modo enfoque a dashboard. Investigado con Playwright: el reproductor (`z-index: 9`) quedaba literalmente tapado — invisible e inaccesible — detrás del panel de configuración (10/11), el cerebro a pantalla completa (12/13) o el modo enfoque (14/15), cualquiera que estuviese abierto mientras el audio sonaba.

## Decisión

### 1. Zoom de cámara reducido aún más

`triggerBrainCameraFocus` baja de zoom 1.14x/mezcla 32% a **zoom 1.07x/mezcla 18%** hacia el nodo activo. Verificado con el barrido automatizado sobre los 15 nodos reales, esta vez exigiendo 0 recorte (umbral 98% de superposición, no 50%): cero etiquetas recortadas, ni siquiera parcialmente, en ningún foco. El efecto de cámara es ahora más sutil, pero el estallido de partículas y el latido activo (ya existentes) siguen comunicando "acá está pasando algo" sin depender del zoom para eso.

### 2. Reproductor de audio: pausa/reanudar, y por encima de cualquier overlay

- Nuevo botón `#pausePlayerBtn` (⏸/▶) en el reproductor flotante, entre la etiqueta y el control de velocidad. Sincronizado con los eventos reales `play`/`pause` de `sharedAudio` (no solo con el click del propio botón), así que refleja el estado real sin importar qué lo haya disparado. La etiqueta también pasa a decir "en pausa" en vez de "reproduciendo" cuando corresponde — antes decía "reproduciendo" incluso pausado.
- `.audio-player` sube de `z-index: 9` a `z-index: 20` — por encima de settings (10/11), cerebro (12/13) y modo enfoque (14/15). Verificado con Playwright (`elementFromPoint` sobre el centro real del botón): antes, un click ahí bajo modo enfoque abierto no llegaba al reproductor; ahora sí.

## Verificado

- 289 tests (sin cambios — cambios puramente frontend).
- Barrido automatizado sobre los 15 nodos reales del cerebro, umbral de superposición 98%: cero etiquetas recortadas (antes de este ADR, ~15-20 casos con recorte real aunque pequeño).
- Reproductor: confirmado con Playwright que el botón de pausa es realmente clickeable (no solo "visible" por CSS) con el modo enfoque abierto encima; ciclo real reproducir → pausar → reanudar confirmado con audio real (`sharedAudio.paused` y la etiqueta cambian correctamente en cada paso).

## Consecuencias

- Si en el futuro se agrega un nuevo overlay a pantalla completa, su z-index debe quedar por debajo de 20 (o el reproductor deja de estar "siempre encima", que es la garantía que se buscó acá).
- El zoom de cámara del cerebro es ahora bastante sutil (1.07x) — si se quiere un efecto más dramático a futuro, hay que resolver el recorte con una técnica distinta (no clippear `.brain-graph` durante el zoom, o etiquetas como overlay HTML fuera de la capa transformada) en vez de seguir bajando el número, que ya está cerca de su límite práctico.
