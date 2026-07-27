# ARCHITECTURE_AUDIT — Auditoría técnica completa de SNARF

**Fecha:** 2026-07-27
**Rol:** Arquitecto Principal de SNARF (auditoría técnica, no de gobernanza — para la auditoría de identidad/principios ver `Architecture Review 0001` y `CONSTITUTION.md`)
**Alcance:** repositorio completo tal como está en `master` (commit `36edfed`), 55 archivos versionados, ~2.245 líneas de código Python + 1 archivo HTML/CSS/JS de 878 líneas.
**Método:** lectura íntegra de cada archivo de código (no muestreo), inspección de imports con `grep`, verificación de dependencias fijadas, existencia de tests/CI, y referencias cruzadas entre módulos. Toda afirmación de este documento está anclada a `archivo:línea` verificable.

**Regla seguida en este documento:** no se describe ningún componente que no exista en el código. Donde el objetivo final imagina subsistemas que hoy no están construidos (base de datos, MCP, múltiples agentes, trading, integración con GitHub), se dice explícitamente que no existen, en vez de proyectarlos como si ya estuvieran presentes.

---

## 1. Resumen general

SNARF hoy es un **monolito Python pequeño y deliberadamente simple**: un único proceso orquestador (`Orchestrator`) que envuelve al modelo Claude con un bucle de tool-use, memoria episódica en un archivo JSONL, y capacidades de integración con Google Workspace (Drive/Gmail/Calendar/YouTube) y ElevenLabs (voz). Tiene tres puntos de entrada equivalentes en intención (texto por terminal, voz por terminal, interfaz web) que convergen todos en el mismo `Orchestrator.handle()`.

Es un **walking skeleton honesto**: no hay código muerto accidental de alcance amplio, no hay dependencias circulares, los imports están limpios, no hay capas fantasma. El costo de esa simplicidad es que casi todo lo que un "sistema operativo personal de IA" necesitaría a mediano plazo —tests, observabilidad, streaming, manejo de errores estructurado, versionado de dependencias, separación de responsabilidades dentro del orquestador— todavía no existe. No es deuda oculta; es superficie no construida todavía, y este documento la hace explícita.

La brecha más grande no es de calidad de código (la calidad de lo que existe es alta para su tamaño), sino de **madurez operacional**: cero tests automatizados, cero CI, cero pineo de versiones de dependencias, cero logging estructurado, cero métricas. Para un proyecto que se declara a sí mismo pensado para "décadas" (ver `FOUNDATION.md`), esta es la primera línea de trabajo, antes que cualquier dashboard o visualización.

## 2. Tecnologías utilizadas

| Categoría | Tecnología | Dónde |
|---|---|---|
| Lenguaje | Python 3.13 (venv local) | todo `snarf/`, `app.py`, `main.py` |
| LLM | Anthropic (`claude-sonnet-5`), SDK `anthropic` | `snarf/capabilities/anthropic_llm.py` |
| Voz (STT/TTS) | ElevenLabs API (`scribe_v1`, `eleven_multilingual_v2`) vía `requests` | `snarf/capabilities/elevenlabs_*.py` |
| Audio local | `sounddevice`, `soundfile`, `afplay` (subprocess, macOS-only) | `snarf/capabilities/audio_io.py` |
| Google Workspace | `google-api-python-client`, `google-auth-oauthlib`, OAuth 2.0 Desktop flow | `snarf/capabilities/google_*.py` |
| Backend web | FastAPI + Uvicorn | `app.py` |
| Config | `python-dotenv`, `.env` | raíz |
| Frontend | HTML/CSS/JS vanilla, **sin build step, sin framework, sin librerías externas** | `web/index.html` (878 líneas, un solo archivo) |
| Persistencia | Archivo JSONL append-only (`data/episodic_memory.jsonl`) — **no hay base de datos** | `snarf/memory/episodic.py` |
| Acceso remoto | Tailscale (HTTPS real vía tailnet, necesario para `getUserMedia`) | infraestructura, fuera del repo |
| Tests / CI | **ninguno** | — |
| Contenedores / IaC | **ninguno** | — |

No existen todavía: base de datos (SQL o vectorial), MCP, framework multiagente, integración con GitHub, ni ninguna capacidad de trading/mercado. El `MASTER_MAP.md` los menciona como dominios futuros, no como algo implementado.

## 3. Mapa completo del proyecto

