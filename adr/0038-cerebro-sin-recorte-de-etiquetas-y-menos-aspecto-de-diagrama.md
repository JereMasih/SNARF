# ADR 0038 — Cerebro: sin recorte de etiquetas al hacer zoom, menos aspecto de diagrama

**Fecha:** 2026-07-29
**Estado:** Aceptado

## Contexto

El fundador probó la malla de ADR 0037 y reportó dos problemas reales, no solo una preferencia estética: (1) los círculos de los nodos y las líneas rectas centro-nodo (un literal "asterisco" de líneas convergiendo en el centro) seguían dominando el aspecto visual sobre la malla orgánica, dándole un aspecto "rústico"; (2) al hacer zoom hacia un nodo (o "en algunas ocasiones"), el texto de otros nodos desaparecía.

## Decisión

### 1. Bug real: recorte de etiquetas durante el zoom de cámara

`triggerBrainCameraFocus` escalaba el grafo entero (`transform: scale()`) con `transform-origin` puesto exactamente en el nodo activo, a 1.55x. Verificado con un barrido automatizado (Playwright, los 15 nodos reales, midiendo el porcentaje de superposición real de cada `<text>` contra el rectángulo visible de `.brain-graph`, no solo mirando capturas): con ese zoom, el lado opuesto del grafo —sobre todo el par diametralmente opuesto Memoria/Calendar, ambos en el radio máximo— quedaba empujado fuera del área visible (`overflow: hidden`), perdiendo su etiqueta por completo.

Corregido moviendo el origen de la escala a solo 32% de la distancia hacia el nodo activo (antes 100%) y bajando el zoom máximo de 1.55x a 1.14x — conserva la sensación de foco de cámara sin empujar nada fuera de cuadro. Verificado con el mismo barrido automatizado sobre los 15 nodos: cero etiquetas por debajo del 50% de superposición visible en ningún foco.

### 2. Menos "diagrama de red", más "entidad de luz"

Sin tocar la lógica de datos: `.brain-edge` (la línea recta centro-nodo, necesaria para que el pulso puntual viaje por `animateMotion`) baja de opacidad 0.35 a 0.13 y de grosor 1 a 0.7 — deja de leerse como un asterisco dominante, la malla orgánica de ADR 0037 pasa a ser el elemento visual principal. `.brain-node` suma un resplandor permanente (`drop-shadow` con `currentColor`, antes solo presente durante el latido activo o en el nodo central) y baja `stroke-width`/`stroke-opacity` — los nodos se sienten como orbes de luz fundiéndose con la malla en vez de círculos de borde duro tipo diagrama técnico.

## Verificado

- 289 tests (sin cambios de conteo — cambio puramente frontend/visual).
- Barrido automatizado con Playwright sobre los 15 nodos reales del grafo, forzando `triggerBrainCameraFocus` uno por uno y midiendo el porcentaje de superposición real de cada etiqueta contra el contenedor visible: `0` etiquetas recortadas (antes, 7 casos reales por debajo del 50% de superposición, algunos en 0%).
- Confirmado visualmente (capturas a 1920×1080, en reposo y con zoom forzado): líneas rectas casi imperceptibles, malla dominante, nodos con resplandor suave, todas las etiquetas legibles en todo momento.

## Consecuencias

- El efecto de foco de cámara es ahora más sutil (1.14x vs 1.55x) — si en el futuro se quiere un zoom más dramático, hay que resolver primero el recorte con otra técnica (por ejemplo, no clippear `.brain-graph` durante el zoom, o renderizar las etiquetas como overlay HTML fuera de la capa transformada) en vez de simplemente subir el número.
