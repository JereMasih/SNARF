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