```
SNARF/
├── FOUNDATION.md, PROJECT_CONTEXT.md, CONSTITUTION.md,      ← Identity/Governance (gobernanza,
│   CHARACTER.md, COGNITION.md, MASTER_MAP.md                  no código)
├── CHANGELOG.md                                              ← History (registro legible)
├── adr/0001..0018-*.md                                       ← History (decisiones técnicas)
├── README.md
├── .env / .env.example                                       ← config de secretos ((.env NO trackeado, correcto)
├── requirements.txt                                          ← dependencias SIN pinear versión
├── credentials/  (gitignored)                                ← tokens OAuth de Google
├── data/episodic_memory.jsonl  (gitignored)                  ← memoria episódica persistente
├── main.py                                                   ← entrypoint CLI (texto / voz terminal)
├── app.py                                                    ← entrypoint web (FastAPI)
├── web/index.html                                            ← frontend completo (un solo archivo)
└── snarf/
    ├── core/
    │   ├── orchestrator.py    ← el cerebro: prompt de sistema, tools, dispatch, loop LLM
    │   └── identity.py        ← concatena FOUNDATION+CONSTITUTION+CHARACTER como system prompt
    ├── capabilities/          ← "hacen, no razonan" (ver COGNITION.md)
    │   ├── base.py            ← contrato Capability (ABC)
    │   ├── anthropic_llm.py, audio_io.py, elevenlabs_stt.py, elevenlabs_tts.py
    │   └── google_auth.py, google_drive.py, google_gmail.py, google_calendar.py, google_youtube.py
    ├── memory/episodic.py     ← log append-only + lecturas derivadas
    ├── runtime/               ← contrato Channel + implementaciones terminal
    │   ├── base.py, text_channel.py, voice_channel.py
    └── specialists/           ← ⚠ ORFANATO (ver sección 18): base.py sin ninguna implementación real
```

## 4. Responsabilidad de cada carpeta

- **raíz (`.md`)** — Identity/Governance/History a nivel documental. No contiene código; define quién es Snarf y bajo qué reglas actúa. `snarf/core/identity.py` la consume literalmente en runtime (ver sección 5).
- **`adr/`** — historial inmutable de decisiones técnicas, una por archivo, nunca editado retroactivamente. Es el mecanismo real del Artículo VIII de `CONSTITUTION.md`.
- **`credentials/`** — secretos de OAuth de Google, fuera de git. Correcto.
- **`data/`** — único almacén de estado persistente de la aplicación (memoria episódica). Fuera de git. Es un archivo, no una base de datos.
- **`snarf/core/`** — el único lugar con lógica de decisión real: arma el prompt de sistema, define qué herramientas existen, despacha llamadas a herramientas, corre el loop del LLM.
- **`snarf/capabilities/`** — "Capacidades" en el sentido de `COGNITION.md`: ejecutan una acción concreta contra un proveedor externo (Anthropic, ElevenLabs, Google), sin ningún criterio de decisión propio. Ninguna capacidad importa a otra capacidad ni al `core` — la dependencia es unidireccional.
- **`snarf/memory/`** — un solo módulo, la memoria episódica. No hay memoria semántica (vectorial) implementada todavía, pese a estar prevista en `MASTER_MAP.md`.
- **`snarf/runtime/`** — contrato `Channel` (`receive`/`send`) e implementaciones para los dos canales de terminal. **No es usado por `app.py`** (ver sección 6 y 18) — es la carpeta con la brecha de diseño más notable del repo.
- **`snarf/specialists/`** — carpeta prevista para la capa "Especialistas Cognitivos" de `COGNITION.md` (razonan pero no deciden). Hoy contiene solo el contrato (`base.py`), sin un solo especialista real, y no está conectada a nada.
- **`web/`** — todo el frontend en un archivo único.

## 5. Responsabilidad de cada módulo

