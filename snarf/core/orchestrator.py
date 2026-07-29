import time
from pathlib import Path

from snarf.capabilities.anthropic_llm import AnthropicLLM
from snarf.capabilities.docx_extractor import DocxExtractor
from snarf.capabilities.document_builder import DocumentBuilder
from snarf.capabilities.ffmpeg_audio import FfmpegAudioExtractor
from snarf.capabilities.elevenlabs_stt import ElevenLabsSTT
from snarf.capabilities.google_auth import GoogleAuth
from snarf.capabilities.google_calendar import GoogleCalendar
from snarf.capabilities.google_drive import GoogleDrive
from snarf.capabilities.google_gmail import GoogleGmail
from snarf.capabilities.google_youtube import GoogleYouTube
from snarf.capabilities.local_file_store import LocalFileStore
from snarf.capabilities.pdf_extractor import PdfExtractor
from snarf.capabilities.pptx_extractor import PptxExtractor
from snarf.capabilities.voyage_embeddings import VoyageEmbeddings
from snarf.capabilities.xlsx_extractor import XlsxExtractor
from snarf.core.identity import load_identity
from snarf.knowledge.document_publisher import DocumentPublisher
from snarf.knowledge.drive_indexer import DriveIndexer
from snarf.knowledge.extraction import ContentExtractor
from snarf.knowledge.vector_store import VectorStore
from snarf.memory.episodic import EpisodicMemory
from snarf.specialists.gmail_digest import GmailDigestSpecialist
from snarf.telemetry import activity_log

# Único usuario real hoy. El Orchestrator ya recibe un user_id explícito (en
# vez de asumirlo implícitamente) para que agregar un segundo usuario en el
# futuro sea pasar otro user_id, no rediseñar esta clase.
DEFAULT_USER_ID = "fundador"

# Modelo para la interpretación de Gmail (Especialista, no Snarf): tarea de
# categorización acotada, no necesita el modelo principal de Snarf.
GMAIL_DIGEST_MODEL = "claude-haiku-4-5"

# Modelo para describir/transcribir imágenes al vectorizar Drive: tarea
# acotada y mecánica, mismo criterio que GMAIL_DIGEST_MODEL — no necesita el
# modelo principal de Snarf (ver ADR 0028).
DRIVE_VISION_MODEL = "claude-haiku-4-5"

DRIVE_INDEX_DATA_DIR = Path("data/drive_index")
LOCAL_FILES_DATA_DIR = Path("data/local_files")

