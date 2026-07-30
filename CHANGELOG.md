# CHANGELOG

Registro de cambios relevantes del proyecto Snarf. Los cambios de gobernanza o arquitectura que requieren justificación quedan además documentados como ADR en `adr/`.

## [2026-07-25] BUILD MODE 001 — Primera versión funcional

### Documentos
- CONSTITUTION.md: primera versión estable (v1.0), reemplaza al borrador candidato. Ver ADR 0001.
- CHARACTER.md: nuevo. Personalidad permanente de Snarf.
- COGNITION.md: nuevo, v0.1. Describe el razonamiento real implementado (walking skeleton).
- MASTER_MAP.md: actualizado para reflejar la existencia de Constitution, Character y Cognition, y para registrar la ausencia de un nivel de Políticas/Procedimientos en la jerarquía documental.

### Arquitectura y código
- Adoptado Python como stack técnico inicial. Ver ADR 0002.
- Implementada arquitectura de tres capas (Capacidades / Especialistas Cognitivos / Snarf). Ver ADR 0003.
- Construido el primer walking skeleton: canal de texto funcional de punta a punta (entrada → Core Cognitivo → memoria episódica → salida). Ver ADR 0004.
- Canal de voz (ElevenLabs) definido como interfaz, pendiente de credencial.

### Repositorio
- `git init` del repositorio.
- Estructura de carpetas creada: `snarf/` (core, capabilities, specialists, runtime), `adr/`, `data/`.

## [2026-07-25] Canal de voz real (ElevenLabs)

- `ElevenLabsTTS` y `ElevenLabsSTT` implementadas contra la API real (antes eran stubs). Nueva Capacidad `LocalAudioIO` para reproducción (`afplay`) y grabación de micrófono (`sounddevice`).
- Voz elegida por el fundador: Antonio - Confident, Gentle and Clear (`es-AR`).
- Verificado: síntesis + reproducción de audio real, y transcripción por round-trip (texto → audio → texto, coincide).
- Pendiente de verificación: captura de micrófono en vivo (requiere ejecución interactiva de `python3 main.py --voice`).
- Ver ADR 0005.

## [2026-07-25] Grabación manual e interfaz visual

- Primera prueba en vivo reveló dos problemas reales: grabación de duración fija desincronizada con el habla real, y un bug en `AnthropicLLM` (asumía que el primer bloque de respuesta siempre era texto; el modelo a veces antepone un bloque de razonamiento). Ambos corregidos.
- `LocalAudioIO` soporta grabación manual start/stop. `VoiceChannel` (terminal) actualizado a este esquema.
- Nuevo punto de entrada `app.py` (FastAPI) + `web/index.html`: interfaz visual con un orbe controlado a un click (escuchar / detener), diseño propio inspirado en el principio de HUD conversacional, sin reproducir ninguna interfaz de ficción con derechos de autor.
- Verificado de punta a punta vía HTTP: grabación real capturada, transcripta, razonada y respondida por voz correctamente.
- Ver ADR 0006.

## [2026-07-25] Grabación en el navegador, dos modos, chat y rediseño visual

- Captura de audio movida del servidor (`sounddevice`) al navegador (`MediaRecorder`) — necesario para que la interfaz tenga sentido desde cualquier dispositivo, no solo la Mac.
- Dos modos intercambiables: mantener presionado y soltar para enviar, o click/click con revisión de texto y envío manual.
- Historial de conversación tipo chat (usuario a la derecha, Snarf a la izquierda), persistente mientras la pestaña está abierta.
- Rediseño visual: fondo con degradé a negro, grilla técnica, línea de escaneo, orbe con rayos y anillos concéntricos.
- Servidor ahora en `0.0.0.0` (antes solo localhost); imprime la URL de red al iniciar.
- Verificado por API: `/transcribe` y `/send` funcionan de punta a punta. Pendiente de verificación manual en navegador (MediaRecorder no se puede probar por este medio).
- Limitación conocida y no resuelta: acceso al micrófono desde el celular vía red local requiere HTTPS (contexto seguro del navegador); pendiente de decisión sobre cómo resolverlo.
- Ver ADR 0007.

## [2026-07-25] Acceso remoto seguro vía Tailscale

- Instalado Tailscale en la Mac y el iPhone del fundador, mismo tailnet.
- `tailscale serve --bg 8000` expone `app.py` con HTTPS gestionado automáticamente en `https://macbook-pro-de-jeremas.tailb10c73.ts.net/`.
- Verificado: la URL responde 200. Pendiente: prueba manual de grabación de voz desde el iPhone.
- Ver ADR 0008.

## [2026-07-25] Correcciones de interfaz para iOS y layout móvil

- Diagnosticadas dos causas probables de que la voz no funcionara en iPhone: `MediaRecorder` etiquetaba el audio como `webm` sin verificar el formato real que graba Safari, y la reproducción de audio ocurría fuera de la ventana de gesto de usuario que exige iOS.
- Detección real de formato soportado (`MediaRecorder.isTypeSupported`) y patrón de "desbloqueo de audio" con un elemento compartido.
- Layout invertido: orbe y controles fijos abajo (alcance del pulgar), chat arriba creciendo hacia arriba.
- Corregidos los bordes blancos en Safari (`viewport-fit=cover`, fondo negro en `html`, `safe-area-inset-*`).
- Más efectos visuales: doble capa de rayos, nebulosas de fondo, partículas, marcas de esquina tipo HUD.
- Errores ahora muestran el detalle técnico en pantalla para poder diagnosticar sin acceso a la consola del dispositivo.
- No verificado contra un iPhone real en esta sesión — pendiente de confirmación del fundador.
- Ver ADR 0009.

## [2026-07-25] Conversaciones persistentes, Markdown y pulido de interfaz

- Memoria episódica agrupable por `conversation_id`; nuevos endpoints `GET /conversations` y `GET /conversations/{id}`.
- Barra lateral desplegable (☰) para listar, retomar y crear conversaciones — funciona igual desde la Mac o el iPhone porque ambos hablan con el mismo backend.
- Snarf ahora formatea sus respuestas en Markdown cuando corresponde (encabezados, listas, negrita, citas, código); el frontend incluye un renderer propio y liviano.
- Selector de modo reducido a un texto pequeño de bajo contraste (antes eran dos botones prominentes). Agregado indicador de "escribiendo" (tres puntos animados).
- Pospuesto explícitamente, a pedido del fundador: que Snarf pueda automodificarse conversando (código o documentos propios). Queda registrado como capacidad futura, no implementada.
- Verificado por API completo. Pendiente confirmación visual del fundador (renderer, barra lateral, animaciones).
- Ver ADR 0010.

## [2026-07-25] Memoria cruzada, modo de texto y orbe holográfico

- Snarf puede ahora buscar y recordar contenido de cualquier conversación pasada, no solo la actual, mediante herramientas (`list_conversations`, `get_conversation`, `search_memory`) que decide usar cuando hace falta. Verificado con un caso real cruzando dos conversaciones distintas.
- Nuevo modo de texto en el selector (click/mantener/texto): campo de texto + enviar, teclado automático en el celular.
- Orbe rediseñado: relleno translúcido tipo fresnel en vez de sólido, con anillos de wireframe 3D simulando un globo y parpadeo sutil — más holográfico, menos "bola sólida".
- Ver ADR 0011.

## [2026-07-25] Audio bajo demanda, selector de modo segmentado, arranque en conversación nueva

- El audio de Snarf ya no se reproduce solo; cada respuesta tiene un botón "▶ escuchar" que abre una ventanita flotante con control de velocidad (1x a 2x, y 0.75x) y botón de cierre para cortar antes de que termine.
- Selector de modo (Mantener / Toque / Texto) rediseñado como control segmentado grande y claro, en vez de un texto chico fácil de tocar por error cerca del orbe.
- La app ahora siempre arranca en una conversación nueva; retomar una anterior es una acción explícita desde la barra lateral.
- Ver ADR 0012.

## [2026-07-25] Autenticación de Google y primera Capacidad de Drive

- Proyecto de Google Cloud creado, credenciales OAuth (App de escritorio) configuradas.
- `GoogleAuth`: autenticación compartida (OAuth + caché/refresh de token) para todas las futuras Capacidades de Google. Un solo consentimiento cubre Drive, Gmail, Calendar y YouTube.
- `GoogleDrive`: listar y leer archivos. Verificado en vivo contra la cuenta real del fundador — trajo archivos reales de su Drive.
- Pendiente: extracción de contenido de PDFs, imágenes, audio y video (hoy solo texto/Google Docs/Sheets). Vectorización todavía no construida.
- Ver ADR 0013.

## [2026-07-25] Gmail, Calendar, YouTube conectados; tablas Markdown

- Nuevas Capacidades: `GoogleGmail`, `GoogleCalendar`, `GoogleYouTube`, todas sobre la autenticación ya aprobada.
- Snarf puede leer correo, agenda, suscripciones y videos que le gustaron al fundador — verificado en conversación real con datos reales.
- `send_message` y `create_event` existen pero no están expuestos como herramientas autónomas todavía: enviar o crear algo es una acción de alto impacto (Constitution, Artículo VII) que necesita un mecanismo de confirmación que todavía no se construyó.
- Corregido: el renderer de Markdown del frontend no soportaba tablas — se detectó en la primera respuesta real de Gmail (llegó como tabla) y se agregó soporte completo con estilo.
- Ver ADR 0014.

## [2026-07-25] Confirmación en dos pasos para acciones de alto impacto

- `gmail_send_message` y `calendar_create_event` ya son herramientas autónomas de Snarf, con protocolo obligatorio de confirmación: primero propone (vista previa, no ejecuta nada), y solo ejecuta de verdad tras una confirmación explícita del fundador en la conversación.
- Verificado en vivo contra el Calendar real: confirmado que el evento no existía antes de aprobar, y que sí existía después, con los datos correctos.
- Limitación conocida y documentada: la barrera depende de que el modelo siga el protocolo; no hay todavía un control independiente del modelo (por ejemplo, un botón de aprobación en la interfaz).
- Ver ADR 0015.

## [2026-07-25] Rendimiento: TTS bajo demanda real, calentamiento de conexión, fix de scroll

- `/send` ya no genera audio salvo que se pida; nuevo endpoint `/tts` bajo demanda. Como efecto secundario positivo, ahora también se puede escuchar el audio de mensajes de conversaciones pasadas.
- Calentamiento de la conexión con Anthropic al arrancar el servidor: primera consulta real bajó de ~10.8s a ~5s; consultas siguientes, ~1.5-2s (medido, no estimado).
- Velocidad de reproducción por defecto: 1.25x. Botón "escuchar" ahora siempre en su propia línea dentro del globo.
- Corregido bug de scroll en Chrome de escritorio tras respuestas largas (layout flexbox con `justify-content: flex-end` no scrolleaba bien con overflow) — reemplazado por el patrón robusto de wrapper interno.
- Ver ADR 0016.

## [2026-07-25] Gestión de calendarios, organización de Gmail/Drive, fixes de interfaz