| Módulo | Responsabilidad | Líneas |
|---|---|---|
| `app.py` | Servidor FastAPI: expone `/`, `/status`, `/transcribe`, `/send`, `/tts`, `/conversations[/id]`; arma el warmup de arranque | 113 |
| `main.py` | Bucle CLI: instancia `Orchestrator` + un `Channel` (texto o voz) y los conecta | 37 |
| `snarf/core/orchestrator.py` | System prompt, catálogo de 24 herramientas, dispatch de herramientas, protocolo de confirmación en dos pasos, loop de memoria por conversación | 468 |
| `snarf/core/identity.py` | Lee `FOUNDATION.md`+`CONSTITUTION.md`+`CHARACTER.md` del disco y los concatena como parte del system prompt | 14 |
| `snarf/capabilities/base.py` | Contrato mínimo (`name`, `available`) que toda capacidad implementa | 10 |
| `snarf/capabilities/anthropic_llm.py` | Cliente Anthropic: `warmup()`, `generate()` con loop de tool-use (máx. 5 rondas) | 74 |
| `snarf/capabilities/audio_io.py` | Grabación/reproducción de audio local (terminal), vía `sounddevice`/`afplay` | 65 |
| `snarf/capabilities/elevenlabs_stt.py` / `elevenlabs_tts.py` | STT/TTS vía API REST de ElevenLabs | 33 / 34 |
| `snarf/capabilities/google_auth.py` | OAuth 2.0 compartido (Desktop flow), cachea token en disco | 53 |
| `snarf/capabilities/google_drive.py` / `google_gmail.py` / `google_calendar.py` / `google_youtube.py` | Wrappers delgados sobre `googleapiclient` para cada servicio | 64 / 96 / 115 / 32 |
| `snarf/memory/episodic.py` | Append-only JSONL + `recent`/`list_conversations`/`get_conversation`/`search` | 71 |
| `snarf/runtime/base.py` | Contrato `Channel` | 13 |
| `snarf/runtime/text_channel.py` | `input()`/`print()` | 11 |
| `snarf/runtime/voice_channel.py` | Push-to-talk manual por terminal usando `LocalAudioIO` + ElevenLabs | 36 |
| `snarf/specialists/base.py` | Contrato `Specialist` + `REGISTRY` — sin usar (sección 18) | 17 |
| `web/index.html` | UI completa: estado visual (orbe), grabación en navegador, chat, sidebar de conversaciones, reproductor de audio, parser Markdown propio | 878 |

## 6. Dependencias entre módulos

El grafo de dependencias es un **DAG limpio, sin ciclos**, con una asimetría real:

```
main.py ──> Orchestrator ──> capabilities/* , core/identity.py , memory/episodic.py
   └──────> runtime/{text,voice}_channel.py ──> capabilities/{audio_io, elevenlabs_*}

app.py ──> Orchestrator (directo, vía orchestrator.handle("visual", ...))
       ──> capabilities/{elevenlabs_stt, elevenlabs_tts} (directo, para /transcribe y /tts)
       ──> (NO usa snarf/runtime/*)
```

**Hallazgo de diseño:** `README.md` afirma "tres formas equivalentes de hablar con Snarf... sobre el mismo Core". Eso es cierto para `Orchestrator`, pero **falso para el contrato `Channel`**: `app.py` nunca implementa ni instancia `Channel` — llama a `orchestrator.handle()` directamente con un string literal `"visual"` como nombre de canal (`app.py:75`), y reimplementa su propia noción de "recibir/enviar" como endpoints HTTP + estado en JavaScript. La abstracción `runtime/base.py` diseñada para unificar los tres canales en realidad solo cubre dos (texto y voz de terminal); el canal web es una implementación paralela que no comparte esa interfaz. No es necesariamente un error — HTTP request/response no tiene la forma de un loop `receive()/send()` — pero hoy es una asimetría no documentada que alguien nuevo en el proyecto descubriría por sorpresa.

Dentro de `capabilities/`, las cuatro clases de Google (`GoogleDrive`, `GoogleGmail`, `GoogleCalendar`, `GoogleYouTube`) dependen únicamente de `google_auth.py` y `base.py` — ninguna depende de otra. Limpio, pero con duplicación estructural (sección 16).

`snarf/specialists/` no tiene ningún dependiente ni dependencia real (sección 18).

## 7. Flujo de datos

```
Entrada del fundador (texto/voz/click)
   → Channel o endpoint HTTP normaliza a texto plano
   → Orchestrator.handle(channel_name, texto, conversation_id)
       → arma system prompt = SYSTEM_PREFIX + identity.load_identity()
       → carga memory.recent(10, conversation_id) como turnos previos
       → AnthropicLLM.generate(system, messages, tools, tool_handler=self._handle_tool)
           → si el modelo pide herramientas → _handle_tool despacha a capabilities/*
             → resultado (dict) vuelve al modelo como tool_result
           → texto final del modelo
       → memory.append(channel, input, response, conversation_id)   [siempre, incluso en modo eco]
   → respuesta devuelta al canal de origen
```