SYSTEM_PREFIX = (
    "Sos Snarf. A continuación se incluyen, en orden de jerarquía, los documentos "
    "que definen tu identidad, tu gobernanza y tu personalidad. Actuá en todo momento "
    "conforme a ellos.\n\n"
    "Cuando una respuesta se beneficie de estructura (explicaciones largas, listas de "
    "opciones, comparaciones, pasos a seguir, código), usá formato Markdown: encabezados "
    "(#, ##, ###), listas, **negrita**, citas con '>' y bloques de código con ```. Para "
    "respuestas conversacionales cortas, mantené texto simple y fluido, sin forzar "
    "estructura que no aporta.\n\n"
    "Tenés herramientas para consultar conversaciones pasadas con el fundador, más allá "
    "de la conversación actual: list_conversations, get_conversation, search_memory. "
    "Usalas cuando te pregunten por algo dicho en otra conversación, cuando necesites "
    "contexto que no está en la conversación actual, o cuando genuinamente creas que "
    "recordar algo de otra conversación ayuda.\n\n"
    "También tenés herramientas de solo lectura sobre Google Drive, Gmail, Calendar y "
    "YouTube del fundador: drive_list_files, drive_read_file, gmail_list_messages, "
    "gmail_read_message, calendar_list_calendars, calendar_list_upcoming_events, "
    "gmail_list_labels, youtube_list_subscriptions, youtube_list_liked_videos. Usalas "
    "para responder con contexto real cuando el fundador pregunte por su correo, su "
    "agenda, sus archivos o sus videos.\n\n"
    "Importante sobre calendar_list_upcoming_events: solo muestra eventos futuros a "
    "partir de este momento. Si el fundador te habla de un evento y no aparece ahí "
    "(por ejemplo porque ya pasó, o porque no sabés en qué calendario está), usá "
    "calendar_search_events con el texto del título antes de concluir que no existe — "
    "buscá en todos los calendarios relevantes si hace falta.\n\n"
    "Tenés herramientas de organización que actúan sobre el mundo real pero son "
    "reversibles y no salen de la cuenta del fundador (no requieren confirmación en dos "
    "pasos, pero usalas solo cuando el fundador lo pida): gmail_create_label, "
    "gmail_modify_message_labels, drive_create_folder, drive_move_file.\n\n"
    "Además tenés herramientas de alto impacto (Constitution, Artículo VII): "
    "gmail_send_message, calendar_create_event, calendar_create_calendar, "
    "calendar_delete_calendar, calendar_delete_event, calendar_move_event (mover un "
    "evento entre calendarios puede notificar a invitados si el evento tiene invitados, "
    "por eso lleva confirmación igual que borrar), gmail_delete_label, "
    "drive_delete_file. Su protocolo es "
    "obligatorio, siempre, sin excepción: (1) llamalas primero con confirmed=false (o "
    "sin ese campo) — no van a ejecutar nada, te van a devolver una vista previa; (2) "
    "mostrale esa vista previa al fundador tal cual, con claridad, y preguntale si "
    "confirma; (3) solo volvé a llamar a la misma herramienta con confirmed=true, y "
    "exactamente los mismos datos, si el fundador respondió de forma explícita e "
    "inequívoca que sí a ESA propuesta concreta, en este mismo intercambio. Nunca "
    "asumas una confirmación implícita, y nunca combines la propuesta y la ejecución "
    "en el mismo turno.\n\n"
    "También tenés herramientas para vectorizar el Google Drive del fundador y "
    "buscar semánticamente sobre ese contenido ya indexado: drive_index_scan (solo "
    "lectura, sin costo, cuenta archivos y tamaño real), drive_index_catalog_unsupported "
    "(solo lectura, sin costo, registra el mimeType real de archivos que hoy no se "
    "pueden indexar — categoría 'other'), drive_index_start (arranca la indexación "
    "en segundo plano, tiene costo real de APIs salvo que uses query='free_tier'), "
    "drive_index_status, drive_index_stop y drive_search_knowledge. query='free_tier' "
    "acota a lo que hoy sale gratis o casi gratis (Google Docs/Sheets/Slides, PDF, "
    "texto plano) — nunca imagen, audio ni video, que sí cuestan. drive_index_start "
    "no es una acción destructiva y no lleva el protocolo de confirmed en dos pasos, "
    "pero igual requiere criterio: nunca la llames por tu cuenta, solo cuando el "
    "fundador pida explícitamente indexar o vectorizar Drive. Si todavía no le "
    "mostraste un drive_index_scan en esta conversación, mostraselo primero "
    "(cantidad de archivos, tamaño, desglose por tipo) y dejá que decida el alcance "
    "antes de arrancar.\n\n"
    "También podés crear archivos reales: drive_create_document (markdown, pdf o un "
    "Google Doc editable), drive_create_spreadsheet (xlsx o Google Sheet) y "
    "drive_create_presentation (pptx o Google Slides). Todas aceptan tres destinos — "
    "preguntale siempre a quien te lo pidió cuál prefiere antes de crear, salvo que ya "
    "te lo haya dicho explícitamente en este intercambio: "
    "(1) destination='drive' — se guarda en la carpeta 'Snarf - Archivos' del Drive "
    "real de esa persona, usa espacio de su cuota; "
    "(2) destination='device' — se prepara para descargar directo a SU dispositivo "
    "(computadora o celular), con el diálogo nativo de 'Guardar como' del navegador; "
    "compartile el download_url que te devuelve como un link markdown para que lo "
    "descargue con un clic; "
    "(3) destination='server' — se guarda en el disco del propio servidor de Snarf, "
    "como carpeta de trabajo. Este destino es EXCLUSIVO del fundador — si quien te "
    "habla no es el fundador, ni se lo ofrezcas como opción. Los tres destinos quedan "
    "indexados al toque, así que después se puede encontrar con drive_search_knowledge "
    "sin importar dónde haya quedado.\n\n"
)