- Corregido bug real: en modo "mantener presionado", un error dejaba el chat sin forma de recuperarse sin refrescar. Ahora cualquier interacción limpia el error y reintenta.
- `/transcribe` degrada con gracia (transcript vacío) en vez de tirar un 500 crudo.
- Corregido scroll horizontal: causado por links Markdown sin renderizar (URLs largas sin espacios); ahora los links se renderizan como `<a>` y se agregó `overflow-wrap` como cinturón de seguridad.
- Selector de modo reducido a un ícono chico en la esquina (antes tres botones siempre visibles) — más espacio para el chat.
- Nuevas Capacidades: gestión completa de calendarios (listar/crear/eliminar), organización de Gmail (etiquetas/carpetas) y Drive (crear carpetas, mover archivos, eliminar) — con el mismo protocolo de confirmación en dos pasos para lo irreversible.
- `Orchestrator._handle_tool` refactorizado de `if/elif` a un registro de handlers.
- Verificado en vivo, incluyendo un ciclo completo de creación y eliminación de un calendario real, confirmado independientemente en ambos sentidos.
- Ver ADR 0017.

## [2026-07-25] Gestión de eventos individuales de calendario

- Encontrada y corregida la causa de una contradicción aparente: se había construido gestión de *calendarios* (ADR 0017), no de *eventos individuales* dentro de un calendario — eran cosas distintas, mal comunicadas como si fueran lo mismo.
- Hallazgo adicional real: `calendar_list_upcoming_events` no muestra eventos pasados, por lo que un evento que ya ocurrió parecía "no existir". Se agregó `calendar_search_events` (busca sin restricción de fecha) y se instruyó a Snarf a usarla en vez de asumir que algo no existe.
- Nuevas herramientas: `calendar_search_events` (lectura), `calendar_delete_event` y `calendar_move_event` (alto impacto, con confirmación).
- Resuelto en vivo, a través del chat, el caso real que expuso el problema: encontrado un evento pasado, borrado un duplicado de prueba, y movido el evento correcto entre calendarios — todo confirmado explícitamente y verificado de forma independiente contra la API real.
- Ver ADR 0018.

## [2026-07-27] Auditoría técnica completa y base de calidad (tests, CI, dependencias fijadas)

- Primera auditoría técnica de arquitectura del repositorio completo (no de gobernanza/identidad, esa fue Architecture Review 0001): documento `ARCHITECTURE_AUDIT.md`, 22 secciones, cada hallazgo anclado a archivo y línea. Confirmó que el código es limpio (sin dependencias circulares, sin imports sueltos) pero con cero madurez operacional: sin tests, sin CI, sin versiones fijadas, sin logging estructurado.
- Identificados con evidencia de código, sin haber tocado nada todavía: causa más probable de que las respuestas largas se corten (`max_tokens=1024` fijo en `AnthropicLLM.generate`, sin chequear `stop_reason`), causa más probable de que el push-to-talk deje de andar en iPhone tras el primer uso (el `MediaStream` del navegador se cachea para siempre y nunca se revalida), y causa más probable del botón de enviar cortado en mobile (`min-height: 100vh` conviviendo con `height: 100dvh` en el mismo `body`). Ninguno corregido todavía — quedan para la siguiente fase de trabajo.
- Se fijaron las versiones exactas de todas las dependencias en `requirements.txt` (antes sin pinear); nuevo `requirements-dev.txt` para dependencias de test.
- Primera suite de tests automatizados del proyecto (27 tests, `pytest`): memoria episódica, dispatch de herramientas del Orchestrator, y — el más importante — que las 8 herramientas de alto impacto (Artículo VII de Constitution) nunca ejecutan la acción real sin `confirmed=true`, para las ocho, una por una.
- Primer pipeline de CI (`GitHub Actions`): corre la suite completa en cada push y pull request.
- Ver ADR 0019.

## [2026-07-27] Corrección de los tres bugs reportados

- Respuestas largas cortadas: `max_tokens` fijo en 1024 sin chequear `stop_reason`, subido a 4096, y ahora se agrega una nota visible cuando una respuesta se trunca en vez de devolverla en silencio como si estuviera completa. Verificado con test unitario (cliente falso) y con una llamada real a la API de Anthropic.
- Push-to-talk muerto en iPhone tras el primer uso: el `MediaStream` del micrófono se cacheaba para siempre; en iOS, backgrounding/bloqueo de pantalla suele matar esos tracks sin avisar, produciendo grabaciones vacías. Ahora se pide un stream nuevo en cada grabación y se libera al terminar. **Confirmado por el fundador en su iPhone real**, tanto en modo "mantener presionado" como en modo "toque".
- Botón de enviar cortado en mobile: dos hipótesis iniciales (conflicto `min-height:100vh`/`height:100dvh`; falta de `min-width:0` en el input de texto) resultaron necesarias pero no suficientes, descartadas con evidencia real de capturas de pantalla del fundador. La causa real: la página completa renderizaba más ancha que el viewport del iPhone en todos los modos (no solo en modo texto), y Safari permitía pellizcar para hacer zoom en vez de ajustarla — solo haciendo zoom-out manual se veía todo encuadrado. Corregido agregando `overflow-x: hidden` a `html` y deshabilitando el zoom táctil (`user-scalable=no`), coherente con que esta es una interfaz tipo HUD fija.
- **Los tres bugs confirmados como resueltos por el fundador en su iPhone real.**
- Ver ADR 0020.

## [2026-07-27] Login por contraseña y credenciales de Google por usuario

- Verificado y descartado un temor real del fundador: sus credenciales de Google nunca estuvieron públicas en GitHub (chequeado contra la historia completa de git y el remoto real), pero la arquitectura sí asumía un único usuario implícito, sin forma de que un segundo usuario conectara su propio Google sin pisar el token del fundador.
- `GoogleAuth` ahora recibe `user_id` y guarda el token en `credentials/tokens/<user_id>.json` (antes un único archivo global); `Orchestrator` recibe `user_id` explícitamente (`DEFAULT_USER_ID = "fundador"` por ahora).
- Nuevo login real: página `web/login.html`, cookie de sesión firmada con `itsdangerous`, contraseña en `SNARF_ACCESS_PASSWORD`, falla cerrado (no abierto) si falta configuración. `/send`, `/transcribe`, `/tts` y `/conversations*` ahora exigen sesión válida — antes la única barrera era la red (Tailscale/LAN).
- Evaluado y pospuesto a propósito: login con Google (el camino correcto para cuando haya multi-usuario real, ya que Snarf ya pide ese mismo consentimiento) y con Apple (no es simple como se asumió, y no destraba nada hoy).
- 11 tests nuevos de autenticación; en el camino se encontró y corrigió un bug real en dos tests existentes que disparaban una llamada real a la API de Anthropic vía el hook de arranque, detectado por duración anómala de la suite.
- Confirmado por el fundador en su navegador real, contra el servidor de producción reiniciado.
- Ver ADR 0021.

## [2026-07-27] Dashboard v1 y plan por fases

- Antes de construir nada, se documentó en ADR 0022 el alcance real y un plan por fases: la visión original del fundador (paneles de Trading, Mercado, GitHub, MCP, y una visualización de red neuronal tipo "Jarvis brain") no tiene todavía ninguno de esos subsistemas construidos, así que la v1 se limita a datos 100% reales, y el resto queda registrado como fases futuras explícitas en `MASTER_MAP.md` (Roadmaps).
- Nuevo endpoint `GET /dashboard/summary`: estado de capacidades (LLM/STT/TTS, y si el usuario actual tiene a Google conectado vía `credentials/tokens/<user_id>.json`) y estadísticas reales de memoria episódica (`EpisodicMemory.stats()`, nuevo: total de mensajes y conversaciones, fecha más antigua/reciente, actividad de los últimos 14 días).
- Nueva vista Dashboard en `web/index.html`, alternable con el Chat por botón (📊) y por swipe táctil horizontal, con layout en grilla responsive (una columna en mobile, varias en desktop aprovechando el ancho disponible). Tres widgets: Estado del sistema, Conversaciones (con gráfico de barras de actividad reciente) y Memoria episódica.
- Nuevo menú de usuario en el sidebar (usuario actual + desplegable con "cerrar sesión" y un placeholder de "configuración, próximamente"), reemplazando al botón de cerrar sesión suelto.
- Explícitamente pospuesto y documentado en ADR 0022: widgets de Capacidades que no existen todavía (Fase 2), y aplicación de escritorio nativa multi-ventana junto con la visualización de red neuronal (Fase 3) — esta última requiere antes un registro real de eventos del `Orchestrator` que hoy no existe.
- 6 tests nuevos (47/47 en total). Verificado por API real contra una instancia aislada en el puerto 8001 (misma práctica que ADR 0020/0021, sin tocar el servidor real del fundador en el puerto 8000) y el JavaScript validado sintácticamente. Pendiente de confirmación visual del fundador en su navegador real — no hay navegador ni motor de automatización disponible en este entorno de desarrollo.
- Ver ADR 0022.

## [2026-07-27] Íconos propios, widgets de Google, configuración de widgets y layout Jarvis en desktop

- Reemplazados todos los íconos de emoji de la interfaz (menú, alternar dashboard/chat, modos de entrada, configuración, cerrar sesión) por SVG propios de trazo delgado, coherentes con la estética HUD ya existente — sin librería externa ni CDN.
- Cuatro widgets nuevos con datos reales, de solo lectura: Google Drive (últimos 5 archivos modificados), Gmail (últimos 5 mensajes), Calendar (próximos 5 eventos), YouTube (últimas 5 suscripciones). Corrige un error de alcance de ADR 0022: estas Capacidades ya existían desde ADR 0013/0014, no eran hipotéticas — no debieron quedar pospuestas a "Fase 2".
- Nuevo panel de configuración (reemplaza el placeholder "próximamente" del menú de usuario): un interruptor por widget para elegir qué mostrar, persistido por usuario en `data/dashboard_prefs/<user_id>.json` (nuevo módulo `snarf/runtime/dashboard_prefs.py`, endpoints `GET`/`PUT /dashboard/preferences`).
- Paneles reordenables arrastrando: mouse en desktop (arrastre inmediato desde un asa dedicada), mantener presionado ~350ms y arrastrar en mobile (mismo mecanismo con Pointer Events para ambos). El orden se guarda junto con la visibilidad.
- Layout "Jarvis" en desktop ancho (`min-width: 900px`) con el Dashboard activado: el chat queda centrado (mismo componente, no una copia) y los widgets rodean alrededor — arriba (actividad de conversaciones), izquierda (lista de conversaciones siempre visible + estado del sistema), derecha (memoria, Drive, Gmail, Calendar, YouTube, estos sí reordenables). En mobile, o en desktop sin el Dashboard activado, se mantiene el comportamiento de ADR 0022 (una vista a la vez).
- Corregida una vulnerabilidad real encontrada en el camino: los datos de Gmail y Calendar no los controla el fundador (el asunto de un email lo define quien se lo envía) — insertarlos sin escapar en el HTML habría sido XSS real. Se agregó `escapeHtml()` y se aplicó a todo campo de origen externo, y por defensa en profundidad también al título de conversación de la lista lateral.
- 21 tests nuevos (68/68 en total). Verificado por API real contra una instancia aislada (puerto 8001) incluyendo los cuatro widgets de Google contra la cuenta real del fundador; JavaScript validado sintácticamente y HTML verificado con balance de tags. **Pendiente crítico:** ni el layout Jarvis ni el arrastre para reordenar fueron vistos en un navegador real — se pide explícitamente confirmación visual del fundador antes de seguir construyendo sobre este layout.
- Ver ADR 0023.

