# ADR 0062 — Entrada en remolino del mini-cerebro, coherente con los tres puntitos

**Fecha:** 2026-07-30
**Estado:** Aceptado

## Contexto

Sobre el mini-cerebro clickeable durante "pensando" (ADR 0060), el fundador pidió una vuelta más: que la aparición no sea instantánea sino una entrada "en remolino" desde chico hasta su tamaño final, y planteó una pregunta de diseño abierta — si los tres puntitos deberían reemplazarse o hacerse coherentes con el mini-cerebro para que juntos comuniquen "pensando" de forma intuitiva, sin decirlo con texto.

## Decisión

Se mantienen los tres puntitos sin cambios — siguen siendo la señal inmediata y universalmente legible de "esperá", y aparecen sin depender de la red (a diferencia del cerebro, que necesita la respuesta real de `/dashboard/brain`). La coherencia pedida se logra ubicando ambos elementos en el mismo renglón (`.thinking-row`, antes el cerebro quedaba debajo) y con una animación de entrada real en el cerebro: `@keyframes brain-swirl-in` combina escala (0.15 → 1) y rotación (-200deg → 0deg) en 0.7s con una curva `cubic-bezier` que da un leve rebote al final — la sensación de "algo que gira y se materializa" en vez de un simple fade-in. Los puntitos siguen su pulso propio (`typing-bounce`) sin tocar; conviven en el mismo renglón como dos señales de la misma idea, no una reemplazando a la otra.

`prefers-reduced-motion: reduce` desactiva la animación (queda en su tamaño final sin más), mismo criterio de accesibilidad que el resto del proyecto.

## Verificado

- 459/459 tests (sin cambios de backend — 100% frontend).
- Playwright en instancia aislada, con una llamada real a Anthropic: los tres puntitos aparecen primero (sin esperar red), el mini-cerebro real se inserta al lado una vez llega `/dashboard/brain`, `getComputedStyle(...).animationName === "brain-swirl-in"` confirma que la animación está aplicada, y el click sigue abriendo el cerebro completo como antes.

## Consecuencias

- Se optó por conservar los tres puntitos en vez de reemplazarlos (pregunta abierta del fundador) — decisión tomada sin volver a preguntar, en línea con el pedido explícito de resolver sin más idas y vueltas. Si al verlo en uso real el fundador prefiere que el cerebro los reemplace del todo, es un cambio de una línea (retirar `.typing` del markup de `showTyping()`), no una reconstrucción.
