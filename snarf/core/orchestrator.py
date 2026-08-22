import hashlib
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from snarf.capabilities.anthropic_llm import (
    DELIVERABLE_END,
    DELIVERABLE_START,
    SPEECH_END,
    SPEECH_START,
    LLMResponse,
    fallback_speech,
)
from snarf.capabilities.local_code_writer import LocalCodeWriter
from snarf.capabilities.discord import Discord
from snarf.capabilities.docx_extractor import DocxExtractor
from snarf.capabilities.document_builder import DocumentBuilder
from snarf.capabilities.ffmpeg_audio import FfmpegAudioExtractor
from snarf.capabilities.elevenlabs_stt import ElevenLabsSTT
from snarf.capabilities.epub_builder import EpubBuilder
from snarf.capabilities.google_auth import GoogleAuth
from snarf.capabilities.google_calendar import GoogleCalendar
from snarf.capabilities.google_drive import GoogleDrive
from snarf.capabilities.google_gmail import GoogleGmail
from snarf.capabilities.google_youtube import GoogleYouTube
from snarf.capabilities.local_file_store import LocalFileStore
from snarf.capabilities.notion import Notion
from snarf.capabilities.notion_auth import NotionAuth
from snarf.capabilities.pdf_extractor import PdfExtractor
from snarf.capabilities.pptx_extractor import PptxExtractor
from snarf.capabilities.voyage_embeddings import VoyageEmbeddings
from snarf.capabilities.web_search import TavilySearch
from snarf.capabilities.xlsx_extractor import XlsxExtractor
from snarf.core.identity import load_identity
from snarf.knowledge.document_publisher import DocumentPublisher
from snarf.knowledge.drive_indexer import DriveIndexer
from snarf.knowledge.episodic_conversation_source import EpisodicConversationSource
from snarf.knowledge.extraction import VISION_SYSTEM_PROMPT, ContentExtractor
# DASHBOARD_CURATOR_SYSTEM_PROMPT: DashboardCuratorSpecialist en sí se
# construye en app.py (no acá, ver ADR 0090), pero PROMPT_DEFAULTS de más
# abajo necesita el default real de los 20 prompts reales en un solo lugar
# para Fase 9.3 (ADR 0144) — este import es solo para ese mapeo.
from snarf.specialists.dashboard_curator import DASHBOARD_CURATOR_SYSTEM_PROMPT
from snarf.knowledge.indexer import KnowledgeIndexer
from snarf.knowledge.local_repo_source import LocalRepoKnowledgeSource
from snarf.knowledge.notion_source import NotionSource
from snarf.knowledge.vector_store import VectorStore
from snarf.memory.episodic import EpisodicMemory
from snarf.mcp.tools import MCP_EXPOSED_TOOLS
from snarf.runtime import (
    areas,
    data_backup,
    introspection,
    llm_routing,
    ops_health,
    os_audit,
    personality_prefs,
    process_control,
    prompt_registry,
    user_profile,
)
from snarf.executive.roles import ROLE_CONFIGS as EXECUTIVE_ROLE_CONFIGS
from snarf.executive.specialist import ExecutiveBoardSpecialist
from snarf.executive.team import DEFAULT_MAX_ROUNDS, TeamSession
from snarf.specialists.gmail_digest import SYSTEM_PROMPT as GMAIL_DIGEST_SYSTEM_PROMPT, GmailDigestSpecialist
from snarf.specialists.bug_reports import STATUSES as BUG_REPORT_STATUSES
from snarf.specialists.bug_reports import TRIAGE_SYSTEM_PROMPT, BugReports
from snarf.specialists.second_brain import SecondBrainManager
from snarf.specialists.project_manager import (
    PROJECTS_DIR,
    SUBFOLDER_SUGGESTION_SYSTEM_PROMPT,
    SUMMARY_SYSTEM_PROMPT as PROJECT_SUMMARY_SYSTEM_PROMPT,
    ProjectManager,
)
from snarf.specialists.productivity.calendar_brief import SYSTEM_PROMPT as CALENDAR_BRIEF_SYSTEM_PROMPT, CalendarBriefSpecialist
from snarf.specialists.productivity.morning_routine import (
    CLASSIFY_SYSTEM_PROMPT as MORNING_ROUTINE_CLASSIFY_SYSTEM_PROMPT,
    SYNTHESIZE_SYSTEM_PROMPT as MORNING_ROUTINE_SYNTHESIZE_SYSTEM_PROMPT,
    MorningRoutineSpecialist,
)
from snarf.specialists.sales.sponsor_inbox_triage import (
    SYSTEM_PROMPT as SPONSOR_INBOX_TRIAGE_SYSTEM_PROMPT,
    SponsorInboxTriageSpecialist,
)
from snarf.specialists.content.mode import BLOG_POST_CONFIG, NEWSLETTER_CONFIG, SOCIAL_POST_CONFIG
from snarf.specialists.content.specialist import ContentSpecialist
from snarf.specialists.agency.client_status import SYSTEM_PROMPT as CLIENT_STATUS_SYSTEM_PROMPT, ClientStatusSpecialist
from snarf.specialists.community.pulse import CommunityPulseSpecialist
from snarf.specialists.finance.books_categorize import (
    SYSTEM_PROMPT as BOOKS_CATEGORIZE_SYSTEM_PROMPT,
    BooksCategorizeSpecialist,
)
from snarf.specialists.finance.monthly_pnl import MonthlyPnLSpecialist
from snarf.specialists.document_writer import DocumentWriter
from snarf.specialists.finance_supervisor import FinanceSupervisor
from snarf.specialists.founder_mood import FounderMood
from snarf.specialists.research.mode import COMPETITOR_WATCH_CONFIG, DEEP_RESEARCH_CONFIG, TREND_SCAN_CONFIG
from snarf.specialists.research.specialist import ResearchSpecialist
from snarf.specialists.skill_factory import SkillFactorySpecialist
from snarf.telemetry import activity_log, context, detail, events, input_preprocessing, spans, usage_tracker

# Identidad del fundador — sigue siendo la ÚNICA con datos en las rutas
# globales de siempre (data/episodic_memory.jsonl y compañía, ver
# self._memory en __init__), preservadas tal cual por compatibilidad hacia
# atrás con sus 180+ conversaciones reales ya en disco. Desde Fase 3 del
# plan de multi-usuario (ADR 0137), app.py ya no instancia un único
# Orchestrator global — mantiene un registro por user_id (ver
# app.py::get_orchestrator) y cualquier user_id que NO sea este recibe rutas
# de datos propias bajo MEMORY_DATA_DIR, nunca comparte archivo con nadie
# más.
DEFAULT_USER_ID = "fundador"

# El modelo no tiene ninguna fuente confiable de "qué día es hoy" por su cuenta
# (solo su sentido de tiempo de entrenamiento, que ya se vio desactualizado en
# la práctica) — get_current_datetime existe para eso. Zona horaria real del
# fundador, no configurable todavía porque hoy hay un solo usuario real.
FOUNDER_TIMEZONE = "America/Argentina/Buenos_Aires"

# Qué proveedor/modelo usa cada rol (orchestrator, gmail_digest, drive_vision,
# project_summary, conversation_title) ya no se hardcodea acá — ver
# snarf/runtime/llm_routing.py (única fuente de verdad, configurable por el
# fundador desde la interfaz sin editar código).

DRIVE_INDEX_DATA_DIR = Path("data/drive_index")
LOCAL_FILES_DATA_DIR = Path("data/local_files")
# Memoria episódica de cualquier user_id que NO sea DEFAULT_USER_ID (ver
# comentario ahí) — un usuario de prueba nuevo nunca toca
# data/episodic_memory.jsonl, tiene su propio archivo acá desde su primera
# conversación.
MEMORY_DATA_DIR = Path("data/users")
# Knowledge Layer generalizada (ver KNOWLEDGE.md) — dominios más allá de
# 'personal' (que sigue viviendo en DRIVE_INDEX_DATA_DIR/DriveIndexer, sin
# tocar). Hoy solo 'code' tiene una fuente real conectada.
KNOWLEDGE_DATA_DIR = Path("data/knowledge")

# Qué tools son de alto impacto (protocolo de confirmación en dos pasos,
# ADR 0015) o de lectura masiva potencialmente costosa (ADR 0067) era hasta
# ahora conocimiento tribal repartido en ~11 métodos (cuáles llaman a
# self._pending()/self._bulk_read_gate()) — estas dos constantes lo vuelven
# un hecho chequeable por test (ver tests/test_mcp_server.py), no solo
# implícito en el código. Usadas por primera vez por el allowlist del
# servidor MCP (ver ADR 0093, snarf/mcp/tools.py): ningún tool de acá puede
# quedar expuesto ahí.
HIGH_IMPACT_TOOLS = frozenset({
    "gmail_send_message",
    "calendar_create_event",
    "calendar_create_calendar",
    "calendar_delete_calendar",
    "calendar_delete_event",
    "calendar_move_event",
    "gmail_delete_label",
    "drive_delete_file",
    "drive_share_file",
    "drive_update_document",
    "project_delete",
    # Skill Factory (Fase H, ver ADR 0095/0102): construir/activar una skill
    "skill_factory_build",
    "skill_factory_activate",
    # Fase I, rama Community: postear en Discord como el fundador/marca.
    "community_post_message",
    # Cockpit del fundador (Fase 9.1 adelantada, ADR 0137/0138): reinicia
    # infraestructura real de esta Mac.
    "ops_process_restart",
    # Lectura/escritura real del cuerpo de una nota de Notion (ADR 0175):
    # update_block reemplaza el texto de un bloque existente, delete_block
    # lo borra — ambos tocan contenido real ya escrito, mismo criterio que
    # drive_update_document/drive_delete_file.
    "notion_update_block",
    "notion_delete_block",
    "notion_update_table_cell",
    # Gaps de capability cerrados en ADR 0180 (Second Brain de Notion,
    # ROADMAP_SECOND_BRAIN_NOTION.md Fase A1): mover una página pierde en
    # silencio las properties que no matchean en la database destino, crear
    # una database y archivar tocan la estructura real del workspace del
    # fundador — mismo criterio que drive_delete_file/project_delete.
    "notion_move_page",
    "notion_create_database",
    "notion_archive_page",
    # Onboarding del Second Brain (ADR 0190): crea una página raíz + 4
    # databases reales en el workspace del fundador — mismo criterio que
    # notion_create_database, siempre confirmed.
    "second_brain_onboarding_auto_build",
})
BULK_READ_GATED_TOOLS = frozenset({
    "drive_list_files",
    "gmail_list_messages",
    "calendar_list_upcoming_events",
    "calendar_search_events",
    "youtube_list_subscriptions",
    "youtube_list_liked_videos",
})

BULK_READ_CONFIRM_THRESHOLD = 50

CONVERSATION_TITLE_SYSTEM_PROMPT = (
    "Generás títulos cortos para conversaciones de chat, a partir de su primer "
    "intercambio real. Respondé ÚNICAMENTE con el título en sí — sin comillas, "
    "sin punto final, sin explicación alrededor — de máximo 6 palabras, en "
    "español, que resuma de qué se trata para reconocerla en una lista."
)
CONVERSATION_TITLE_MAX_CHARS = 60