## [2026-07-27] Fixes de layout Jarvis, CI y arrastre; widgets más útiles

- **Layout Jarvis roto en desktop, corregido:** faltaba `position: relative; z-index: 2` en `#appRoot` — los fondos fijos de la interfaz pintaban por encima de las tres zonas nuevas (arriba/izquierda/derecha), que estaban geométricamente bien ubicadas pero invisibles. Encontrado con `document.elementFromPoint` usando Playwright (Chromium headless), instalado en este entorno por primera vez para poder verificar visualmente en vez de a ciegas.
- **CI roto en GitHub Actions, corregido:** `pythonpath = .` agregado a `pytest.ini` — el workflow corre `pytest` a secas (no `python -m pytest`), que nunca agregó el directorio del proyecto a `sys.path`. Bug preexistente, no introducido por el trabajo de hoy; encontrado revisando el run fallido que el fundador vio pasar por el widget de Gmail.
- **Arrastre para reordenar paneles, roto en celular real, corregido:** se cancelaba el gesto si el dedo se movía más de 6px durante los 350ms de espera — umbral irreal para un toque humano. Eliminada esa cancelación (el asa ya bloquea el scroll nativo con `touch-action: none`, así que no protegía nada) y agrandada el área táctil del asa.
- **Widgets con más contexto:** subtítulo corto en cada uno explicando qué muestra; Drive ahora enlaza a cada archivo real y muestra fecha/tamaño; Gmail enlaza a cada mensaje real; Calendar enlaza a cada evento real; YouTube enlaza a cada canal real. Nuevo selector dentro del propio widget de Gmail para elegir cuántos mensajes ver (5/10/20), persistido por usuario.
- 5 tests nuevos (73/73). Primera verificación con navegador real del proyecto: capturas de pantalla de desktop y mobile después de cada fix, y una simulación de arrastre táctil con jitter realista.
- Ver ADR 0024.

## [2026-07-27] Interpretación de Gmail: primer Especialista Cognitivo real

- Nuevo `snarf/specialists/gmail_digest.py` (`GmailDigestSpecialist`): primer Especialista Cognitivo real del proyecto (la capa existía documentada desde ADR 0004 pero vacía). Razona sobre la bandeja de entrada de Gmail con su propio system prompt (agrupa por categoría, señala qué conviene revisar y por qué), reutilizando las Capacidades `GoogleGmail` y `AnthropicLLM` ya existentes.
- Nueva herramienta de chat `gmail_summarize_inbox`: Snarf puede interpretar el correo cuando se le pida, sin necesitar confirmación (es de solo lectura). Por defecto devuelve la interpretación ya cacheada; `force_refresh=true` genera una nueva.
- Nuevo refresco automático en segundo plano: primer componente de Snarf que actúa sin que medie un pedido del fundador — un loop de `asyncio` en `app.py` reinterpreta la bandeja cada `GMAIL_DIGEST_REFRESH_MINUTES` (30 por defecto), solo si hay Google conectado y LLM disponible.
- Widget de Gmail del dashboard ampliado con un botón "interpretar bandeja" y el texto de la última interpretación, en Markdown.
- 18 tests nuevos (91/91 en total).
- Ver ADR 0025.

## [2026-07-27] Refresco de Gmail bajo demanda, reusabilidad de Capacidades/Especialistas, costo de tokens

- **Corregido a pedido del fundador:** eliminado el loop de refresco en segundo plano de ADR 0025. Ahora es 100% impulsado por el navegador — se dispara al abrir el dashboard (comparando barato el último mensaje contra la interpretación cacheada) y se repite cada 5 minutos solo mientras el dashboard sigue abierto y visible (pausado con la Page Visibility API). Cero costo cuando no se está usando.
- **Bug real corregido:** arrastrar paneles en el navegador de escritorio no funcionaba — el mousedown disparaba selección de texto nativa, y los listeners de arrastre estaban en el asa (chica) en vez de en `document`, así que dejaban de recibir eventos en cuanto el cursor se alejaba. Verificado esta vez con un arrastre de mouse real (no sintético).
- **Bug real corregido:** el botón de modo de entrada (mantener/toque/texto) no hacía nada — un bug latente de ADR 0023: al reemplazar emojis por íconos SVG, un chequeo de `e.target !== modeFab` dejó de funcionar porque el clic ahora aterriza en el `<svg>` hijo, no en el botón.
- Tipografía monoespaciada reemplazada por la pila de San Francisco (`-apple-system`/`system-ui`) — más legible, mismo estilo Jarvis.
- **Reusabilidad de Capacidades/Especialistas garantizada con un test** (`tests/test_architecture_boundaries.py`): nunca importan `snarf.core`, `snarf.runtime` ni `app.py` — ya era cierto por diseño, ahora queda fijo para que no se erosione.
- **Primera optimización real de costo de tokens:** el system prompt de Snarf (idéntico en cada llamada, en cualquier conversación) ahora usa prompt caching de Anthropic. La interpretación de Gmail pasa a usar `claude-haiku-4-5` (más barato) en vez del modelo principal de Snarf — es una tarea de categorización acotada, no conversación con identidad.
- 3 tests nuevos (93/93 en total).
- Ver ADR 0026.

## [2026-07-27] Panel superior movible y transparencia de paneles/burbujas

- El panel de arriba (Conversaciones) ya no está fijo — se fusionó con la columna derecha en un solo grupo reordenable: el primer widget del orden ocupa la franja superior, el resto la columna derecha. La columna izquierda (conversaciones + estado del sistema) sigue fija, a pedido explícito del fundador.
- `makeReorderable` generalizada para reordenar entre varios contenedores a la vez, no solo dentro de uno.
- Paneles y burbujas de chat pasan de un tinte plano a un degradé radial (centro más visible, bordes más oscuros) con vidrio esmerilado, coherente con el resto de la estética Jarvis — confirmado que la línea de escaneo de fondo sigue pasando por detrás.
- Verificado con Playwright (arrastre de mouse real, promoviendo un widget a la franja superior) y con captura de pantalla.
- Ver ADR 0027.

## [2026-07-27] Textura de paneles, tipografía y modos de entrada simplificados a dos

- Degradé más marcado (centro claro, bordes oscuros) con resplandor cian interior en paneles y burbujas de chat; títulos de widget menos pesados visualmente (peso 400 en vez de 500, tamaño levemente mayor).
- Selector de modo de entrada simplificado de tres modos a dos: **toque** (orbe, ahora más chico, ~133px en vez de 180px) y **teclado** (ahora el modo por defecto en desktop y en mobile). Se eliminó "mantener presionado".
- El modo teclado tiene un botón de micrófono embebido junto al campo de texto: graba, transcribe y coloca el texto para revisar antes de enviar, sin una vista previa separada. Botón de enviar rediseñado como flecha hacia arriba.
- Pospuesto explícitamente a una ronda dedicada: ancho variable por widget, zona izquierda flexible, y posición reubicable del módulo de chat — es, en los hechos, un editor de layout tipo grilla genérico, no un ajuste de CSS.
- Verificado con Playwright, incluyendo el flujo completo de grabar-transcribir-completar el campo con un dispositivo de audio falso y una llamada real a la API de transcripción.
- Ver adenda de ADR 0027.

## [2026-07-27] Vidrio esmerilado real en paneles y burbujas (aún sin commitear, a pedido del fundador)

- El primer ajuste de degradé subía la opacidad en vez de bajarla — corregido: menos opacidad en todo el degradé, `backdrop-filter` de 15px + saturación, para que la línea de escaneo y las partículas de fondo se vean difuminadas *a través* de paneles y burbujas, en vez de tapadas.
- Verificado con capturas de pantalla reales.
- Ajuste posterior, misma jornada: el fundador pidió aún más transparencia y *menos* difuminado (para disfrutar la línea con nitidez, no perderla en el blur) — `backdrop-filter` bajado de 15px a 4px y opacidad del degradé reducida más todavía en `.dash-widget`, `.msg.user` y `.msg.snarf`. Verificado con Playwright contra el servidor real.
- Suite completa: 93/93 sin cambios (CSS puro).
- Sin ADR de cierre todavía: el fundador pidió frenar el commit/push hasta terminar de ajustar el look visual.

## [2026-07-28] Vectorización de Google Drive y panel de costo de API en tiempo real

- Nuevo panel "Costo de API" en el dashboard (`snarf/telemetry/`): estima en tiempo real el gasto de Anthropic, ElevenLabs y Voyage a partir de cada llamada real (nunca inventado), con desglose por proveedor y aclaración explícita de que es una estimación según tarifa pública, no el saldo real de cada cuenta.
- Construida la extracción de contenido por tipo de archivo que faltaba desde ADR 0013/0014 (PDF, imagen, audio, video) y el pipeline completo de vectorización de Google Drive (`snarf/knowledge/`): extracción → chunking → embeddings (Voyage AI, `voyage-4-lite`) → `chromadb` local, con progreso reanudable por archivo.
- Cinco herramientas nuevas para Snarf: `drive_index_scan` (solo lectura, cuenta archivos/tamaño por tipo sin gastar nada), `drive_index_start`/`drive_index_status`/`drive_index_stop` (indexación en segundo plano, siempre disparada a pedido explícito, nunca automática) y `drive_search_knowledge` (búsqueda semántica sobre lo ya indexado).
- Evaluada y pospuesta a propósito una infraestructura multi-usuario para esto: no existe todavía un segundo usuario real: los datos quedaron namespaced por `user_id` desde el día uno para que agregarlo, cuando corresponda, sea pasar otro `user_id`, no rediseñar el pipeline.
- `drive_index_scan` corrido en vivo contra el Drive real del fundador (37.479 archivos indexables + 5.251 carpetas, ~820GB): el mayor consumidor de espacio es video (1.824 archivos, ~576GB), seguido de una categoría "other" sin extractor hoy (9.854 archivos, ~230GB) — PDF, imagen, audio y texto/Google Docs juntos son una fracción menor del total (~20GB).
- Nuevo `drive_index_catalog_unsupported` + alias `query='free_tier'`, y corrido en vivo también: de los ~230GB de "other", ~212GB son software (instaladores ZIP, artefactos de un proyecto Unity) sin valor de conocimiento personal; el resto son robots/indicadores de trading reales en `.zip`/`.rar`/`.dll` (identificables por nombre, no extraíbles como texto) y, sin buscarlo, 95 `.docx` + 41 `.epub` + otros documentos personales genuinamente valiosos que hoy no tienen extractor — candidatos claros para una próxima ronda.
- Corregido un bug real encontrado en el camino: un archivo marcado `error` en el manifest (por ejemplo, por falta de `VOYAGE_API_KEY`) quedaba descartado para siempre en vez de reintentarse en la próxima corrida.
- 67 tests nuevos (160/160 en total). Encontrado y corregido durante la construcción: un fallo real en el extractor (no solo un tipo no soportado) tiraba abajo el thread de indexación entero en silencio, sin registrar nada — cubierto con test de regresión.
- Ver ADR 0028.