Todo el estado que persiste entre reinicios del proceso vive en dos únicos lugares: `data/episodic_memory.jsonl` (conversaciones) y `credentials/google_token.json` (sesión OAuth). No hay ningún otro almacén.

## 8. Flujo de una conversación

Idéntico en texto-terminal y en web hasta el `Orchestrator`; diverge solo en la capa de transporte:

- **Terminal:** `main.py` → `TextChannel.receive()` (bloqueante, `input()`) → `Orchestrator.handle("text", ...)` → `TextChannel.send()` (`print`).
- **Web:** `web/index.html` → `fetch("/send")` (JSON) → `app.py:send()` → `Orchestrator.handle("visual", ...)` → JSON de vuelta → `addMessage()` en el DOM.

En ambos casos, `conversation_id` es lo único que decide qué ventana de memoria (`memory.recent(10, conversation_id)`) se carga como contexto. En terminal, **no se pasa `conversation_id` nunca** (`main.py:29` no lo incluye) — cada sesión de terminal cae en `conversation_id=None`, y `memory.recent()` con `conversation_id=None` no filtra por conversación: devuelve los últimos 10 registros de **todos** los canales y todas las conversaciones mezclados (`episodic.py:37-41`, el filtro solo se aplica `if conversation_id is not None`). Esto significa que hoy, usar `main.py` en modo texto mezcla memoria de conversaciones web anteriores como contexto, sin que el usuario lo pida ni lo sepa. Es un hallazgo funcional real, no solo estético (sección 14).

## 9. Flujo de voz

Existen **dos implementaciones de voz completamente independientes**, que no comparten código de captura/reproducción (solo comparten las clases `ElevenLabsSTT`/`ElevenLabsTTS`):

**Terminal (`main.py --voice`):**
```
Enter → LocalAudioIO.start_recording() (sounddevice.InputStream)
Enter → LocalAudioIO.stop_recording() → WAV bytes
      → ElevenLabsSTT.transcribe() → texto → Orchestrator.handle()
      → ElevenLabsTTS.synthesize() → LocalAudioIO.play() (afplay, subprocess, macOS-only)
```

**Web (`app.py` + `web/index.html`):**
```
click/hold → MediaRecorder (navegador) → Blob
           → POST /transcribe → ElevenLabsSTT.transcribe() → texto
           → (modo click) revisión manual en textarea, o (modo hold) envío directo
           → POST /send → Orchestrator.handle()
           → texto se muestra; audio NO se genera automáticamente
           → solo si el usuario toca "▶ escuchar": POST /tts → ElevenLabsTTS.synthesize() → <audio> del navegador
```

`LocalAudioIO` (captura/reproducción nativa macOS) no se usa en absoluto en el flujo web — el navegador hace ese trabajo. Esto es correcto y esperado, pero confirma que "voz" no es una capacidad única y transversal sino dos integraciones paralelas que hay que mantener por separado.

## 10. Flujo de memoria

```
Orchestrator.handle() ──append──> episodic.jsonl (una línea por turno, nunca editada)
Orchestrator.handle() ──recent(10, conversation_id)──> episodic.jsonl (lee y parsea el archivo ENTERO)
app.py /conversations ──list_conversations()──> episodic.jsonl (lee y parsea el archivo ENTERO)
app.py /conversations/{id} ──get_conversation()──> episodic.jsonl (lee y parsea el archivo ENTERO)
Orchestrator (tool search_memory) ──search()──> episodic.jsonl (lee y parsea el archivo ENTERO)
```

Cuatro de las cinco operaciones de lectura hacen un **full scan + `json.loads` de cada línea del archivo completo** en cada llamada (`episodic.py:31-35`, método `_read_all`, sin índice ni paginación). Con el volumen actual (walking skeleton, semanas de uso) esto es instantáneo. Para un sistema que su propia visión describe como acumulando memoria "durante décadas", este patrón se degrada linealmente con el tamaño del historial y eventualmente se vuelve el cuello de botella de latencia dominante — mucho antes de que haga falta cualquier base vectorial. Es, hoy, la deuda técnica de mayor certeza de convertirse en un problema real si nada cambia (sección 20/21).

Adicionalmente: `memory.recent(10, ...)` siempre trae los últimos 10 turnos crudos (texto completo de cada uno) como mensajes del historial de chat, sin ningún presupuesto de tokens ni resumen — una sola conversación con respuestas largas puede consumir buena parte de la ventana de contexto solo en "historial", sin que el sistema lo note ni lo gestione.