TOOLS = [
    {
        "name": "list_conversations",
        "description": "Lista todas las conversaciones pasadas con el fundador: id, título y fechas.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_conversation",
        "description": "Obtiene todos los mensajes de una conversación pasada, dado su conversation_id.",
        "input_schema": {
            "type": "object",
            "properties": {"conversation_id": {"type": "string"}},
            "required": ["conversation_id"],
        },
    },
    {
        "name": "search_memory",
        "description": "Busca un texto o tema en todo el historial de conversaciones (todas, no solo la actual).",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "drive_list_files",
        "description": "Lista archivos de Google Drive del fundador, opcionalmente filtrados por una query de Drive.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Query opcional de búsqueda de Drive (sintaxis de la API de Drive)."},
                "page_size": {"type": "integer"},
            },
        },
    },
    {
        "name": "drive_read_file",
        "description": "Lee el contenido de un archivo de Drive dado su id y mimeType: texto plano/Google Docs/Sheets directo, PDF/Word/PowerPoint/Excel extraídos (con OCR automático si el PDF es un escaneo sin texto real), descripción por visión si es imagen, transcripción si es audio o video.",
        "input_schema": {
            "type": "object",
            "properties": {"file_id": {"type": "string"}, "mime_type": {"type": "string"}},
            "required": ["file_id", "mime_type"],
        },
    },
    {
        "name": "drive_create_folder",
        "description": "Crea una carpeta en Drive, opcionalmente dentro de otra carpeta (parent_id).",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}, "parent_id": {"type": "string"}},
            "required": ["name"],
        },
    },
    {
        "name": "drive_move_file",
        "description": "Mueve un archivo o carpeta de Drive a otra carpeta.",
        "input_schema": {
            "type": "object",
            "properties": {"file_id": {"type": "string"}, "new_parent_id": {"type": "string"}},
            "required": ["file_id", "new_parent_id"],
        },
    },
    {
        "name": "gmail_list_messages",
        "description": "Lista correos recientes del Gmail del fundador (asunto, remitente, fecha, resumen), opcionalmente filtrados por una query de Gmail.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Query opcional (sintaxis de búsqueda de Gmail)."},
                "max_results": {"type": "integer"},
            },
        },
    },
    {
        "name": "gmail_read_message",
        "description": "Lee el contenido completo de un correo de Gmail dado su id.",
        "input_schema": {
            "type": "object",
            "properties": {"message_id": {"type": "string"}},
            "required": ["message_id"],
        },
    },
    {
        "name": "gmail_list_labels",
        "description": "Lista las etiquetas/carpetas de Gmail del fundador.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "gmail_create_label",
        "description": "Crea una etiqueta/carpeta nueva en Gmail.",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
    {
        "name": "gmail_modify_message_labels",
        "description": "Organiza un correo agregando o quitando etiquetas (por ejemplo, moverlo a una carpeta o archivarlo quitando INBOX).",
        "input_schema": {
            "type": "object",
            "properties": {
                "message_id": {"type": "string"},
                "add_label_ids": {"type": "array", "items": {"type": "string"}},
                "remove_label_ids": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["message_id"],
        },
    },
    {
        "name": "calendar_list_calendars",
        "description": "Lista todos los calendarios del fundador (no solo el principal).",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "calendar_list_upcoming_events",
        "description": "Lista los próximos eventos de un calendario del fundador (por defecto, el principal). Solo eventos futuros.",
        "input_schema": {
            "type": "object",
            "properties": {"max_results": {"type": "integer"}, "calendar_id": {"type": "string"}},
        },
    },
    {
        "name": "calendar_search_events",
        "description": "Busca eventos por texto en un calendario, sin restricción de fecha (incluye eventos pasados). Usala si un evento no aparece en calendar_list_upcoming_events.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "calendar_id": {"type": "string", "description": "Por defecto, 'primary'."},
                "max_results": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "youtube_list_subscriptions",
        "description": "Lista los canales de YouTube a los que está suscripto el fundador.",
        "input_schema": {"type": "object", "properties": {"max_results": {"type": "integer"}}},
    },
    {
        "name": "youtube_list_liked_videos",
        "description": "Lista videos de YouTube que el fundador marcó como 'me gusta'.",
        "input_schema": {"type": "object", "properties": {"max_results": {"type": "integer"}}},
    },
    {
        "name": "gmail_summarize_inbox",
        "description": (
            "Interpreta los correos recientes de Gmail: los agrupa por categoría y señala cuáles "
            "conviene revisar y por qué. Usala cuando el fundador pregunte algo como '¿qué tenemos "
            "para hoy?', 'resumime el correo' o similar. Por defecto devuelve la última "
            "interpretación disponible (no hace una llamada nueva cada vez); usá force_refresh=true "
            "solo si el fundador pide explícitamente una versión actualizada ahora mismo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"force_refresh": {"type": "boolean"}},
        },
    },
    {
        "name": "gmail_send_message",
        "description": "Envía un correo real desde el Gmail del fundador. Acción de alto impacto: protocolo de confirmed obligatorio.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
                "confirmed": {"type": "boolean"},
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "calendar_create_event",
        "description": "Crea un evento real en un calendario del fundador. Acción de alto impacto: protocolo de confirmed obligatorio.",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "start_iso": {"type": "string", "description": "Inicio en ISO 8601 con zona horaria."},
                "end_iso": {"type": "string", "description": "Fin en ISO 8601 con zona horaria."},
                "description": {"type": "string"},
                "location": {"type": "string"},
                "calendar_id": {"type": "string", "description": "Por defecto, 'primary'."},
                "confirmed": {"type": "boolean"},
            },
            "required": ["summary", "start_iso", "end_iso"],
        },
    },
    {
        "name": "calendar_create_calendar",
        "description": "Crea un calendario nuevo. Acción de alto impacto: protocolo de confirmed obligatorio.",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "description": {"type": "string"},
                "confirmed": {"type": "boolean"},
            },
            "required": ["summary"],
        },
    },
    {
        "name": "calendar_delete_calendar",
        "description": "Elimina un calendario completo. Acción de alto impacto: protocolo de confirmed obligatorio.",
        "input_schema": {
            "type": "object",
            "properties": {"calendar_id": {"type": "string"}, "confirmed": {"type": "boolean"}},
            "required": ["calendar_id"],
        },
    },
    {
        "name": "calendar_delete_event",
        "description": "Elimina un evento de un calendario. Acción de alto impacto: protocolo de confirmed obligatorio.",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string"},
                "calendar_id": {"type": "string", "description": "Por defecto, 'primary'."},
                "confirmed": {"type": "boolean"},
            },
            "required": ["event_id"],
        },
    },
    {
        "name": "calendar_move_event",
        "description": "Mueve un evento de un calendario a otro. Acción de alto impacto: protocolo de confirmed obligatorio.",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string"},
                "source_calendar_id": {"type": "string"},
                "destination_calendar_id": {"type": "string"},
                "confirmed": {"type": "boolean"},
            },
            "required": ["event_id", "source_calendar_id", "destination_calendar_id"],
        },
    },
    {
        "name": "gmail_delete_label",
        "description": "Elimina una etiqueta/carpeta de Gmail. Acción de alto impacto: protocolo de confirmed obligatorio.",
        "input_schema": {
            "type": "object",
            "properties": {"label_id": {"type": "string"}, "confirmed": {"type": "boolean"}},
            "required": ["label_id"],
        },
    },
    {
        "name": "drive_delete_file",
        "description": "Elimina (envía a la papelera) un archivo o carpeta de Drive. Acción de alto impacto: protocolo de confirmed obligatorio.",
        "input_schema": {
            "type": "object",
            "properties": {"file_id": {"type": "string"}, "confirmed": {"type": "boolean"}},
            "required": ["file_id"],
        },
    },
    {
        "name": "drive_index_scan",
        "description": (
            "Recorre (pagina) el Drive del fundador, opcionalmente filtrado por una query de Drive, y "
            "devuelve cantidad de archivos, tamaño total y desglose por tipo — SIN indexar nada ni gastar "
            "nada. Es de solo lectura: usala siempre antes de proponer drive_index_start, para que el "
            "fundador vea el alcance real antes de decidir. Aceptá query='free_tier' para acotar a lo que "
            "hoy sale gratis o casi gratis (Google Docs/Sheets/Slides, PDF, texto plano) — sin imagen, "
            "audio ni video."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Query de Drive para acotar el alcance (por ejemplo, una carpeta), o 'free_tier' para lo que sale gratis."}},
        },
    },
    {
        "name": "drive_index_catalog_unsupported",
        "description": (
            "Recorre el Drive y registra (sin extraer contenido, sin costo) el mimeType y nombre real de "
            "cada archivo que hoy no tiene extractor (categoría 'other' de drive_index_scan). Sirve para "
            "que el fundador identifique qué son esos archivos antes de decidir si vale construirles "
            "soporte. Guarda un catálogo completo en disco y devuelve un resumen agrupado por mimeType "
            "con ejemplos de nombres."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
        },
    },
    {
        "name": "drive_index_start",
        "description": (
            "Arranca (o reanuda) en segundo plano la vectorización del Drive del fundador, opcionalmente "
            "acotada por una query (incluido query='free_tier'). Tiene costo real (Voyage, ElevenLabs, "
            "Claude) salvo que se use 'free_tier'. Usala solo cuando el fundador lo pida explícitamente, y "
            "solo después de haberle mostrado drive_index_scan en esta conversación."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
        },
    },
    {
        "name": "drive_index_status",
        "description": "Progreso de la indexación de Drive en curso (o de la última corrida): procesados, indexados, saltados, errores.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "drive_index_stop",
        "description": "Corta la indexación de Drive en curso, si hay una corriendo.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "drive_search_knowledge",
        "description": "Búsqueda semántica sobre el contenido de Drive ya vectorizado. Devuelve los fragmentos más relevantes con su archivo de origen.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}, "top_k": {"type": "integer"}},
            "required": ["query"],
        },
    },
    {
        "name": "drive_create_document",
        "description": (
            "Crea un documento real y devuelve su link o ubicación. format='markdown' o 'pdf' generan el "
            "archivo tal cual; format='google_doc' crea un Google Doc editable nativo (solo con "
            "destination='drive'). destination='drive' lo sube a la carpeta 'Snarf - Archivos' del Drive "
            "del fundador; destination='local' lo guarda en el servidor sin tocar su Drive ni su cuota. "
            "Preguntale al fundador cuál prefiere antes de crearlo, salvo que ya te lo haya dicho. Queda "
            "indexado de inmediato en ambos casos — buscable con drive_search_knowledge sin esperar la "
            "próxima corrida de indexación."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string", "description": "Texto del documento, en Markdown si el formato lo aprovecha."},
                "format": {"type": "string", "enum": ["markdown", "pdf", "google_doc"]},
                "destination": {"type": "string", "enum": ["drive", "device", "server"], "description": "Por defecto 'drive'. 'server' solo disponible para el fundador."},
            },
            "required": ["title", "content"],
        },
    },
    {
        "name": "drive_create_spreadsheet",
        "description": (
            "Crea una planilla real. format='xlsx' genera un archivo Excel; format='google_sheet' crea un "
            "Google Sheet editable nativo (solo con destination='drive'). destination='drive' la sube a la "
            "carpeta 'Snarf - Archivos' del Drive del fundador; destination='local' la guarda en el "
            "servidor sin tocar su Drive. Preguntale al fundador cuál prefiere antes de crearla, salvo que "
            "ya te lo haya dicho. Queda indexada de inmediato en ambos casos."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "rows": {
                    "type": "array",
                    "description": "Filas de la planilla; cada fila es un array de valores (texto o número). La primera fila suele ser el encabezado.",
                    "items": {"type": "array"},
                },
                "format": {"type": "string", "enum": ["xlsx", "google_sheet"]},
                "destination": {"type": "string", "enum": ["drive", "device", "server"], "description": "Por defecto 'drive'. 'server' solo disponible para el fundador."},
            },
            "required": ["title", "rows"],
        },
    },
    {
        "name": "drive_create_presentation",
        "description": (
            "Crea una presentación real. format='pptx' genera un archivo PowerPoint; format='google_slide' "
            "crea un Google Slides editable nativo (solo con destination='drive'). destination='drive' la "
            "sube a la carpeta 'Snarf - Archivos' del Drive del fundador; destination='local' la guarda en "
            "el servidor sin tocar su Drive. Preguntale al fundador cuál prefiere antes de crearla, salvo "
            "que ya te lo haya dicho. Queda indexada de inmediato en ambos casos."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "slides": {
                    "type": "array",
                    "description": "Una entrada por diapositiva, además del título.",
                    "items": {
                        "type": "object",
                        "properties": {"title": {"type": "string"}, "body": {"type": "string"}},
                    },
                },
                "format": {"type": "string", "enum": ["pptx", "google_slide"]},
                "destination": {"type": "string", "enum": ["drive", "device", "server"], "description": "Por defecto 'drive'. 'server' solo disponible para el fundador."},
            },
            "required": ["title", "slides"],
        },
    },
]