SYSTEM_PREFIX = (
    "Sos Snarf. A continuación se incluyen, en orden de jerarquía, los documentos "
    "que definen tu identidad, tu gobernanza y tu personalidad. Actuá en todo momento "
    "conforme a ellos.\n\n"
    "Cuando una respuesta se beneficie de estructura (explicaciones largas, listas de "
    "opciones, comparaciones, pasos a seguir, código), usá formato Markdown: encabezados "
    "(#, ##, ###), listas, **negrita**, citas con '>' y bloques de código con ```. Para "
    "respuestas conversacionales cortas, mantené texto simple y fluido, sin forzar "
    "estructura que no aporta. TODO link que compartas (un download_url, un link de Drive, "
    "cualquier URL) va SIEMPRE en sintaxis Markdown [texto](url) — nunca como URL pelada — "
    "porque en la interfaz del fundador un link plano no es clickeable.\n\n"
    f"Al final de CADA respuesta, sin excepción, agregá un bloque delimitado exactamente "
    f"así:\n{SPEECH_START}\n<versión hablada>\n{SPEECH_END}\n"
    "La versión hablada es la narración en voz de ESA MISMA respuesta que acabás de "
    "mostrar en pantalla — no es un resumen acortado, cubre todo lo sustancial de lo "
    "que está en pantalla, dicho con naturalidad para que se entienda escuchado en vez "
    "de leído: sin markdown, sin listas numeradas leídas literalmente, sin URLs "
    "deletreadas, sin encabezados leídos como tales. Si la respuesta en pantalla es "
    "larga (un plan, un análisis extenso), la narración hablada también lo es — nunca la "
    "acortes solo porque es larga. Nunca oculta información incómoda: un riesgo o un "
    "dato faltante que está en pantalla también va en la versión hablada. El bloque de "
    "habla nunca aparece en pantalla — se separa antes de mostrarte al fundador.\n\n"
    f"Además, SOLO cuando la respuesta contenga un entregable puntual y pedido "
    f"explícitamente (un plan, un documento, una copia, un texto concreto que el "
    f"fundador pidió que le armaras) y sea claramente distinguible de la charla o el "
    f"comentario alrededor, agregá un segundo bloque después del de habla, delimitado "
    f"exactamente así:\n{DELIVERABLE_START}\n<solo el entregable, nada más>\n"
    f"{DELIVERABLE_END}\n"
    "Este bloque es SOLO el entregable en sí — el plan, el documento, la copia — "
    "fraseado para voz igual que la narración hablada (sin markdown, sin URLs "
    "deletreadas), lo más completo posible, sin nada de lo que dijiste antes (el "
    "encuadre, la explicación de cómo está armado) ni de lo que planteás después. Es "
    "para que el fundador pueda escuchar únicamente lo que pidió, nada de la "
    "conversación alrededor. Si la respuesta es puramente conversacional y no hay "
    "ningún entregable puntual que aislar, no incluyas este bloque — la mayoría de las "
    "respuestas no lo necesitan. Tampoco aparece nunca en pantalla.\n\n"
    "Antes de empezar a escribir una respuesta larga (un documento extenso, un plan "
    "detallado, un texto de varios miles de caracteres), decidí DE ANTEMANO si conviene "
    "un documento real en vez de intentar que entre en pantalla — no esperes a que se "
    "corte a mitad de camino para recién ahí reaccionar. Si estimás que no va a entrar, "
    "generá directamente un documento con drive_create_document (format='markdown', o "
    "'google_doc' si destination='drive') con el contenido completo, y en la respuesta "
    "en pantalla avisá que lo hiciste y dale el link o el download_url. Preguntá el "
    "destino (drive/device/server) como con cualquier documento, salvo que ya te lo "
    "hayan dicho en este intercambio. Si igual una respuesta se corta (llegaste al "
    "límite sin haberlo previsto), no lo disimules: decilo explícitamente y ofrecé "
    "generar el documento con el contenido completo en el siguiente turno.\n\n"
    "Cuando armes un documento o entregable a partir de contenido que leíste de OTRA fuente (una "
    "nota de Notion, un archivo de Drive, un email, etc.): usá el texto real que te devolvió la "
    "herramienta de lectura en ESTE MISMO turno — nunca reuses un resumen o fragmento que vos "
    "mismo generaste en un turno anterior de la conversación como si fuera el contenido completo, "
    "aunque lo parezca (si en algún momento mostraste un fragmento y dijiste algo como 'el "
    "fragmento que aparece empieza con', ese texto NO es la fuente completa, es tu propio recorte). "
    "Nunca digas 'texto completo'/'contenido íntegro'/'ya generé el documento con todo' sin haber "
    "vuelto a leer la fuente real en esa misma llamada — Principio VI de FOUNDATION.md (Honestidad "
    "Intelectual) aplica también acá: mejor 'tomé un fragmento, ¿querés que traiga el resto?' que "
    "afirmar completitud sin haberla verificado de verdad (bug real, ver ADR 0177: un documento se "
    "presentó como 'con el texto completo' cuando en realidad solo tenía el fragmento inicial que "
    "Snarf ya había mostrado en el chat, no el cuerpo real de la nota).\n\n"
    "Si un pedido combina acciones ambiguas o no tenés ninguna herramienta real que lo "
    "resuelva (ej. te piden integrar con un sistema externo que no tenés conectado), "
    "decilo directo en la respuesta — qué podés hacer, qué no, y por qué — en vez de "
    "intentarlo a fuerza de llamadas a herramientas hasta quedarte sin margen y cortar "
    "el turno sin decir nada útil.\n\n"
    "Cada herramienta ya trae, en su propia descripción del schema, qué hace y cuándo "
    "usarla — no lo repitas ni lo asumas distinto de lo que ahí dice. Lo que sigue es "
    "SOLO guía que va más allá de la descripción de una tool puntual (cruza varias, o "
    "es un protocolo que no cabe ahí).\n\n"
    "list_conversations/get_conversation/search_memory son también la base de Memoria "
    "consistente (CHARACTER.md): si un pedido revela un hueco real de capacidad — algo "
    "que el fundador necesitó y ninguna herramienta tuya resuelve — señalalo como "
    "propuesta concreta en la respuesta, nunca lo construyas ni lo actives por tu cuenta "
    "(Constitution, Art. III y IV). Si el fundador pide explícitamente una revisión de "
    "patrones repetidos en conversaciones pasadas (nunca la hagas de forma automática o "
    "sin que la pidan), usá list_conversations + search_memory para juntar evidencia real "
    "antes de proponer candidatos a mejora o tarea nueva.\n\n"
    "Las herramientas de organización reversibles (etiquetas, mover/renombrar/crear "
    "carpetas) no requieren confirmación en dos pasos, pero usalas solo cuando el "
    "fundador lo pida, nunca por iniciativa propia.\n\n"
    "Toda herramienta que su propia descripción marque como 'alto impacto' (Constitution, "
    "Artículo VII) sigue este protocolo, obligatorio, siempre, sin excepción: (1) llamala "
    "primero con confirmed=false (o sin ese campo) — no va a ejecutar nada, te va a "
    "devolver una vista previa; (2) mostrale esa vista previa al fundador tal cual, con "
    "claridad, y preguntale si confirma; (3) solo volvé a llamarla con confirmed=true, y "
    "exactamente los mismos datos, si el fundador respondió de forma explícita e "
    "inequívoca que sí a ESA propuesta concreta, en este mismo intercambio. Nunca asumas "
    "una confirmación implícita, y nunca combines la propuesta y la ejecución en el mismo "
    "turno. calendar_move_event: mover un evento entre calendarios puede notificar a "
    "invitados si el evento tiene invitados, por eso lleva confirmación igual que borrar. "
    "drive_update_document tiene su propia excepción a este protocolo (ver su "
    "descripción) — no la repitas distinto de como está ahí.\n\n"
    "Si ya le dijiste al fundador, en este mismo turno o antes en esta conversación, que una "
    "herramienta de alto impacto NO puede ejecutarse por un motivo estructural real (una "
    "credencial que falta, una API externa deshabilitada, un permiso denegado — algo que no se "
    "arregla solo con confirmar de nuevo) y el fundador te pide repetir esa MISMA acción sin haber "
    "resuelto la causa real, no vuelvas a mostrar la vista previa de siempre como si nada hubiera "
    "pasado: recordale el motivo real primero, en esa misma respuesta, y preguntale cómo quiere "
    "seguir (resolver la causa, o una alternativa distinta) — nunca le hagas gastar otra ronda "
    "completa de confirmación en algo que ya sabés, por esta misma conversación, que va a fallar "
    "de nuevo exactamente igual (bug real, ver ADR 0177: un fundador tuvo que confirmar dos veces "
    "la misma edición de un Google Doc sabiendo Snarf, desde el turno anterior, que la API estaba "
    "deshabilitada).\n\n"
    "drive_list_files, gmail_list_messages, calendar_list_upcoming_events, "
    "calendar_search_events, youtube_list_subscriptions y youtube_list_liked_videos "
    "tienen un protocolo de confirmed EQUIVALENTE al de arriba, pero por un motivo "
    "distinto: no es que sean irreversibles, es que un pedido grande (más de 50 "
    "resultados) tiene un costo real, tanto en tokens (ese resultado se re-transmite en "
    "cada turno futuro de la conversación mientras siga en el historial) como en la "
    "cuota de la API externa — un pedido real de mil correos costó más de un dólar en "
    "una sola llamada. Mismos tres pasos que arriba, pero frasealo en términos de "
    "costo, no de irreversibilidad ('esto puede salir caro, ¿igual querés que traiga "
    "los N?'). Si el fundador confirma, ejecutá exactamente la cantidad que pidió — "
    "nunca la recortes en silencio, preguntar antes NUNCA es prohibir para siempre. "
    "Para pedidos razonables (50 o menos) no hace falta nada de esto, ejecutá "
    "directo.\n\n"
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
    "Además de Drive, tenés acceso al propio código y documentación de Snarf: "
    "codebase_search busca semánticamente ahí (requiere haber indexado antes con "
    "knowledge_index_start(domain='code'), sin costo real más allá de embeddings). "
    "knowledge_search(domain=...) es el mismo tipo de búsqueda generalizada a "
    "cualquier dominio de la Knowledge Layer — 'personal' (Drive) o 'code' ya tienen "
    "fuente real; el resto (business/trading/marketing/finance) todavía no, y el "
    "tool te lo va a decir explícito en vez de devolver algo inventado.\n\n"
    "También podés crear archivos reales: drive_create_document (markdown, pdf o un "
    "Google Doc editable), drive_create_spreadsheet (xlsx o Google Sheet) y "
    "drive_create_presentation (pptx o Google Slides). Cuando el destino sea "
    "destination='drive', preferí SIEMPRE el formato nativo de Google (format='google_doc' "
    "en drive_create_document, o el equivalente en los otros dos tools) por sobre markdown o "
    "pdf plano — es lo que se puede editar y compartir naturalmente ahí adentro. Markdown/pdf "
    "quedan para destination='device' o 'server', o cuando el fundador pida explícitamente "
    "ese formato. Todas aceptan tres destinos — "
    "preguntale siempre a quien te lo pidió cuál prefiere antes de crear, salvo que ya "
    "te lo haya dicho explícitamente en este intercambio: "
    "(1) destination='drive' — se guarda en la carpeta 'Snarf/Archivos' del Drive "
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
    "También tenés 'Proyectos': cada uno es una carpeta propia en el Drive del fundador "
    "(con subcarpetas propuestas automáticamente), un prompt/instrucciones propias, y sus "
    "propias listas de tareas y notas — project_create, project_list, project_get, "
    "project_set_prompt, project_add_task, project_complete_task, project_delete_task, "
    "project_add_note, project_delete_note, project_search (búsqueda semántica acotada a "
    "lo que se subió a ESE proyecto vía Snarf, no todo lo que haya en su carpeta de Drive) "
    "y project_delete (alto impacto, ver arriba). Cuando el fundador te pida trabajar 'en' "
    "o 'sobre' un Proyecto puntual, llamá project_get primero y seguí el prompt propio de "
    "ese proyecto para esa respuesta, además de tu personalidad de siempre — el prompt del "
    "proyecto complementa quién sos, nunca lo reemplaza.\n\n"
    "Convenciones para tareas y notas de Proyectos (todas de texto, no cambian el schema): "
    "(1) antes de agregar una tarea con project_add_task, si el proyecto tiene tareas o notas "
    "parecidas, usá project_search para chequear que no sea un duplicado — si lo es, avisá en "
    "vez de cargarla de nuevo; (2) para descartar una tarea sin perder por qué (no hay estado "
    "'descartada' en el schema, es binario hecha/pendiente), nunca la borres en silencio: "
    "primero project_add_note con el texto '[DESCARTADA: <motivo>] <texto original de la "
    "tarea>', recién después project_delete_task; (3) si una tarea o nota surgió de otra "
    "conversación o de un pedido puntual del fundador, agregá al final del texto algo como "
    "'(origen: <de qué conversación o cuándo salió>)' para no perder esa trazabilidad; (4) si "
    "una tarea depende de que otra se resuelva primero, agregá 'depende de: <id o descripción "
    "corta de la otra tarea>' al final de su texto; (5) antes de entregar un consolidado del "
    "backlog, contá cuántas tareas hay por tipo/prioridad y decilo primero en una línea, y si "
    "existe un consolidado anterior (buscalo con project_search o drive_search_knowledge), "
    "agregá una sección corta de continuidad: qué se agregó desde ese consolidado, qué se "
    "completó, qué sigue pendiente de antes. (6) una tarea de tipo 'especialista' (proponer un "
    "Specialist nuevo) no entra bien en una sola línea como un bug o una mejora — usá esta "
    "plantilla extendida en su texto: 'TIPO: especialista · Rol: <qué hace> · Disparador: "
    "<cuándo se invoca> · Herramientas requeridas: <cuáles> · Límites explícitos de autoridad: "
    "<qué NO puede hacer por su cuenta>'. (7) cuando un project_get o project_list te "
    "muestre un proyecto con muchas tareas sueltas sin completar (más de 15-20) o notas "
    "visiblemente viejas sin procesar, avisá proactivamente que conviene consolidar o "
    "purgar antes de seguir sumando — no lo calles ni lo dejes crecer en silencio. (8) si "
    "el fundador pide explícitamente un snapshot/consolidado del backlog de un proyecto "
    "en Drive (nunca de forma automática, solo a pedido): reuní tareas y notas con "
    "project_get, armalo en Markdown con fecha y el resumen numérico del punto (5), y "
    "crealo con drive_create_document(format='google_doc', destination='drive') dentro "
    "de una subcarpeta 'Seguimiento' del proyecto — si esa subcarpeta no existe todavía "
    "entre las subcarpetas del proyecto, guardalo en la carpeta principal del proyecto y "
    "avisá que 'Seguimiento' no existía.\n\n"
    "También tenés herramientas sobre el Notion del fundador (requieren NOTION_API_KEY "
    "configurada — si no lo está, vas a recibir un error explícito de la herramienta, no "
    "lo disimules, decile al fundador que falta configurar la integración): "
    "notion_search (buscar páginas/bases de datos por texto), notion_read_page (leer el "
    "texto COMPLETO de una página — recorre toggles, tablas y el bloque especial de "
    "transcripción de reuniones de Notion, ver ADR 0175), notion_create_page (crear una "
    "subpágina nueva con título y contenido) y notion_append_to_page (agregar contenido al "
    "final de una ya existente). "
    "Para trabajar con databases (bases de datos) reales del fundador: notion_get_database "
    "(trae el schema real de properties de esa database — SIEMPRE llamala primero antes de "
    "crear o actualizar un registro, para saber qué properties existen y de qué tipo es cada "
    "una — select/multi-select/date/number/checkbox/relation/etc — nunca inventes nombres o "
    "tipos de properties), notion_query_database (buscar/filtrar registros existentes) y "
    "notion_create_database_item/notion_update_page_properties (crear o modificar un registro, "
    "con las properties ya en la forma tipada exacta que exige esa database). "
    "notion_search/notion_read_page/notion_create_page/notion_append_to_page/notion_get_database/"
    "notion_query_database/notion_create_database_item/notion_update_page_properties son "
    "reversibles desde el propio Notion — no llevan protocolo de confirmed. "
    "Para editar o borrar contenido YA EXISTENTE dentro del cuerpo de una página (no solo "
    "agregar al final): notion_list_blocks trae cada fragmento real con su block_id y su type "
    "— llamala siempre antes de tocar nada, nunca inventes un block_id. notion_update_block "
    "reemplaza el texto de un bloque puntual (protocolo de confirmed una vez por bloque por "
    "conversación, igual que drive_update_document); para una celda de tabla real (type='table_row' "
    "en notion_list_blocks) usá notion_update_table_cell en vez de notion_update_block — una fila "
    "de tabla no tiene texto único, tiene columnas, y esta tool arma el payload correcto sin perder "
    "las demás columnas (mismo protocolo de confirmed que notion_update_block). notion_delete_block "
    "borra un bloque (protocolo "
    "de confirmed obligatorio SIEMPRE, cada vez, igual que drive_delete_file — nunca lo trates "
    "como ya confirmado por una edición anterior en la misma nota). "
    "notion_index_start/notion_index_status vectorizan ese Notion (páginas y filas de databases) "
    "al dominio 'personal' de la Knowledge Layer, mismo criterio que drive_index_start — usalos "
    "solo cuando el fundador lo pida explícitamente. "
    "Gaps de estructura (ADR 0180): notion_create_database crea una database NUEVA bajo una página "
    "(distinto de notion_create_database_item, que crea un registro dentro de una ya existente); "
    "notion_move_page cambia una página de database — SIEMPRE avisá antes qué properties se van a "
    "perder si no matchean en la destino, Notion las descarta en silencio; notion_archive_page/"
    "notion_restore_page mandan una página a la papelera y la recuperan de ahí. "
    "notion_move_page/notion_create_database/notion_archive_page son de alto impacto (confirmed "
    "obligatorio siempre). notion_update_page_cover/notion_update_page_icon (y sus equivalentes de "
    "database) cambian portada/ícono, reversibles, sin confirmed.\n\n"
    "Second Brain (ver ROADMAP_SECOND_BRAIN_NOTION.md, ADR 0179/0182): si el fundador ya organiza su "
    "Notion con la jerarquía Área→Proyecto→Recursos/Archivo (método PARA), second_brain_status te dice "
    "si está conectado (databases reales ya mapeadas) — si no lo está, decilo explícito, no inventes "
    "una jerarquía que no existe. second_brain_list_areas/second_brain_get_area leen las Áreas reales; "
    "second_brain_list_projects (con o sin area_id)/second_brain_get_project leen los Proyectos; "
    "second_brain_list_resources/second_brain_list_archive leen lo asociado a un Proyecto puntual. "
    "second_brain_get_area_home trae el panorama agregado de un Área (Proyectos+Recursos+Archivo) más "
    "un análisis generado por LLM — usa el cacheado si existe; second_brain_area_report_refresh lo "
    "regenera a pedido explícito. second_brain_link_project vincula un Proyecto de Snarf ya existente a "
    "una página real de Notion (valida que exista antes de guardar). Todas de solo lectura o reversibles, "
    "reflejan Notion en vivo — nunca hay un segundo lugar de verdad acá.\n\n"
    "Onboarding del Second Brain (ADR 0190): si second_brain_status dice que no está conectado y el "
    "fundador (o un usuario nuevo) quiere empezar a usarlo, primero EXPLICÁ qué es la jerarquía Área→"
    "Proyecto→Recursos→Archivo (método PARA) y por qué — nunca construyas nada en silencio. Después "
    "preguntá: ¿prefiere que Snarf le arme la estructura desde cero (second_brain_onboarding_auto_build, "
    "requiere que antes comparta una página de su Notion con la integración y te pase su id — alto "
    "impacto, confirmed obligatorio), o ya tiene sus propias databases y prefiere mapearlas "
    "(second_brain_onboarding_suggest_mapping propone un mapeo por nombre, "
    "second_brain_onboarding_apply_mapping lo guarda recién cuando el fundador lo confirme)?\n\n"
    "Supervisores periódicos (ADR 0197): finance_supervisor_get_snapshot trae el último P&L real + "
    "interpretación del fundador — None si nunca configuró una Sheet (avisale que necesita "
    "finance_supervisor_set_sheet(file_id) primero, nunca inventes un estado financiero sin eso). "
    "founder_mood_get_snapshot trae señales de ánimo/estado interpretadas de la memoria episódica "
    "reciente, cada una con su base real (hecho/inferencia/hipótesis) — nunca la presentes como más "
    "certera de lo que esa etiqueta indica, y nunca la uses para diagnosticar ni dar consejos "
    "psicológicos, es solo contexto adicional para vos.\n\n"
    "Reportes de bugs (bug_report_create/bug_report_list/bug_report_get/bug_report_update_status): el "
    "fundador reporta un problema normalmente desde un botón dedicado de la interfaz, no en el chat — "
    "pero si te pregunta por un bug reportado (en ESTA conversación o en cualquier otra), usá "
    "bug_report_list/bug_report_get para traer el contexto real (conversación original, últimas turnos, "
    "categoría/severidad/plan si ya fue clasificado) ANTES de responder — nunca asumas que te acordás "
    "solo de un reporte viejo, y nunca inventes su estado o su plan. Un reporte clasificado automáticamente "
    "trae `plan` con lo que habría que investigar/corregir — mostráselo tal cual si el fundador pregunta "
    "qué se va a hacer, no lo repitas distinto.\n\n"
    "executive_board_consult convoca al board asesor de Inteligencia Ejecutiva (7 roles: cto, "
    "coo, research, ceo, cfo, cmo, creative) — nunca la llames por tu cuenta, solo cuando el "
    "fundador pida explícitamente una consulta al board. Elegí solo los roles relevantes a la "
    "pregunta (roles=None consulta a los 7, más lento y más caro que acotar). Cada afirmación "
    "de cada rol trae su propia basis (hecho/inferencia/hipótesis/estimación/opinión) — nunca "
    "muestres ese detalle crudo salvo pedido explícito, sintetizá vos las posturas en una "
    "respuesta coherente, marcando con claridad si hay desacuerdo real entre roles.\n\n"
    "executive_team_run convoca un EQUIPO (distinto del board, ver arriba) para producir y aprobar "
    "internamente un plan/borrador real — usala solo cuando el fundador pida explícitamente que un "
    "equipo produzca/itere algo, nunca por tu cuenta. Si el objetivo es planear un documento largo "
    "para escribir a Notion (ver document_write_start más abajo, ADR 0199), pedile en el objective "
    "que el equipo entregue un PLAN de secciones (una línea por sección, título y brief corto) — "
    "nunca el documento entero redactado, eso lo hace document_write_start sección por sección "
    "después, con su propio contexto acotado. Si hay una Sheet financiera configurada o señales de "
    "ánimo recientes relevantes al objetivo, sumá finance_supervisor_get_snapshot/"
    "founder_mood_get_snapshot como contexto real dentro del objective (ej. una restricción real de "
    "presupuesto) — nunca inventes esos datos si no están disponibles.\n\n"
    "document_write_start/document_write_continue/document_write_status (ADR 0199): para un "
    "documento LARGO hacia una página de Notion ya existente, dividido en secciones — nunca le "
    "pidas al LLM que redacte el documento entero en un solo mensaje tuyo, eso es exactamente lo "
    "que este mecanismo evita. document_write_start necesita el page_id real (conseguilo con "
    "notion_search o del proyecto vinculado, nunca lo inventes) y el plan de secciones (a mano, o "
    "el que aprobó executive_team_run). Escribe y verifica la primera sección en la misma llamada; "
    "para el resto, llamá document_write_continue repetidamente con el mismo write_id hasta que "
    "completed sea true — nunca le digas al fundador que el documento está listo si sections_stuck "
    "no viene vacío, mostrale cuáles quedaron atascadas tal cual. El progreso queda guardado: si la "
    "conversación se corta a mitad, una próxima conversación puede retomarla con document_write_status/"
    "document_write_continue sobre el mismo write_id.\n\n"
    "skill_factory_build/skill_factory_activate (ver ADR 0095/0102): cuando el fundador pida "
    "construir una skill nueva, VOS conversás en tu propia voz para juntar la especificación "
    "(rama, nombre, qué tiene que hacer, qué Capacidades ya existentes puede reusar) — nunca "
    "delegues esa conversación en la herramienta. Con la especificación clara, llamá "
    "skill_factory_build con confirmed=false (o sin ese campo) para previsualizar, mostrale el "
    "plan al fundador tal cual, y solo con un sí explícito volvé a llamarla con confirmed=true. Si "
    "devuelve status='built', mostrale que los tests reales pasaron y preguntale si confirma "
    "reiniciar el server para activarla — solo con un sí explícito nuevo llamá "
    "skill_factory_activate con confirmed=true (mismo protocolo de dos pasos, una confirmación "
    "nueva de verdad, nunca recordada de una construcción anterior). Si devuelve status='aborted' "
    "o 'failed', mostrale el motivo real al fundador tal cual, nunca lo disimules ni reintentes "
    "por tu cuenta.\n\n"
)

