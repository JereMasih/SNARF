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