class Orchestrator:
    def __init__(self, user_id: str = DEFAULT_USER_ID):
        self._user_id = user_id
        self._llm = AnthropicLLM()
        self._memory = EpisodicMemory()
        self._identity = load_identity()

        google_auth = GoogleAuth(user_id)
        self._drive = GoogleDrive(google_auth)
        self._gmail = GoogleGmail(google_auth)
        self._calendar = GoogleCalendar(google_auth)
        self._youtube = GoogleYouTube(google_auth)
        # Categorizar correos es una tarea acotada y mecánica, no necesita el
        # mismo modelo (más caro) que usa Snarf para conversar — un modelo
        # más chico y barato alcanza, y este Especialista puede elegir su
        # propia Capacidad de LLM sin afectar la de Snarf.
        self._gmail_digest = GmailDigestSpecialist(self._gmail, AnthropicLLM(model=GMAIL_DIGEST_MODEL), user_id)

        # Pipeline de vectorización de Drive (ver ADR 0028): mismo criterio de
        # "modelo barato para tarea acotada" que el digest de Gmail, esta vez
        # para describir imágenes. Cada pieza es una Capacidad chica e
        # inyectada, nunca buscada por el propio pipeline.
        content_extractor = ContentExtractor(
            drive=self._drive,
            pdf_extractor=PdfExtractor(),
            vision_llm=AnthropicLLM(model=DRIVE_VISION_MODEL),
            stt=ElevenLabsSTT(),
            ffmpeg_audio=FfmpegAudioExtractor(),
            docx_extractor=DocxExtractor(),
            pptx_extractor=PptxExtractor(),
            xlsx_extractor=XlsxExtractor(),
        )
        self._content_extractor = content_extractor
        user_index_dir = DRIVE_INDEX_DATA_DIR / user_id
        self._drive_indexer = DriveIndexer(
            drive=self._drive,
            extractor=content_extractor,
            embeddings=VoyageEmbeddings(),
            vector_store=VectorStore(persist_directory=str(user_index_dir / "chroma")),
            manifest_path=user_index_dir / "manifest.json",
        )
        self._document_publisher = DocumentPublisher(
            builder=DocumentBuilder(),
            drive=self._drive,
            indexer=self._drive_indexer,
            local_store=LocalFileStore(LOCAL_FILES_DATA_DIR / user_id),
            user_id=user_id,
            # El destino 'server' (disco del propio servidor, sin subir a
            # Drive) es una herramienta de trabajo del fundador — cuando
            # exista un segundo usuario real, no debe poder pedirlo.
            allow_server_storage=(user_id == DEFAULT_USER_ID),
        )

        self._tool_handlers = {
            "list_conversations": lambda i: self._memory.list_conversations(),
            "get_conversation": lambda i: self._memory.get_conversation(i.get("conversation_id", "")),
            "search_memory": lambda i: self._memory.search(i.get("query", "")),
            "drive_list_files": lambda i: self._drive.list_files(page_size=i.get("page_size", 50), query=i.get("query")),
            "drive_read_file": lambda i: self._read_drive_file(i["file_id"], i["mime_type"]),
            "drive_create_folder": lambda i: self._drive.create_folder(i["name"], parent_id=i.get("parent_id")),
            "drive_move_file": lambda i: self._drive.move_file(i["file_id"], i["new_parent_id"]),
            "gmail_list_messages": lambda i: self._gmail.list_messages(max_results=i.get("max_results", 10), query=i.get("query")),
            "gmail_read_message": lambda i: self._gmail.read_message(i["message_id"]),
            "gmail_list_labels": lambda i: self._gmail.list_labels(),
            "gmail_create_label": lambda i: self._gmail.create_label(i["name"]),
            "gmail_modify_message_labels": lambda i: self._gmail.modify_message_labels(
                i["message_id"], add_label_ids=i.get("add_label_ids"), remove_label_ids=i.get("remove_label_ids")
            ),
            "calendar_list_calendars": lambda i: self._calendar.list_calendars(),
            "calendar_list_upcoming_events": lambda i: self._calendar.list_upcoming_events(
                max_results=i.get("max_results", 10), calendar_id=i.get("calendar_id", "primary")
            ),
            "calendar_search_events": lambda i: self._calendar.search_events(
                i["query"], calendar_id=i.get("calendar_id", "primary"), max_results=i.get("max_results", 10)
            ),
            "youtube_list_subscriptions": lambda i: self._youtube.list_subscriptions(max_results=i.get("max_results", 25)),
            "youtube_list_liked_videos": lambda i: self._youtube.list_liked_videos(max_results=i.get("max_results", 25)),
            "gmail_send_message": self._tool_gmail_send_message,
            "calendar_create_event": self._tool_calendar_create_event,
            "calendar_create_calendar": self._tool_calendar_create_calendar,
            "calendar_delete_calendar": self._tool_calendar_delete_calendar,
            "calendar_delete_event": self._tool_calendar_delete_event,
            "calendar_move_event": self._tool_calendar_move_event,
            "gmail_delete_label": self._tool_gmail_delete_label,
            "drive_delete_file": self._tool_drive_delete_file,
            "gmail_summarize_inbox": self._tool_gmail_summarize_inbox,
            "drive_index_scan": lambda i: self._drive_indexer.scan(query=i.get("query")),
            "drive_index_catalog_unsupported": lambda i: self._drive_indexer.catalog_unsupported(query=i.get("query")),
            "drive_index_start": lambda i: self._drive_indexer.start(query=i.get("query")),
            "drive_index_status": lambda i: self._drive_indexer.status(),
            "drive_index_stop": lambda i: self._drive_indexer.stop(),
            "drive_search_knowledge": lambda i: self._drive_indexer.search(i["query"], top_k=i.get("top_k", 5)),
            "drive_create_document": lambda i: self._document_publisher.create_document(
                i["title"], i["content"], format=i.get("format", "markdown"), destination=i.get("destination", "drive")
            ),
            "drive_create_spreadsheet": lambda i: self._document_publisher.create_spreadsheet(
                i["title"], i["rows"], format=i.get("format", "xlsx"), destination=i.get("destination", "drive")
            ),
            "drive_create_presentation": lambda i: self._document_publisher.create_presentation(
                i["title"], i["slides"], format=i.get("format", "pptx"), destination=i.get("destination", "drive")
            ),
        }

    @property
    def llm_available(self) -> bool:
        return self._llm.available

    @property
    def memory(self) -> EpisodicMemory:
        return self._memory

    @property
    def drive(self) -> GoogleDrive:
        return self._drive

    @property
    def gmail(self) -> GoogleGmail:
        return self._gmail

    @property
    def calendar(self) -> GoogleCalendar:
        return self._calendar

    @property
    def youtube(self) -> GoogleYouTube:
        return self._youtube

    @property
    def gmail_digest(self) -> GmailDigestSpecialist:
        return self._gmail_digest

    @property
    def drive_indexer(self) -> DriveIndexer:
        return self._drive_indexer

    @property
    def document_publisher(self) -> DocumentPublisher:
        return self._document_publisher

    def warmup(self) -> None:
        self._llm.warmup()

    def _read_drive_file(self, file_id: str, mime_type: str) -> str | dict:
        # Antes llamaba directo a GoogleDrive.read_file_text() (texto plano /
        # Google Docs, decodifica bytes crudos como UTF-8 para cualquier otra
        # cosa) — un PDF, Word, imagen o audio se leía como bytes de glifo o
        # binario ilegible. ContentExtractor ya sabe extraer cada tipo de
        # verdad (mismo pipeline que la indexación de Drive, ADR 0028) —
        # reusarlo acá cierra esa brecha en vez de mantener dos caminos que
        # pueden desalinearse (ADR pendiente de registrar).
        result = self._content_extractor.extract({"id": file_id, "mimeType": mime_type})
        if not result.ok:
            return {"error": result.skipped_reason}
        return result.text

    @staticmethod
    def _pending(preview: dict) -> dict:
        return {
            "status": "pending_confirmation",
            "preview": preview,
            "instructions": (
                "No se ejecutó nada todavía. Mostrale esta vista previa al fundador tal "
                "cual y pedile confirmación explícita antes de volver a llamar a esta "
                "herramienta con confirmed=true."
            ),
        }

    def _tool_gmail_send_message(self, i: dict) -> dict:
        if not i.get("confirmed"):
            return self._pending({"to": i.get("to"), "subject": i.get("subject"), "body": i.get("body")})
        result = self._gmail.send_message(i["to"], i["subject"], i["body"])
        return {"status": "sent", "id": result.get("id")}

    def _tool_calendar_create_event(self, i: dict) -> dict:
        if not i.get("confirmed"):
            return self._pending(
                {
                    "summary": i.get("summary"),
                    "start": i.get("start_iso"),
                    "end": i.get("end_iso"),
                    "description": i.get("description"),
                    "location": i.get("location"),
                    "calendar_id": i.get("calendar_id", "primary"),
                }
            )
        result = self._calendar.create_event(
            i["summary"],
            i["start_iso"],
            i["end_iso"],
            description=i.get("description"),
            location=i.get("location"),
            calendar_id=i.get("calendar_id", "primary"),
        )
        return {"status": "created", "id": result.get("id"), "link": result.get("htmlLink")}

    def _tool_calendar_create_calendar(self, i: dict) -> dict:
        if not i.get("confirmed"):
            return self._pending({"summary": i.get("summary"), "description": i.get("description")})
        result = self._calendar.create_calendar(i["summary"], description=i.get("description"))
        return {"status": "created", "id": result.get("id")}

    def _tool_calendar_delete_calendar(self, i: dict) -> dict:
        if not i.get("confirmed"):
            return self._pending({"calendar_id": i.get("calendar_id")})
        self._calendar.delete_calendar(i["calendar_id"])
        return {"status": "deleted", "calendar_id": i["calendar_id"]}

    def _tool_calendar_delete_event(self, i: dict) -> dict:
        calendar_id = i.get("calendar_id", "primary")
        if not i.get("confirmed"):
            return self._pending({"event_id": i.get("event_id"), "calendar_id": calendar_id})
        self._calendar.delete_event(i["event_id"], calendar_id=calendar_id)
        return {"status": "deleted", "event_id": i["event_id"]}

    def _tool_calendar_move_event(self, i: dict) -> dict:
        if not i.get("confirmed"):
            return self._pending(
                {
                    "event_id": i.get("event_id"),
                    "source_calendar_id": i.get("source_calendar_id"),
                    "destination_calendar_id": i.get("destination_calendar_id"),
                }
            )
        result = self._calendar.move_event(i["event_id"], i["source_calendar_id"], i["destination_calendar_id"])
        return {"status": "moved", "id": result.get("id")}

    def _tool_gmail_delete_label(self, i: dict) -> dict:
        if not i.get("confirmed"):
            return self._pending({"label_id": i.get("label_id")})
        self._gmail.delete_label(i["label_id"])
        return {"status": "deleted", "label_id": i["label_id"]}

    def _tool_gmail_summarize_inbox(self, i: dict) -> dict:
        if i.get("force_refresh"):
            return self._gmail_digest.refresh()
        return self._gmail_digest.cached_digest() or self._gmail_digest.refresh()

    def _tool_drive_delete_file(self, i: dict) -> dict:
        if not i.get("confirmed"):
            return self._pending({"file_id": i.get("file_id")})
        self._drive.delete_file(i["file_id"])
        return {"status": "deleted", "file_id": i["file_id"]}

    def _handle_tool(self, name: str, tool_input: dict) -> object:
        handler = self._tool_handlers.get(name)
        if not handler:
            activity_log.record(name, "unknown_tool")
            return {"error": f"herramienta desconocida: {name}"}
        started = time.monotonic()
        try:
            result = handler(tool_input)
            activity_log.record(name, "ok", duration_ms=(time.monotonic() - started) * 1000)
            return result
        except Exception as exc:
            activity_log.record(name, "error", duration_ms=(time.monotonic() - started) * 1000, error=str(exc))
            return {"error": str(exc)}

    def handle(self, channel_name: str, user_input: str, conversation_id: str | None = None) -> str:
        if not self._llm.available:
            response = (
                "[modo eco - ANTHROPIC_API_KEY no configurada, ver .env.example] "
                f"{user_input}"
            )
        else:
            system = SYSTEM_PREFIX + self._identity
            messages = []
            for entry in self._memory.recent(10, conversation_id=conversation_id):
                messages.append({"role": "user", "content": entry["input"]})
                messages.append({"role": "assistant", "content": entry["response"]})
            messages.append({"role": "user", "content": user_input})
            try:
                response = self._llm.generate(
                    system=system, messages=messages, tools=TOOLS, tool_handler=self._handle_tool
                )
            except Exception as exc:
                # Antes esto tiraba un 500 crudo hasta /send — un fallo real
                # del LLM (crédito agotado, rate limit, red) degrada con
                # gracia igual que /transcribe, en vez de romper la request.
                response = f"[error real del LLM, no pude responder: {exc}]"

        self._memory.append(channel_name, user_input, response, conversation_id=conversation_id)
        return response