## [2026-07-28] Extractores de Office, registro real de actividad, y visión de negocio registrada

- Nuevos `DocxExtractor`/`PptxExtractor`/`XlsxExtractor` (`.docx`/`.pptx`/`.xlsx`) sumados al tier gratuito de vectorización de Drive — los documentos personales reales que aparecieron en el catálogo de "other" (planes de negocio, etc.) ahora sí tienen extractor, sin costo de API.
- Nuevo registro real de actividad del Orchestrator (`snarf/telemetry/activity_log.py`, `GET /dashboard/activity`): qué herramienta se ejecuta, cuándo, y con qué resultado — la base de datos real que pedía el fundador antes de construir cualquier visualización tipo "cerebro de Snarf". Sin widget visual todavía, a propósito.
- El fundador planteó una visión mucho más amplia (dashboard de costos/ingresos/mercados/campañas de negocio, reemplazo de sus chatbots externos con migración de "Proyectos" de ChatGPT, arquitectura de Especialistas por dominio, creación/exportación de documentos, onboarding). Se registró completa en `MASTER_MAP.md` con el orden de ejecución acordado, sin construir las piezas grandes todavía — varias necesitan una fuente de datos real (costos, ingresos, mercado) que hoy no existe, y este proyecto no muestra datos inventados.
- 23 tests nuevos (183/183 en total).
- Ver ADR 0029.

## [2026-07-28] Snarf crea, recibe y vectoriza archivos reales; corregido rate limit de Voyage; piloto de video verificado

- **Vectorización de Drive corriendo de verdad**: `VOYAGE_API_KEY` configurada, con método de pago agregado por el fundador para destrabar el límite de 3 requests/minuto de las cuentas nuevas de Voyage (bug real corregido: `VoyageEmbeddings` no pasaba `max_retries` al SDK, así que la mayoría de los embeddings fallaban directo en vez de esperar y reintentar). También se corrigió el alcance real de `query='free_tier'`: `contains 'text/'` traía miles de archivos de código fuente/configuración de un backup de Python/Unity que Drive clasifica como texto — acotado a `text/plain` exacto.
- **Piloto de video verificado en vivo**: 19 archivos reales (carpeta "Grabaciones", 10.4GB) — transcripción + vectorización, 0 errores, **$2.03 de costo real medido** (no estimado). Extrapolación a los ~576GB de video totales: ~$40 y ~18 horas, basada en la proporción real GB→minutos del piloto, no en una suposición a ciegas.
- **Snarf puede crear archivos reales**: `DocumentBuilder` (Markdown/PDF/PPTX/XLSX, todo local) + `GoogleDrive.upload_file` (con conversión real a Google Doc/Sheet/Slide nativo al subir, sin necesitar la API de Google Docs aparte) + `DocumentPublisher`. Tres herramientas nuevas: `drive_create_document`, `drive_create_spreadsheet`, `drive_create_presentation` — devuelven el link real de Drive y quedan indexados al instante.
- **Snarf puede recibir archivos**: nuevo `POST /files/upload` + botón de adjuntar en la interfaz. Todo lo subido se guarda en la carpeta `Snarf - Archivos` y se indexa de inmediato; si es una imagen, la descripción que genera la visión se devuelve directo al chat.
- Reorganizado el roadmap en `MASTER_MAP.md` a pedido del fundador: **Fundación técnica** (vectorización de Drive, archivos, migración a un VPS Linux, segundo usuario de prueba) tiene que cerrarse antes de sumar **Capacidades** nuevas (mercado, ChatGPT, cerebro Jarvis, negocio). La migración a VPS pasó de "buena idea" a "primero de lo que sigue": el fundador reportó que la interfaz se sentía lenta incluso antes de la indexación, accediendo desde el celular a través de un túnel hacia la Mac — la ruta de red completa es la causa raíz más probable, no solo la carga del indexado.
- 33 tests nuevos (216/216 en total). Verificado en vivo contra el Drive real: un Markdown, un Google Doc (por conversión real) y un Excel, los tres creados, indexados, y encontrados con una búsqueda semántica real inmediatamente después.
- **Adenda, misma jornada**: el fundador preguntó cómo evitar que los archivos que Snarf crea queden duplicados (el real en Drive + una copia local desperdiciando espacio en el futuro VPS). Aclarado y verificado: nunca hubo duplicación — lo local siempre fue el índice vectorial (texto+embeddings), nunca el archivo.
- **Segunda adenda, misma jornada**: el fundador pidió una distinción más fina — además de Drive, poder mandar un archivo directo a su propio dispositivo (con el diálogo nativo de "Guardar como" de su sistema operativo), y reservarse solo para él la opción de usar el disco del propio servidor como carpeta de trabajo. `destination` pasa a tener tres valores: `drive`, `device` (nuevo endpoint `GET /files/local/<user_id>/<archivo>`, con su link de descarga real) y `server` (mismo mecanismo, sin link, exclusivo del fundador — `allow_server_storage` gateado en código y en el prompt). 19 tests nuevos (235/235 en total). Verificado en vivo: `device` y `server` ambos crean el archivo real en disco, indexado, sin ninguna llamada a Drive; `device` con su `download_url` real y funcional.
- Ver ADR 0030.

## [2026-07-29] Indexación desacoplada de la sesión, runbook de VPS, y cookie de sesión endurecida

- El proceso de vectorización del tier gratuito se relanzó como proceso desacoplado de verdad (`nohup` + `disown`, reparentado a `init`) — antes moría si se cerraba la sesión de Claude Code; ahora sobrevive, incluida la propia Mac quedando sin esa terminal abierta.
- Nuevo `VPS_MIGRATION.md`: runbook completo (sin ejecutar) para el ítem 4 de la Fundación técnica. Recomienda seguir usando Tailscale desde el VPS en vez de montar un dominio público — mismo mecanismo ya probado (ADR 0008), que además resulta ser el "túnel" que el fundador no identificaba al describir la lentitud de la interfaz.
- Corregido un detalle de seguridad real encontrado al preparar el runbook: la cookie de sesión no tenía `secure=True`. Agregado — defensa en profundidad, no depender de que Tailscale sea la única capa de HTTPS. Los `TestClient` de los tests pasaron a `base_url="https://testserver"` para poder seguir probando el login con la cookie marcada `Secure`.
- 1 test nuevo (236/236 en total).

## [2026-07-29] Cerebro de Snarf — visualización tipo Jarvis del Orchestrator

- El fundador reordenó el plan del día: antes de migrar a VPS o seguir indexando Drive, construir la visualización "cerebro de Snarf" — el prerrequisito (registro real de actividad, ADR 0029) ya estaba listo y es lo que más necesita ahora para entender el estado del sistema.
- Relevadas todas las fuentes de datos reales antes de diseñar: `activity_log.jsonl` (el prerrequisito nombrado) estaba en la práctica vacío (cero eventos desde que se instrumentó); la fuente rica en datos reales hoy es `usage_log.jsonl` (4.126 líneas, de la corrida de indexación con Voyage) y el manifiesto de indexación ya persistido (4.618 archivos). El diseño combina las tres fuentes.
- Nuevo `snarf/telemetry/brain.py`: mapea las 35 herramientas reales del Orchestrator y los 3 vendors reales (Anthropic/ElevenLabs/Voyage) a 9 nodos de Capacidad + el nodo central Orchestrator, con un test de regresión que impide que una herramienta nueva quede sin mapear en silencio. Nuevo endpoint `GET /dashboard/brain`.
- Nuevo widget "Cerebro" en el dashboard: mini-grafo con tamaño de nodo real (nunca vacío), que se expande a pantalla completa con el grafo grande + un feed de actividad en vivo. Pulsos de luz animados (SVG `animateMotion`) viajan del centro a cada nodo en cada evento real, con el mismo patrón de polling 100% impulsado por el navegador que el digest de Gmail (solo mientras la pantalla está abierta y visible).
- 17 tests nuevos (253/253 en total). Verificado en vivo con Playwright (login real, desktop y mobile, sin errores de consola ni requests fallidos) — capturas confirman nodos de tamaño real distinto y el feed mostrando actividad real.
- Ver ADR 0031.
- **Bug real encontrado al verificar en vivo, corregido en el momento**: `secrets.compare_digest` no acepta `str` con caracteres no-ASCII (tildes, ñ) — el login del fundador tiraba un 500 en vez de comparar la contraseña. Corregido codificando ambos lados a bytes antes de comparar (1 test nuevo, 254/254).

## [2026-07-29] PDF con fuentes Type3 + fallback de OCR; cerebro de Snarf con dos capas y latido diferenciado

- **Bug real reportado por el fundador**: ciertos PDFs (exportados desde apps móviles/navegadores) usan fuentes Type3 embebidas — el texto es seleccionable/copiable en cualquier visor real, pero `PdfExtractor` (basado en `pypdf`) devolvía texto vacío o basura. Reescrito sobre PyMuPDF (`fitz`), que resuelve el CMap/ToUnicode de Type3 de forma nativa. Decisión de licencia explícita con el fundador: PyMuPDF es AGPL-v3 (elegida sobre la alternativa MIT `pdfplumber`, con Type3 menos confiable) — sin problema para uso interno, a revisar si Snarf se ofrece como servicio a terceros a futuro.
- Nuevo fallback de OCR con Tesseract (`spa+eng`, paquete de idioma español instalado en el entorno del fundador) para PDFs sin ninguna capa de texto real — rasterizado con la misma librería, sin dependencia extra. Si ninguna estrategia encuentra texto usable, ahora se declara explícito (`skipped_reason`) en vez de indexar contenido vacío en silencio.
- **Cerebro de Snarf, con capturas de referencia de Jarvis (Iron Man) como guía**: pasa de un anillo plano de 9 nodos a dos anillos — Especialistas Cognitivos (interno, hoy solo el digest de Gmail) y Capacidades (externo) — reflejando la arquitectura real de tres capas del proyecto (COGNITION.md, ADR 0003) en vez de una lista arbitraria. El nodo "voz" se separó en `stt`/`tts` (dato que `usage_log` ya distinguía, antes escondido).
- Cada nodo late distinto según su estado real: latido rápido y brillante si tuvo actividad en los últimos 60 segundos, latido lento de espera si no — nunca apagado del todo, nunca inventando actividad que no ocurrió. Un edge activo suma además un flujo continuo de luz (CSS puro) sobre el pulso puntual por evento que ya existía.
- 15 tests nuevos (264/264 en total). Verificado en vivo con Playwright: los 12 nodos renderizan sin recortes de etiqueta (el viewBox del SVG se ajustó de 400×400 a 500×500 para el nuevo layout de dos anillos), en desktop y mobile, sin errores de consola; el estado activo/idle confirmado inyectando un snapshot controlado.
- Ver ADR 0032.

## [2026-07-29] Cerebro de Snarf: anillo de entrada, paleta real de marca, nodos fantasma