## 11. Flujo de herramientas

```
AnthropicLLM.generate() ──(hasta 5 rondas)──>
  response.stop_reason == "tool_use"?
    sí → por cada bloque tool_use → tool_handler(name, input) = Orchestrator._handle_tool()
           → self._tool_handlers.get(name) (dict, 24 entradas) → ejecuta capability real
           → excepción atrapada y devuelta como {"error": str(exc)} (nunca revienta el loop)
         → resultado serializado a JSON como tool_result → nueva ronda
    no → concatena bloques de texto → respuesta final
  si se agotan las 5 rondas → "[demasiadas consultas a herramientas, no llegué a una respuesta final]"
```

Las 8 herramientas de "alto impacto" (`gmail_send_message`, `calendar_create_event`, `calendar_create_calendar`, `calendar_delete_calendar`, `calendar_delete_event`, `calendar_move_event`, `gmail_delete_label`, `drive_delete_file`) están **efectivamente gateadas en código** (no solo por prompt): cada handler chequea `i.get("confirmed")` antes de ejecutar nada real (`orchestrator.py:370-439`). Esto es más sólido de lo habitual en sistemas de agentes — el modelo no puede saltarse la vista previa aunque "decida" hacerlo, porque la ejecución real está detrás de ese if. Lo que **no** está gateado en código es la decisión de *cuándo* el modelo debe pasar `confirmed=true`: eso depende enteramente de que el modelo interprete correctamente la instrucción en `SYSTEM_PREFIX` ("solo si el fundador respondió de forma explícita e inequívoca"). Ya está documentado como limitación conocida en `MASTER_MAP.md` — este audit lo confirma con lectura de código y lo mantiene como el hallazgo de seguridad más importante del repo (sección 20).

## 12. Flujo de APIs

APIs externas consumidas, todas síncronas, **sin retry ni backoff en ningún punto del código**:

| API | Usada en | Timeout configurado | Retry |
|---|---|---|---|
| Anthropic Messages | `anthropic_llm.py:54` | el del SDK por defecto | no |
| ElevenLabs STT | `elevenlabs_stt.py:24-30` | 60s | no |
| ElevenLabs TTS | `elevenlabs_tts.py:27-32` | 30s | no |
| Google Drive/Gmail/Calendar/YouTube | `google_*.py` | el del SDK por defecto | no |

Endpoints propios (FastAPI, `app.py`): `GET /`, `GET /status`, `POST /transcribe`, `POST /send`, `POST /tts`, `GET /conversations`, `GET /conversations/{id}`. **Ninguno tiene autenticación propia** — la única barrera es que el proceso solo es alcanzable vía red local o Tailscale (control de acceso a nivel de infraestructura, no de aplicación). `GET /status` solo verifica presencia de variables de entorno/config (`app.py:49-55`), no hace ningún ping real a Anthropic/Google/ElevenLabs — puede reportar "todo disponible" con un token de Google ya vencido o una API key inválida.

## 13. Flujo de streaming

**No existe streaming en ningún punto del sistema.** `AnthropicLLM.generate()` usa `messages.create()` sin `stream=True` (`anthropic_llm.py:54`); `/send` es un POST/JSON bloqueante de punta a punta; el frontend simula actividad con un indicador de "escribiendo" (`showTyping()`, `web/index.html:634`) que es puramente decorativo — no refleja tokens reales llegando, porque no hay ningún canal (SSE/WebSocket) por el que podrían llegar. Esto es directamente relevante para el BUG 2 reportado (sección 14/próximos pasos): cualquier diagnóstico que asuma un problema de streaming, buffer o SSE parte de una premisa que no aplica a este código — el mecanismo de transporte no es la causa posible, porque no existe.

## 14. Problemas detectados

Ordenados por severidad real, no por orden de aparición:

1. **`max_tokens=1024` hardcodeado sin manejo de `stop_reason`** (`anthropic_llm.py:51,72`). Es la causa más probable, con evidencia directa de código, del bug reportado "las respuestas largas se cortan": el modelo puede truncar su propia respuesta a mitad de oración al llegar a 1024 tokens de salida (~700-800 palabras), y el código no distingue ese caso (`stop_reason == "max_tokens"`) de una respuesta completa — simplemente concatena el texto parcial y lo devuelve como si fuera la respuesta final, sin avisar al usuario ni reintentar. No es un problema de streaming/SSE/timeout como sugeriría investigar por esas vías: es un límite de salida fijo, sin verificación.
2. **Memoria de terminal sin `conversation_id` mezcla contexto de todas las conversaciones** (sección 8; `main.py:29`, `episodic.py:37-41`). Bug funcional silencioso, no solo de prolijidad.
3. **Cero tests automatizados, cero CI** en todo el repositorio (verificado: no existe ningún archivo `test*`, ni `.github/`). Cada bug corregido en este proyecto hasta ahora (scroll, hold-mode sin salida de error, `/transcribe` 500, audio eager) se descubrió por uso manual en producción, no por una red de seguridad automatizada. Es el ítem que más condiciona la velocidad segura de todo lo que sigue.
4. **Dependencias sin pinear** (`requirements.txt`, ninguna línea tiene versión). Un `pip install` futuro puede traer versiones incompatibles del SDK de Anthropic, FastAPI o `google-api-python-client` sin ningún aviso, rompiendo producción de forma no reproducible.
5. **Stream de micrófono cacheado indefinidamente en el navegador** (`web/index.html:758-760`, `ensureStream()`): el `MediaStream` se pide una sola vez y se reutiliza para siempre. En iOS Safari, backgrounding/bloqueo de pantalla suele terminar los tracks del stream sin que el código lo detecte (no hay listener de `track.onended` ni chequeo de `readyState`). **Esta es, con evidencia de código, la hipótesis de causa raíz más fuerte para el BUG 1** (push-to-talk funciona una vez en iPhone y después deja de andar): se sigue intentando grabar sobre un stream muerto, produciendo un blob vacío o casi vacío, que el guard `len(audio_bytes) < 2000` de `app.py:63` convierte en un transcript vacío silencioso — indistinguible de "no funcionó". Pendiente de confirmar en dispositivo real antes de tocar código (Fase 6, no ahora).
6. **`min-height: 100vh` conviviendo con `height: 100dvh` en el mismo `body`** (`web/index.html:18-21`). En iOS Safari, `100vh` puede exceder el viewport visual real cuando la barra de direcciones está visible, mientras que `100dvh` es exactamente el viewport visible; tener ambas reglas en el mismo elemento puede forzar una altura mayor a la visible y empujar el `control-bar` (con el botón de enviar) fuera de la pantalla. Hipótesis de causa raíz razonable para el BUG 3 ("botón enviar cortado"), a confirmar en dispositivo antes de tocar código.
7. **`Orchestrator` concentrando 468 líneas y creciendo linealmente con cada integración nueva** (definición de las 24 herramientas, sus 24 handlers, y la lógica de confirmación, todo en un solo archivo). Ya es el archivo más grande y más difícil de navegar del repo; cada integración futura (Notion, GitHub, lo que sea) lo va a hacer crecer más en el mismo archivo si no se interviene antes (sección 21).
8. **`/status` no verifica salud real de las APIs externas** (`app.py:49-55`) — solo confirma que hay claves configuradas, no que Anthropic/Google/ElevenLabs respondan. Un token de Google vencido puede pasar desapercibido hasta que una herramienta falla en medio de una conversación real.
9. **Sin logging estructurado**: los únicos rastros de error son `print()` (`app.py:68`) y excepciones silenciadas (`anthropic_llm.py:34-35`, `main.py:30-32`). No hay forma de saber, sin estar mirando la terminal en el momento exacto, si algo falló.

## 15. Código muerto

- **`LocalAudioIO.record()`** (`audio_io.py:30-35`) — método de grabación de duración fija, reemplazado por `start_recording()`/`stop_recording()` según el propio `CHANGELOG.md`. Verificado por `grep`: **cero llamadas** a `.record(` en todo el código fuente. Candidato directo a eliminar.
- El resto del código no tiene funciones, clases ni ramas muertas detectadas — es notablemente limpio para su tamaño.

## 16. Duplicaciones

