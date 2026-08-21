# ADR 0188 — Second Brain: skeleton de carga real entre niveles

**Fecha:** 2026-08-20
**Estado:** Aceptado

## Contexto

Fase C3 del plan Second Brain (`ROADMAP_SECOND_BRAIN_NOTION.md`, ver ADR 0179), continuación directa de
C2. Al verificar C2 en vivo con Playwright ya se confirmó que el reparentado a desktop (`#dashHistoryParked`
→ grilla del dashboard) funciona sin cambios de código nuevos — es el mismo mecanismo genérico ya real
desde ADR 0035, y el tab "Second Brain" lo hereda automáticamente por ser el mismo tipo de elemento que
"Proyectos"/"Conversaciones". Lo que sí quedaba pendiente, encontrado real al navegar en vivo durante la
verificación de C2: al cambiar de nivel (Área→Proyecto, Proyecto→conversaciones, "← volver") sin nada
todavía en cache, la lista VIEJA quedaba visible hasta que el fetch nuevo resolvía — confuso, parecía que
el click no había hecho nada.

## Decisión

`showProjectPanelLoading()` (nuevo, `web/index.html`): reemplaza el contenido de la lista por
"cargando…" — se llama en `enterArea`, `exitArea`, `enterProject` y `exitProject`, pero **solo si
`readCache()` no tiene nada todavía para la clave del nivel destino** — con cache, sigue el patrón
stale-while-revalidate de siempre (instantáneo, sin este skeleton, sin parpadeo). Mismo criterio de costo
de ADR 0067: nunca mostrar un estado de carga cuando ya hay algo real para mostrar de inmediato.

**Ajuste al alcance original, deliberado**: no se construyeron transiciones CSS de expand/collapse
(animación de apertura/cierre de nivel) — es puro pulido visual sin verificación funcional real posible
más allá de "se ve lindo", y el tiempo se priorizó en el skeleton real (que sí resuelve un problema de
usabilidad concreto, encontrado en vivo) y en verificar de punta a punta que la navegación de 3 niveles
funciona sin errores. Se puede sumar después sin tocar la lógica de datos.

Los estados vacíos ("sin Áreas todavía", "sin proyectos todavía en esta Área") ya se habían resuelto en
C2 (`renderAreaListInto`/`renderAreaProjectsInto`) — este ADR no repite ese trabajo.

## Verificado

- Sin cambios de backend — `.venv/bin/python -m pytest -q` sigue en 1610/1610 (fase 100% frontend).
- **Playwright real** contra un server de prueba (puerto 8000): al entrar a un Proyecto con la cache de
  `localStorage` limpiada a propósito, la lista muestra "cargando…" de inmediato (capturado a los 50ms del
  click, antes de que la respuesta real del servidor llegue) y el home real del proyecto se renderiza
  correctamente después. Navegación completa ida y vuelta (entrar a un proyecto → "← volver", reabriendo
  el menú hamburguesa que `enterProject` cierra en mobile, comportamiento preexistente no tocado) — lista
  real de proyectos del fundador visible al volver, cero errores de consola.

## Consecuencias

- Fase C5 (Home de Área en la UI) y C4 (Home de proyecto enriquecido) pueden reusar
  `showProjectPanelLoading()` tal cual para sus propios niveles/estados de carga si hace falta.
- Transiciones CSS quedan como mejora futura, sin ticket propio — no bloquea nada del resto del plan.