TOOLS = [
    {
        "name": "get_current_datetime",
        "description": (
            "Devuelve la fecha y hora real actual (servidor), con la zona horaria del "
            "fundador. Llamala antes de timestampear cualquier documento, evento o registro, "
            "o cuando necesites saber con certeza qué día es hoy — nunca lo asumas de tu "
            "propio conocimiento, no es confiable."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "measure_text_length",
        "description": (
            "Cuenta caracteres y palabras REALES (con código, no estimación) de un texto. "
            "Usala siempre que una tarea tenga un límite duro de longitud (ej. 'reducí esto a "
            "4000 caracteres'): generá el texto, medilo con esta herramienta, y si excede el "
            "límite recortá o regenerá más corto y volvé a medir antes de responder. Nunca "
            "reportes una cifra de longitud que no salga de esta herramienta."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
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
        "description": "Lista archivos de Google Drive del fundador, opcionalmente filtrados por una query de Drive. Un page_size grande (más de 50) tiene un costo real — protocolo de confirmed, ver más abajo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Query opcional. Aceptás sintaxis real de la API de Drive (ej. \"name contains "
                        "'informe'\") si la conocés, o directamente texto libre (ej. 'informe de ventas') "
                        "— si no parece sintaxis real de Drive, se busca automáticamente como texto "
                        "completo real."
                    ),
                },
                "page_size": {"type": "integer"},
                "confirmed": {"type": "boolean"},
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
        "description": "Lista correos recientes del Gmail del fundador (asunto, remitente, fecha, resumen), opcionalmente filtrados por una query de Gmail. Un max_results grande (más de 50) tiene un costo real — protocolo de confirmed, ver más abajo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Query opcional (sintaxis de búsqueda de Gmail)."},
                "max_results": {"type": "integer"},
                "confirmed": {"type": "boolean"},
            },
        },
    },
    {
        "name": "gmail_read_message",
        "description": (
            "Lee el contenido completo de un correo de Gmail dado su id. El id SIEMPRE "
            "tiene que salir de un resultado real de gmail_list_messages o de "
            "gmail_summarize_inbox (campo 'messages'[].id de su resultado) — nunca lo "
            "inventes ni lo derives del asunto/remitente/snippet. Si no tenés ese id a "
            "mano (por ejemplo, el correo se mencionó en una respuesta anterior pero no "
            "volviste a listar/resumir en este turno), llamá primero gmail_summarize_inbox "
            "o gmail_list_messages para conseguirlo, no asumas que no podés acceder al "
            "correo."
        ),
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
        "description": "Lista los próximos eventos de un calendario del fundador (por defecto, el principal). Solo eventos futuros. Un max_results grande (más de 50) tiene un costo real — protocolo de confirmed, ver más abajo.",
        "input_schema": {
            "type": "object",
            "properties": {"max_results": {"type": "integer"}, "calendar_id": {"type": "string"}, "confirmed": {"type": "boolean"}},
        },
    },
    {
        "name": "calendar_search_events",
        "description": "Busca eventos por texto en un calendario, sin restricción de fecha (incluye eventos pasados). Usala si un evento no aparece en calendar_list_upcoming_events. Un max_results grande (más de 50) tiene un costo real — protocolo de confirmed, ver más abajo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "calendar_id": {"type": "string", "description": "Por defecto, 'primary'."},
                "max_results": {"type": "integer"},
                "confirmed": {"type": "boolean"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "youtube_list_subscriptions",
        "description": "Lista los canales de YouTube a los que está suscripto el fundador. Un max_results grande (más de 50) tiene un costo real — protocolo de confirmed, ver más abajo.",
        "input_schema": {"type": "object", "properties": {"max_results": {"type": "integer"}, "confirmed": {"type": "boolean"}}},
    },
    {
        "name": "youtube_list_liked_videos",
        "description": "Lista videos de YouTube que el fundador marcó como 'me gusta'. Un max_results grande (más de 50) tiene un costo real — protocolo de confirmed, ver más abajo.",
        "input_schema": {"type": "object", "properties": {"max_results": {"type": "integer"}, "confirmed": {"type": "boolean"}}},
    },
    {
        "name": "gmail_summarize_inbox",
        "description": (
            "Interpreta los correos recientes de Gmail: los agrupa por categoría y señala cuáles "
            "conviene revisar y por qué. Usala para un pedido acotado a SOLO el correo (ej. "
            "'resumime el correo', 'qué tengo en la bandeja') — si el fundador pregunta por el "
            "arranque del día en general (ej. '¿qué tenemos para hoy?', '¿cómo arranco el día?'), "
            "usá morning_routine en su lugar, que ya combina esto con la agenda y con el detalle "
            "real de lo urgente. Por defecto devuelve la última interpretación disponible (no hace "
            "una llamada nueva cada vez); usá force_refresh=true solo si el fundador pide "
            "explícitamente una versión actualizada ahora mismo. OJO: la categorización "
            "(urgente/revisar/etc) se arma solo con remitente+asunto+fragmento corto de cada correo, "
            "NUNCA con el cuerpo completo — si el fundador pide el detalle de un correo puntual que "
            "salió acá como urgente/prioritario, o si vos mismo necesitás leerlo para poder "
            "responder algo accionable, llamá gmail_read_message con el id real de ESE correo (está "
            "en el campo 'messages' del resultado de esta misma tool, un array con "
            "id/subject/from/date por mensaje) antes de responder — nunca showear la categorización "
            "como si fuera el contenido, y nunca digas que no podés acceder al correo sin haber "
            "llamado gmail_read_message primero."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"force_refresh": {"type": "boolean"}},
        },
    },
    {
        "name": "calendar_brief",
        "description": (
            "Interpreta los próximos eventos reales del Google Calendar del fundador en un resumen "
            "accionable — agrupa por día, señala conflictos de horario reales. Usala para un pedido "
            "acotado a SOLO la agenda (ej. 'resumime la agenda', 'qué tengo agendado') — si el "
            "fundador pregunta por el arranque del día en general (ej. '¿qué tenemos para hoy?', "
            "'¿cómo arranco el día?'), usá morning_routine en su lugar, que ya combina esto con el "
            "correo. Por defecto devuelve la última interpretación disponible; usá force_refresh=true "
            "solo si el fundador pide explícitamente una versión actualizada ahora mismo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"force_refresh": {"type": "boolean"}},
        },
    },
    {
        "name": "morning_routine",
        "description": (
            "Arma la rutina matutina completa del fundador en UNA sola llamada: agenda del día + "
            "correos agrupados por categoría, y ya viene con el cuerpo real leído (no solo el "
            "fragmento) de los correos que la propia interpretación marcó como urgentes o que "
            "requieren una acción concreta — nunca hace falta encadenar gmail_read_message a mano "
            "después de esta tool para los prioritarios, ya está resuelto adentro. Usala cuando el "
            "fundador pregunte algo como '¿qué tenemos para hoy?', '¿cómo arranco el día?', 'dame el "
            "pantallazo de la mañana' o similar — para un pedido acotado a solo correo o solo agenda, "
            "usá gmail_summarize_inbox o calendar_brief en su lugar. Por defecto devuelve la última "
            "interpretación disponible (no hace una llamada nueva cada vez); usá force_refresh=true "
            "solo si el fundador pide explícitamente una versión actualizada ahora mismo. Si igual "
            "necesitás el detalle de un correo que esta tool NO marcó como prioritario, llamá "
            "gmail_read_message con su id real (está en el campo 'messages' del resultado)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "force_refresh": {"type": "boolean"},
                "max_messages": {"type": "integer"},
                "max_events": {"type": "integer"},
            },
        },
    },
    {
        "name": "research_deep_dive",
        "description": (
            "Investiga un tema a fondo: búsqueda web real (Tavily, si está configurado) + "
            "transcripciones reales de videos de YouTube si se pasan URLs — sintetiza un informe "
            "estructurado, lo publica como documento real en Drive y lo deja indexado (buscable con "
            "knowledge_search/drive_search_knowledge de inmediato). Si ninguna fuente real está "
            "disponible, lo dice explícito en vez de inventar un informe."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string"},
                "video_urls": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["topic"],
        },
    },
    {
        "name": "research_trend_scan",
        "description": (
            "Igual que research_deep_dive, pero enfocado en detectar tendencias/patrones reales que "
            "se repiten entre varias fuentes distintas sobre un tema — nunca una tendencia basada en "
            "una sola mención."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string"},
                "video_urls": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["topic"],
        },
    },
    {
        "name": "research_competitor_watch",
        "description": (
            "Igual que research_deep_dive, pero enfocado en analizar actores/competidores reales de "
            "un mercado o nicho a partir de fuentes reales."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string"},
                "video_urls": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["topic"],
        },
    },
    {
        "name": "content_write_blog_post",
        "description": (
            "Redacta un borrador real de post de blog a partir de un brief, lo publica como "
            "documento real en Drive y lo deja indexado. Si pasás reference_material (datos reales "
            "sobre el fundador/su negocio), la redacción se basa en eso para cualquier afirmación "
            "concreta — nunca inventa una cifra o hecho que no esté ahí."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"brief": {"type": "string"}, "reference_material": {"type": "string"}},
            "required": ["brief"],
        },
    },
    {
        "name": "content_write_social_post",
        "description": "Igual que content_write_blog_post, pero para un post corto de redes sociales.",
        "input_schema": {
            "type": "object",
            "properties": {"brief": {"type": "string"}, "reference_material": {"type": "string"}},
            "required": ["brief"],
        },
    },
    {
        "name": "content_write_newsletter",
        "description": "Igual que content_write_blog_post, pero para una newsletter en tono personal del fundador.",
        "input_schema": {
            "type": "object",
            "properties": {"brief": {"type": "string"}, "reference_material": {"type": "string"}},
            "required": ["brief"],
        },
    },
    {
        "name": "sales_sponsor_inbox_triage",
        "description": (
            "Interpreta correos recientes de Gmail que podrían ser oportunidades reales de sponsor/"
            "partnership (búsqueda acotada, no la bandeja entera) — separa oportunidades reales de "
            "menciones casuales de la palabra clave, y señala cuáles conviene responder primero. "
            "Usala cuando el fundador pregunte algo como '¿tengo propuestas de sponsors?' o similar. "
            "Por defecto devuelve la última interpretación disponible; usá force_refresh=true solo "
            "si el fundador pide explícitamente una versión actualizada ahora mismo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"force_refresh": {"type": "boolean"}},
        },
    },
    {
        "name": "finance_books_categorize",
        "description": (
            "Lee una Google Sheet real de transacciones (file_id, mantenida por el fundador o "
            "exportada de su banco/contable — columnas date/description/amount o "
            "fecha/descripcion/monto) y categoriza cada transacción real vía LLM. Nunca inventa una "
            "transacción que no esté en la Sheet real."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"file_id": {"type": "string"}},
            "required": ["file_id"],
        },
    },
    {
        "name": "finance_monthly_pnl",
        "description": (
            "Calcula un P&L real y determinístico (ingresos, gastos por categoría, neto) sobre "
            "transacciones YA categorizadas (ver finance_books_categorize) — nunca un LLM, es una "
            "suma real sobre montos reales."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "transactions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"amount": {"type": "number"}, "category": {"type": "string"}},
                    },
                }
            },
            "required": ["transactions"],
        },
    },
    {
        "name": "community_pulse",
        "description": (
            "Métricas reales de la comunidad de Discord del fundador (miembros, mensajes recientes, "
            "autores activos) — determinístico, nunca inventa una cifra. Si Discord todavía no está "
            "configurado, lo dice explícito."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"message_limit": {"type": "integer", "description": "Default 100."}},
        },
    },
    {
        "name": "community_post_message",
        "description": (
            "ALTO IMPACTO. Postea un mensaje real en el canal de Discord de la comunidad, en nombre "
            "del fundador/marca. Protocolo de confirmed obligatorio, mismo criterio que "
            "gmail_send_message."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"content": {"type": "string"}},
            "required": ["content"],
        },
    },
    {
        "name": "agency_client_status",
        "description": (
            "Genera un status semanal real para el cliente de un Proyecto (tareas/notas reales del "
            "proyecto, ver project_get) y lo publica como documento real en Drive. Nunca inventa un "
            "avance que no esté reflejado en las tareas/notas reales."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"project_id": {"type": "string"}},
            "required": ["project_id"],
        },
    },
    {
        "name": "ops_system_health",
        "description": (
            "Diagnóstico real del sistema ahora mismo: disponibilidad real de LLM/Google, cuántas "
            "llamadas recientes reales del Orchestrator hubo y cuántas fallaron, tamaño real en "
            "disco de data/. Reúne señales que ya se registran, nunca inventa una cifra nueva."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"n": {"type": "integer", "description": "Cantidad de llamadas recientes a revisar. Default 50."}},
        },
    },
    {
        "name": "ops_backup_now",
        "description": (
            "Dispara un backup real ahora mismo (normalmente corre solo cada 6hs) — copia memoria "
            "episódica, logs, preferencias, Proyectos, etc. a data_backups/ con timestamp. Aditivo, "
            "nunca toca los datos en vivo, no requiere confirmación."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "ops_process_status",
        "description": (
            "Solo para el fundador. Estado real de los procesos/LaunchAgents propios de Snarf en "
            "esta Mac (server principal, servers MLX locales, Kokoro TTS, watchdog de memoria): si "
            "están corriendo, PID real, RAM real usada (rss_mb). Nunca inventa un dato: "
            "running=false/pid=null/rss_mb=null cuando de verdad no está corriendo."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "ops_process_restart",
        "description": (
            "ALTO IMPACTO. Solo para el fundador. Reinicia real (launchctl kickstart) uno de los "
            "servers locales de Snarf (MLX local, Kokoro TTS, watchdog) — nunca el server principal "
            "(com.snarf.server), que no puede reiniciarse a sí mismo desde acá. Protocolo de "
            "confirmed obligatorio, mismo criterio que community_post_message."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"label": {"type": "string", "description": "Ej. 'com.snarf.mlx-fast'."}},
            "required": ["label"],
        },
    },
    {
        "name": "gmail_send_message",
        "description": (
            "Envía un correo real desde el Gmail del fundador. Acción de alto impacto: protocolo "
            "de confirmed obligatorio. Si el destinatario es un contacto del fundador (no el "
            "fundador mismo), antes de redactar decidí si corresponde primera persona (como si el "
            "fundador mismo escribiera, sin mencionar a Snarf) o tercera persona (Snarf redactando "
            "en su nombre) — no asumas un modo fijo, evaluá el caso. Si es tercera persona: abrí "
            "con algo como 'Hola [nombre], [fundador] me pidió que te comparta esto...', identificate "
            "como 'el asistente de [fundador]' (nunca menciones 'IA' o 'inteligencia artificial'), "
            "desarrollá el contenido pedido, cerrá invitando a responder el mail con dudas o a hablar "
            "directamente con el fundador, y firmá 'Saludos, Snarf'."
        ),
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
        "name": "codebase_search",
        "description": (
            "Búsqueda semántica sobre el propio código y documentación de Snarf (snarf/**/*.py, "
            "adr/*.md, tests/**/*.py, y los documentos de la raíz del repo) — el dominio 'code' de "
            "la Knowledge Layer (ver KNOWLEDGE.md). Costo cero más allá de embeddings: no hace "
            "ninguna llamada de red para leer el contenido, ya vive en disco. Requiere haber "
            "indexado antes con knowledge_index_start(domain='code')."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}, "top_k": {"type": "integer"}},
            "required": ["query"],
        },
    },
    {
        "name": "knowledge_search",
        "description": (
            "Búsqueda semántica sobre un dominio real de la Knowledge Layer (ver KNOWLEDGE.md). "
            "domain='personal' busca sobre Drive Y Notion ya indexados juntos (mismo motor que "
            "drive_search_knowledge) — usá el parámetro opcional 'source' ('drive' o 'notion') para "
            "acotar a uno solo cuando el fundador pregunte puntualmente por su Notion (áreas, "
            "proyectos, notas, tareas) o puntualmente por Drive; domain='code' busca sobre el propio "
            "repositorio de Snarf; domain='conversations' busca sobre el propio historial de "
            "conversaciones (mismo motor que conversations_search, sin filtro por proyecto acá — usar "
            "conversations_search si hace falta filtrar). Los demás dominios "
            "(business/trading/marketing/finance) todavía no tienen fuente real conectada — devuelve "
            "eso explícito en vez de inventar resultados."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "domain": {
                    "type": "string",
                    "enum": ["personal", "code", "conversations", "business", "trading", "marketing", "finance"],
                },
                "top_k": {"type": "integer"},
                "source": {
                    "type": "string",
                    "enum": ["drive", "notion"],
                    "description": "Solo tiene efecto con domain='personal' — acota a una sola fuente.",
                },
            },
            "required": ["query", "domain"],
        },
    },
    {
        "name": "conversations_search",
        "description": (
            "Búsqueda semántica sobre el propio historial de conversaciones de Snarf (dominio "
            "'conversations' de la Knowledge Layer, ver KNOWLEDGE.md) — cada conversación completa es "
            "un ítem indexable, no mensaje por mensaje. `project_id` es opcional: si se pasa, acota la "
            "búsqueda solo a conversaciones asignadas a ese proyecto (mismo project_id real de "
            "project_list/project_get). Requiere haber indexado antes con "
            "knowledge_index_start(domain='conversations')."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "project_id": {"type": "string", "description": "Opcional — acota a un proyecto real."},
                "top_k": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "knowledge_index_start",
        "description": (
            "Arranca (o reanuda) en segundo plano la indexación de un dominio de la Knowledge Layer. "
            "domain='code' (el propio repositorio) y domain='conversations' (el propio historial) "
            "tienen una fuente real conectable por esta vía — domain='personal' se indexa con "
            "drive_index_start, no acá. Sin costo real de vendor más allá de embeddings (Voyage)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"domain": {"type": "string", "enum": ["code", "conversations"]}},
            "required": ["domain"],
        },
    },
    {
        "name": "knowledge_index_status",
        "description": "Progreso de la indexación de un dominio de la Knowledge Layer en curso (o de la última corrida).",
        "input_schema": {
            "type": "object",
            "properties": {"domain": {"type": "string", "enum": ["code", "conversations"]}},
            "required": ["domain"],
        },
    },
    {
        "name": "telemetry_cost_summary",
        "description": (
            "Costo real de operar Snarf (dólares reales por vendor — Anthropic/ElevenLabs/Voyage/etc. — "
            "en las últimas 24hs y últimos N días), calculado a partir de usage_log.jsonl real. Esto es el "
            "opex real de Snarf, no la caja/ingresos del negocio del fundador — esos todavía no tienen "
            "fuente real conectada (ver KNOWLEDGE.md, dominio 'business')."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"recent_days": {"type": "integer", "description": "Default 7."}},
        },
    },
    {
        "name": "system_introspect",
        "description": (
            "Catálogo real de Snarf en este momento: ruteo de modelo/proveedor por rol (incluida la "
            "junta ejecutiva), qué tools están disponibles (nombre + descripción, nunca el input_schema "
            "completo), y los 7 roles reales del board asesor. Mismo dato real que ya usa GET "
            "/n8n/introspect (ADR 0140) — solo lectura, ninguna implementación nueva de ningún dato."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "os_audit",
        "description": (
            "Auditoría real de solo lectura del propio repo de Snarf: ¿los paths que CLAUDE.md/"
            "MASTER_MAP.md referencian existen de verdad en disco (routing roto)?, fechas reales de "
            "ADRs/CHANGELOG/roadmaps (¿algo quedó congelado?), archivos sueltos en la raíz, higiene de "
            "git (secretos trackeados, .gitignore real), y skills/agents de .claude/ rotos (SKILL.md "
            "faltante o frontmatter incompleto). Nunca modifica nada — devuelve señales crudas reales "
            "para que armes vos el reporte (nunca inventes hallazgos que no vengan de acá). Es la "
            "versión de este chequeo que corre desde tu propio chat — la Skill de Claude Code "
            "equivalente (.claude/skills/os-audit/SKILL.md) solo corre dentro de una sesión de Claude "
            "Code, nunca la invoques ni la menciones como si fuera lo mismo que esto."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "executive_board_consult",
        "description": (
            "Convoca al board asesor de Inteligencia Ejecutiva (ver COGNITION.md, ADR 0094/0098) — "
            "hasta 7 roles (cto/coo/research/ceo/cfo/cmo/creative) opinan en paralelo, cada uno desde "
            "un proceso separado con acceso de solo lectura a un subconjunto real y acotado de tus "
            "herramientas (nunca pueden ejecutar ni mutar nada). Cada afirmación de cada rol viene "
            "etiquetada con su basis real (hecho/inferencia/hipótesis/estimación/opinión) — nunca "
            "muestres ese detalle crudo al fundador salvo que lo pida explícitamente, en cambio "
            "sintetizá las posturas en tu propia voz. Nunca la llames por tu cuenta: solo cuando el "
            "fundador pida explícitamente una consulta al board (ej. 'preguntale al board', 'qué "
            "opinan mis asesores sobre X'). roles=None consulta a los 7; pasá una lista acotada "
            "cuando la pregunta claramente solo concierne a algunos (ej. una pregunta puramente "
            "técnica solo necesita cto)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "roles": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["cto", "coo", "research", "ceo", "cfo", "cmo", "creative"],
                    },
                },
            },
            "required": ["question"],
        },
    },
    {
        "name": "executive_team_run",
        "description": (
            "Convoca un EQUIPO de roles de la Inteligencia Ejecutiva (ADR 0198, distinto de "
            "executive_board_consult) para producir y aprobar internamente un artefacto real — un "
            "borrador de plan/campaña/documento, no solo opiniones. A diferencia del board (una sola "
            "ronda, nunca decide), el equipo itera: genera un borrador, cada rol lo critica con su "
            "propio criterio marcando objeciones BLOQUEANTE/SUGERENCIA/SIN OBJECIÓN, y si hay alguna "
            "bloqueante se revisa el borrador y se repite hasta max_rounds. El resultado indica "
            "approved_by_exhaustion=true si se aprobó por agotar las rondas sin resolver todas las "
            "objeciones — decíselo así de honesto al fundador, nunca como consenso real si no lo fue. "
            "El equipo NUNCA ejecuta ninguna tool mutante por su cuenta — el borrador vuelve a vos, y "
            "si el fundador quiere usarlo para algo real (ej. escribirlo a Notion), eso pasa por las "
            "tools normales con su propio gate. Nunca la llames por tu cuenta: solo cuando el fundador "
            "pida explícitamente que un equipo produzca/itere un plan o documento."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "objective": {"type": "string"},
                "roles": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["cto", "coo", "research", "ceo", "cfo", "cmo", "creative"],
                    },
                },
                "max_rounds": {"type": "integer"},
            },
            "required": ["objective", "roles"],
        },
    },
    {
        "name": "document_write_start",
        "description": (
            "Arranca la escritura confiable de un documento LARGO hacia una página de Notion ya "
            "existente (ADR 0199) — dividido en secciones, cada una generada y escrita por separado "
            "(nunca todo el documento en un solo prompt/llamada, evita el límite de tokens del modelo). "
            "Escribe y verifica (releyendo la página) la primera sección en esta misma llamada; para "
            "las siguientes hay que llamar document_write_continue repetidamente con el write_id que "
            "devuelve, una vez por sección, hasta que 'completed' sea true. El progreso queda persistido "
            "en disco — sobrevive un corte de sesión o un reinicio del server, se puede seguir después "
            "con document_write_continue/document_write_status sobre el mismo write_id. Usala solo "
            "cuando el fundador pida escribir un documento real y largo a una página de Notion "
            "concreta que ya exista (page_id) — nunca inventes el page_id, conseguilo antes con "
            "notion_search o del proyecto vinculado."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "page_id": {"type": "string"},
                "title": {"type": "string"},
                "objective": {"type": "string", "description": "Objetivo real del documento, da contexto a cada sección."},
                "sections": {
                    "type": "array",
                    "description": "Plan de secciones ya definido (ej. por executive_team_run) — una entrada por sección.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "brief": {"type": "string"},
                        },
                        "required": ["title"],
                    },
                },
            },
            "required": ["page_id", "title", "sections"],
        },
    },
    {
        "name": "document_write_continue",
        "description": (
            "Avanza UNA sección más de una escritura de documento ya arrancada con document_write_start "
            "(mismo write_id). Llamala repetidamente hasta que la respuesta diga completed=true. Si una "
            "sección queda en sections_stuck, algo falló de forma persistente (generación, escritura, o "
            "verificación) tras varios reintentos — decíselo explícito al fundador, nunca digas que el "
            "documento está listo si sections_stuck no está vacío."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"write_id": {"type": "string"}},
            "required": ["write_id"],
        },
    },
    {
        "name": "document_write_status",
        "description": "Progreso real de una escritura de documento (arrancada con document_write_start), sin avanzar ningún paso — de solo lectura.",
        "input_schema": {
            "type": "object",
            "properties": {"write_id": {"type": "string"}},
            "required": ["write_id"],
        },
    },
    {
        "name": "skill_factory_build",
        "description": (
            "ALTO IMPACTO. Construye una skill nueva de verdad, con el modelo local del fundador como "
            "motor de escritura (ver ADR 0095/0102/0130) — crea un módulo Specialist nuevo, su test, "
            "y suma el tool correspondiente al Orchestrator, siguiendo el Skill Framework (ADR "
            "0101). Solo llamala después de conversar vos mismo con el fundador para juntar la "
            "especificación (rama, nombre, descripción, y las aclaraciones que hagan falta) — vos "
            "hacés esa conversación en tu propia voz, nunca esta herramienta. Alcance estrictamente "
            "acotado a construir/activar una skill nueva: nunca edita FOUNDATION/CONSTITUTION/"
            "CHARACTER/COGNITION/MASTER_MAP ni código fuera de ese flujo — si el motor se sale de ese "
            "alcance, la construcción se aborta sola y te lo informa. Al ser un modelo local (más "
            "barato pero menos confiable que un modelo grande), esperá que falle más seguido que un "
            "pedido de código común — si devuelve status='failed' o 'aborted', mostrale el motivo "
            "real al fundador, nunca lo disimules. Cada construcción es una confirmación nueva, "
            "nunca se recuerda un 'sí' de una vez anterior."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "branch": {"type": "string", "description": "Rama del mapa (ej. research, finance, productivity)."},
                "skill_name": {"type": "string"},
                "description": {"type": "string"},
                "clarifying_answers": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"question": {"type": "string"}, "answer": {"type": "string"}},
                    },
                },
                "confirmed": {"type": "boolean"},
            },
            "required": ["branch", "skill_name", "description"],
        },
    },
    {
        "name": "skill_factory_activate",
        "description": (
            "ALTO IMPACTO. Activa una skill ya construida (status='built', ver skill_factory_status) "
            "reiniciando el server real — nunca queda 'caliente' sin reiniciar (ver ADR 0095/0102). "
            "Solo llamala después de que skill_factory_build haya devuelto status='built' con los "
            "tests reales pasando, y con una confirmación explícita nueva del fundador para ESTE "
            "reinicio puntual."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"proposal_id": {"type": "string"}, "confirmed": {"type": "boolean"}},
            "required": ["proposal_id"],
        },
    },
    {
        "name": "skill_factory_status",
        "description": "Estado real de una propuesta de skill (building/built/activated/aborted/failed), con el detalle de por qué si falló o se abortó.",
        "input_schema": {
            "type": "object",
            "properties": {"proposal_id": {"type": "string"}},
            "required": ["proposal_id"],
        },
    },
    {
        "name": "drive_create_document",
        "description": (
            "Crea un documento real y devuelve su link o ubicación. format='markdown' o 'pdf' generan el "
            "archivo tal cual; format='google_doc' crea un Google Doc editable nativo (solo con "
            "destination='drive'). destination='drive' lo sube a la carpeta 'Snarf/Archivos' del Drive "
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
            "carpeta 'Snarf/Archivos' del Drive del fundador; destination='local' la guarda en el "
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
            "sube a la carpeta 'Snarf/Archivos' del Drive del fundador; destination='local' la guarda en "
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
    {
        "name": "drive_rename_file",
        "description": "Renombra un archivo o carpeta real de Drive. Reversible y de bajo riesgo (no expone ni borra nada) — no requiere confirmación en dos pasos.",
        "input_schema": {
            "type": "object",
            "properties": {"file_id": {"type": "string"}, "new_name": {"type": "string"}},
            "required": ["file_id", "new_name"],
        },
    },
    {
        "name": "convert_to_epub",
        "description": (
            "Convierte un documento ya subido a Drive (PDF, TXT o Markdown) en un EPUB3 válido, listo para "
            "Kindle/Apple Books/lectores de ebooks, y lo sube de vuelta a la carpeta 'Snarf/Archivos' del "
            "Drive del fundador. Detecta automáticamente si el documento es un guion (diálogos "
            "'Nombre.- texto' con escenas/actos), un texto con capítulos, o texto corrido, y arma la "
            "navegación/portada acorde — forzá 'mode' solo si la autodetección da un resultado incorrecto. "
            "Usar cuando el fundador pida convertir un archivo a epub/ebook o 'formato para Kindle/lector'. "
            "Pedile título y autor si no los mencionó — no asumas datos si el documento ya los trae "
            "visibles (podés confirmarlos leyéndolo primero con drive_read_file). Solo funciona con PDFs "
            "con texto seleccionable, no escaneados/imagen."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file_id": {"type": "string", "description": "file_id de Drive del documento fuente."},
                "source_name": {
                    "type": "string",
                    "description": "Nombre real del archivo fuente en Drive, con extensión (ej. 'monologo.pdf') — necesario para saber cómo leerlo.",
                },
                "title": {"type": "string"},
                "author": {"type": "string"},
                "mode": {
                    "type": "string",
                    "enum": ["auto", "dialogue", "chapters", "flow"],
                    "description": "Por defecto 'auto' (autodetecta). Forzar solo si la autodetección se equivocó.",
                },
            },
            "required": ["file_id", "source_name", "title", "author"],
        },
    },
    {
        "name": "drive_share_file",
        "description": (
            "Da acceso real a un archivo de Drive: a una persona puntual (con email) o vía link público "
            "(sin email). Cambia quién puede ver/editar algo fuera de la cuenta del fundador — herramienta "
            "de alto impacto, mismo protocolo de confirmación en dos pasos que drive_delete_file."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file_id": {"type": "string"},
                "role": {"type": "string", "enum": ["reader", "writer", "commenter"], "description": "Por defecto 'reader'."},
                "email": {"type": "string", "description": "Si se omite, el archivo queda accesible por link público."},
                "confirmed": {"type": "boolean"},
            },
            "required": ["file_id"],
        },
    },
    {
        "name": "drive_update_document",
        "description": (
            "Reemplaza TODO el contenido de un Google Doc YA EXISTENTE por new_content (texto plano). "
            "Herramienta de alto impacto (modifica un documento real, no uno nuevo) — protocolo de "
            "confirmed obligatorio la primera vez que se edita CADA documento en una conversación; "
            "ediciones siguientes al MISMO documento, más adelante en la misma conversación, no hace "
            "falta volver a pedirle confirmación al fundador (ya la dio para ese documento en esta "
            "sesión) — llamá directo con confirmed=true. Para leer el contenido actual antes de decidir "
            "qué reemplazar, usá drive_read_file."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file_id": {"type": "string"},
                "new_content": {"type": "string", "description": "Texto plano completo que reemplaza todo el documento."},
                "confirmed": {"type": "boolean"},
            },
            "required": ["file_id", "new_content"],
        },
    },
    {
        "name": "project_create",
        "description": (
            "Crea un Proyecto nuevo de Snarf: carpeta propia en Drive (con subcarpetas propuestas "
            "automáticamente según el tipo de proyecto), prompt propio vacío, listas de tareas y notas "
            "vacías."
        ),
        "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
    },
    {
        "name": "project_list",
        "description": "Lista todos los Proyectos existentes: id, nombre, cantidad de tareas y notas.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "project_get",
        "description": "Detalle completo de un Proyecto: nombre, prompt propio, carpeta de Drive, tareas y notas.",
        "input_schema": {"type": "object", "properties": {"project_id": {"type": "string"}}, "required": ["project_id"]},
    },
    {
        "name": "project_set_prompt",
        "description": "Actualiza el prompt/instrucciones propias de un Proyecto.",
        "input_schema": {
            "type": "object",
            "properties": {"project_id": {"type": "string"}, "prompt": {"type": "string"}},
            "required": ["project_id", "prompt"],
        },
    },
    {
        "name": "project_add_task",
        "description": "Agrega una tarea a un Proyecto.",
        "input_schema": {
            "type": "object",
            "properties": {"project_id": {"type": "string"}, "text": {"type": "string"}},
            "required": ["project_id", "text"],
        },
    },
    {
        "name": "project_complete_task",
        "description": "Marca una tarea de un Proyecto como hecha, o la reabre si ya estaba hecha (alterna el estado).",
        "input_schema": {
            "type": "object",
            "properties": {"project_id": {"type": "string"}, "task_id": {"type": "string"}},
            "required": ["project_id", "task_id"],
        },
    },
    {
        "name": "project_delete_task",
        "description": "Borra una tarea de un Proyecto.",
        "input_schema": {
            "type": "object",
            "properties": {"project_id": {"type": "string"}, "task_id": {"type": "string"}},
            "required": ["project_id", "task_id"],
        },
    },
    {
        "name": "project_add_note",
        "description": "Agrega una nota a un Proyecto.",
        "input_schema": {
            "type": "object",
            "properties": {"project_id": {"type": "string"}, "text": {"type": "string"}},
            "required": ["project_id", "text"],
        },
    },
    {
        "name": "project_delete_note",
        "description": "Borra una nota de un Proyecto.",
        "input_schema": {
            "type": "object",
            "properties": {"project_id": {"type": "string"}, "note_id": {"type": "string"}},
            "required": ["project_id", "note_id"],
        },
    },
    {
        "name": "project_search",
        "description": (
            "Búsqueda semántica acotada a los archivos de un Proyecto puntual — solo encuentra contenido "
            "que se subió a ESE proyecto a través de Snarf (drive_create_document/spreadsheet/presentation "
            "o /files/upload con project_id), no todo lo que haya en su carpeta de Drive."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "query": {"type": "string"},
                "top_k": {"type": "integer"},
            },
            "required": ["project_id", "query"],
        },
    },
    {
        "name": "project_delete",
        "description": (
            "Borra el registro de un Proyecto (nombre, prompt, tareas, notas) — NUNCA borra la carpeta ni "
            "los archivos reales de Drive de ese proyecto. Herramienta de alto impacto, mismo protocolo de "
            "confirmación en dos pasos que drive_delete_file."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"project_id": {"type": "string"}, "confirmed": {"type": "boolean"}},
            "required": ["project_id"],
        },
    },
    {
        "name": "project_assign_conversation",
        "description": (
            "Asigna una conversación existente a un Proyecto — a partir de ahí, el prompt propio de ese "
            "proyecto se aplica automáticamente en todos los turnos de esa conversación, no solo cuando se "
            "lo menciona. Si la conversación ya pertenecía a otro proyecto, la reasigna (la respuesta indica "
            "de cuál a cuál, para trazabilidad). No reescribe el historial ya generado — solo cambia el "
            "comportamiento hacia adelante. Reversible, no requiere confirmación en dos pasos."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"project_id": {"type": "string"}, "conversation_id": {"type": "string"}},
            "required": ["project_id", "conversation_id"],
        },
    },
    {
        "name": "project_unassign_conversation",
        "description": (
            "Quita la asociación de una conversación con su Proyecto (vuelve a project_id nulo) — a partir "
            "de ahí, esa conversación vuelve a comportarse solo con el prompt base de Snarf, sin rastro del "
            "prompt del proyecto anterior. No borra la conversación. Reversible, no requiere confirmación."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"conversation_id": {"type": "string"}},
            "required": ["conversation_id"],
        },
    },
    {
        "name": "project_list_conversations",
        "description": (
            "Lista las conversaciones asociadas a un Proyecto puntual (id, título, fechas) — mismo formato "
            "que list_conversations. No busca sobre archivos subidos al proyecto (eso es project_search, "
            "una cosa distinta)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"project_id": {"type": "string"}},
            "required": ["project_id"],
        },
    },
    {
        "name": "bug_report_create",
        "description": (
            "Crea un reporte de bug real, con la conversación activa capturada como contexto — reversible "
            "(se puede descartar con bug_report_update_status), no lleva protocolo de confirmed. Usala "
            "solo cuando el fundador te pida explícitamente reportar/anotar un problema en la "
            "conversación (el flujo normal es el botón dedicado de la interfaz, esto es para cuando lo "
            "pide en el chat en su lugar)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"description": {"type": "string"}},
            "required": ["description"],
        },
    },
    {
        "name": "bug_report_list",
        "description": (
            "Lista los reportes de bugs del fundador (id, descripción, estado, categoría, severidad, "
            "fecha) — opcionalmente filtrados por status ('nuevo', 'clasificado', 'planificado', "
            "'en_progreso', 'resuelto', 'descartado'). Los reporta el fundador desde el botón de reporte "
            "de la interfaz, no algo que vos crees por tu cuenta salvo pedido explícito."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"status": {"type": "string", "enum": list(BUG_REPORT_STATUSES)}},
        },
    },
    {
        "name": "bug_report_get",
        "description": (
            "Trae el detalle completo de un reporte de bug puntual, incluido el contexto real capturado "
            "al momento de reportarlo (conversation_id y las últimas turnos de esa conversación) — usala "
            "SIEMPRE que el fundador pregunte por un bug reportado, para traer el contexto original en "
            "vez de asumir que te acordás solo, aunque sea una conversación distinta a esta."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"report_id": {"type": "string"}},
            "required": ["report_id"],
        },
    },
    {
        "name": "bug_report_update_status",
        "description": (
            "Cambia el estado de un reporte de bug (con una nota corta de qué pasó) — reversible, sin "
            "protocolo de confirmed, mismo criterio que project_add_note. Usala cuando el fundador pida "
            "explícitamente marcar un bug como resuelto/descartado/en progreso, o para dejar constancia "
            "real de que ya lo estás mirando."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "report_id": {"type": "string"},
                "status": {"type": "string", "enum": list(BUG_REPORT_STATUSES)},
                "note": {"type": "string"},
            },
            "required": ["report_id", "status"],
        },
    },
    {
        "name": "notion_search",
        "description": (
            "Busca páginas y bases de datos en el Notion del fundador por texto. Requiere NOTION_API_KEY "
            "configurada — si no está, devuelve un error explícito, no inventes resultados."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "notion_read_page",
        "description": (
            "Lee el texto plano COMPLETO de una página de Notion, dado su page_id (obtenido con "
            "notion_search o de un registro de notion_query_database). Recorre todo el contenido real, "
            "no solo el primer nivel — incluye lo que hay adentro de toggles (acordeones), tablas, y del "
            "bloque especial de transcripción de reuniones de Notion (pestañas Resumen/Notas/"
            "Transcripción, etiquetadas así en el texto que devuelve). Ver ADR 0175."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"page_id": {"type": "string"}},
            "required": ["page_id"],
        },
    },
    {
        "name": "notion_list_blocks",
        "description": (
            "Igual que notion_read_page, pero sin aplanar a un solo texto — devuelve una lista de "
            "fragmentos, cada uno con su block_id, su type (paragraph, heading_1/2/3, quote, callout, "
            "bulleted_list_item, numbered_list_item, to_do, toggle, table_row, etc.) y su texto actual. "
            "Usala ANTES de notion_update_block o notion_delete_block para identificar el block_id y el "
            "type reales del fragmento puntual que el fundador quiere cambiar — nunca los inventes. Los "
            "fragmentos con id=null son etiquetas sintéticas (secciones de una transcripción), no "
            "bloques reales, no se pueden editar ni borrar."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"page_id": {"type": "string"}},
            "required": ["page_id"],
        },
    },
    {
        "name": "notion_update_block",
        "description": (
            "Reemplaza el texto real de UN bloque puntual ya existente dentro de una página de Notion "
            "(no toda la página) — block_id y block_type vienen de notion_list_blocks, tienen que "
            "coincidir con el bloque real o la API de Notion lo rechaza. Solo sirve para tipos con texto "
            "propio (paragraph, heading_1/2/3, quote, callout, bulleted_list_item, numbered_list_item, "
            "to_do, toggle) — no para table_row ni para los bloques de transcripción en sí. Herramienta "
            "de alto impacto: protocolo de confirmed obligatorio la primera vez que se edita CADA bloque "
            "en una conversación; volver a editar el MISMO block_id más adelante en la misma conversación "
            "no requiere pedir confirmación de nuevo (mismo criterio que drive_update_document)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "block_id": {"type": "string"},
                "block_type": {"type": "string"},
                "content": {"type": "string"},
                "confirmed": {"type": "boolean"},
            },
            "required": ["block_id", "block_type", "content"],
        },
    },
    {
        "name": "notion_update_table_cell",
        "description": (
            "Reemplaza el texto de UNA celda puntual de una fila de tabla (table_row) real dentro de una "
            "página de Notion — notion_update_block NO sirve para esto (una fila de tabla no tiene "
            "rich_text propio, tiene columnas). block_id es el id de la FILA (viene de notion_list_blocks, "
            "type='table_row'); column_index es 0-based, mismo orden que el texto 'Col A | Col B | ...' que "
            "ya viste en notion_read_page/notion_list_blocks para esa fila. Trae internamente las demás "
            "columnas antes de escribir, para no perderlas. Herramienta de alto impacto: mismo protocolo de "
            "confirmed que notion_update_block (una vez por bloque por conversación)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "block_id": {"type": "string"},
                "column_index": {"type": "integer"},
                "content": {"type": "string"},
                "confirmed": {"type": "boolean"},
            },
            "required": ["block_id", "column_index", "content"],
        },
    },
    {
        "name": "notion_delete_block",
        "description": (
            "Borra un bloque puntual de una página de Notion (queda en la papelera de Notion, "
            "recuperable ahí — mismo criterio de reversibilidad que drive_delete_file). Herramienta de "
            "alto impacto: protocolo de confirmed obligatorio SIEMPRE, cada vez, sin excepción — a "
            "diferencia de notion_update_block, borrar no se recuerda de una confirmación anterior en la "
            "misma conversación."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"block_id": {"type": "string"}, "confirmed": {"type": "boolean"}},
            "required": ["block_id"],
        },
    },
    {
        "name": "notion_create_page",
        "description": (
            "Crea una página nueva de Notion, como subpágina de parent_page_id, con un título y contenido "
            "en texto plano (párrafos separados por línea en blanco). Reversible desde Notion (se puede "
            "borrar ahí mismo) — no lleva protocolo de confirmed, mismo criterio que drive_create_folder."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "parent_page_id": {"type": "string"},
                "title": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["parent_page_id", "title"],
        },
    },
    {
        "name": "notion_append_to_page",
        "description": "Agrega contenido (texto plano, párrafos separados por línea en blanco) al final de una página de Notion ya existente.",
        "input_schema": {
            "type": "object",
            "properties": {"page_id": {"type": "string"}, "content": {"type": "string"}},
            "required": ["page_id", "content"],
        },
    },
    {
        "name": "notion_get_database",
        "description": (
            "Trae el schema real de una database de Notion (nombre + properties tipadas: select, "
            "multi-select, date, number, checkbox, relation, etc). Llamala SIEMPRE antes de "
            "notion_create_database_item o notion_update_page_properties sobre esa database — "
            "las properties que mandes en esas dos tienen que coincidir en nombre y tipo con lo "
            "que devuelve acá, nunca inventadas."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"database_id": {"type": "string"}},
            "required": ["database_id"],
        },
    },
    {
        "name": "notion_query_database",
        "description": (
            "Busca/filtra registros (páginas) dentro de una database de Notion. `filter` y `sorts` "
            "son opcionales y van en el formato real de la API de Notion (objetos filter/sorts de "
            "POST /databases/{id}/query) — sin filtro, trae los primeros page_size registros tal cual."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "database_id": {"type": "string"},
                "filter": {"type": "object", "description": "Filtro en el formato real de la API de Notion, opcional."},
                "sorts": {"type": "array", "items": {"type": "object"}, "description": "Orden en el formato real de la API de Notion, opcional."},
                "page_size": {"type": "integer"},
            },
            "required": ["database_id"],
        },
    },
    {
        "name": "notion_create_database_item",
        "description": (
            "Crea un registro nuevo (página) dentro de una database de Notion. `properties` va en "
            "la forma tipada exacta que exige esa database (ver notion_get_database) — ej. "
            "{'Nombre': {'title': [{'text': {'content': '...'}}]}, 'Estado': {'select': {'name': "
            "'Hecho'}}}. Reversible desde Notion — no lleva protocolo de confirmed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "database_id": {"type": "string"},
                "properties": {"type": "object"},
            },
            "required": ["database_id", "properties"],
        },
    },
    {
        "name": "notion_update_page_properties",
        "description": (
            "Cambia properties tipadas de una página existente de Notion (típicamente un registro "
            "dentro de una database) — mismo formato tipado que notion_create_database_item, y "
            "mismo criterio de llamar antes a notion_get_database para conocer el schema real."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "page_id": {"type": "string"},
                "properties": {"type": "object"},
            },
            "required": ["page_id", "properties"],
        },
    },
    {
        "name": "notion_move_page",
        "description": (
            "Mueve una página existente de Notion a OTRA database, cambiando su parent. Notion "
            "descarta en silencio (sin avisar) cualquier property de la página que no exista, por "
            "nombre y tipo, en la database destino — llamá antes a notion_get_database de la "
            "database destino y avisá al fundador qué properties se van a perder, si alguna, antes "
            "de pedir confirmación. Herramienta de alto impacto: protocolo de confirmed obligatorio "
            "SIEMPRE, cada vez."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "page_id": {"type": "string"},
                "new_parent_database_id": {"type": "string"},
                "confirmed": {"type": "boolean"},
            },
            "required": ["page_id", "new_parent_database_id"],
        },
    },
    {
        "name": "notion_create_database",
        "description": (
            "Crea una database NUEVA de Notion (no un registro) bajo una página padre — a diferencia "
            "de notion_create_database_item, que crea un registro dentro de una database YA "
            "existente. `properties` va en la forma tipada exacta que exige la API de Notion para "
            "definir el schema (ej. {'Nombre': {'title': {}}, 'Estado': {'select': {'options': "
            "[{'name': 'Por hacer'}]}}}). Herramienta de alto impacto: protocolo de confirmed "
            "obligatorio SIEMPRE, cada vez — crea estructura real y permanente en el workspace del "
            "fundador."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "parent_page_id": {"type": "string"},
                "title": {"type": "string"},
                "properties": {"type": "object"},
                "confirmed": {"type": "boolean"},
            },
            "required": ["parent_page_id", "title", "properties"],
        },
    },
    {
        "name": "notion_update_page_cover",
        "description": (
            "Cambia (o quita, con cover_url=null) la portada de una página de Notion. Solo acepta "
            "una URL de imagen externa — no se puede subir un archivo directo por esta vía. "
            "Reversible desde Notion — no lleva protocolo de confirmed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"page_id": {"type": "string"}, "cover_url": {"type": ["string", "null"]}},
            "required": ["page_id", "cover_url"],
        },
    },
    {
        "name": "notion_update_page_icon",
        "description": (
            "Cambia (o quita, con icon=null) el ícono de una página de Notion. `icon` va en la forma "
            "tipada real de Notion: emoji ({'type': 'emoji', 'emoji': '🎯'}) o externo "
            "({'type': 'external', 'external': {'url': '...'}}). Reversible desde Notion — no lleva "
            "protocolo de confirmed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"page_id": {"type": "string"}, "icon": {"type": ["object", "null"]}},
            "required": ["page_id", "icon"],
        },
    },
    {
        "name": "notion_update_database_cover",
        "description": "Igual que notion_update_page_cover pero para una database entera.",
        "input_schema": {
            "type": "object",
            "properties": {"database_id": {"type": "string"}, "cover_url": {"type": ["string", "null"]}},
            "required": ["database_id", "cover_url"],
        },
    },
    {
        "name": "notion_update_database_icon",
        "description": "Igual que notion_update_page_icon pero para una database entera.",
        "input_schema": {
            "type": "object",
            "properties": {"database_id": {"type": "string"}, "icon": {"type": ["object", "null"]}},
            "required": ["database_id", "icon"],
        },
    },
    {
        "name": "notion_archive_page",
        "description": (
            "Envía una página de Notion a la papelera (recuperable ahí con notion_restore_page, "
            "mismo criterio de reversibilidad que drive_delete_file). Herramienta de alto impacto: "
            "protocolo de confirmed obligatorio SIEMPRE, cada vez."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"page_id": {"type": "string"}, "confirmed": {"type": "boolean"}},
            "required": ["page_id"],
        },
    },
    {
        "name": "notion_restore_page",
        "description": "Restaura una página de Notion archivada previamente con notion_archive_page. Reversible desde Notion — no lleva protocolo de confirmed.",
        "input_schema": {
            "type": "object",
            "properties": {"page_id": {"type": "string"}},
            "required": ["page_id"],
        },
    },
    {
        "name": "notion_index_start",
        "description": (
            "Arranca (o reanuda) en segundo plano la vectorización semántica del Notion del fundador "
            "(páginas y filas de databases, dominio 'personal' — ver ADR 0173). Requiere NOTION_API_KEY "
            "configurada y páginas compartidas con la integración. Tiene costo real (Voyage). Usala solo "
            "cuando el fundador lo pida explícitamente."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "notion_index_status",
        "description": "Progreso de la indexación de Notion en curso (o de la última corrida): procesados, indexados, saltados, errores.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "second_brain_status",
        "description": (
            "Estado del Second Brain de Notion del fundador (ver ADR 0179/0182): si ya tiene mapeadas "
            "las databases reales de Área/Proyecto/Recursos/Archivo (is_connected) y cuáles son. Si "
            "no está conectado todavía, decilo explícito — no inventes una jerarquía que no existe."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "second_brain_list_areas",
        "description": "Lista las Áreas reales del Second Brain (nivel superior de la jerarquía Área→Proyecto→Recursos/Archivo) — vacío si el Second Brain todavía no está conectado (ver second_brain_status).",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "second_brain_get_area",
        "description": "Trae una Área puntual del Second Brain por su id de página de Notion.",
        "input_schema": {
            "type": "object",
            "properties": {"area_id": {"type": "string"}},
            "required": ["area_id"],
        },
    },
    {
        "name": "second_brain_list_projects",
        "description": (
            "Lista los Proyectos reales del Second Brain — sin area_id, todos; con area_id, solo los "
            "de esa Área (requiere que el fundador ya haya mapeado qué property de la database de "
            "Proyectos relaciona con Área, si no, la tool devuelve un error explícito)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"area_id": {"type": "string"}},
        },
    },
    {
        "name": "second_brain_get_project",
        "description": "Trae un Proyecto puntual del Second Brain por su id de página de Notion.",
        "input_schema": {
            "type": "object",
            "properties": {"project_id": {"type": "string"}},
            "required": ["project_id"],
        },
    },
    {
        "name": "second_brain_list_resources",
        "description": "Lista los Recursos reales del Second Brain asociados a un Proyecto puntual.",
        "input_schema": {
            "type": "object",
            "properties": {"project_id": {"type": "string"}},
            "required": ["project_id"],
        },
    },
    {
        "name": "second_brain_list_archive",
        "description": "Lista lo archivado del Second Brain asociado a un Proyecto puntual.",
        "input_schema": {
            "type": "object",
            "properties": {"project_id": {"type": "string"}},
            "required": ["project_id"],
        },
    },
    {
        "name": "second_brain_get_area_home",
        "description": (
            "Panorama agregado real de un Área: sus Proyectos, Recursos y Archivo (de TODOS sus "
            "Proyectos juntos), más un análisis/reporte generado por LLM sobre datos reales — nunca "
            "inventa proyectos ni actividad. Si Recursos/Archivo todavía no están mapeados en el "
            "Second Brain, lo dice explícito (resources_mapped/archive_mapped=false) en vez de mostrar "
            "cero como si fuera un dato real. Usa el reporte cacheado si ya existe uno; para forzar uno "
            "nuevo usá second_brain_area_report_refresh."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"area_id": {"type": "string"}},
            "required": ["area_id"],
        },
    },
    {
        "name": "second_brain_area_report_refresh",
        "description": "Regenera el análisis/reporte de un Área desde cero (ignora el cacheado) — usalo cuando el fundador pida explícitamente actualizarlo.",
        "input_schema": {
            "type": "object",
            "properties": {"area_id": {"type": "string"}},
            "required": ["area_id"],
        },
    },
    {
        "name": "second_brain_onboarding_auto_build",
        "description": (
            "Onboarding del Second Brain (ADR 0190): crea desde cero, bajo una página real ya "
            "compartida con la integración (parent_page_id), la página raíz 'Snarf Second Brain' + 4 "
            "databases reales (Áreas/Proyectos/Recursos/Archivo, método PARA) con relaciones entre "
            "ellas, y completa el mapeo. Usalo solo cuando el fundador confirme explícitamente que "
            "quiere que Snarf construya la estructura por él — antes, explicale qué es cada nivel "
            "(Área/Proyecto/Recursos/Archivo) y por qué, no lo crees en silencio. Herramienta de alto "
            "impacto: confirmed obligatorio siempre."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "parent_page_id": {"type": "string"},
                "confirmed": {"type": "boolean"},
            },
            "required": ["parent_page_id"],
        },
    },
    {
        "name": "second_brain_onboarding_suggest_mapping",
        "description": (
            "Onboarding del Second Brain: busca databases YA existentes en el workspace del fundador "
            "que se parezcan por nombre a Área/Proyecto/Recursos/Archivo y propone un mapeo — nunca lo "
            "guarda por su cuenta. Usala cuando el fundador diga que ya tiene su propia estructura "
            "armada y prefiere mapearla en vez de que Snarf cree una nueva."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "second_brain_onboarding_apply_mapping",
        "description": (
            "Guarda el mapeo real de databases del Second Brain — usala después de que el fundador "
            "confirme (a partir de second_brain_onboarding_suggest_mapping, o dictándolo directo) qué "
            "database real corresponde a cada rol. Reversible (se puede volver a mapear después), no "
            "lleva confirmed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "areas": {"type": "string"},
                "proyectos": {"type": "string"},
                "recursos": {"type": "string"},
                "archivo": {"type": "string"},
                "property_map": {"type": "object"},
            },
        },
    },
    {
        "name": "second_brain_link_project",
        "description": (
            "Vincula un Proyecto de Snarf ya existente a una página real de Notion (típicamente una "
            "fila de la database de Proyectos mapeada) — a partir de acá, ese Proyecto tiene su "
            "'hermano' real en Notion. Valida que la página exista antes de guardar el vínculo (nunca "
            "guarda un id inventado). Reversible desde el propio proyecto — no lleva confirmed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "notion_page_id": {"type": "string"},
            },
            "required": ["project_id", "notion_page_id"],
        },
    },
    {
        "name": "finance_supervisor_get_snapshot",
        "description": (
            "Último snapshot real del supervisor financiero periódico (ADR 0197): P&L determinístico "
            "(ingresos/gastos por categoría/neto) + una interpretación breve generada sobre esos datos "
            "reales. None si el usuario todavía no configuró ninguna Google Sheet real "
            "(finance_supervisor_set_sheet) o si el loop periódico todavía no corrió una vez."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "finance_supervisor_set_sheet",
        "description": (
            "Configura qué Google Sheet real (file_id) es la planilla de finanzas de este usuario, "
            "para que el supervisor financiero periódico sepa de dónde leer — sin esto, nunca genera "
            "ningún snapshot. Reversible, no lleva confirmed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"file_id": {"type": "string"}},
            "required": ["file_id"],
        },
    },
    {
        "name": "founder_mood_get_snapshot",
        "description": (
            "Último snapshot real del supervisor de ánimo/estado del fundador (ADR 0197, slot "
            "FOUNDER_MODEL) — señales interpretadas de la memoria episódica reciente, cada una con su "
            "etiqueta de base real (hecho/inferencia/hipótesis). None si el loop periódico todavía no "
            "corrió una vez. Nunca lo presentes como un dato más certero de lo que la etiqueta de base "
            "real indica."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "personality_set_sarcasm",
        "description": (
            "Ajusta el nivel de ingenio seco/sarcasmo de Snarf (0-10, en pasos de 0.5) a pedido "
            "explícito del fundador en la conversación — ej. 'subime el sarcasmo', 'bajalo un toque', "
            "'poné el humor en 9'. Persiste como la preferencia guardada (mismo efecto que mover el "
            "control en configuración) hasta el próximo cambio, explícito o por configuración. No usar "
            "esto para bajar el tono ante una situación crítica o de peso emocional — eso es criterio "
            "de comportamiento en el momento (ver CHARACTER.md), no un cambio de configuración."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"level": {"type": "number", "minimum": 0, "maximum": 10}},
            "required": ["level"],
        },
    },
    {
        "name": "profile_set_name",
        "description": (
            "Guarda el nombre real de quien te está hablando, apenas te lo diga (la primera vez que "
            "lo mencione, o si contesta cuando se lo preguntaste porque no lo sabías). Persiste para "
            "siempre en todas las conversaciones futuras con este mismo usuario — no hace falta volver "
            "a preguntarlo. Nunca llames a esto con un nombre que no te haya dado la propia persona en "
            "este intercambio — nunca inventado, nunca adivinado por contexto."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
]


def sarcasm_instruction(level: float) -> str:
    """Traduce el dial 0-10 de "Ingenio seco" (CHARACTER.md v0.3) a una
    instrucción de sistema concreta. En 0 no agrega nada — comportamiento de
    siempre, sin intensificar."""
    if level <= 0:
        return ""
    if level <= 3:
        tone = "un ingenio seco apenas perceptible, casi siempre implícito"
    elif level <= 6:
        tone = "un ingenio seco notorio, con comentarios irónicos frecuentes"
    elif level <= 8.5:
        tone = "sarcasmo filoso y frecuente, con comentarios directos e ingeniosos"
    else:
        tone = "sarcasmo al límite, mordaz y constante, sin perder nunca el respeto de fondo"
    return (
        f"\n\nNivel de ingenio seco/sarcasmo configurado: {level}/10 — mostrá {tone}. "
        "Esto NUNCA reemplaza la utilidad ni la honestidad, y NUNCA aplica ante una decisión "
        "crítica, un riesgo de alto impacto o una corrección importante — ahí prevalece siempre "
        "el registro serio de CHARACTER.md, sin importar este número, y sin que eso signifique "
        "bajarlo: es una excepción de comportamiento en el momento, no un cambio de configuración.\n"
    )


def profile_identity_instruction(name: str | None) -> str:
    """Instrucción de identidad del usuario — nunca inventada (Principio VI de
    FOUNDATION.md). Si no hay nombre guardado, le pide a Snarf que lo
    pregunte en vez de asumir uno."""
    if name:
        return (
            f"\n\nEl nombre real de quien te está hablando es {name} — dirigite a esa persona "
            "por ese nombre (con la naturalidad que corresponda a tu personalidad), nunca uses "
            "otro nombre ni lo cambies por tu cuenta.\n"
        )
    return (
        "\n\nTodavía no sabés el nombre real de quien te está hablando. Nunca inventes ni "
        "asumas un nombre — si en algún momento del intercambio te parece natural preguntarlo, "
        "preguntáselo directamente, y en cuanto te lo diga guardalo con la tool "
        "profile_set_name. Hasta entonces, dirigite a la persona sin usar ningún nombre propio.\n"
    )


# ~2000 tokens — generoso para una respuesta larga normal (un plan completo real
# rondó 1500-2400 caracteres en verificaciones de esta sesión), pero corta el
# caso real de un resultado de herramienta gigante (ej. un barrido de mil
# correos) quedando embebido en una respuesta y repitiéndose turno a turno
# mientras siga en la ventana de las últimas 10 entradas (ver ADR de esta
# ronda: una sola llamada re-cacheó 523.869 tokens por esto).
HISTORY_REPLAY_MAX_CHARS = 8000

# Retrieval proactivo de Notion (ADR 0192): TTL corto del cache en memoria
# de _proactive_notion_context — alcanza para no repetir el pipeline de
# embeddings+Chroma si el fundador manda varios mensajes seguidos sobre lo
# mismo, sin quedar tan viejo como para mostrar algo desactualizado si
# cambia de tema.
NOTION_RETRIEVAL_CACHE_TTL_SECONDS = 120
# top_k chico a propósito: esto se suma al system prompt de CADA turno de
# una conversación de proyecto vinculado a Notion, no es una búsqueda a
# pedido — un resumen corto y relevante pesa mucho menos en tokens que una
# lista larga de resultados.
NOTION_RETRIEVAL_TOP_K = 3

# Ver _summarize_history_entry — tope duro sobre el tamaño de lo que se le
# manda al rol history_compaction, independiente del umbral de arriba (que
# solo decide CUÁNDO compactar, nunca cuánto puede pesar la entrada).
HISTORY_COMPACTION_INPUT_MAX_CHARS = 32000


HISTORY_COMPACTION_SYSTEM_PROMPT = (
    "Vas a recibir un mensaje largo: una entrada vieja del historial de una conversación real "
    "entre el fundador y Snarf. Tu única tarea es resumirlo de forma fiel y compacta para que "
    "Snarf recuerde de qué se trató sin tener que re-leer todo el contenido original en cada "
    "turno futuro — conservá todos los datos concretos (números, nombres propios, decisiones "
    "tomadas, resultados reales) y el sentido completo. Nunca inventes ni agregues nada que no "
    "esté en el texto original (Principio VI de FOUNDATION.md: nunca datos inventados como "
    "reales). Devolvé SOLO el resumen, sin comentarios, sin introducción, sin markdown."
)


def _hard_cut_for_replay(text: str) -> str:
    """Corte duro por caracteres — red de seguridad si el resumen real (ver
    Orchestrator._capped_for_replay) no está disponible o falla, y forma
    original de este mecanismo antes de esa mejora."""
    if len(text) <= HISTORY_REPLAY_MAX_CHARS:
        return text
    return (
        text[:HISTORY_REPLAY_MAX_CHARS]
        + "\n\n[... contenido extenso omitido acá para no re-pagar su costo en cada turno — "
        "el resultado completo ya se entregó y sigue disponible en pantalla; no hace falta "
        "rehacer la tarea, alcanza con recordar que ya se hizo ...]"
    )


# Fase 9.3 del plan de observabilidad/n8n (ADR 0144) — mapeo completo
# prompt_id -> texto default real, mismo listado que
# snarf/runtime/prompt_registry.py::PROMPT_IDS (ver ADR 0141 para la
# correspondencia original archivo/constante). Vive acá porque este módulo
# ya importa los 20 textos reales para wirear cada Specialist — un solo
# lugar, nunca una segunda copia de estos textos.
PROMPT_DEFAULTS: dict[str, str] = {
    "orchestrator_system_prefix": SYSTEM_PREFIX,
    "conversation_title": CONVERSATION_TITLE_SYSTEM_PROMPT,
    "history_compaction": HISTORY_COMPACTION_SYSTEM_PROMPT,
    "drive_vision": VISION_SYSTEM_PROMPT,
    "gmail_digest": GMAIL_DIGEST_SYSTEM_PROMPT,
    "dashboard_curator": DASHBOARD_CURATOR_SYSTEM_PROMPT,
    "project_manager_subfolder_suggestion": SUBFOLDER_SUGGESTION_SYSTEM_PROMPT,
    "project_manager_summary": PROJECT_SUMMARY_SYSTEM_PROMPT,
    "calendar_brief": CALENDAR_BRIEF_SYSTEM_PROMPT,
    "morning_routine_classify": MORNING_ROUTINE_CLASSIFY_SYSTEM_PROMPT,
    "morning_routine_synthesize": MORNING_ROUTINE_SYNTHESIZE_SYSTEM_PROMPT,
    "research_deep_research": DEEP_RESEARCH_CONFIG.system_prompt,
    "research_trend_scan": TREND_SCAN_CONFIG.system_prompt,
    "research_competitor_watch": COMPETITOR_WATCH_CONFIG.system_prompt,
    "content_blog_post": BLOG_POST_CONFIG.system_prompt,
    "content_social_post": SOCIAL_POST_CONFIG.system_prompt,
    "content_newsletter": NEWSLETTER_CONFIG.system_prompt,
    "client_status": CLIENT_STATUS_SYSTEM_PROMPT,
    "books_categorize": BOOKS_CATEGORIZE_SYSTEM_PROMPT,
    "sponsor_inbox_triage": SPONSOR_INBOX_TRIAGE_SYSTEM_PROMPT,
    **{
        f"executive_board_{role}": config.system_prompt
        for role, config in EXECUTIVE_ROLE_CONFIGS.items()
    },
}


class Orchestrator:
    def __init__(self, user_id: str = DEFAULT_USER_ID):
        self._user_id = user_id
        # self._llm y self._title_llm quedan como instancias fijas (no una
        # factory como los 3 Especialistas de abajo) porque muchos tests
        # existentes hacen monkeypatch.setattr(orchestrator._llm, "_client",
        # ...) contra el objeto ya construido — una factory que resuelve
        # distinto en cada acceso rompería ese patrón. Se refrescan
        # explícitamente vía refresh_llm_routing() cuando el ruteo cambia de
        # verdad (ver PUT /llm-routing en app.py), no en cada turno.
        self._llm = llm_routing.build_llm("orchestrator")
        self._title_llm = llm_routing.build_llm("conversation_title")
        # Bug real corregido en Fase 3 del plan de multi-usuario (ADR 0137):
        # EpisodicMemory() sin argumentos apuntaba siempre a las rutas
        # globales de siempre (data/episodic_memory.jsonl), sin importar qué
        # user_id se le pasara a este constructor — dos Orchestrator de dos
        # usuarios distintos habrían compartido el mismo historial de
        # conversaciones. DEFAULT_USER_ID sigue usando esas rutas globales a
        # propósito (compatibilidad con datos reales ya en disco); cualquier
        # otro user_id recibe su propio archivo bajo MEMORY_DATA_DIR.
        if user_id == DEFAULT_USER_ID:
            self._memory = EpisodicMemory()
        else:
            user_memory_dir = MEMORY_DATA_DIR / user_id
            self._memory = EpisodicMemory(
                path=user_memory_dir / "episodic_memory.jsonl",
                project_links_path=user_memory_dir / "conversation_projects.json",
                titles_path=user_memory_dir / "conversation_titles.json",
            )
        self._identity = load_identity()
        # Cache en memoria (no persistida — se pierde con cada reinicio, y
        # está bien: es barata de reconstruir) de resúmenes reales de
        # entradas de historial demasiado largas (ver _capped_for_replay más
        # abajo) — sin esto, la misma entrada vieja se re-resumiría con una
        # llamada nueva al LLM en cada turno mientras siga dentro de la
        # ventana de las últimas 10 entradas.
        self._history_summary_cache: dict[str, str] = {}
        # Retrieval proactivo de Notion (ADR 0192) — cache en memoria de
        # (query normalizada) -> (timestamp, resultado), TTL corto. Evita
        # repetir el pipeline de embeddings+Chroma en cada turno si el
        # fundador escribe varios mensajes seguidos sobre lo mismo.
        self._notion_retrieval_cache: dict[str, tuple[float, str | None]] = {}

        google_auth = GoogleAuth(user_id)
        self._drive = GoogleDrive(google_auth)
        self._gmail = GoogleGmail(google_auth)
        self._calendar = GoogleCalendar(google_auth)
        self._youtube = GoogleYouTube(google_auth)
        # notion_auth (ADR 0186): NotionAuth resuelve el token real de este
        # user_id si ya conectó su propio Notion vía OAuth — si no,
        # Notion._resolve_token() cae de vuelta al NOTION_API_KEY global
        # (mismo comportamiento de siempre para el fundador mientras no
        # exista todavía la integración pública registrada en Notion).
        self._notion = Notion(notion_auth=NotionAuth(user_id))
        # Mismo criterio que project_summary (GmailDigestSpecialist/
        # ProjectManager, ADR 0026): tarea acotada, modelo barato por
        # default, elegible aparte desde Configuración sin tocar código.
        self._second_brain = SecondBrainManager(
            self._notion, user_id, lambda: llm_routing.build_resilient_llm("second_brain_report")
        )
        # Categorizar correos es una tarea acotada y mecánica, no necesita el
        # mismo modelo (más caro) que usa Snarf para conversar — un modelo
        # más chico y barato alcanza, y este Especialista puede elegir su
        # propia Capacidad de LLM sin afectar la de Snarf. Se pasa una
        # factory (lambda), nunca la instancia ya resuelta — así un cambio de
        # ruteo desde configuración se aplica sin reiniciar el servidor
        # (bug real encontrado en esta misma ronda: antes quedaba fijo al
        # momento de construir el Orchestrator).
        self._gmail_digest = GmailDigestSpecialist(
            self._gmail,
            lambda: llm_routing.build_resilient_llm("gmail_digest"),
            user_id,
            lambda: prompt_registry.get_active_text("gmail_digest", GMAIL_DIGEST_SYSTEM_PROMPT),
        )
        # Fase I, rama Productivity (ver plan de expansión) — mismo patrón
        # cache-first que GmailDigestSpecialist.
        self._calendar_brief = CalendarBriefSpecialist(
            self._calendar,
            lambda: llm_routing.build_resilient_llm("calendar_brief"),
            user_id,
            lambda: prompt_registry.get_active_text("calendar_brief", CALENDAR_BRIEF_SYSTEM_PROMPT),
        )
        # Compone gmail+calendar en una sola rutina, con el cuerpo real ya
        # leído para los correos prioritarios (ver ADR de esta ronda) — no
        # reemplaza gmail_digest/calendar_brief (siguen sirviendo un pedido
        # acotado a solo correo o solo agenda), es la respuesta al "qué
        # tenemos hoy" combinado sin depender de que el Orchestrator
        # encadene bien varias tool calls en el mismo turno.
        self._morning_routine = MorningRoutineSpecialist(
            self._gmail,
            self._calendar,
            lambda: llm_routing.build_resilient_llm("morning_routine"),
            user_id,
            lambda: prompt_registry.get_active_text("morning_routine_classify", MORNING_ROUTINE_CLASSIFY_SYSTEM_PROMPT),
            lambda: prompt_registry.get_active_text("morning_routine_synthesize", MORNING_ROUTINE_SYNTHESIZE_SYSTEM_PROMPT),
        )
        # Fase I, rama Sales — mismo patrón cache-first, búsqueda de Gmail
        # acotada a oportunidades reales de sponsor/partnership.
        self._sponsor_inbox_triage = SponsorInboxTriageSpecialist(
            self._gmail,
            lambda: llm_routing.build_resilient_llm("sponsor_inbox_triage"),
            user_id,
            lambda: prompt_registry.get_active_text("sponsor_inbox_triage", SPONSOR_INBOX_TRIAGE_SYSTEM_PROMPT),
        )
        # Fase I, rama Finance — v1 sin vendor nuevo: una Google Sheet real
        # que el fundador mantiene, leída vía GoogleDrive.read_file_text()
        # (ya exporta un Sheet real como CSV). monthly_pnl es determinístico,
        # nunca un LLM.
        self._books_categorize = BooksCategorizeSpecialist(
            self._drive,
            lambda: llm_routing.build_resilient_llm("books_categorize"),
            user_id,
            lambda: prompt_registry.get_active_text("books_categorize", BOOKS_CATEGORIZE_SYSTEM_PROMPT),
        )
        self._monthly_pnl = MonthlyPnLSpecialist()
        # Supervisores periódicos (ADR 0197, Track D del roadmap Second
        # Brain) — compone los Specialists de Finance ya reales de arriba,
        # nunca un cálculo/categoría nueva.
        self._finance_supervisor = FinanceSupervisor(
            self._books_categorize,
            self._monthly_pnl,
            user_id,
            lambda: llm_routing.build_resilient_llm("finance_supervisor"),
        )
        self._founder_mood = FounderMood(
            self._memory, user_id, lambda: llm_routing.build_resilient_llm("founder_mood_supervisor")
        )
        # Escritura confiable de documentos largos (ADR 0199, Fase D4) —
        # compone la Capacidad Notion ya real de arriba, mismo criterio de
        # modelo barato por default para una tarea acotada por sección.
        self._document_writer = DocumentWriter(
            self._notion, lambda: llm_routing.build_resilient_llm("document_writer_section"), user_id
        )
        # Fase I, rama Community — vendor decidido (Discord), lazy-client
        # desde env vars (DISCORD_BOT_TOKEN/DISCORD_GUILD_ID/
        # DISCORD_CHANNEL_ID). Sin credencial real, available es False y
        # ningún método real se llama.
        self._discord = Discord()
        self._community_pulse = CommunityPulseSpecialist(self._discord)

        # Pipeline de vectorización de Drive (ver ADR 0028): mismo criterio de
        # "modelo barato para tarea acotada" que el digest de Gmail, esta vez
        # para describir imágenes. Cada pieza es una Capacidad chica e
        # inyectada, nunca buscada por el propio pipeline.
        content_extractor = ContentExtractor(
            drive=self._drive,
            pdf_extractor=PdfExtractor(),
            vision_llm_factory=lambda: llm_routing.build_resilient_llm("drive_vision"),
            stt=ElevenLabsSTT(),
            ffmpeg_audio=FfmpegAudioExtractor(),
            docx_extractor=DocxExtractor(),
            pptx_extractor=PptxExtractor(),
            xlsx_extractor=XlsxExtractor(),
            vision_system_prompt_provider=lambda: prompt_registry.get_active_text("drive_vision", VISION_SYSTEM_PROMPT),
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
        # Notion, mismo dominio 'personal' que Drive (ADR 0173): motor
        # genérico KnowledgeIndexer (pensado para fuentes sin la complejidad
        # de extracción por mimetype que Drive sí tiene) sobre NotionSource,
        # escribiendo al MISMO persist_directory que self._drive_indexer —
        # así conviven en la misma colección física sin tocar
        # _tool_knowledge_search, que ya busca ahí para domain='personal'.
        # Manifiesto propio para que el tracking de qué ya se indexó no se
        # pise con el de Drive (mismos IDs no garantizados entre las dos
        # fuentes).
        self._notion_indexer = KnowledgeIndexer(
            source=NotionSource(self._notion),
            embeddings=VoyageEmbeddings(),
            vector_store=VectorStore(persist_directory=str(user_index_dir / "chroma")),
            manifest_path=user_index_dir / "notion_manifest.json",
        )
        # Knowledge Layer generalizada (ver KNOWLEDGE.md, ADR 0093): dominio
        # 'code' indexa el propio repositorio de Snarf — costo cero más allá
        # de embeddings, sin la complejidad de extracción por mimetype que
        # Drive sí tiene. 'personal' sigue sirviéndose de self._drive_indexer
        # sin cambios; este es un motor nuevo y aditivo, no un reemplazo.
        code_index_dir = KNOWLEDGE_DATA_DIR / user_id / "code"
        self._code_indexer = KnowledgeIndexer(
            source=LocalRepoKnowledgeSource(),
            embeddings=VoyageEmbeddings(),
            vector_store=VectorStore(persist_directory=str(code_index_dir / "chroma"), collection_name="code"),
            manifest_path=code_index_dir / "manifest.json",
        )
        # Segundo dominio nuevo desde 'code' (ADR de esta ronda): el propio
        # historial de conversaciones, mismo precedente exacto — costo cero
        # más allá de embeddings, EpisodicMemory ya es la fuente de verdad
        # real, sin llamada de red para leer contenido. 'project_id' viaja
        # como metadata real por conversación (ver EpisodicConversationSource)
        # para poder filtrar la búsqueda por proyecto sin un dominio aparte.
        conversations_index_dir = KNOWLEDGE_DATA_DIR / user_id / "conversations"
        self._conversations_indexer = KnowledgeIndexer(
            source=EpisodicConversationSource(self._memory),
            embeddings=VoyageEmbeddings(),
            vector_store=VectorStore(
                persist_directory=str(conversations_index_dir / "chroma"), collection_name="conversations"
            ),
            manifest_path=conversations_index_dir / "manifest.json",
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
        # Conversión a EPUB3 (ADR 0202): capacidad propia del Orchestrator,
        # no depende de ninguna skill de Claude Code — ver
        # snarf/capabilities/epub_builder.py.
        self._epub_builder = EpubBuilder()
        # Fase I, rama Research (ver plan de expansión): una sola clase real,
        # tres configs — comparten Capacidades reales (búsqueda web,
        # transcripciones de YouTube, publicación de documentos), solo
        # cambia el system prompt y el rol de ruteo de LLM.
        self._web_search = TavilySearch()
        self._research_specialists = {
            config.mode: ResearchSpecialist(
                config,
                self._web_search,
                self._youtube,
                self._document_publisher,
                lambda role=config.llm_routing_role: llm_routing.build_resilient_llm(role),
                user_id,
                lambda cfg=config: prompt_registry.get_active_text(cfg.llm_routing_role, cfg.system_prompt),
            )
            for config in (DEEP_RESEARCH_CONFIG, TREND_SCAN_CONFIG, COMPETITOR_WATCH_CONFIG)
        }
        # Fase I, rama Content — mismo patrón "una clase, N configs" que
        # Research/Inteligencia Ejecutiva. Generación de imágenes queda
        # fuera (ver IMAGE_GENERATION_RESEARCH.md, sin decisión de vendor).
        self._content_specialists = {
            config.mode: ContentSpecialist(
                config,
                self._document_publisher,
                lambda role=config.llm_routing_role: llm_routing.build_resilient_llm(role),
                user_id,
                lambda cfg=config: prompt_registry.get_active_text(cfg.llm_routing_role, cfg.system_prompt),
            )
            for config in (BLOG_POST_CONFIG, SOCIAL_POST_CONFIG, NEWSLETTER_CONFIG)
        }
        # Mismo criterio que GmailDigestSpecialist: modelo barato para una
        # tarea acotada (sugerir 2-4 nombres de subcarpeta por proyecto).
        # projects_dir namespaced por user_id (ADR 0183, mismo patrón que
        # EpisodicMemory arriba, ADR 0137) — DEFAULT_USER_ID sigue en
        # PROJECTS_DIR a propósito (compatibilidad con datos reales ya en
        # disco), cualquier otro user_id recibe su propia carpeta.
        self._projects = ProjectManager(
            self._drive,
            self._drive_indexer,
            lambda: llm_routing.build_resilient_llm("project_summary"),
            user_id,
            lambda: prompt_registry.get_active_text(
                "project_manager_subfolder_suggestion", SUBFOLDER_SUGGESTION_SYSTEM_PROMPT
            ),
            lambda: prompt_registry.get_active_text("project_manager_summary", PROJECT_SUMMARY_SYSTEM_PROMPT),
            projects_dir=PROJECTS_DIR if user_id == DEFAULT_USER_ID else MEMORY_DATA_DIR / user_id / "projects",
            second_brain=self._second_brain,
        )
        self._bug_reports = BugReports(lambda: self._memory, user_id)
        # Fase I, rama Agency — único código genuinamente nuevo (el resto
        # ya está cubierto por conversación + drive_create_document, mismo
        # criterio que Proposal Drafts en la rama Sales).
        self._client_status = ClientStatusSpecialist(
            self._projects,
            self._document_publisher,
            lambda: llm_routing.build_resilient_llm("client_status"),
            user_id,
            lambda: prompt_registry.get_active_text("client_status", CLIENT_STATUS_SYSTEM_PROMPT),
        )
        # Inteligencia Ejecutiva (ver COGNITION.md, ADR 0094/0098): cada rol
        # corre en su propio proceso MCP (snarf/executive/process.py), nunca
        # in-process — es el segundo consumidor real que justificó reabrir
        # MCP (ADR 0093). llm_factory_for_role reusa el mismo ruteo con
        # fallback automático entre proveedores que el resto del wiring real.
        self._executive_board = ExecutiveBoardSpecialist(
            llm_factory_for_role=lambda role: llm_routing.build_resilient_llm(f"executive_{role}"), user_id=user_id
        )
        # Mecanismo de "equipo" multi-agente (ADR 0198) — reusa el mismo
        # factory de LLM por rol que el board de arriba para las críticas
        # (consult_role), más un rol de ruteo nuevo dedicado para redactar/
        # revisar el borrador en sí.
        self._executive_team = TeamSession(
            draft_llm_factory=lambda: llm_routing.build_resilient_llm("executive_team_writer"),
            role_llm_factory_for_role=lambda role: llm_routing.build_resilient_llm(f"executive_{role}"),
        )
        # Skill Factory (Fase H, ver ADR 0095/0102/0130): Snarf construyendo y
        # activando una skill nueva de verdad, con el modelo local del
        # fundador como motor de escritura (ADR 0130 — el CLI de Claude Code
        # no tiene forma soportada de apuntar a un modelo no-Claude) —
        # alcance estrecho y nombrado, cada construcción quema su propia
        # confirmación (Constitution Art. VII, nunca una delegación general).
        self._code_writer = LocalCodeWriter(
            llm_factory=lambda: llm_routing.build_resilient_llm("skill_factory_writer"), repo_root=Path.cwd()
        )
        self._skill_factory = SkillFactorySpecialist(code_writer=self._code_writer, repo_root=Path.cwd())

        self._tool_handlers = {
            "get_current_datetime": lambda i: self._tool_get_current_datetime(),
            "measure_text_length": lambda i: self._tool_measure_text_length(i.get("text", "")),
            "list_conversations": lambda i: self._memory.list_conversations(),
            "get_conversation": lambda i: self._memory.get_conversation(i.get("conversation_id", "")),
            "search_memory": lambda i: self._memory.search(i.get("query", "")),
            "drive_list_files": lambda i: self._bulk_read_gate(
                "page_size", i, 50, lambda n: self._drive.list_files(page_size=n, query=i.get("query"))
            ),
            "drive_read_file": lambda i: self._read_drive_file(i["file_id"], i["mime_type"]),
            "drive_create_folder": lambda i: self._drive.create_folder(i["name"], parent_id=i.get("parent_id")),
            "drive_move_file": lambda i: self._drive.move_file(i["file_id"], i["new_parent_id"]),
            "gmail_list_messages": lambda i: self._bulk_read_gate(
                "max_results", i, 10, lambda n: self._gmail.list_messages(max_results=n, query=i.get("query"))
            ),
            "gmail_read_message": lambda i: self._gmail.read_message(i["message_id"]),
            "gmail_list_labels": lambda i: self._gmail.list_labels(),
            "gmail_create_label": lambda i: self._gmail.create_label(i["name"]),
            "gmail_modify_message_labels": lambda i: self._gmail.modify_message_labels(
                i["message_id"], add_label_ids=i.get("add_label_ids"), remove_label_ids=i.get("remove_label_ids")
            ),
            "calendar_list_calendars": lambda i: self._calendar.list_calendars(),
            "calendar_list_upcoming_events": lambda i: self._bulk_read_gate(
                "max_results", i, 10,
                lambda n: self._calendar.list_upcoming_events(max_results=n, calendar_id=i.get("calendar_id", "primary")),
            ),
            "calendar_search_events": lambda i: self._bulk_read_gate(
                "max_results", i, 10,
                lambda n: self._calendar.search_events(i["query"], calendar_id=i.get("calendar_id", "primary"), max_results=n),
            ),
            "youtube_list_subscriptions": lambda i: self._bulk_read_gate(
                "max_results", i, 25, lambda n: self._youtube.list_subscriptions(max_results=n)
            ),
            "youtube_list_liked_videos": lambda i: self._bulk_read_gate(
                "max_results", i, 25, lambda n: self._youtube.list_liked_videos(max_results=n)
            ),
            "gmail_send_message": self._tool_gmail_send_message,
            "calendar_create_event": self._tool_calendar_create_event,
            "calendar_create_calendar": self._tool_calendar_create_calendar,
            "calendar_delete_calendar": self._tool_calendar_delete_calendar,
            "calendar_delete_event": self._tool_calendar_delete_event,
            "calendar_move_event": self._tool_calendar_move_event,
            "gmail_delete_label": self._tool_gmail_delete_label,
            "drive_delete_file": self._tool_drive_delete_file,
            "gmail_summarize_inbox": self._tool_gmail_summarize_inbox,
            "calendar_brief": self._tool_calendar_brief,
            "morning_routine": self._tool_morning_routine,
            "research_deep_dive": lambda i: self._research_specialists["deep_research"].research(
                i["topic"], i.get("video_urls")
            ),
            "research_trend_scan": lambda i: self._research_specialists["trend_scan"].research(
                i["topic"], i.get("video_urls")
            ),
            "research_competitor_watch": lambda i: self._research_specialists["competitor_watch"].research(
                i["topic"], i.get("video_urls")
            ),
            "content_write_blog_post": lambda i: self._content_specialists["blog_post"].draft(
                i["brief"], i.get("reference_material", "")
            ),
            "content_write_social_post": lambda i: self._content_specialists["social_post"].draft(
                i["brief"], i.get("reference_material", "")
            ),
            "content_write_newsletter": lambda i: self._content_specialists["newsletter"].draft(
                i["brief"], i.get("reference_material", "")
            ),
            "sales_sponsor_inbox_triage": self._tool_sales_sponsor_inbox_triage,
            "finance_books_categorize": lambda i: self._books_categorize.categorize(i["file_id"]),
            "finance_monthly_pnl": lambda i: self._monthly_pnl.compute(i["transactions"]),
            "community_pulse": lambda i: self._community_pulse.pulse(i.get("message_limit", 100)),
            "community_post_message": self._tool_community_post_message,
            "agency_client_status": lambda i: self._client_status.generate(i["project_id"]),
            "ops_system_health": lambda i: ops_health.system_health(
                llm_available=self._llm.available,
                google_available=self._drive.available,
                recent_activity=activity_log.recent(i.get("n", 50)),
            ),
            "ops_backup_now": lambda i: {"snapshot": str(data_backup.backup_now())},
            "ops_process_status": self._tool_ops_process_status,
            "ops_process_restart": self._tool_ops_process_restart,
            "drive_index_scan": lambda i: self._drive_indexer.scan(query=i.get("query")),
            "drive_index_catalog_unsupported": lambda i: self._drive_indexer.catalog_unsupported(query=i.get("query")),
            "drive_index_start": lambda i: self._drive_indexer.start(query=i.get("query")),
            "drive_index_status": lambda i: self._drive_indexer.status(),
            "drive_index_stop": lambda i: self._drive_indexer.stop(),
            "drive_search_knowledge": lambda i: self._drive_indexer.search(i["query"], top_k=i.get("top_k", 5)),
            "codebase_search": lambda i: self._code_indexer.search(i["query"], top_k=i.get("top_k", 5)),
            "conversations_search": lambda i: self._conversations_indexer.search(
                i["query"], top_k=i.get("top_k", 5),
                where={"project_id": i["project_id"]} if i.get("project_id") else None,
            ),
            "knowledge_search": lambda i: self._tool_knowledge_search(i),
            "knowledge_index_start": lambda i: self._knowledge_index_start(i["domain"]),
            "knowledge_index_status": lambda i: self._knowledge_index_status(i["domain"]),
            "telemetry_cost_summary": lambda i: usage_tracker.summarize(recent_days=i.get("recent_days", 7)),
            "system_introspect": lambda i: introspection.system_snapshot(
                tools=TOOLS, safe_tool_names=MCP_EXPOSED_TOOLS - HIGH_IMPACT_TOOLS - BULK_READ_GATED_TOOLS
            ),
            "os_audit": lambda i: os_audit.run_audit(),
            "executive_board_consult": lambda i: self._executive_board.consult(i["question"], i.get("roles")),
            "executive_team_run": lambda i: self._executive_team.run(
                i["objective"], i["roles"], i.get("max_rounds", DEFAULT_MAX_ROUNDS)
            ),
            "document_write_start": lambda i: self._document_writer.start(
                i["page_id"], i["title"], i["sections"], i.get("objective", "")
            ),
            "document_write_continue": lambda i: self._document_writer.continue_write(i["write_id"]),
            "document_write_status": lambda i: self._document_writer.status(i["write_id"]),
            "skill_factory_build": self._tool_skill_factory_build,
            "skill_factory_activate": self._tool_skill_factory_activate,
            "skill_factory_status": lambda i: self._skill_factory.status(i["proposal_id"]),
            "drive_create_document": lambda i: self._document_publisher.create_document(
                i["title"], i["content"], format=i.get("format", "markdown"), destination=i.get("destination", "drive")
            ),
            "drive_create_spreadsheet": lambda i: self._document_publisher.create_spreadsheet(
                i["title"], i["rows"], format=i.get("format", "xlsx"), destination=i.get("destination", "drive")
            ),
            "drive_create_presentation": lambda i: self._document_publisher.create_presentation(
                i["title"], i["slides"], format=i.get("format", "pptx"), destination=i.get("destination", "drive")
            ),
            "drive_rename_file": lambda i: self._drive.rename_file(i["file_id"], i["new_name"]),
            "convert_to_epub": self._tool_convert_to_epub,
            "drive_share_file": self._tool_drive_share_file,
            "drive_update_document": self._tool_drive_update_document,
            "project_create": lambda i: self._projects.create(i["name"]),
            "project_list": lambda i: self._projects.list_projects(),
            "project_get": lambda i: self._projects.get(i["project_id"]),
            "project_set_prompt": lambda i: self._projects.set_prompt(i["project_id"], i["prompt"]),
            "project_add_task": lambda i: self._projects.add_task(i["project_id"], i["text"]),
            "project_complete_task": lambda i: self._projects.complete_task(i["project_id"], i["task_id"]),
            "project_delete_task": lambda i: self._projects.delete_task(i["project_id"], i["task_id"]),
            "project_add_note": lambda i: self._projects.add_note(i["project_id"], i["text"]),
            "project_delete_note": lambda i: self._projects.delete_note(i["project_id"], i["note_id"]),
            "project_search": lambda i: self._projects.search_within(i["project_id"], i["query"], top_k=i.get("top_k", 5)),
            "project_delete": self._tool_project_delete,
            "project_assign_conversation": lambda i: self._memory.assign_conversation(i["conversation_id"], i["project_id"]),
            "project_unassign_conversation": lambda i: self._memory.unassign_conversation(i["conversation_id"]),
            "project_list_conversations": lambda i: self._memory.list_conversations(project_id=i["project_id"]),
            "bug_report_create": lambda i: self._bug_reports.create(
                i["description"], conversation_id=context.get_conversation_id(), view="chat"
            ),
            "bug_report_list": lambda i: self._bug_reports.list_reports(status=i.get("status")),
            "bug_report_get": lambda i: self._bug_reports.get(i["report_id"]),
            "bug_report_update_status": lambda i: self._bug_reports.update_status(
                i["report_id"], i["status"], note=i.get("note", "")
            ),
            "personality_set_sarcasm": self._tool_personality_set_sarcasm,
            "profile_set_name": self._tool_profile_set_name,
            "notion_search": lambda i: self._notion.search(i["query"]),
            "notion_read_page": lambda i: self._notion.read_page_text(i["page_id"]),
            "notion_list_blocks": lambda i: self._notion.list_blocks(i["page_id"]),
            "notion_update_block": self._tool_notion_update_block,
            "notion_update_table_cell": self._tool_notion_update_table_cell,
            "notion_delete_block": self._tool_notion_delete_block,
            "notion_create_page": lambda i: self._notion.create_page(
                i["parent_page_id"], i["title"], i.get("content", "")
            ),
            "notion_append_to_page": lambda i: self._notion.append_to_page(i["page_id"], i["content"]),
            "notion_get_database": lambda i: self._notion.get_database(i["database_id"]),
            "notion_query_database": lambda i: self._notion.query_database(
                i["database_id"], filter=i.get("filter"), sorts=i.get("sorts"), page_size=i.get("page_size", 100)
            ),
            "notion_create_database_item": lambda i: self._notion.create_database_item(
                i["database_id"], i["properties"]
            ),
            "notion_update_page_properties": lambda i: self._notion.update_page_properties(
                i["page_id"], i["properties"]
            ),
            "notion_index_start": lambda i: self._notion_indexer.start(),
            "notion_index_status": lambda i: self._notion_indexer.status(),
            "notion_move_page": self._tool_notion_move_page,
            "notion_create_database": self._tool_notion_create_database,
            "notion_update_page_cover": lambda i: self._notion.update_page_cover(i["page_id"], i.get("cover_url")),
            "notion_update_page_icon": lambda i: self._notion.update_page_icon(i["page_id"], i.get("icon")),
            "notion_update_database_cover": lambda i: self._notion.update_database_cover(
                i["database_id"], i.get("cover_url")
            ),
            "notion_update_database_icon": lambda i: self._notion.update_database_icon(
                i["database_id"], i.get("icon")
            ),
            "notion_archive_page": self._tool_notion_archive_page,
            "notion_restore_page": lambda i: self._notion.restore_page(i["page_id"]),
            "second_brain_status": lambda i: {
                "connected": self._second_brain.is_connected(),
                "database_map": self._second_brain.get_database_map(),
            },
            "second_brain_list_areas": lambda i: self._second_brain.list_areas(),
            "second_brain_get_area": lambda i: self._second_brain.get_area(i["area_id"]),
            "second_brain_list_projects": lambda i: self._second_brain.list_projects(i.get("area_id")),
            "second_brain_get_project": lambda i: self._second_brain.get_project(i["project_id"]),
            "second_brain_list_resources": lambda i: self._second_brain.list_resources(i["project_id"]),
            "second_brain_list_archive": lambda i: self._second_brain.list_archive(i["project_id"]),
            "second_brain_link_project": self._tool_second_brain_link_project,
            "second_brain_onboarding_auto_build": self._tool_second_brain_onboarding_auto_build,
            "second_brain_onboarding_suggest_mapping": lambda i: self._second_brain.suggest_mapping(),
            "second_brain_onboarding_apply_mapping": lambda i: self._second_brain.save_database_map(i),
            "finance_supervisor_get_snapshot": lambda i: self._finance_supervisor.get_snapshot(),
            "finance_supervisor_set_sheet": lambda i: self._finance_supervisor.set_sheet_file_id(i["file_id"]),
            "founder_mood_get_snapshot": lambda i: self._founder_mood.get_snapshot(),
            "second_brain_get_area_home": lambda i: self._second_brain.cached_area_report(i["area_id"]),
            "second_brain_area_report_refresh": lambda i: self._second_brain.generate_area_report(i["area_id"]),
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
    def calendar_brief(self) -> CalendarBriefSpecialist:
        return self._calendar_brief

    @property
    def morning_routine(self) -> MorningRoutineSpecialist:
        return self._morning_routine

    @property
    def executive_board(self) -> ExecutiveBoardSpecialist:
        return self._executive_board

    @property
    def skill_factory(self) -> SkillFactorySpecialist:
        return self._skill_factory

    @property
    def drive_indexer(self) -> DriveIndexer:
        return self._drive_indexer

    @property
    def code_indexer(self) -> KnowledgeIndexer:
        return self._code_indexer

    @property
    def conversations_indexer(self) -> KnowledgeIndexer:
        return self._conversations_indexer

    @property
    def document_publisher(self) -> DocumentPublisher:
        return self._document_publisher

    @property
    def projects(self) -> ProjectManager:
        return self._projects

    @property
    def second_brain(self) -> SecondBrainManager:
        return self._second_brain

    @property
    def finance_supervisor(self) -> FinanceSupervisor:
        return self._finance_supervisor

    @property
    def founder_mood(self) -> FounderMood:
        return self._founder_mood

    @property
    def document_writer(self) -> DocumentWriter:
        return self._document_writer

    @property
    def bug_reports(self) -> BugReports:
        return self._bug_reports

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

    # Dominios reales de la Knowledge Layer generalizada (ver KNOWLEDGE.md) —
    # 'personal' sigue sirviéndose de DriveIndexer sin cambios; 'code' y
    # 'conversations' (ADR de esta ronda) usan el motor genérico
    # KnowledgeIndexer. El resto todavía no tiene fuente real conectada: se
    # declara explícito en vez de fabricar un resultado (Principio VI).
    _KNOWLEDGE_DOMAINS_WITHOUT_SOURCE_YET = ("business", "trading", "marketing", "finance")

    def _tool_knowledge_search(self, i: dict) -> dict | list[dict]:
        domain = i["domain"]
        query = i["query"]
        top_k = i.get("top_k", 5)
        if domain == "personal":
            source = i.get("source")
            where = {"location": source} if source else None
            return self._drive_indexer.search(query, top_k=top_k, where=where)
        if domain == "code":
            return self._code_indexer.search(query, top_k=top_k)
        if domain == "conversations":
            return self._conversations_indexer.search(query, top_k=top_k)
        return {
            "error": (
                f"El dominio '{domain}' todavía no tiene una fuente real conectada en la Knowledge "
                "Layer (ver KNOWLEDGE.md) — no hay nada indexado que buscar todavía."
            )
        }

    def _knowledge_index_start(self, domain: str) -> dict:
        if domain == "code":
            return self._code_indexer.start()
        if domain == "conversations":
            return self._conversations_indexer.start()
        return {
            "error": (
                f"Indexación no disponible todavía para domain='{domain}' por esta vía. "
                "domain='personal' se indexa con drive_index_start, no con knowledge_index_start."
            )
        }

    def _knowledge_index_status(self, domain: str) -> dict:
        if domain == "code":
            return self._code_indexer.status()
        if domain == "conversations":
            return self._conversations_indexer.status()
        return {"error": f"Sin indexador real para domain='{domain}' todavía."}

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

    def _bulk_read_gate(self, param: str, i: dict, default: int, run):
        # Bug real que motivó esto: un pedido de "barrido de mil correos" sin
        # ningún tope costó $1.09 en una sola llamada (523.869 tokens
        # escritos al cache), 22% del gasto real de un día entero (ver ADR de
        # esta ronda). Mismo protocolo que _pending() para acciones de alto
        # impacto, pero acá el motivo es el costo real (tokens + cuota de la
        # API externa), no la irreversibilidad — y a propósito es solo un
        # umbral de CONFIRMACIÓN, nunca de bloqueo: si el fundador confirma,
        # se ejecuta exactamente la cantidad que pidió, sin recortarla en
        # silencio. "Preguntar antes" nunca es "prohibir para siempre".
        requested = i.get(param, default)
        if requested > BULK_READ_CONFIRM_THRESHOLD and not i.get("confirmed"):
            return self._pending({param: requested})
        return run(requested)

    def _tool_get_current_datetime(self) -> dict:
        now = datetime.now(ZoneInfo(FOUNDER_TIMEZONE))
        return {
            "iso": now.isoformat(),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M"),
            "weekday": now.strftime("%A"),
            "timezone": FOUNDER_TIMEZONE,
        }

    def _tool_measure_text_length(self, text: str) -> dict:
        return {
            "characters": len(text),
            "words": len(text.split()),
        }

    def _tool_skill_factory_build(self, i: dict) -> dict:
        if not i.get("confirmed"):
            return self._pending(
                {"branch": i["branch"], "skill_name": i["skill_name"], "description": i["description"]}
            )
        return self._skill_factory.build_skill(
            i["branch"], i["skill_name"], i["description"], i.get("clarifying_answers")
        )

    def _tool_skill_factory_activate(self, i: dict) -> dict:
        if not i.get("confirmed"):
            return self._pending({"proposal_id": i["proposal_id"]})
        return self._skill_factory.activate(i["proposal_id"])

    def _tool_community_post_message(self, i: dict) -> dict:
        if not i.get("confirmed"):
            return self._pending({"content": i.get("content")})
        return self._discord.send_message(i["content"])

    def _tool_ops_process_status(self, i: dict) -> dict:
        if self._user_id != DEFAULT_USER_ID:
            return {"error": "Este tool es solo para el fundador."}
        return {"processes": process_control.status()}

    def _tool_ops_process_restart(self, i: dict) -> dict:
        if self._user_id != DEFAULT_USER_ID:
            return {"error": "Este tool es solo para el fundador."}
        if not i.get("confirmed"):
            return self._pending({"label": i.get("label")})
        try:
            return process_control.restart(i["label"])
        except ValueError as exc:
            return {"error": str(exc)}

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

    def _tool_calendar_brief(self, i: dict) -> dict:
        if i.get("force_refresh"):
            return self._calendar_brief.refresh()
        return self._calendar_brief.cached_brief() or self._calendar_brief.refresh()

    def _tool_morning_routine(self, i: dict) -> dict:
        kwargs = {}
        if "max_messages" in i:
            kwargs["max_messages"] = i["max_messages"]
        if "max_events" in i:
            kwargs["max_events"] = i["max_events"]
        if i.get("force_refresh"):
            return self._morning_routine.refresh(**kwargs)
        return self._morning_routine.cached_routine() or self._morning_routine.refresh(**kwargs)

    def _tool_sales_sponsor_inbox_triage(self, i: dict) -> dict:
        if i.get("force_refresh"):
            return self._sponsor_inbox_triage.refresh()
        return self._sponsor_inbox_triage.cached_triage() or self._sponsor_inbox_triage.refresh()

    def _tool_convert_to_epub(self, i: dict) -> dict:
        # Crea contenido NUEVO en el Drive del fundador a partir de un
        # archivo que ya le pertenece — mismo criterio que
        # drive_create_document/document_write_start (ninguno de esos exige
        # confirmed), no el de drive_delete_file/drive_update_document (que
        # tocan o borran contenido ya existente).
        source_bytes = self._drive.read_file_bytes(i["file_id"])
        try:
            epub_bytes, mode_used = self._epub_builder.convert(
                source_bytes, i["source_name"], i["title"], i["author"], mode=i.get("mode", "auto"),
            )
        except ValueError as exc:
            return {"error": str(exc)}
        created = self._drive.upload_file(
            f"{i['title']}.epub", epub_bytes, "application/epub+zip", parent_id=self._document_publisher.folder_id(),
        )
        self._drive_indexer.index_file(created)
        return {
            "status": "created",
            "id": created["id"],
            "name": created["name"],
            "webViewLink": created.get("webViewLink"),
            "mode_used": mode_used,
        }

    def _tool_drive_delete_file(self, i: dict) -> dict:
        if not i.get("confirmed"):
            return self._pending({"file_id": i.get("file_id")})
        self._drive.delete_file(i["file_id"])
        return {"status": "deleted", "file_id": i["file_id"]}

    def _tool_drive_share_file(self, i: dict) -> dict:
        if not i.get("confirmed"):
            return self._pending({"file_id": i.get("file_id"), "role": i.get("role", "reader"), "email": i.get("email")})
        result = self._drive.share_file(i["file_id"], role=i.get("role", "reader"), email=i.get("email"))
        return {"status": "shared", "permission_id": result.get("id")}

    def _tool_drive_update_document(self, i: dict) -> dict:
        if not i.get("confirmed"):
            current = ""
            try:
                current = self._drive.read_document_text(i.get("file_id", ""))
            except Exception:
                pass
            return self._pending(
                {
                    "file_id": i.get("file_id"),
                    "new_content": i.get("new_content"),
                    "current_content_preview": current[:500],
                }
            )
        return self._drive.replace_document_body(i["file_id"], i["new_content"])

    def _tool_notion_update_block(self, i: dict) -> dict:
        if not i.get("confirmed"):
            preview = {
                "block_id": i.get("block_id"),
                "block_type": i.get("block_type"),
                "new_content": i.get("content"),
            }
            try:
                preview["current_content"] = self._notion.get_block(i["block_id"])["text"]
            except Exception:
                pass
            return self._pending(preview)
        return self._notion.update_block(i["block_id"], i["block_type"], i["content"])

    def _tool_notion_update_table_cell(self, i: dict) -> dict:
        if not i.get("confirmed"):
            preview = {
                "block_id": i.get("block_id"),
                "column_index": i.get("column_index"),
                "new_content": i.get("content"),
            }
            try:
                row = self._notion.get_table_row(i["block_id"])
                preview["current_cells"] = row["cells"]
            except Exception:
                pass
            return self._pending(preview)
        return self._notion.update_table_cell(i["block_id"], i["column_index"], i["content"])

    def _tool_notion_delete_block(self, i: dict) -> dict:
        if not i.get("confirmed"):
            preview = {"block_id": i.get("block_id")}
            try:
                preview["current_content"] = self._notion.get_block(i["block_id"])["text"]
            except Exception:
                pass
            return self._pending(preview)
        return self._notion.delete_block(i["block_id"])

    def _tool_notion_move_page(self, i: dict) -> dict:
        if not i.get("confirmed"):
            preview = {
                "page_id": i.get("page_id"),
                "new_parent_database_id": i.get("new_parent_database_id"),
            }
            # Aviso real de qué properties existen en la database destino —
            # Notion descarta en silencio cualquiera de la página que no
            # matchee ahí; best-effort, nunca bloquea el preview si falla.
            try:
                dest_schema = self._notion.get_database(i["new_parent_database_id"])["properties"]
                preview["destination_properties"] = list(dest_schema.keys())
            except Exception:
                pass
            return self._pending(preview)
        return self._notion.move_page(i["page_id"], i["new_parent_database_id"])

    def _tool_notion_create_database(self, i: dict) -> dict:
        if not i.get("confirmed"):
            return self._pending(
                {
                    "parent_page_id": i.get("parent_page_id"),
                    "title": i.get("title"),
                    "properties": i.get("properties"),
                }
            )
        return self._notion.create_database(i["parent_page_id"], i["title"], i["properties"])

    def _tool_notion_archive_page(self, i: dict) -> dict:
        if not i.get("confirmed"):
            return self._pending({"page_id": i.get("page_id")})
        return self._notion.archive_page(i["page_id"])

    def _tool_project_delete(self, i: dict) -> dict:
        # A propósito solo borra el registro local de Snarf — ProjectManager.
        # delete() NUNCA toca la carpeta/archivos reales de Drive, para no
        # repetir el incidente de datos reales de esta misma sesión.
        if not i.get("confirmed"):
            return self._pending({"project_id": i.get("project_id")})
        return self._projects.delete(i["project_id"])

    def _tool_second_brain_link_project(self, i: dict) -> dict:
        # Reusa get_project (ya valida existencia real + no-archivada) en vez
        # de un método de validación aparte — mismo dato, un solo camino.
        notion_page = self._second_brain.get_project(i["notion_page_id"])
        if notion_page is None:
            return {
                "status": "error",
                "message": "No se encontró esa página en Notion (o está archivada) — verificá el id.",
            }
        record = self._projects.set_notion_link(i["project_id"], i["notion_page_id"])
        if record is None:
            return {"status": "error", "message": f"No existe el proyecto {i['project_id']} en Snarf."}
        return {
            "status": "linked",
            "project_id": record["id"],
            "notion_project_page_id": record["notion_project_page_id"],
        }

    def _tool_second_brain_onboarding_auto_build(self, i: dict) -> dict:
        if not i.get("confirmed"):
            return self._pending({"parent_page_id": i.get("parent_page_id")})
        return self._second_brain.auto_build_workspace(i["parent_page_id"])

    def _tool_personality_set_sarcasm(self, i: dict) -> dict:
        # Cambio de configuración explícito y deliberado (el fundador lo pidió
        # por mensaje) — mismo peso que tocar el slider a mano, así que
        # persiste de una. Distinto del damping en situación crítica, que es
        # puro criterio del modelo y nunca toca este valor guardado.
        prefs = personality_prefs.save_prefs(self._user_id, {"sarcasm_level": i["level"]})
        return {"status": "updated", "sarcasm_level": prefs["sarcasm_level"]}

    def _tool_profile_set_name(self, i: dict) -> dict:
        # Persiste para siempre, atado al mismo user_id de las credenciales de
        # Google y el resto de las preferencias — nunca inventado, solo lo que
        # la propia persona dijo en este intercambio (ver ADR de esta feature).
        profile = user_profile.save_profile(self._user_id, {"name": i["name"]})
        return {"status": "updated", "name": profile["name"]}

    def _handle_tool(self, name: str, tool_input: dict) -> object:
        handler = self._tool_handlers.get(name)
        if not handler:
            activity_log.record(name, "unknown_tool", detalle=detail.extract(name, "unknown_tool", tool_input, None))
            return {"error": f"herramienta desconocida: {name}"}
        if name in ("executive_board_consult", "executive_team_run"):
            # Fase 22 (ADR 0165): marca que este turno consultó a la Junta
            # Directiva ANTES de que se decida el área — nunca decide el
            # área en sí (eso sigue siendo el lookup determinístico de
            # areas.area_for_tool más abajo), solo queda como contexto
            # auditable en el span de Project Manager de una tool posterior.
            # executive_team_run (ADR 0198) se suma acá mismo: un equipo
            # también es una consulta real a roles de la Inteligencia
            # Ejecutiva, mismo criterio de auditoría.
            context.set_board_consulted(True)
        area_id = areas.area_for_tool(name)
        if area_id is None:
            return self._handle_tool_span(name, tool_input)
        # Project Manager + área (Fase 22, ADR 0165): dos spans "workflow"
        # reales (mismo kind que "turn"/"executive_board", ver spans.py) que
        # antes no existían — hoy la tool colgaba plana bajo "turn". El PM
        # cierra apenas decide el área (su trabajo real es ese lookup, nada
        # más — no fingir un span "vivo" haciendo algo que no hace) mientras
        # sigue siendo el padre ambiente: context.span() solo se libera al
        # salir del `with`, así que abrir area_span/tool span DESPUÉS de
        # finish(pm) igual los anida correctamente bajo pm.
        pm = spans.start_workflow("project_manager", detalle=f"tool={name} area={area_id}")
        with spans.active(pm):
            spans.finish(
                pm, estado="completo",
                attributes={"area": area_id, "tool": name, "board_consulted": context.get_board_consulted()},
            )
            area_span = spans.start_workflow(f"area:{area_id}")
            try:
                with spans.active(area_span):
                    result = self._handle_tool_span(name, tool_input)
            except BaseException:
                spans.fail(area_span, reason="unhandled")
                raise
            spans.finish(area_span, estado="completo")
        return result

    def _handle_tool_span(self, name: str, tool_input: dict) -> object:
        handler = self._tool_handlers[name]
        started = time.monotonic()
        # spans.start_tool (Fase 1 del plan de observabilidad): abre un
        # tool.started correlacionado con el turno/tool/subagente que lo
        # llamó. `spans.active(span)` es lo que hace que cualquier llamada
        # LLM que el propio handler dispare (un Specialist llamando a su
        # rol) quede automáticamente parentada a ESTE tool call, sin que el
        # Specialist tenga que saber nada de spans — cierra el gap #3 de
        # TELEMETRY_SCHEMA.md (correlacionar un tool call con el LLM que
        # dispara adentro) sin tocar ningún Specialist.
        span = spans.start_tool(name, detalle=detail.extract(name, "started", tool_input, None))
        try:
            with spans.active(span):
                result = handler(tool_input)
            activity_log.record(
                name, "ok", duration_ms=(time.monotonic() - started) * 1000,
                detalle=detail.extract(name, "ok", tool_input, result),
                preview=detail.extract_preview(name, tool_input, result),
                span=span,
            )
            # HITL genérico (Fase 8, ADR 0143): mismo chokepoint que ya abre
            # tool.started/tool.finished — nunca una segunda implementación
            # del protocolo de confirmed en dos pasos, solo su observabilidad
            # real sobre el event bus.
            if isinstance(result, dict) and result.get("status") == "pending_confirmation":
                events.record_lifecycle_event(
                    events.APPROVAL_REQUESTED, span,
                    detalle=detail.truncate_detalle(f"Pide confirmación: {name}"),
                    preview=result.get("preview"),
                )
            elif tool_input.get("confirmed") is True and (name in HIGH_IMPACT_TOOLS or name in BULK_READ_GATED_TOOLS):
                events.record_lifecycle_event(
                    events.APPROVAL_GRANTED, span, detalle=detail.truncate_detalle(f"Confirmado: {name}")
                )
            return result
        except Exception as exc:
            activity_log.record(name, "error", duration_ms=(time.monotonic() - started) * 1000, error=str(exc), span=span)
            return {"error": str(exc)}

    def _capped_for_replay(self, text: str) -> str:
        """Lo que se vuelve a mandar al LLM al reconstruir el historial de una
        conversación — nunca lo que se guarda ni lo que se muestra en la UI.
        Antes: un corte duro por caracteres que perdía en silencio todo lo que
        pasaba el tope. Ahora: un resumen real (vía el rol history_compaction,
        modelo barato) que condensa fielmente en vez de truncar — cacheado en
        memoria por contenido, así la misma entrada vieja no se re-resume en
        cada turno mientras siga dentro de la ventana de últimas 10 entradas.
        Si el resumen falla por cualquier motivo (LLM no disponible, error de
        red), cae al corte duro de siempre — nunca rompe el turno."""
        if len(text) <= HISTORY_REPLAY_MAX_CHARS:
            return text
        cache_key = hashlib.sha256(text.encode("utf-8")).hexdigest()
        cached = self._history_summary_cache.get(cache_key)
        if cached is not None:
            return cached
        summary = self._summarize_history_entry(text)
        self._history_summary_cache[cache_key] = summary
        return summary

    def _proactive_notion_context(self, query: str) -> str | None:
        """Retrieval proactivo (ADR 0192): resumen corto de lo más relevante
        ya indexado de Notion para lo que el fundador acaba de escribir —
        sin que tenga que pedirlo con knowledge_search. Ajuste honesto al
        diseño original del roadmap: NO filtra por project_id (los ítems
        indexados de Notion no llevan esa etiqueta — solo `location`/
        `notion_url`, ver NotionSource, ADR 0173 — filtrar por un campo que
        no existe devolvería siempre vacío) — busca sobre TODO lo indexado
        de Notion, acotado por relevancia semántica real. Nunca rompe el
        turno: cualquier fallo (Notion no indexado, error de embeddings)
        degrada a None en silencio."""
        manifest = self._notion_indexer.manifest_summary()
        if not manifest.get("indexed"):
            return None
        cache_key = query.strip().lower()
        cached = self._notion_retrieval_cache.get(cache_key)
        if cached and time.time() - cached[0] < NOTION_RETRIEVAL_CACHE_TTL_SECONDS:
            return cached[1]
        try:
            results = self._notion_indexer.search(query, top_k=NOTION_RETRIEVAL_TOP_K)
            context = "\n---\n".join(r["text"] for r in results if r.get("text")) or None
        except Exception:
            context = None
        self._notion_retrieval_cache[cache_key] = (time.time(), context)
        return context

    def _summarize_history_entry(self, text: str) -> str:
        # Tope duro ANTES de intentar compactar vía LLM: una entrada extrema
        # (ej. una respuesta anterior con el volcado completo de un resultado
        # de herramienta gigante) puede superar los ~20K tokens — mandarle eso
        # entero al rol history_compaction (modelo rápido local, mlx_lm.server
        # en esta misma Mac) tumbó el server real por out-of-memory de Metal
        # (ver ADR de esta ronda: 31GB de RAM real, casi toda la Mac). Por
        # encima de este tope se corta directo, sin pasar por el LLM — no hay
        # forma segura de "compactar" algo tan grande con un modelo de 4B.
        if len(text) > HISTORY_COMPACTION_INPUT_MAX_CHARS:
            return _hard_cut_for_replay(text)
        try:
            llm = llm_routing.build_resilient_llm("history_compaction")
            if not llm.available:
                raise RuntimeError("history_compaction no disponible")
            system = prompt_registry.get_active_text("history_compaction", HISTORY_COMPACTION_SYSTEM_PROMPT)
            result = llm.generate(system=system, messages=[{"role": "user", "content": text}])
            summary = result.text.strip()
            if summary:
                return summary
        except Exception:
            pass
        return _hard_cut_for_replay(text)

    def handle(
        self,
        channel_name: str,
        user_input: str,
        conversation_id: str | None = None,
        input_audio_id: str | None = None,
        request_id: str | None = None,
        reply_to_id: str | None = None,
        attachment_file_id: str | None = None,
        attachment_name: str | None = None,
        attachment_mime_type: str | None = None,
    ) -> LLMResponse:
        # project_id ya no viaja como parámetro por mensaje (eso no alcanzaba:
        # una conversación recién creada sin mensajes no tenía nada que
        # taggear, y reasignarla no tenía dónde guardar "cuál es su proyecto
        # actual"). Se resuelve acá, por conversation_id, contra la
        # asociación persistente real (Proyectos Mark II) — así se aplica
        # automáticamente en TODOS los turnos mientras dure la asignación,
        # sin que el frontend tenga que recordarlo. Calculado antes del if
        # para quedar disponible también en modo eco (memory.append de abajo
        # lo necesita en cualquier caso).
        project_id = self._memory.get_conversation_project(conversation_id) if conversation_id else None

        # "Responder a este mensaje" (ver ADR de esta ronda): el texto citado
        # se resuelve acá, contra la memoria real — nunca se confía en lo que
        # el frontend diga que Snarf dijo. Si el id no existe (mensaje viejo
        # sin id, carrera, id inválido), se degrada en silencio: el turno
        # sigue sin la cita, nunca rompe por esto.
        quoted_text = None
        if reply_to_id and conversation_id:
            quoted_entry = self._memory.get_entry(conversation_id, reply_to_id)
            if quoted_entry:
                quoted_text = quoted_entry.get("response")

        # Contexto por thread (snarf/telemetry/context.py, ver ADR 0079 y el
        # precedente de ADR 0041 sobre threading.local en un singleton
        # compartido): mientras dure este turno, cualquier evento de
        # telemetría emitido más abajo (tool calls vía _handle_tool, la
        # llamada al LLM) queda taggeado con este conversation_id — sin eso,
        # "agregar costo por sesión" (Fase 3 del plan de HUD) no tendría de
        # dónde sacar la sesión. Siempre se limpia en el finally, nunca
        # sobrevive más allá de este turno.
        context.set_conversation_id(conversation_id)
        # user_id (Fase 1 del plan de observabilidad): el Orchestrator es
        # una instancia fija por user_id (ver __init__) — se propaga acá
        # para que cada evento de este turno quede particionado por usuario,
        # sin esperar a que exista multi-usuario real (Fase 3) para
        # agregarlo, y así evitar una segunda migración de esquema después.
        context.set_user_id(self._user_id)
        # Rol real para usage_log/telemetry_events (ADR de esta ronda) — acá
        # sí es siempre "orchestrator" porque este método es exactamente ese
        # rol de instancia fija (ver comentario de _ResilientLLM en
        # llm_routing.py sobre por qué no pasa por ahí).
        context.set_llm_role("orchestrator")
        # request_id (ver snarf/runtime/cancellation.py y ADR de esta ronda):
        # viaja por contexto, no por generate_kwargs, porque ese dict se pasa
        # sin cambios a otras dos capacidades LLM (OpenAICompatible, Gemini)
        # con firma estricta — solo AnthropicLLM._create() lo lee de acá para
        # poder cortar el stream a mitad de camino.
        context.set_request_id(request_id)
        # board_consulted (Fase 22 del plan de observabilidad/n8n, ADR 0165):
        # reseteado acá por la misma razón defensiva que conversation_id/
        # user_id de arriba — _handle_tool lo pone en True si este turno
        # consultó a la Junta Directiva antes de rutear una tool a un área,
        # nunca decide el área (eso sigue siendo un lookup determinístico
        # contra snarf/runtime/areas.py), solo queda como contexto auditable.
        context.set_board_consulted(False)
        # spans.start_workflow (Fase 1): raíz de la traza de este turno —
        # todo tool call y toda llamada LLM de acá para abajo (incluido el
        # fan-out de la Inteligencia Ejecutiva, ver executive/specialist.py)
        # comparte este trace_id y cuelga de este event_id como padre.
        turn = spans.start_workflow("turn", detalle=detail.truncate_detalle(user_input))
        try:
            with spans.active(turn):
                if not self._llm.available:
                    echo_text = (
                        "[modo eco - ANTHROPIC_API_KEY no configurada, ver .env.example] "
                        f"{user_input}"
                    )
                    response = LLMResponse(text=echo_text, speech=fallback_speech(echo_text))
                else:
                    system = prompt_registry.get_active_text("orchestrator_system_prefix", SYSTEM_PREFIX) + self._identity
                    # Se relee en cada turno (no se cachea en __init__ como
                    # self._identity) — a diferencia de los documentos de identidad,
                    # este valor puede cambiar a mitad de una conversación (desde
                    # configuración o por la tool personality_set_sarcasm) y debe
                    # reflejarse sin reiniciar Snarf.
                    sarcasm_level = personality_prefs.load_prefs(self._user_id)["sarcasm_level"]
                    system += sarcasm_instruction(sarcasm_level)
                    # Se relee en cada turno por el mismo motivo que sarcasm_level —
                    # profile_set_name puede guardar el nombre a mitad de conversación
                    # y tiene que reflejarse en el turno siguiente, sin reiniciar.
                    system += profile_identity_instruction(user_profile.load_profile(self._user_id)["name"])
                    if attachment_file_id:
                        # Adjunto pendiente (ADR 0202): el frontend recién lo
                        # subió a Drive en este mismo envío — nunca antes,
                        # mientras el fundador todavía estaba escribiendo. El
                        # file_id ya es real y usable con convert_to_epub/
                        # drive_read_file/etc., pero la ACCIÓN la decide
                        # únicamente lo que el fundador pidió en su texto —
                        # nunca asumir qué hacer con el archivo si no lo dijo.
                        mime_note = f", mime_type: {attachment_mime_type}" if attachment_mime_type else ""
                        system += (
                            f"\n\nEl fundador acaba de adjuntar el archivo \"{attachment_name}\" "
                            f"(file_id: {attachment_file_id}{mime_note}) a este mismo mensaje — ya está "
                            "subido a su Drive. Hacé con él exactamente lo que te pida en su texto (por "
                            "ejemplo convert_to_epub si pide convertirlo a ebook/epub, o drive_read_file "
                            "si pide que lo leas/resumas)."
                        )
                    if project_id:
                        # Si el proyecto no existe más o no tiene prompt propio, se
                        # degrada en silencio (nunca rompe el turno).
                        project = self._projects.get(project_id)
                        if project and project.get("prompt"):
                            system += (
                                f"\n\nEstás trabajando dentro del proyecto '{project['name']}'. "
                                f"Instrucciones propias de este proyecto:\n{project['prompt']}\n"
                            )
                        # Retrieval proactivo de Notion (ADR 0192) — solo si
                        # el proyecto ya tiene Second Brain vinculado, nunca
                        # gasta el pipeline de embeddings en proyectos sin
                        # Notion.
                        if project and project.get("notion_project_page_id"):
                            notion_context = self._proactive_notion_context(user_input)
                            if notion_context:
                                system += (
                                    "\n\nEsto está indexado de tu Notion y podría ser relevante para lo "
                                    "que acabás de escribir — usalo si aplica, nunca lo repitas literal "
                                    f"sin necesidad:\n{notion_context}\n"
                                )
                    messages = []
                    for entry in self._memory.recent(10, conversation_id=conversation_id):
                        messages.append({"role": "user", "content": self._capped_for_replay(entry["input"])})
                        messages.append({"role": "assistant", "content": self._capped_for_replay(entry["response"])})
                    history_chars = sum(len(m["content"]) for m in messages)
                    history_entries = len(messages) // 2
                    # La cita solo se agrega al mensaje que el LLM ve ESTE turno
                    # — memory.append() más abajo sigue guardando user_input tal
                    # cual lo escribió el fundador, nunca envuelto. Si se
                    # guardara envuelto, un replay futuro de este mismo turno
                    # (ver el loop de arriba) repetiría la cita en cada mensaje
                    # posterior de la conversación, inflando tokens sin sentido.
                    effective_input = (
                        f'[Respondiendo puntualmente a esto que dijiste antes: "{quoted_text}"]\n\n{user_input}'
                        if quoted_text
                        else user_input
                    )
                    messages.append({"role": "user", "content": effective_input})
                    # Fase 6 del plan de HUD: registro real de cuánto contexto
                    # viaja alrededor de lo que el fundador efectivamente
                    # escribió — nunca una llamada extra al modelo, solo
                    # tamaños ya calculados acá mismo.
                    input_preprocessing.record(conversation_id, user_input, len(system), history_chars, history_entries)
                    generate_kwargs = {"system": system, "messages": messages, "tools": TOOLS, "tool_handler": self._handle_tool}
                    # Si el rol está en un fallback automático ya vencido (ver
                    # llm_routing.maybe_revert_expired_fallback), reintenta solo
                    # el proveedor local por defecto ANTES de usar el fallback
                    # vigente — chequeo barato (compare de timestamps) salvo que
                    # de verdad corresponda reintentar. self._llm no está
                    # envuelto en _ResilientLLM acá (ver comentario más abajo),
                    # por eso el intento vive inline igual que attempt_fallback.
                    reverted_response, reverted_entry = llm_routing.maybe_revert_expired_fallback(
                        "orchestrator", llm_routing.load_routing()["orchestrator"], **generate_kwargs
                    )
                    if reverted_response is not None:
                        response = reverted_response
                        self.refresh_llm_routing()
                    else:
                        try:
                            response = self._llm.generate(**generate_kwargs)
                        except Exception as exc:
                            # Fallback automático real (ver llm_routing.attempt_fallback
                            # y ADR de esta ronda): un fallo real de PROVEEDOR (crédito
                            # agotado, rate limit, 5xx) reintenta solo con el siguiente
                            # proveedor disponible antes de rendirse. self._llm no está
                            # envuelto acá (ver comentario en attempt_fallback: muchos
                            # tests reemplazan orchestrator._llm._client/.generate
                            # directamente) — por eso el intento vive inline.
                            fallback_response, new_entry = llm_routing.attempt_fallback("orchestrator", llm_routing.load_routing()["orchestrator"], exc, **generate_kwargs)
                            if fallback_response is not None:
                                response = fallback_response
                                self.refresh_llm_routing()  # instancia fija — la próxima ronda ya tiene que usar el proveedor que funcionó
                            else:
                                # Antes esto tiraba un 500 crudo hasta /send — un fallo
                                # real del LLM degrada con gracia igual que /transcribe,
                                # en vez de romper la request. Se llega acá solo si
                                # ademas el fallback automático se agotó con todos los
                                # proveedores disponibles (o el error no era de
                                # proveedor, ver is_provider_level_error).
                                error_text = f"[error real del LLM, no pude responder: {exc}]"
                                response = LLMResponse(text=error_text, speech=fallback_speech(error_text))
            spans.finish(turn, estado="completo")
        except Exception:
            # Cualquier error real ya manejado arriba (LLM caído, fallback
            # agotado) termina en una LLMResponse de error, no en una
            # excepción hasta acá — este except cubre solo lo genuinamente
            # inesperado (ver ADR de esta ronda). No vuelve a inventar una
            # respuesta: re-lanza tal cual, el turno queda marcado failed.
            spans.fail(turn, reason="unhandled")
            raise
        finally:
            context.clear_llm_role()
            context.clear_conversation_id()
            context.clear_request_id()
            context.clear_user_id()
            context.clear_board_consulted()

        self._memory.append(
            channel_name, user_input, response.text,
            conversation_id=conversation_id, project_id=project_id, input_audio_id=input_audio_id,
            speech=response.speech, deliverable=response.deliverable,
            cancelled=response.cancelled,
            id=request_id, reply_to_id=reply_to_id,
        )
        return response

    def generate_conversation_title(self, conversation_id: str) -> None:
        """Genera y persiste un título corto para esta conversación a partir de
        su primer intercambio real. Pensada para llamarse una sola vez, como
        tarea de background apenas responde el primer mensaje (ver /send en
        app.py) — nunca bloquea ni rompe nada: si el LLM barato no está
        disponible o la llamada falla, la conversación se queda con el
        fallback existente (substring del primer mensaje, ver
        EpisodicMemory.list_conversations)."""
        if not self._title_llm.available:
            return
        entries = self._memory.get_conversation(conversation_id)
        if not entries:
            return
        first = entries[0]
        listing = f"Usuario: {first['input']}\n\nRespuesta: {first['response'][:500]}"
        context.set_conversation_id(conversation_id)
        context.set_user_id(self._user_id)
        context.set_llm_role("conversation_title")
        # spans.start_workflow (Fase 1): traza propia, distinta de la del
        # turno de chat que la disparó como background task (ver /send en
        # app.py) — es una llamada LLM real e independiente, no un hijo del
        # turno principal, que para entonces ya terminó y devolvió su
        # respuesta.
        turn = spans.start_workflow("conversation_title", detalle=detail.truncate_detalle(listing))
        title_kwargs = {
            "system": prompt_registry.get_active_text("conversation_title", CONVERSATION_TITLE_SYSTEM_PROMPT),
            "messages": [{"role": "user", "content": listing}],
        }
        title = None
        try:
            with spans.active(turn):
                reverted_response, reverted_entry = llm_routing.maybe_revert_expired_fallback(
                    "conversation_title", llm_routing.load_routing()["conversation_title"], **title_kwargs
                )
                if reverted_response is not None:
                    title = reverted_response.text
                    self.refresh_llm_routing()
                else:
                    try:
                        title = self._title_llm.generate(**title_kwargs).text
                    except Exception as exc:
                        # Mismo fallback automático que el chat principal (ver
                        # attempt_fallback) — un título es de bajo riesgo (nunca
                        # bloquea la respuesta real), pero no hay motivo para
                        # perderlo solo porque el proveedor de este rol se quedó
                        # sin crédito mientras otro sigue disponible.
                        fallback_response, new_entry = llm_routing.attempt_fallback(
                            "conversation_title", llm_routing.load_routing()["conversation_title"], exc, **title_kwargs
                        )
                        if fallback_response is not None:
                            title = fallback_response.text
                            self.refresh_llm_routing()
            spans.finish(turn, estado="completo" if title else "error")
        except Exception:
            spans.fail(turn, reason="unhandled")
            raise
        finally:
            context.clear_llm_role()
            context.clear_conversation_id()
            context.clear_user_id()
        title = (title or "").strip().strip('"').strip("'").rstrip(".")
        if title:
            self._memory.set_title(conversation_id, title[:CONVERSATION_TITLE_MAX_CHARS])

    def refresh_llm_routing(self) -> None:
        """Reconstruye self._llm/self._title_llm contra la configuración de
        ruteo vigente (snarf/runtime/llm_routing.py) — llamado desde
        PUT /llm-routing apenas el fundador cambia algo, para que el cambio
        se aplique en el próximo turno sin reiniciar el servidor. Bug real
        encontrado en esta misma ronda: sin esto, cambiar el rol
        "conversation_title" a Gemini desde la interfaz no tenía ningún
        efecto hasta el próximo reinicio — el título seguía cayendo al
        fallback en silencio. Los otros 3 roles (gmail_digest, drive_vision,
        project_summary) ya se resuelven en cada llamada vía factory, no
        necesitan este refresh."""
        self._llm = llm_routing.build_llm("orchestrator")
        self._title_llm = llm_routing.build_llm("conversation_title")
