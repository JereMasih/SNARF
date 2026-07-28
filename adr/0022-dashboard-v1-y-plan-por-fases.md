# ADR 0022 — Dashboard v1 (datos reales) y plan por fases

**Fecha:** 2026-07-27
**Estado:** Aceptado — verificado por API real y suite de tests; falta confirmación visual del fundador en su navegador real

## Contexto

ADR 0019 había pospuesto explícitamente el dashboard y la visualización tipo "Jarvis brain" hasta que existiera contenido real que mostrar más allá del flujo único LLM+herramientas+memoria, y hasta calibrar el alcance junto al fundador para evitar "arquitectura astronauta" (`MASTER_MAP.md`). ADR 0020 registró que, cerrada la ronda de los tres bugs, el dashboard era el siguiente paso, con la condición de que cualquier trabajo de interfaz futuro fuera responsive para escritorio y múltiples dispositivos, no solo iPhone.

El fundador pidió retomar el dashboard ahora. Antes de escribir código se acordó frenar y documentar primero el alcance real y el plan por fases, en vez de asumir directamente la visión original completa (paneles de Trading, Mercado, GitHub, MCP, y una visualización de red neuronal tipo "Jarvis brain" con nodos iluminándose por el flujo real del sistema) — ninguno de esos subsistemas existe hoy.

La visión completa que el fundador describió, para que quede registrada y no se pierda entre fases:

- Un menú de usuario (hoy inexistente) en la interfaz: quién es el usuario actual y un desplegable con "cerrar sesión" y, a futuro, configuración de usuario.
- Navegación entre Chat y Dashboard por swipe/páginas, tanto en mobile como desktop.
- En desktop, a futuro: una aplicación real, con múltiples ventanas ocupando múltiples monitores/escritorios (el fundador tiene tres monitores en su oficina), mostrando la visualización de red neuronal ("los flujos de Snarf latiendo con luces").
- En mobile: swipe/scroll, y configurable por el usuario (qué widgets ver).
- Principio de extensibilidad: cada nueva Capacidad o Especialista que se agregue a Snarf debe poder sumar su propio widget al dashboard, mostrando información relevante, de forma opt-in por el usuario.

## Decisión

Se construye ahora una v1 web, dentro de la misma interfaz existente (`web/index.html`, mismo servidor FastAPI), y se deja documentado como plan explícito lo que corresponde a fases futuras, para no tener que reabrir esta discusión de alcance cada vez que se retome el tema.

### Fase 1 (esta ronda) — Dashboard v1 con datos reales, dentro de la web actual

1. **Menú de usuario**: nuevo control en la interfaz (usuario actual + desplegable con "cerrar sesión" y placeholder de "configuración, próximamente"). Reemplaza al botón de cerrar sesión suelto en el sidebar, consolidando acciones de cuenta en un solo lugar.
2. **Vista Dashboard**: nueva vista alternable con el Chat mediante un control explícito (botón) y, además, gesto de swipe horizontal en dispositivos táctiles — sin depender solo del gesto, porque no es descubrible por sí solo.
3. **Layout responsive real**: en mobile, un widget por pantalla/columna (scroll o swipe entre ellos); en desktop, grilla que aprovecha el ancho disponible mostrando varios widgets a la vez. No se construye todavía multi-ventana ni gestión de monitores — eso depende de convertir Snarf en una aplicación de escritorio nativa (fase 3).
4. **Widgets v1, todos sobre datos que ya existen hoy** (ningún dato inventado ni simulado):
   - **Estado del sistema**: disponibilidad real de LLM, STT, TTS (ya expuesto en `/status`) y estado de la conexión Google del usuario actual (si hay token guardado en `credentials/tokens/<user_id>.json`).
   - **Conversaciones**: total de conversaciones y de mensajes, y actividad reciente (mensajes por día, últimos 14 días) a partir de `episodic_memory.jsonl`.
   - **Memoria**: tamaño total de la memoria episódica (cantidad de entradas) y fecha de la más antigua/reciente.