- Con capturas de referencia del cerebro de Jarvis en *Avengers: Age of Ultron*, tercera vuelta sobre el cerebro: nodos de entrada (texto/voz/archivo), múltiples niveles de profundidad, y una paleta de colores saturados estilo Iron Man/neón. Límite puesto explícitamente antes de construir: se distingue por tipo real de archivo (imagen/audio/video/documento, `categorize_mime`), no por género semántico (canción vs. podcast) — eso el sistema no lo sabe, y mostrarlo sería inventar un dato.
- **Paleta no inventada**: se buscó en el Drive ya indexado del fundador y se encontró el documento real `PALETA DE COLORES JERE MASIH TRADER` — su paleta de marca de trading, con los hex exactos que pidió (Magenta, Aqua, Violeta, Verde, sobre negro/violeta oscuro). Usada tal cual, sumando rojo/blanco/gris/amarillo para los estados que faltaban.
- Nuevo `snarf/telemetry/input_log.py`: primera instrumentación real de los tres puntos de entrada a Snarf (`/send`, `/transcribe`, `/files/upload`) — ninguno emitía ningún evento hasta ahora. Nuevo anillo "Entrada" en el cerebro (el más interno), con `input_text`/`input_voice`/`input_file`.
- Nuevo estado "fantasma" (gris, sin animación) para nodos que nunca tuvieron actividad real — distinto de "en espera" (sí tiene historia, no reciente).
- **Bug real encontrado y corregido en la propia verificación en vivo**: la regla base de nodos/pulsos traía un color por defecto que, por orden de declaración en la hoja de estilos, pisaba siempre a la clase de color real de cada nodo — todo se veía aqua sin importar el tier. Corregido quitando ese default; cada nodo real ya lleva su propia clase de color explícita.
- 19 tests nuevos (273/273 en total). Verificado en vivo con Playwright, incluida una inyección de snapshot con actividad en todos los tiers para confirmar la paleta completa funcionando junta (magenta, violeta, blanco, aqua).
- Ver ADR 0033.

## [2026-07-29] `drive_read_file` extrae de verdad; el cerebro gana partículas, resplandor y cámara

- **Bug real reportado por el fundador**: probó el fix de PDF con un archivo real (`Peso_16-07-2026.pdf`, composición corporal con fuentes Type3) y Snarf seguía devolviendo bytes crudos. Causa real: `drive_read_file` (la herramienta de lectura en el chat) nunca pasaba por `ContentExtractor`/`PdfExtractor` — llamaba directo a `GoogleDrive.read_file_text()`, que decodifica cualquier binario como UTF-8 a lo bruto. El fix de ADR 0032 solo tocaba el camino de indexación, no este.
- `Orchestrator._read_drive_file` ahora reusa `ContentExtractor` — un solo camino de verdad para extraer contenido de Drive, con OCR automático para PDF escaneado, visión para imagen, transcripción para audio/video. **Verificado en vivo**: el PDF real del fundador ahora extrae el análisis de composición corporal completo y legible.
- **Instancia real del fundador (puerto 8002) reiniciada**: corría desde el lunes con el código viejo en memoria — Python no recarga solo. Relanzada con `nohup`/`disown` (mismo patrón que el indexado), confirmada contra el mismo entorno virtual.
- **Cerebro de Snarf, cuarta vuelta**: nueva capa `<canvas>` de partículas — ambiente con resplandor real (blending aditivo, no un blur simulado), estallido de partículas por cada evento real (coloreado según el nodo o rojo si fue error), y una cámara que hace zoom hacia el nodo que se activa (~1.55x, ~2.4s) y vuelve sola a la vista general. SVG y canvas se mueven siempre juntos (un solo transform compartido) para que el zoom nunca desalinee las dos capas. Primera vez que el proyecto usa canvas — todo lo anterior sigue siendo SVG/CSS.
- **`/send` degrada con gracia ante un fallo real del LLM**: encontrado al cerrar la jornada — la cuenta de la API de Anthropic del fundador (separada de su suscripción de Claude Pro) se quedó sin crédito, y `/send` tiraba un HTTP 500 crudo en vez de un mensaje entendible. `Orchestrator.handle()` ahora envuelve la llamada al LLM en `try/except`, mismo criterio que ya usaba `/transcribe` para fallos de STT.
- 3 tests nuevos (276/276 en total). Verificado en vivo con Playwright: partículas con resplandor real en desktop y mobile, cámara confirmada en zoom real inyectando un evento controlado, loop de animación confirmado apagado tras cerrar (sin fugas). Instancia real reiniciada dos veces en la jornada, la segunda con este último fix.
- Ver ADR 0034.

## [2026-07-29] Grilla de dashboard unificada y redimensionable, modo enfoque, tres bugs de UI

- **Tres bugs reales corregidos**: texto redundante en modo teclado ("escribí tu mensaje", cuando el placeholder ya decía lo mismo); la app abría el teclado nativo en mobile al arrancar sin que el usuario tocara nada (`textInput.focus()` disparándose solo); y "escuchar" a veces no generaba audio — en realidad sí lo generaba, pero `sharedAudio.play()` fallaba en silencio (política de autoplay, o una carga interrumpida por otro click) y el reproductor flotante igual se mostraba como si estuviera sonando. Los tres corregidos, el último con el error ahora visible en vez de tragado.
- **Grilla de dashboard unificada (solo desktop, ≥900px)**: reemplaza las tres zonas fijas de antes por una sola grilla de 12 columnas donde todo bloque —incluidos el historial de conversaciones y el chat con Snarf, antes fijos y fuera del sistema de widgets— se puede arrastrar para reposicionar y redimensionar (ancho y alto) libremente, con la posición/tamaño guardados por usuario. Reordenamiento actualizado de comparar solo altura a comparar altura y ancho (necesario con bloques de tamaño variable). Nuevo mecanismo de resize, mismo estilo que el de reordenar ya existente.
- **Bug real corregido de paso**: `_normalize()` de las preferencias del dashboard reconstruía `widget_options` a mano, hardcodeado solo a la clave de Gmail — cualquier otro dato ahí (por ejemplo, el tamaño de otro widget) se perdía en silencio al guardar. Generalizado a todos los widgets, con validación real.
- **Modo enfoque**: el chat se expande a pantalla completa con la misma barra lateral que ya existía para el menú hamburguesa de mobile (historial, nueva conversación, usuario/configuración) — reusada, no duplicada.
- Desktop arranca siempre en el Dashboard (antes: Chat), con la distribución guardada la última vez.
- **"Proyectos" registrado, no construido**: el fundador pidió, en la misma ronda, que Snarf tenga su propia versión de "Proyectos" al estilo Claude/ChatGPT (prompt de proyecto, archivos organizados en Drive con vectorizado, propuesta automática de carpetas). Es una Capacidad nueva entera — queda registrada en `MASTER_MAP.md`, con su propio ciclo de diseño pendiente, no mezclada con este cambio.
- 10 tests nuevos (285/285 en total). Verificado en vivo con Playwright, incluido contra el archivo real de preferencias del fundador (de antes de este cambio): migró sin intervención manual, con las Capacidades que ya tenía ocultas manualmente siguiendo ocultas. Resize y modo enfoque confirmados con interacciones reales (arrastrar y recargar; enviar un mensaje real y recibir respuesta real dentro del modo enfoque). Mobile confirmado sin ningún cambio.
- Ver ADR 0035.

## [2026-07-29] Análisis de eficiencia de tokens: cacheo del historial de conversación, TTL de 1h, CLAUDE.md

- El fundador pasó tres transcripciones sobre metodología de ahorro de tokens en Claude/Claude Code y pidió analizar la eficiencia real del proyecto. Confirmado contra código y datos reales (`data/usage_log.jsonl`, 53 llamadas del día): el cacheo de system+tools ya funcionaba (`cache_read_tokens` fijo en 14.895 en casi toda llamada real), pero el array de `messages` no tenía ningún punto de cacheo — se reprocesaba entero, a tarifa completa, en cada llamada y en cada ronda del loop de herramientas.
- `AnthropicLLM.generate()` gana un segundo punto de cacheo: el último mensaje de cada llamada (y de cada ronda del loop de herramientas) se marca con `cache_control`, sin mutar nunca la lista original que pasa el llamador. Ambos puntos de cacheo (system+tools, y este nuevo) pasan de TTL default de 5 minutos a 1 hora explícito — Snarf llama a la API directa, no a la suscripción de Claude, así que corría bajo el TTL corto pese a que el patrón real de uso del fundador (entradas y salidas espaciadas, digest de Gmail cada 5 min) se beneficia del TTL largo.
- Nuevo `CLAUDE.md`: índice liviano para sesiones de Claude Code futuras (apunta a `MASTER_MAP.md` y las convenciones ya establecidas, no las repite) — aplicando a las propias sesiones de trabajo el mismo hábito que recomiendan las transcripciones.
- 3 tests nuevos (288/288 en total).
- Ver ADR 0036.

## [2026-07-29] Orden default del dashboard, legibilidad a 1920×1080, y malla volumétrica del cerebro

- **Orden default del dashboard de escritorio**, pedido concreto del fundador: historial a la izquierda (alto completo), cerebro arriba centrado, sistema/costo al lado del cerebro, chat debajo, y conversaciones/memoria/Drive/Gmail/Calendar/YouTube formando una columna a la derecha que sigue bajando. Logrado reordenando `WIDGET_IDS` y ajustando `DEFAULT_SPANS` (backend + espejo en frontend) — el auto-flow disperso de la grilla (ADR 0035) hace el resto. El archivo real de preferencias del fundador se regeneró directamente al nuevo orden (cambiar el default de Python no alcanza para una preferencia ya guardada), preservando su elección manual de ocultar YouTube.
- **Legibilidad a 1920×1080**: `rem` es siempre relativo al `<html>` raíz, no al ancestro más cercano — el tamaño de fuente base del modo escritorio sube de 16px (default del navegador, sin ajustar hasta ahora) a 18px dentro del mismo breakpoint de ancho ya existente, sin tocar cada clase suelta. Mobile no se toca.
- **Cerebro de Snarf, quinta vuelta, con capturas reales de la escena de creación de Ultron** (*Avengers: Age of Ultron*): nueva capa de malla de filamentos sobre el canvas de partículas ya existente — satélites alrededor de cada nodo real, coloreados con el color real de ese nodo/tier, enlazados con sus vecinos más cercanos (incluso entre nodos distintos, para que lea como una masa conectada y no triángulos sueltos). Nueva aura volumétrica (gradiente radial con respiración lenta) y viñeta de fondo, más brillo en el nodo central y el latido activo. Ninguna lógica real de datos se tocó — es pura atmósfera, igual que las partículas ambiente ya existentes. Se aclaró explícitamente el límite de ADR 0006 (no reproducir el esquema de color literal de la franquicia): se toma el estilo, no los colores azul/dorado — la paleta real Jere Masih Trader se mantiene.
- De paso, el fundador preguntó por qué Snarf no usa MCP y pidió una política Skills-vs-MCP para este repo — respondido y registrado en `CLAUDE.md` (es una convención de cómo trabajamos con Claude Code en este proyecto, no una decisión de arquitectura de Snarf-producto).
- 288/288 tests (sin tests nuevos — cambio mayormente visual/frontend). Verificado en vivo con Playwright a 1920×1080 (orden de bloques, tamaño de fuente, cero errores de consola) y en mobile (390×844, sin cambios, tamaño de fuente vuelve a 16px). Cerebro verificado a pantalla completa en ambos anchos, loop de animación confirmado apagado al cerrar.
- Ver ADR 0037.

