from snarf.capabilities.anthropic_llm import AnthropicLLM
from snarf.capabilities.google_auth import GoogleAuth
from snarf.capabilities.google_calendar import GoogleCalendar
from snarf.capabilities.google_drive import GoogleDrive
from snarf.capabilities.google_gmail import GoogleGmail
from snarf.capabilities.google_youtube import GoogleYouTube
from snarf.core.identity import load_identity
from snarf.memory.episodic import EpisodicMemory

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
    "gmail_read_message, calendar_list_upcoming_events, youtube_list_subscriptions, "
    "youtube_list_liked_videos. Usalas para responder con contexto real cuando el "
    "fundador pregunte por su correo, su agenda, sus archivos o sus videos.\n\n"
    "Además tenés gmail_send_message y calendar_create_event, que sí actúan sobre el "
    "mundo real (envían un correo real, crean un evento real). Son acciones de alto "
    "impacto (Constitution, Artículo VII) y su protocolo es obligatorio, siempre, sin "
    "excepción: (1) llamalas primero con confirmed=false (o sin ese campo) — no van a "
    "ejecutar nada, te van a devolver una vista previa; (2) mostrale esa vista previa al "
    "fundador tal cual, con claridad, y preguntale si confirma; (3) solo volvé a llamar "
    "a la misma herramienta con confirmed=true, y exactamente los mismos datos, si el "
    "fundador respondió de forma explícita e inequívoca que sí a ESA propuesta concreta, "
    "en este mismo intercambio. Nunca asumas una confirmación implícita, nunca la des "
    "por sentada de un mensaje anterior ambiguo, y nunca combines la propuesta y la "
    "ejecución en el mismo turno.\n\n"
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
        "description": "Lee el contenido de texto de un archivo de Drive dado su id y mimeType (solo texto: Google Docs, Sheets, texto plano).",
        "input_schema": {
            "type": "object",
            "properties": {"file_id": {"type": "string"}, "mime_type": {"type": "string"}},
            "required": ["file_id", "mime_type"],
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
        "name": "calendar_list_upcoming_events",
        "description": "Lista los próximos eventos del calendario principal del fundador.",
        "input_schema": {"type": "object", "properties": {"max_results": {"type": "integer"}}},
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
        "name": "gmail_send_message",
        "description": (
            "Envía un correo real desde el Gmail del fundador. Acción de alto impacto: primero "
            "llamala con confirmed=false para obtener una vista previa (no envía nada), mostrala "
            "al fundador, y solo llamala de nuevo con confirmed=true tras su confirmación "
            "explícita a esa propuesta concreta."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
                "confirmed": {
                    "type": "boolean",
                    "description": "true únicamente si el fundador ya confirmó explícitamente esta acción concreta.",
                },
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "calendar_create_event",
        "description": (
            "Crea un evento real en el calendario del fundador. Acción de alto impacto: mismo "
            "protocolo que gmail_send_message — primero confirmed=false para obtener una vista "
            "previa (no crea nada), mostrarla, y solo confirmed=true tras confirmación explícita."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "start_iso": {"type": "string", "description": "Inicio en ISO 8601 con zona horaria."},
                "end_iso": {"type": "string", "description": "Fin en ISO 8601 con zona horaria."},
                "description": {"type": "string"},
                "location": {"type": "string"},
                "confirmed": {
                    "type": "boolean",
                    "description": "true únicamente si el fundador ya confirmó explícitamente esta acción concreta.",
                },
            },
            "required": ["summary", "start_iso", "end_iso"],
        },
    },
]


class Orchestrator:
    def __init__(self):
        self._llm = AnthropicLLM()
        self._memory = EpisodicMemory()
        self._identity = load_identity()

        google_auth = GoogleAuth()
        self._drive = GoogleDrive(google_auth)
        self._gmail = GoogleGmail(google_auth)
        self._calendar = GoogleCalendar(google_auth)
        self._youtube = GoogleYouTube(google_auth)

    @property
    def llm_available(self) -> bool:
        return self._llm.available

    @property
    def memory(self) -> EpisodicMemory:
        return self._memory

    def warmup(self) -> None:
        self._llm.warmup()

    def _handle_tool(self, name: str, tool_input: dict) -> object:
        try:
            if name == "list_conversations":
                return self._memory.list_conversations()
            if name == "get_conversation":
                return self._memory.get_conversation(tool_input.get("conversation_id", ""))
            if name == "search_memory":
                return self._memory.search(tool_input.get("query", ""))
            if name == "drive_list_files":
                return self._drive.list_files(
                    page_size=tool_input.get("page_size", 50), query=tool_input.get("query")
                )
            if name == "drive_read_file":
                return self._drive.read_file_text(tool_input["file_id"], tool_input["mime_type"])
            if name == "gmail_list_messages":
                return self._gmail.list_messages(
                    max_results=tool_input.get("max_results", 10), query=tool_input.get("query")
                )
            if name == "gmail_read_message":
                return self._gmail.read_message(tool_input["message_id"])
            if name == "calendar_list_upcoming_events":
                return self._calendar.list_upcoming_events(max_results=tool_input.get("max_results", 10))
            if name == "youtube_list_subscriptions":
                return self._youtube.list_subscriptions(max_results=tool_input.get("max_results", 25))
            if name == "youtube_list_liked_videos":
                return self._youtube.list_liked_videos(max_results=tool_input.get("max_results", 25))
            if name == "gmail_send_message":
                if not tool_input.get("confirmed"):
                    return {
                        "status": "pending_confirmation",
                        "preview": {
                            "to": tool_input.get("to"),
                            "subject": tool_input.get("subject"),
                            "body": tool_input.get("body"),
                        },
                        "instructions": (
                            "No se envió nada todavía. Mostrale esta vista previa al fundador "
                            "tal cual y pedile confirmación explícita antes de volver a llamar "
                            "a esta herramienta con confirmed=true."
                        ),
                    }
                result = self._gmail.send_message(tool_input["to"], tool_input["subject"], tool_input["body"])
                return {"status": "sent", "id": result.get("id")}
            if name == "calendar_create_event":
                if not tool_input.get("confirmed"):
                    return {
                        "status": "pending_confirmation",
                        "preview": {
                            "summary": tool_input.get("summary"),
                            "start": tool_input.get("start_iso"),
                            "end": tool_input.get("end_iso"),
                            "description": tool_input.get("description"),
                            "location": tool_input.get("location"),
                        },
                        "instructions": (
                            "No se creó nada todavía. Mostrale esta vista previa al fundador "
                            "tal cual y pedile confirmación explícita antes de volver a llamar "
                            "a esta herramienta con confirmed=true."
                        ),
                    }
                result = self._calendar.create_event(
                    tool_input["summary"],
                    tool_input["start_iso"],
                    tool_input["end_iso"],
                    description=tool_input.get("description"),
                    location=tool_input.get("location"),
                )
                return {"status": "created", "id": result.get("id"), "link": result.get("htmlLink")}
        except Exception as exc:
            return {"error": str(exc)}
        return {"error": f"herramienta desconocida: {name}"}

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
            response = self._llm.generate(
                system=system, messages=messages, tools=TOOLS, tool_handler=self._handle_tool
            )

        self._memory.append(channel_name, user_input, response, conversation_id=conversation_id)
        return response