5. **Principio de extensibilidad, adoptado desde ahora**: cada widget es una función independiente en el frontend más un campo independiente en la respuesta de `/dashboard/summary`; agregar un widget nuevo no debe requerir tocar los existentes. Este principio se aplica recién cuando se agregue la próxima Capacidad real (no hay nada más que agregar hoy).

### Fase 2 (futura, sin fecha) — Widgets de nuevas Capacidades

A medida que se agreguen Capacidades reales (extracción de contenido de Drive, trading, GitHub, MCP, lo que sea que se decida construir), cada una suma su widget correspondiente al dashboard, opt-in por el usuario. Requiere antes que exista la Capacidad real — no se construyen widgets de subsistemas que no existen.

### Fase 3 (futura, sin fecha) — Aplicación de escritorio nativa y visualización de red neuronal

- Convertir Snarf en una aplicación de escritorio real (candidatos a evaluar cuando llegue el momento: Tauri, Electron), con soporte de múltiples ventanas para aprovechar múltiples monitores.
- Visualización tipo "Jarvis brain": requiere antes una fuente de datos real que hoy no existe — un registro de actividad/eventos del `Orchestrator` (qué herramienta se ejecutó, cuándo, con qué resultado; hoy `episodic_memory.jsonl` solo guarda input/response de texto, no qué herramientas se llamaron). Esa capacidad de logging de eventos es un prerrequisito de esta fase, no algo que se pueda simular con datos de mentira.
- No se empieza ninguna de las dos hasta decidir junto al fundador, en su momento, con qué framework y con qué alcance — evitando construir infraestructura para una visión que todavía puede cambiar.

## Descartado explícitamente en esta ronda

- Paneles de Trading, Mercado, GitHub, MCP: no existen las Capacidades/Especialistas que los alimentarían. Se construyen cuando esas Capacidades existan (Fase 2).
- Visualización de red neuronal ("Jarvis brain"): pospuesta a Fase 3, requiere logging de eventos que no existe hoy.
- Aplicación de escritorio nativa multi-ventana: pospuesta a Fase 3.

## Verificado

- Suite completa de tests (47/47, antes 41): 6 tests nuevos — `EpisodicMemory.stats()` (memoria vacía, conteo de mensajes/conversaciones, bucket de actividad de hoy) y `/dashboard/summary` (datos reales, `google_connected` en ambos estados, rechazo sin sesión).
- Verificado extremo a extremo contra una instancia real de `app.py` en un puerto de prueba aislado (8001, sin tocar el servidor real del fundador en el puerto 8000, misma práctica que ADR 0020/0021): login real, `/dashboard/summary` devolviendo los datos reales de `data/episodic_memory.jsonl` (90 mensajes, 31 conversaciones) y detectando correctamente el token real de Google del fundador (`google_connected: true`).
- El JavaScript de `web/index.html` se validó sintácticamente con el motor JavaScriptCore del sistema (parseo puro, sin ejecutar contra un DOM real) — sin errores.
- **Limitación real de esta verificación:** no hay navegador ni motor de automatización disponible en este entorno (`chromium-cli`, Playwright y Node no están instalados) para confirmar visualmente el layout, el swipe táctil o el menú desplegable en un DOM real. Queda pendiente de confirmación del fundador en su navegador real, como en ADR 0020 y ADR 0021.

## Consecuencias

- El dashboard de hoy es deliberadamente chico: tres widgets sobre datos 100% reales, no una maqueta de algo más grande. Coherente con la lección repetida del proyecto (ADR 0019) de no construir sobre subsistemas que no existen.
- Cualquier Capacidad nueva que se agregue de acá en más debería considerar, como parte de su propio diseño, si le corresponde un widget en el dashboard (Fase 2) — se registra la expectativa aquí para no tener que redescubrirla.
- El menú de usuario nuevo dejará de tener un solo ítem (cerrar sesión) en cuanto exista una página real de configuración de usuario o multi-usuario — hoy es deliberadamente mínimo.