## [2026-07-29] Mensaje honesto cuando el STT falla de verdad (no cuando no se escuchó nada)

- **Bug real reportado por el fundador**: el botón de micrófono "no transcribía". Causa real, encontrada en el log del servidor real: la cuenta de ElevenLabs se quedó sin crédito (`quota_exceeded`, 0 créditos restantes) — el STT (Scribe v1) fallaba en cada intento. `/transcribe` ya degradaba con gracia (nunca un error crudo), pero devolvía siempre `{"transcript": ""}`, indistinguible de un silencio genuino — la interfaz le decía "no se escuchó nada, probá de nuevo" aunque el micrófono hubiera funcionado perfecto y reintentar no fuera a cambiar nada.
- `/transcribe` ahora suma un campo `error` solo cuando el STT en sí lanzó una excepción (nunca en los casos de audio corto o sin credenciales, que siguen siendo `{"transcript": ""}` sin más). El frontend (los dos flujos de grabación, modo tap y modo teclado) muestra ese mensaje real en vez del genérico cuando está presente.
- Aclarado aparte, a pedido del fundador: cambiar la *voz* de ElevenLabs no ahorra crédito (la tarifa de TTS depende del modelo — `eleven_multilingual_v2` hoy — no de qué voz premade se elige); y el STT (`scribe_v1`) no tiene tiers de calidad para elegir, así que no hay ningún ajuste de configuración que resuelva una cuota agotada — solo cargar crédito o esperar la renovación del plan.
- 1 test nuevo (289/289 en total). Verificado en vivo con Playwright interceptando `/transcribe` para simular el fallo real sin gastar crédito.

## [2026-07-29] TTS pasa a eleven_turbo_v2_5 (mismo costo que Flash, mejor calidad)

- El fundador preguntó cómo abaratar ElevenLabs. Confirmado contra la documentación oficial (no una suposición): `eleven_multilingual_v2` (el modelo que usábamos) cuesta 1 crédito/carácter; `eleven_turbo_v2_5` y `eleven_flash_v2_5` cuestan la mitad (0.5 créditos/carácter) — mismo precio entre sí, Turbo con mejor calidad/profundidad emocional que Flash a cambio de ~200ms más de latencia (250-300ms vs ~75ms), diferencia irrelevante para Snarf porque la síntesis ocurre después de que el LLM ya generó la respuesta completa, no en streaming en vivo.
- `ElevenLabsTTS.DEFAULT_MODEL` pasa de `eleven_multilingual_v2` a `eleven_turbo_v2_5` — la mitad de costo por el mismo texto, sin resignar calidad frente a la alternativa igual de barata (Flash).

## [2026-07-29] Cerebro: sin recorte de etiquetas al hacer zoom, menos aspecto de diagrama

- **Bug real reportado por el fundador**: al hacer zoom hacia un nodo (o "en algunas ocasiones"), el texto de otros nodos desaparecía. Causa real, confirmada con un barrido automatizado (no solo mirando capturas): el zoom de cámara escalaba el grafo entero con el origen puesto exactamente en el nodo activo a 1.55x, empujando el lado opuesto del grafo (sobre todo el par diametralmente opuesto Memoria/Calendar) fuera del área visible recortada. Corregido bajando el zoom a 1.14x y mezclando el origen de escala solo 32% hacia el nodo activo (antes 100%) — verificado con Playwright sobre los 15 nodos reales: cero etiquetas recortadas en ningún foco (antes, 7 casos reales).
- **Menos "diagrama de red", más "entidad de luz"**: el fundador señaló que los círculos y las líneas rectas centro-nodo (un literal asterisco) seguían dominando sobre la malla orgánica nueva, con aspecto "rústico". Bajada la opacidad/grosor de esas líneas rectas (siguen existiendo, las necesita el pulso puntual) y sumado un resplandor permanente a los nodos — se sienten orbes de luz fundidos con la malla, no círculos de diagrama técnico.
- 289/289 tests (cambio puramente visual). Ver ADR 0038.

## [2026-07-29] CHARACTER v0.2: ingenio seco, responsabilidad propia, registro y cercanía

- El fundador pasó un prompt de personalidad pensado como imitación directa de J.A.R.V.I.S. (nombrando a Marvel/Iron Man, con "Señor Masih" como eco literal del personaje). Señalado antes de tocar nada: `CHARACTER.md` v0.1 ya tenía, escrita dos veces, la regla contraria explícita — tomar los principios de trato, nunca imitar al personaje por nombre o forma superficial (mismo criterio de ADR 0006 para el cerebro visual). El fundador confirmó mantener esa regla y adoptar solo el espíritu del prompt.
- `CHARACTER.md` pasa a v0.2: nuevo rasgo **ingenio seco** (humor sutil al servicio de un propósito, nunca gratuito); nuevo rasgo **responsabilidad propia** (reconocer un error propio directo, sin sobreactuar); **pensamiento crítico** ampliado (ejecutar con el mismo profesionalismo aunque el fundador no siga una objeción ya señalada); nueva sección **Registro y cercanía** (predominantemente por nombre de pila, más formal ante decisiones críticas o de alto impacto — la formalidad vive en la estructura de la respuesta, nunca en un honorífico; la cercanía puede profundizarse con el historial compartido).
- Deliberadamente no incorporados los marcos de tipificación del prompt original (MBTI/Eneagrama) — etiquetas decorativas para rasgos ya cubiertos de forma conductual, inconsistentes con la voz ya establecida del documento.
- 289/289 tests (cambio de documento, no de código — aplica al reiniciar el servidor real, `load_identity()` lee `CHARACTER.md` de disco al construir el Orchestrator).
- Ver ADR 0039.

## [2026-07-29] Cerebro sin ningún recorte real, reproductor con pausa y siempre visible

- **Bug real, persistente**: el fundador seguía viendo la primera letra de algunas etiquetas del cerebro (Memoria, Conocimiento, Documentos, Orchestrator, Voz, Texto) cortada "en algunos casos". El fix de ADR 0038 (zoom 1.14x) reducía el recorte pero no lo eliminaba del todo — verificado con el mismo barrido automatizado sobre los 15 nodos reales, esta vez exigiendo cero recorte (no solo <50%): quedaban ~15-20 casos de recorte chico, concentrados en las etiquetas más largas de los nodos cercanos al eje horizontal del anillo externo. Zoom bajado a 1.07x, mezcla de cámara a 18% — verificado: cero recorte, ni parcial, en ningún foco.
- **Bug real, causa encontrada con Playwright**: el reproductor de audio flotante tenía `z-index: 9`, por debajo del panel de configuración, el cerebro a pantalla completa y el modo enfoque (10 a 15) — quedaba literalmente tapado e inaccesible detrás de cualquiera de esos paneles mientras el audio sonaba. Subido a `z-index: 20` (por encima de todo lo demás). Confirmado con `elementFromPoint` que el botón ahora sí recibe el click estando el modo enfoque abierto encima.
- **Pausa/reanudar**: nuevo botón en el reproductor, sincronizado con los eventos reales `play`/`pause` del audio (no solo con su propio click) — la etiqueta también pasa a decir "en pausa" en vez de seguir diciendo "reproduciendo" cuando está pausado.
- 289/289 tests. Ver ADR 0040.

## [2026-07-29] Gmail resiliente ante fallos transitorios, uso real por API, y dashboard con tamaños más justos

- **Bug real, causa encontrada inspeccionando el server en vivo**: el widget de Gmail devolvía `[SSL] record layer failure` — la conexión `googleapiclient` cacheada como singleton en `GoogleDrive`/`GoogleGmail`/`GoogleCalendar`/`GoogleYouTube` puede quedar rota en un proceso de larga vida. Nuevo decorador `retry_once_with_fresh_client`: reintenta una sola vez con el cliente reconstruido ante cualquier fallo, sin ocultar un fallo real y persistente. Aplicado solo a lecturas idempotentes, nunca a `upload_file`/`send_message`/mutaciones (riesgo de duplicar el efecto en un reintento).
- Fechas y enlaces reales en Gmail: la lista de mensajes ya tenía el dato (`date`) pero no se mostraba; el digest interpretado por el LLM ahora viene acompañado de una referencia estructurada real (id/asunto/de/fecha) por mensaje, en vez de depender de que la prosa libre del LLM mencione fechas o links (que sería inventar datos).
- Nuevo widget "Uso real de APIs": consumo trackeado localmente (llamadas, tokens, caracteres, segundos) por Anthropic/ElevenLabs/Voyage, más el cupo real de la cuenta de ElevenLabs (`GET /v1/user/subscription`, en vivo) — el panel de costo existente es una estimación en dólares, nunca fue un saldo real, por eso cargar crédito en ElevenLabs no lo movía.
- Tamaños de widgets del dashboard recalibrados usando como evidencia los tamaños que el propio fundador ya había elegido a mano en su layout guardado (no una preferencia estética a ciegas) — solo cambia el default para instalaciones nuevas, el layout ya guardado no se tocó.
- `#textInput` pasa de `<input>` de una línea a un `<textarea>` que crece hasta ~6 líneas visibles antes de scrollear internamente; `Shift+Enter` inserta salto de línea real, `Enter` solo sigue enviando. Mismo tratamiento en el cuadro de revisión de transcripción por voz.
- 305/305 tests. Ver ADR 0041.

## [2026-07-29] Respaldo automático de `data/`

- **Incidente real durante esta sesión**: al verificar en vivo el widget de uso, Claude Code escribió datos de prueba en el `data/usage_log.jsonl` real por error, y al intentar revertirlo con una sintaxis de `head` no soportada en macOS terminó sobreescribiendo el archivo real completo con uno vacío — perdiendo sin posibilidad de recuperación las 4304 líneas de historial real de uso acumulado. No estaba en git (gitignored a propósito), no había snapshot ni backup de ningún tipo.
- Nuevo `snarf/runtime/data_backup.py`: respalda automáticamente memoria episódica, logs de actividad/uso/entrada, preferencias del dashboard, caché del digest de Gmail y archivos locales (no el índice de Drive, regenerable desde la fuente real) a `data_backups/`, con los últimos 14 snapshots. Se dispara al arrancar el server y cada 6 horas mientras corre.
- 305/305 tests. Ver ADR 0042.

## [2026-07-29] Desktop usable de verdad: reintento triple, widgets que no se cortan, Gmail reordenado

