# ADR 0087 — Dock v2: glow volumétrico real (SVG), y supersede el límite de color literal para este componente puntual

**Fecha:** 2026-08-03
**Estado:** Aceptado

## Contexto

El fundador rechazó el resultado de ADR 0086 ("un dos tercios de círculo
cortado... círculos horribles, sin gracia, sin profundidad, sin luz
volumétrica, sin efecto 3D") y pidió una reconstrucción real con fidelidad
directa a sus 6 referencias visuales, autorizando explícitamente reusar la
estética literal (no solo la lógica) — incluida la posibilidad de superar
el límite de "estilo sí, color literal de la franquicia no" fijado en ADR
0006/0037.

## Aclaración de gobernanza (importante, sin drama)

Esa restricción de color **nunca fue un principio de FOUNDATION.md ni
CONSTITUTION.md** (que rigen propósito, identidad, estructura de
autoridad) — fue una decisión de diseño ordinaria, registrada como ADR.
Constitution Artículo II le da al fundador autoridad final sobre dirección
y principios del proyecto; revisar un ADR de diseño anterior con una ADR
nueva es el mecanismo normal de este repo (ver, por ejemplo, ADR 0044
corrigiendo el diagnóstico de ADR 0041), no una excepción ni un "salteo"
de gobernanza. No hizo falta ni se buscó ningún atajo.

## Decisión

**Supersede, solo para el dock de la Vista HUD** (no para el resto de la
interfaz, que sigue con su paleta cian/monocromática de siempre): se
autoriza un acento rojo (`--hud-signal-red: #ff3b3b`) para las etiquetas y
líneas guía, imitando directamente el patrón visual de las referencias
(anillos técnicos + captions en rojo). El resto de la interfaz de Snarf no
cambia.

### Reconstrucción real con SVG (no solo CSS)

- **Hub central real**: `<svg>` con `<circle>`s concéntricos — anillo
  externo punteado (órbita estática), anillo de marcas rotando
  (`animation: hud-omega-rotate 26s linear infinite`), anillo interno y
  núcleo con **glow real** vía `feGaussianBlur`/`feMerge` (filtros SVG,
  no solo `box-shadow` — el detalle exacto que el fundador señaló como
  ausente: "sin luz volumétrica, sin efecto 3D").
- **Líneas guía reales**: por cada chip abierto, una `<line>` SVG desde el
  hub hasta la posición exacta del chip — mismo espacio de píxeles reales
  que los nodos HTML (el `viewBox` del SVG se fija dinámicamente al tamaño
  real del contenedor en cada build, para que la línea termine exacto en
  cada chip, sin aproximar). Se iluminan en rojo al enfocar/seleccionar el
  nodo correspondiente.
- **Chips rediseñados**: de círculo plano a paralelogramo (`clip-path`,
  imitando los íconos angulares de las referencias), con glow en tres
  capas (`box-shadow` apilado: nítido + medio + amplio, simulando difusión
  real de luz) y relleno con gradiente.
- **Etiquetas**: mono-espaciadas, versalitas, con letter-spacing, en el
  rojo nuevo — mismo patrón tipográfico de las referencias.

### Dos bugs reales encontrados y corregidos verificando con Playwright (no visualmente a ojo)

1. **`.hud-mini-node` con `position: relative` en vez de `absolute`** —
   error de tipeo real durante la reescritura: rompía el hit-test de
   click/hover en todos los chips (el navegador reportaba
   `document.elementFromPoint()` devolviendo un ancestro, nunca el chip).
   Nunca se hubiera visto solo mirando el render — se encontró recién
   inspeccionando `elementFromPoint` real.
2. **El hitbox invisible del anillo (70px, para abrir/cerrar el dock)
   seguía activo con el dock abierto**, tapando cualquier chip cercano al
   centro (típicamente el de mayor prioridad real, justo el más
   importante). Corregido: el hitbox se desactiva por completo
   (`pointer-events: none`) al abrir; cerrar pasa a hacerse clickeando
   cualquier espacio vacío del dock.

## Verificado

- `.venv/bin/python -m pytest -q` — 605/605 passed (cambio 100%
  frontend).
- Playwright contra un servidor real: `elementFromPoint` en el centro de
  un chip confirma que el propio chip (no un ancestro) responde al mouse;
  `mouse.move` real dispara `data-state="focus"` + línea guía activa +
  label visible; `mouse.click` real selecciona (`data-state="select"`);
  click en espacio vacío del dock cierra. Cero errores de consola en
  todos los escenarios. 10 líneas guía reales dibujadas y alineadas con
  sus chips correspondientes.

## Limitación honesta, no resuelta en esta ADR

El dock vive en una franja de ~190px de alto dentro del panel modal del
cerebro (`#brainPanel`, no una pantalla completa) — a diferencia de las
referencias del fundador, que son ilustraciones a pantalla completa. A
esa escala, el detalle fino (texto de las etiquetas, grosor relativo de
los anillos) es necesariamente menos legible que en las referencias. No
se agrandó el panel en esta ADR — si el fundador quiere el dock a pantalla
completa o en un espacio dedicado más grande, es una decisión de layout
aparte.

## Consecuencias

- `web/hud_dock_prototype.html` (standalone, Fase 2/5) sigue sin este
  rediseño — mismo pendiente ya registrado en ADR 0086.
- `--hud-signal-red` queda documentado como excepción deliberada y acotada
  al dock — no se usa en ningún otro lugar de la interfaz.