1. **Boilerplate idéntico repetido 4 veces** en `GoogleDrive`, `GoogleGmail`, `GoogleCalendar`, `GoogleYouTube`: mismo `__init__(self, auth=None)`, misma property `available`, mismo patrón de `_client()` con lazy-build (solo cambia el nombre/versión del servicio en `build(...)`). ~10 líneas idénticas × 4 clases. Candidato claro a una clase base `GoogleAPICapability` con `SERVICE_NAME`/`SERVICE_VERSION` como atributos de clase.
2. **El protocolo de confirmación en dos pasos está copiado a mano 7 veces** (`orchestrator.py:370-439`): cada método `_tool_*` de alto impacto repite el mismo `if not i.get("confirmed"): return self._pending({...})`. Funciona, pero cualquier herramienta de alto impacto nueva depende de que quien la escriba recuerde copiar el patrón correctamente — no hay nada en el sistema de tipos ni en el registro que lo fuerce.
3. **El catálogo de herramientas vive en 3 lugares que deben mantenerse sincronizados a mano**: la lista `TOOLS` (schema para el modelo), el diccionario `_tool_handlers` (despacho), y la prosa de `SYSTEM_PREFIX` que enumera los nombres de herramientas por categoría. Agregar una herramienta nueva de alto impacto hoy requiere editar correctamente en 4 sitios (schema, dict, método handler, prosa del prompt); no hay ninguna verificación de que los tres primeros queden consistentes entre sí.

## 17. Imports innecesarios

Ninguno detectado. Se revisó cada archivo `.py` línea por línea: todos los imports declarados se usan. Esto es una fortaleza real del código actual, no una omisión de la auditoría — vale la pena preservarla a medida que el proyecto crece (por ejemplo, con un linter en CI, sección 22).

## 18. Componentes huérfanos

- **`snarf/specialists/` (contrato `Specialist` + `REGISTRY`)** — verificado por `grep -rn "specialists"`: **cero referencias** fuera del propio archivo, en todo el repositorio. Es la única carpeta de código completamente desconectada del sistema. No es necesariamente un error tenerla (documenta una intención arquitectónica futura de `COGNITION.md`), pero hoy es peso muerto: nadie la importa, nadie la registra, no hay un solo `Specialist` real implementado.
- **`snarf/runtime/*` respecto de `app.py`** (ya detallado en sección 6): no es un huérfano completo (sí lo usan `main.py` y sus dos canales de terminal), pero el canal más usado del sistema (web) no lo conoce.

## 19. Dependencias circulares

Ninguna. El grafo de imports es un DAG limpio (sección 6): `capabilities/` no importa de `core/`, `runtime/` ni `memory/`; `core/` importa de `capabilities/` y `memory/` pero nunca al revés. Esto facilita razonar sobre el sistema y es una base sana para cualquier refactor futuro.

## 20. Riesgos técnicos

1. **El protocolo de confirmación en dos pasos depende enteramente del comportamiento del modelo dentro de un mismo turno** (sección 11) — ya señalado como límite conocido en `MASTER_MAP.md`, confirmado ahora por lectura de código. Es el riesgo de mayor impacto potencial del sistema completo: una mala interpretación del modelo en una herramienta de alto impacto (borrar un calendario, enviar un correo) no tiene ningún control técnico independiente que lo detenga.
2. **Alcance OAuth completo** (`drive`, `gmail.modify`+`gmail.send`, `calendar` — no restringido a `drive.file` ni a etiquetas/calendarios específicos, `google_auth.py:12-18`). Razonable hoy para un solo usuario (el fundador) sobre su propia cuenta, pero es acceso total de lectura/escritura sobre Drive, Gmail y Calendar completos; si el token en `credentials/google_token.json` se filtrara, el radio de daño es máximo.
3. **Sin autenticación de aplicación en los endpoints HTTP** (sección 12) — hoy mitigado únicamente por la topología de red (Tailscale/LAN). Un error de configuración de red convierte a Snarf en una API abierta capaz de enviar correos y modificar el calendario del fundador.
4. **Full-file scan de la memoria episódica en cada lectura** (sección 10) — riesgo de degradación de latencia que crece con el propio éxito del proyecto (más años de uso → más lento cada turno), justo lo opuesto de lo que un sistema pensado para "décadas" necesita.
5. **Dependencia de `afplay`** (`audio_io.py:28`) ata la reproducción de audio por terminal exclusivamente a macOS — no es portable a Linux/contenedores si algún día Snarf necesita correr en un servidor en vez de la laptop del fundador.
6. **Cero tests + dependencias sin pinear** (secciones 14.3/14.4) combinados son el mayor riesgo compuesto: un `pip install` de rutina, meses después, podría romper algo en silencio y no habría ninguna red que lo detecte antes de que el fundador lo note usando el sistema.

## 21. Deuda técnica

Priorizada por relación esfuerzo/beneficio, no por orden de mención en este documento:

1. Pinear versiones en `requirements.txt` (esfuerzo trivial, elimina un riesgo de reproducibilidad real).
2. Suite mínima de tests (unitarios para `episodic.py`, `orchestrator._handle_tool`, y un smoke test de `app.py` con TestClient de FastAPI) + CI que la corra en cada push. Es la pieza individual que más cambia el perfil de riesgo de todo lo demás.
3. Extraer el registro de herramientas de `Orchestrator` a una estructura declarativa única (una tool = una entrada, que genere schema + handler + confirmación desde el mismo lugar) para eliminar la sincronización manual en 3-4 sitios (sección 16.3).
4. Base class `GoogleAPICapability` para eliminar la duplicación de las 4 integraciones de Google (sección 16.1).
5. Reemplazar `print()`/excepciones silenciadas por logging estructurado (aunque sea `logging` estándar con niveles, antes de pensar en cualquier dashboard).
6. Paginar o indexar `episodic.py` antes de que el archivo JSONL crezca lo suficiente para que el full-scan se note (hoy no urge; en 1-2 años de uso real, si nada cambia, sí).
7. Decidir explícitamente el destino de `snarf/specialists/`: implementarlo con un caso de uso real, o retirarlo hasta que exista ese caso de uso (coherente con la "Regla de crecimiento" que el propio `MASTER_MAP.md` ya se autoimpone).
8. Eliminar `LocalAudioIO.record()` (código muerto confirmado, sección 15).

## 22. Recomendaciones

**Recomendación central de este audit:** el objetivo final que describe este modo de trabajo (sistema operativo personal de IA, observable durante diez años) es válido y coherente con `FOUNDATION.md`/`PROJECT_CONTEXT.md`. Pero las Fases 3, 4 y 5 tal como están redactadas en el prompt original (dashboard en tiempo real con paneles de Trading/Mercado/GitHub/MCP, visualización tipo Jarvis con nodos iluminándose) **describen un sistema que todavía no existe**: hoy no hay base de datos, no hay MCP, no hay múltiples agentes, no hay integración con GitHub, no hay ninguna capacidad de trading o mercado. Construir esa observabilidad ahora sería, literalmente, la "arquitectura astronauta" que el propio `Architecture Review 0001` de este proyecto identificó como riesgo desde el día uno, y que `MASTER_MAP.md` conjura explícitamente con su "Regla de crecimiento": no crear estructura antes de que exista contenido real que la justifique.

Por eso, antes de avanzar a Fase 2 (diagramas Mermaid) y Fases 3-5 (observabilidad/dashboard/Jarvis brain) tal como fueron pedidas, la secuencia que protege mejor la coherencia del sistema a 10 años es:

1. **Cerrar la deuda de la sección 21, ítems 1-2 primero** (pinear dependencias, tests mínimos + CI). Es barato ahora y carísimo de agregar retroactivamente una vez que haya un dashboard, un Jarvis brain y más integraciones corriendo encima de un código sin red de seguridad.
2. **Confirmar en dispositivo real las hipótesis de causa raíz de los 3 bugs** (sección 14, ítems 1, 5, 6) antes de tocar código — ya están acotadas a líneas exactas, así que la corrección en sí es de bajo riesgo una vez confirmadas.
3. Recién ahí, Fase 2 (diagramas Mermaid del sistema **tal como es hoy**, no aspiracional) y una observabilidad mínima real (logging estructurado + métricas de latencia/tokens, que es infraestructura genuinamente útil hoy) — en vez de un dashboard en tiempo real con paneles para subsistemas que aún no existen.
4. El "Snarf Brain" tipo Jarvis (Fase 4) es una idea legítima y con valor real, pero su honestidad depende de representar el flujo que este audit acaba de documentar (seccion 7-13) — no una arquitectura de agentes/MCP/base de datos que todavía no fue construida. Vale la pena reservarla para cuando haya más de un tipo de flujo interesante que mostrar (hoy el sistema tiene esencialmente un solo camino: LLM + tool loop).

Quedo a la espera de tu decisión sobre cómo seguir: puedo (a) proceder con el punto 1 de esta lista como Fase 2 de trabajo real, (b) ir directamente a confirmar y corregir los 3 bugs, o (c) ajustar el alcance de las Fases 3-5 a lo que el sistema real puede sostener hoy y recién ahí construir esa capa. No voy a mezclar análisis con implementación ni a avanzar sin tu confirmación, tal como pediste.