- **Bug real, confirmado en vivo**: el reintento único de ADR 0041 no alcanzaba — el mismo `[SSL] record layer failure` podía pegarle también al reintento (falla de red genuinamente intermitente). `retry_once_with_fresh_client` pasa a `retry_with_fresh_client`, con 3 intentos en total y una pausa corta entre cada uno.
- **Bug real de CSS**: al achicar un widget arrastrando su esquina, el título y subtítulo podían recortarse junto con el contenido. Corregido con `flex-shrink: 0` — ahora solo el cuerpo del widget se comprime/scrollea, título y subtítulo quedan siempre completos.
- Gmail: la interpretación de la bandeja ahora va primero, la lista de mensajes (con su selector de cantidad) queda debajo — antes era al revés.
- **Bug real preexistente, no de esta sesión**: en modo desktop, el botón que abre el menú de usuario (configuración del dashboard, cerrar sesión) estaba oculto sin ningún reemplazo — quedaban completamente inalcanzables en escritorio. Restaurado.
- El toggle de modo Toque/Teclado se oculta en desktop (redundante ahí: la caja de texto ya tiene su propio botón de micrófono).
- Confirmado (no es un bug nuevo): los widgets de costo y uso mostrando $0.00/0 caracteres son la consecuencia directa y esperada del incidente de ADR 0042 — el cupo real de ElevenLabs sí se muestra correctamente.
- 305/305 tests. Ver ADR 0043.

## [2026-07-29] El fallo SSL de Google era una condición de carrera, no la red

- **Diagnóstico corregido**: el reintento triple de ADR 0043 no eliminó el error `[SSL] record layer failure` en producción — seguía apareciendo bajo uso real del dashboard. Reproducido a voluntad: 24 llamadas concurrentes reales (`ThreadPoolExecutor`) contra Gmail/Calendar/Drive, compartiendo el `self._service` cacheado de cada Capacidad, producían fallos SSL reales consistentemente; la misma API llamada secuencialmente nunca fallaba. Causa real: FastAPI corre cada endpoint en un thread del pool, el dashboard dispara varios widgets en paralelo, y `httplib2` (la base de `googleapiclient`) no es thread-safe para compartir un cliente entre threads — dos threads leyendo/escribiendo el mismo socket TLS corrompen la conexión.
- `GoogleDrive`/`GoogleGmail`/`GoogleCalendar`/`GoogleYouTube` pasan a cachear su cliente en `threading.local()` — cada thread tiene el suyo, nunca comparte el socket de otro. Verificado: el mismo escenario de 24 llamadas concurrentes reales, ahora con 0 fallos.
- 313/313 tests (8 nuevos verificando aislamiento real entre threads). Ver ADR 0044.

## [2026-07-29] Capacidad "Proyectos" (Mark I)

- Nueva Capacidad completa, registrada desde ADR 0035 y nunca construida hasta hoy: cada Proyecto es una carpeta propia en Drive (con subcarpetas propuestas por un modelo barato según el tipo de proyecto), un prompt/instrucciones propias, y sus propias listas de tareas y notas.
- Prerrequisito resuelto en el camino: "Snarf - Archivos" y la nueva carpeta de Proyectos se unificaron bajo una sola carpeta raíz "Snarf" en el Drive del fundador (migración real verificada: mismos archivos, mismos ids, solo cambió el padre), separada de sus carpetas propias.
- `GoogleDrive` suma `rename_file` (bajo riesgo) y `share_file` (alto impacto, gateado por confirmación — da acceso real a otra persona o vía link público).
- Búsqueda semántica acotada a un proyecto puntual (`project_search`): `POST /files/upload` acepta un `project_id` opcional que sube a la carpeta de ESE proyecto y etiqueta el índice — sin esto, la búsqueda por proyecto habría quedado vacía para siempre.
- 11 herramientas nuevas para el chat (`project_create`, `project_list`, `project_get`, tareas, notas, `project_search`, `project_delete` con confirmación), más endpoints REST para la barra lateral (que ahora tiene un switcher Conversaciones/Proyectos) y un panel de detalle con prompt editable, tareas, notas y link real a Drive.
- 348/348 tests. Verificado con un proyecto real creado y borrado contra el Drive real, y con Playwright de punta a punta en una copia aislada del repo. Ver ADR 0045.

## [2026-07-29] Dial de "Ingenio seco"/sarcasmo configurable

- CHARACTER.md v0.2 → v0.3: el rasgo permanente "Ingenio seco" (ADR 0039, antes fijo y discreto) declara ahora un eje configurable de intensidad — mismo criterio que ya usaba "Registro y cercanía" para variar la formalidad situacionalmente sin dejar de ser un rasgo permanente. El invariante no negociable en ningún nivel: nunca reemplaza la seriedad ante crisis, riesgo de alto impacto o corrección importante.
- Nueva escala 0-10 (medio punto de precisión), con default **7.5** — a pedido explícito del fundador, la única preferencia de este repo donde "sin configurar" es una intensificación deliberada, no "igual que antes". Configurable desde un slider nuevo en el panel de ajustes (primer control deslizante de esta UI) o pidiéndoselo a Snarf directamente por mensaje ("subime/bajame el sarcasmo") vía la tool nueva `personality_set_sarcasm`.
- El nivel se relee en cada turno de conversación (no se cachea como la identidad) — un cambio a mitad de charla se refleja sin reiniciar Snarf. El comportamiento más serio ante una crisis es puro criterio del modelo en el momento: nunca toca el número guardado, para no quedar "pegado" abajo si la conversación corta abrupto a mitad de una situación difícil.
- 369/369 tests. Verificado con Playwright contra una instancia real aislada. Ver ADR 0046.

## [2026-07-29] Proyectos Mark II: conversaciones formalmente asociadas a un proyecto

- Nueva fuente de verdad persistente (`data/conversation_projects.json`, en `EpisodicMemory`) para "a qué proyecto pertenece esta conversación" — reemplaza el enfoque más simple de Mark I.5 (project_id como parámetro por mensaje, nunca persistido), que no alcanzaba para asignar una conversación recién creada o reasignarla más tarde. El tag histórico por-entrada del log se mantiene intacto como auditoría, nunca se reescribe retroactivamente.
- Tools nuevas sin gate de confirmación (reversibles, no tocan terceros): `project_assign_conversation`, `project_unassign_conversation`, `project_list_conversations`. Nuevos endpoints REST: `PUT`/`DELETE /conversations/{id}/project`, `GET /projects/{id}/conversations`.
- `GET /projects/{id}` se enriquece con estadísticas reales (`file_count`, `pending_task_count`, `conversations`) y un resumen generado por Snarf (`cached_summary`, mismo patrón que el digest de Gmail) — completa lo que había quedado pausado de Mark I.5.
- El modal chico de detalle de proyecto se retira: entrar a un proyecto desde la barra lateral ahora la escala para mostrar solo sus conversaciones, y el área de chat muestra el "home" del proyecto (estadísticas, resumen, prompt con contador de caracteres, tareas, notas) mientras no haya ninguna conversación abierta.
- Dos bugs reales encontrados con Playwright y corregidos: `file_count` contaba las propias subcarpetas del proyecto como archivos; volver a "todos los proyectos" cerraba la barra lateral entera en vez de solo la lista.
- 398/398 tests. Verificado de punta a punta con Playwright contra una instancia real aislada (Drive/LLM reales), limpiado sin dejar rastro en producción. Ver ADR 0047.

## [2026-07-29] Proyectos usable de verdad en escritorio, menú contextual, copiar y cerebro vivo

- **Bug raíz encontrado usando la interfaz real**: entrar a un proyecto en escritorio dejaba "una pantalla sin nada" — `enterProject()` llamaba `showChat()`, que apaga el modo Jarvis; en escritorio eso oculta la grilla donde vive reparentado el chat y muestra el `#viewChat` original, vacío desde el arranque. Corregido: `showChat()` solo se llama fuera de escritorio.
- El cajón del hamburguesa en escritorio ya no duplica el historial de conversaciones/proyectos (redundante con el bloque fijo de la grilla) — queda solo para configuración y cerrar sesión.
- Nuevo botón fijo "🏠 home del proyecto" para volver sin salir de la conversación.
- El icono suelto 📁/✕ se reemplaza por un menú contextual (⋮, mismo patrón visual que el menú de usuario) — suma "mover a otro proyecto" dentro de la vista de un proyecto, que antes faltaba.
- Título "(nueva conversación)" que se quedaba pegado para siempre: `sendText()` ahora refresca las listas al completar el primer mensaje.
- Botones de copiar en las respuestas de Snarf: la respuesta completa, y cada bloque de código/entregable por separado (sin arrastrar el comentario alrededor).
- El widget colapsado del cerebro de Snarf ahora hace poll propio cada 4s (antes una foto fija) — se siente vivo sin tener que abrir la pantalla completa. Cada nodo del grafo reemplaza su título de texto por un ícono, con el nombre completo como tooltip.
- 398/398 tests (sin cambios de backend esta ronda). Verificado con Playwright en escritorio contra una instancia real aislada. Ver ADR 0048.

## [2026-07-29] Grabación estilo WhatsApp, cerebro con íconos propios, y más pulido de Proyectos

- **Regresión de ADR 0048 corregida**: el modo enfoque en escritorio se quedaba sin nada al costado — la regla que oculta las pestañas del cajón del hamburguesa no distinguía el estado en que esa misma barra se reutiliza como panel fijo del modo enfoque.
- Grabación de voz en modo texto: se retira el toggle de click (mic en rojo confundible con la flecha de enviar, que en realidad dejaba la grabación colgada sin transcribir) y se reemplaza por el patrón de WhatsApp/Telegram/ChatGPT — mantener presionado graba, soltar transcribe y envía directo, deslizar a la izquierda cancela, deslizar hacia arriba bloquea para grabar manos libres.
- El cerebro de Snarf reemplaza los emoji de la ronda anterior por íconos propios dibujados en el mismo lenguaje visual monolínea del resto de la interfaz, con el mismo pulso de luz de los nodos activos aplicado también al ícono.
- Nuevo indicador de en qué proyecto está una conversación abierta (antes no existía ningún rastro salvo en el home).
- Se retira el swipe lateral chat↔dashboard en mobile — interfería con el scroll horizontal real dentro de bloques de código/tablas en los globos de chat.
- "+ nueva conversación" ahora también disponible en la barra lateral dentro de un proyecto (antes solo en el home); "borrar proyecto" se reubica al final del home, lejos de una acción de uso diario.
- Backlog real de "Incubadora de Ideas" revisado en Drive — sin conflictos con el trabajo de esta sesión.
- 398/398 tests (sin cambios de backend). Verificado con Playwright en escritorio y en mobile (con micrófono falso). Ver ADR 0049.

## [2026-07-29] Notas de voz reproducibles (estilo WhatsApp) y caché de audio de Snarf

- Nuevo `snarf/memory/audio_store.py`: las notas de voz del usuario ahora se guardan como archivos reales (`data/audio/`, nunca en el log de texto) y quedan reproducibles en el chat como una nota de voz — botón de reproducir + transcripción disponible debajo como desplegable, en vez de mostrarse siempre.
- Las respuestas de Snarf siguen mostrándose como texto igual que siempre (sin cambio de interfaz ahí) — lo que cambia es que escucharlas varias veces ya no vuelve a pagar ni esperar una síntesis nueva de ElevenLabs: `/tts` cachea por contenido del texto.
- Protocolo de limpieza real: las transcripciones y respuestas de texto se guardan para siempre como siempre; los archivos de audio en sí (notas de voz + caché de TTS) se purgan solos a los 7 días — a pedido explícito del fundador, priorizando espacio sobre "replay histórico" de audios viejos.
- Nuevo endpoint `GET /audio/{id}` (con validación estricta contra path traversal).
- 414/414 tests (16 nuevos). Verificado con Playwright contra una instancia real aislada: guardado/servido de audio real, 404 ante ids inválidos, render del bubble de nota de voz con su desplegable, y caché de TTS confirmada con un contador real de llamadas a síntesis. Ver ADR 0050.

## [2026-07-29] Reproductor de nota de voz embebido por burbuja (reemplaza el reproductor flotante)

- El reproductor flotante único de siempre (pausa/velocidad/cerrar, pero sin forma real de volver a darle play tras pausarlo) se retira por completo. Reemplazado por un reproductor embebido propio por burbuja — el mismo componente para la nota de voz del usuario y para la de Snarf — con play/pausa real (confirmado que reanudar funciona), progreso seekable, velocidad, y un menú ⋮ con **compartir** (Web Share API, pensado para iPhone) y **descargar**.
- El botón de las respuestas de Snarf pasa de "▶ escuchar" a "🎙️ generar nota de voz": genera (o recupera de caché, instantáneo) y reemplaza el propio botón por el reproductor real, en vez de reproducir directo en el reproductor flotante de un solo uso.
- 414/414 tests. Verificado con Playwright: pausar/reanudar de verdad con un audio real de ~16 segundos, seek por click en la barra, ciclo de velocidad, y el menú de descargar. Ver ADR 0051.

## [2026-07-29] Cerebro: pulso de activación suave y haces de luz reales

- El "latido" de un nodo activo era un doble golpe con salto de escala grande (hasta 1.2×) — se veía como un "tac-tac" feo, sobre todo con varios nodos activos a la vez. Ahora es un solo pulso suave (máximo 1.05×), con la diferenciación real llevada a la luminosidad/glow. El ícono de cada nodo ya no escala nada al activarse — pulsa solo brillo y opacidad.
- Los haces de luz que viajan entre nodos activos se ven más gruesos, brillantes y con segmentos más largos — se leen como un haz real, no una línea punteada genérica.
- **Bug real encontrado en el camino**: el grosor de esos haces nunca se aplicaba de verdad — una regla de CSS declarada en el orden equivocado lo pisaba en silencio desde que existe el efecto.
- El feed de eventos del cerebro ahora muestra el mismo ícono real de cada nodo junto al texto de cada fila (había quedado sin ninguno tras retirar los emoji).
- 414/414 tests (sin cambios de backend). Verificado con Playwright. Ver ADR 0052.

## [2026-07-29] Cerebro: flujo de partículas orgánico y más niebla volumétrica

- El "haz de luz" entre nodos era una línea de guiones en movimiento — mecánico, "tac tac tac" según el fundador. Reemplazado por un flujo real de partículas que viajan del orquestador a cada nodo activo, con velocidad y deriva propias (nunca sincronizadas entre sí, nunca sobre rieles).
- Más niebla de luz volumétrica (partículas grandes, lentas y tenues, distintas de las puntuales de siempre) y más partículas en general.
- El zoom de cámara al enfocar un nodo activo ya no es siempre el mismo valor exacto — varía dentro de un rango en cada evento.
- 414/414 tests (sin cambios de backend). Verificado con Playwright: el edge activo ya no anima guiones, y dos capturas separadas por 600ms muestran las partículas de flujo en posiciones distintas. Ver ADR 0053.

## [2026-07-29] Proyectos se separa en 3 nodos reales del cerebro (sin costo nuevo)

- Las 14 herramientas de Proyectos caían todas en un único nodo del cerebro — de lejos el más cargado, y el más opaco (no se veía qué parte estaba realmente activa). Usando el mismo `tool_name` que `activity_log` ya registraba sin costo nuevo, se separan en 3 nodos reales: gestión, tareas y notas, y conversaciones (Proyectos Mark II).
- 414/414 tests (1 actualizado para cubrir los 3 nodos con tool_names reales distintos). Verificado con Playwright contra el snapshot real del backend. Ver ADR 0054.

## [2026-07-29] Protocolo de crecimiento del cerebro + más nodos (Gmail/Calendar)

- Se establece un protocolo permanente (comentario al inicio de `snarf/telemetry/brain.py`, referenciado desde la "Regla de crecimiento" de MASTER_MAP.md): cada tool/Capacidad/Especialista/canal nuevo evalúa en el mismo cambio si merece nodo propio en el cerebro, en vez de encajarlo por comodidad en uno ya existente — con un test nuevo que pone un techo real de tools por nodo "specialist" para que la decisión no se posponga para siempre.
- Aplicado como segundo caso real: Gmail (7 tools → leer/organizar/enviar) y Calendar (8 tools → ver/editar) se separan igual que Proyectos, usando datos que ya se registraban sin costo nuevo.
- El cerebro pasa de 17 nodos reales (al empezar esta sesión) a 22.
- 415/415 tests. Verificado con Playwright contra el snapshot real. Ver ADR 0055.

## [2026-07-30] Capa de voz con proveedores intercambiables (Groq/Kokoro) + split texto/habla

- ElevenLabs quedaba cableado para toda la voz (STT del audio grabado, TTS de cada respuesta completa) — nuevo `snarf/voice/` con `STTProvider`/`TTSProvider` detrás de un router, proveedor activo elegido en `voice/config.yaml`, nunca en código.
- STT: Groq (`whisper-large-v3-turbo`, ~USD 0.04/hora) como primario, con fallback 100% local y gratis (`faster-whisper`) cuando no hay red o Groq falla.
- TTS: nuevo tier "local" con Kokoro-FastAPI corriendo en Docker (CPU, gratis) como default de toda conversación cotidiana — ElevenLabs pasa a ser tier "premium" exclusivo, nunca usado en silencio.
- La optimización de mayor impacto real: cada respuesta ahora se separa en versión completa (a pantalla) y versión hablada breve (a voz, <400 caracteres, sin markdown, nunca oculta un riesgo o dato faltante) — ya no se lee en voz alta la respuesta entera con formato.
- En la burbuja de cada respuesta: si el turno vino por voz, el resumen hablado se genera y aparece listo para tocar solo, sin click (nunca se reproduce automático) — si vino por texto, sigue siendo un botón manual. Nuevo botón separado y más discreto ("🔊 completa") para escuchar la respuesta larga entera, siempre a pedido.
- Docker instalado y usado desde el día uno (Colima) — el mismo contenedor de Kokoro va a correr igual en el futuro VPS.
- 444/444 tests (30 nuevos). Verificado con Kokoro real en Docker (3 voces en español reales probadas), con Playwright (mensaje de chat real, nota de voz generada y reproducida con audio real, auto-audio por turno de voz) y con `GROQ_API_KEY` real: 6 audios reales ya grabados transcriptos en rioplatense correcto, sin artefactos. Ver ADR 0056.

## [2026-07-30] Bug real corregido: 4 llamadores de generate() rotos + refinamiento de la burbuja de audio

- **Bug real en producción**: el cambio de `AnthropicLLM.generate()` para devolver texto+habla (entrada anterior de este mismo día) rompió en silencio otros 4 puntos que llamaban a `generate()` esperando un string plano — el digest de Gmail del dashboard tiraba un error real (`Object of type LLMResponse is not JSON serializable`), y lo mismo afectaba el resumen de Proyectos y la descripción por visión de imágenes al indexar Drive. Ningún test lo agarró porque los tests de esos 3 módulos usan su propio `FakeLLM` de juguete, no el real — corregidos los 4 llamadores y los 3 fakes.
- En la burbuja de audio: la duración total ahora se ve ANTES de tocar play (no solo durante), los reproductores de audio quedan siempre arriba del texto completo (nunca abajo, mezclados con los botones), y tocar "escuchar resumen" o "escuchar completa" ahora reproduce automático apenas está listo (tocar el botón ya es la confirmación de que se lo quiere escuchar).
- Íconos SVG propios (mic / parlante) en los botones de audio, mismo estilo que el resto de la interfaz — nunca emoji.
- 444/444 tests. Verificado con Playwright: orden correcto de la burbuja, duración visible y correcta en todo momento, autoplay real, y dos reproductores con duraciones reales distintas (12s vs 38s) confirmando que resumen y completa son contenido genuinamente distinto. Ver ADR 0056 (actualizado).

## [2026-07-30] Multibotón mic/enviar y envío combinado texto+voz

- El botón de grabar y el de enviar estaban siempre los dos visibles, sin ningún criterio — se leía como dos botones sueltos en vez de uno. Ahora se muestran según el estado real: solo mic si no hay nada escrito, mic+flecha si hay un borrador (a propósito: permite grabar una nota de voz encima de texto ya escrito), solo mic mientras se graba sin bloquear, tachito+flecha si la grabación quedó bloqueada en manos libres.
- Si había texto escrito antes de grabar, se perdía en silencio al enviar la nota de voz — ahora se manda todo junto, texto + transcripción, como un solo mensaje.
- 444/444 tests (sin cambios de backend). Verificado con Playwright simulando el gesto completo (mantener presionado, deslizar arriba para bloquear, soltar el dedo, tocar enviar) y el envío combinado con una transcripción de prueba. Ver ADR 0057.

## [2026-07-30] Cerebro: flujo de partículas en ambos sentidos, dos colores

- El flujo de partículas entre nodos viajaba en un solo sentido (orquestador → nodo). Ahora hay partículas en ambas direcciones a la vez mientras un nodo está activo: las que van usan el color propio del nodo, las que vuelven son blancas — se lee como ida y vuelta real de información, no un solo flujo.
- 444/444 tests (sin cambios de backend). Verificado con Playwright: partículas en ambas direcciones, exactamente 2 colores distintos en pantalla, confirmado también visualmente. Ver ADR 0058.

## [2026-07-30] Ronda de bugs reales: audio duplicado, scroll, grabación mobile

- El audio de "resumen" podía salir idéntico al de "completa" en respuestas largas e importantes (un plan de negocio) — el modelo a veces ignoraba el límite de 400 caracteres del resumen. Reforzada la instrucción y sumado un tope de seguridad real en el código (nunca vuelve a pasar, sin importar qué decida el modelo).
- Nueva instrucción: si una respuesta no entra en el límite de un mensaje, Snarf genera un archivo Markdown con el contenido completo en vez de truncar en silencio.
- Barras de desplazamiento ocultas por default en toda la interfaz — aparecen solo mientras se hace scroll de verdad, nunca permanentes (resuelve también el textarea de una sola línea mostrando una barra sin necesidad real).
- El scroll del chat ya no "se escapa" hacia el resto de la página al llegar al final.
- Bug real en mobile: un toque rápido en el micrófono podía dejar la interfaz grabando sin ninguna forma de pararla (race real entre el permiso de micrófono y el toque). Ahora hace falta mantener presionado de verdad para que arranque a grabar, y mientras graba el ícono cambia a un cuadrado rojo de stop.
- 445/445 tests. Verificado con Playwright y micrófono simulado. Ver ADR 0059.
