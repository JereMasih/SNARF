import asyncio
import base64
import os
import socket
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

from fastapi import BackgroundTasks, Cookie, Depends, FastAPI, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

from snarf.capabilities.elevenlabs_tts import ElevenLabsTTS
from snarf.capabilities.google_auth import TOKENS_DIR as GOOGLE_TOKENS_DIR
from snarf.core.orchestrator import DEFAULT_USER_ID, LOCAL_FILES_DATA_DIR, Orchestrator
from snarf.memory.audio_store import MIME_BY_EXT, AudioStore
from snarf.runtime.dashboard_prefs import load_prefs, save_prefs
from snarf.runtime.personality_prefs import load_prefs as load_personality_prefs, save_prefs as save_personality_prefs
from snarf.runtime.user_profile import load_profile as load_user_profile, save_profile as save_user_profile
from snarf.runtime import llm_routing
from snarf.runtime import data_backup
from snarf.knowledge.extraction import categorize_mime
from snarf.specialists import dashboard_curator as dashboard_curator_module
from snarf.specialists.dashboard_curator import DashboardCuratorSpecialist
from snarf.telemetry import (
    activity_log,
    brain,
    cost_history,
    detail,
    events,
    input_log,
    input_preprocessing,
    relevance,
    usage_tracker,
    verbs,
    widget_summary,
    widget_templates,
)
from snarf.voice.router import TierUnavailable, VoiceRouter
from snarf.runtime.web_auth import (
    SESSION_COOKIE_NAME,
    SESSION_MAX_AGE_SECONDS,
    create_session_token,
    is_authenticated,
    password_matches,
    require_user,
)

app = FastAPI()
voice_router = VoiceRouter()
# Instancia separada solo para subscription_info() del widget de dashboard
# (cupo real de la cuenta de ElevenLabs) — ya no es quien sintetiza la voz de
# cada turno, eso lo decide voice_router según voice/config.yaml.
_elevenlabs_for_dashboard = ElevenLabsTTS()
orchestrator = Orchestrator(user_id=DEFAULT_USER_ID)
audio_store = AudioStore()


def _dashboard_curation_snapshot() -> dict:
    all_events = events.all_events()
    today_key = datetime.now(ZoneInfo(cost_history.FOUNDER_TIMEZONE)).strftime("%Y-%m-%d")
    day_summary = cost_history.by_day(all_events)
    return widget_summary.curation_snapshot(all_events, day_summary, today_key=today_key)


# Vista HUD del dashboard (rediseño radial) — Especialista Cognitivo real
# (no un módulo de código más) que cura el dashboard a partir de datos ya
# reales (ver snarf/telemetry/widget_summary.py). Mismo patrón cache-first
# que GmailDigestSpecialist: nunca llama al LLM en cada request del
# navegador, solo el loop periódico de abajo lo refresca de verdad.
dashboard_curator = DashboardCuratorSpecialist(
    snapshot_provider=_dashboard_curation_snapshot,
    llm_factory=lambda: llm_routing.build_resilient_llm("dashboard_curator"),
    user_id=DEFAULT_USER_ID,
)
dashboard_curating_in_progress = False


def _google_connected(user_id: str) -> bool:
    return (GOOGLE_TOKENS_DIR / f"{user_id}.json").exists()


BACKUP_INTERVAL_SECONDS = 6 * 3600
# Política de retención acordada con el fundador: transcripciones/respuestas
# de texto se guardan para siempre (episodic_memory.jsonl, de siempre); los
# archivos de audio en sí (notas de voz + respuestas de Snarf cacheadas) se
# purgan a los 7 días — son la parte cara en espacio, no en información.
AUDIO_PURGE_MAX_AGE_SECONDS = 7 * 24 * 3600
AUDIO_PURGE_INTERVAL_SECONDS = 6 * 3600


async def _periodic_backup_loop():
    while True:
        await asyncio.sleep(BACKUP_INTERVAL_SECONDS)
        data_backup.backup_now()


async def _periodic_audio_purge_loop():
    while True:
        await asyncio.sleep(AUDIO_PURGE_INTERVAL_SECONDS)
        audio_store.purge_older_than(AUDIO_PURGE_MAX_AGE_SECONDS)


# Cadencia real del curador del dashboard: nunca disparado por el poll del
# navegador (GET /dashboard/widget_summaries siempre sirve el cache) — solo
# este loop de backend llama al LLM de verdad. Chequea cada minuto si la
# señal real cambió (nodo más relevante distinto, alerta de costo nueva,
# cambio en la cantidad de errores recientes) para refrescar antes si hace
# falta, pero nunca más seguido que eso — mismo criterio de control de costo
# que ya evitó el incidente real de gasto documentado en este repo.
DASHBOARD_CURATION_INTERVAL_SECONDS = 10 * 60
DASHBOARD_CURATION_CHECK_INTERVAL_SECONDS = 60


def _dashboard_curation_signal() -> tuple:
    snapshot = _dashboard_curation_snapshot()
    top_node = snapshot["summaries"][0]["node_id"] if snapshot["summaries"] else None
    return (top_node, snapshot["cost_alert"] is not None, len(snapshot["recent_errors"]))


async def _periodic_dashboard_curation_loop():
    global dashboard_curating_in_progress
    last_signal = None
    elapsed_since_refresh = DASHBOARD_CURATION_INTERVAL_SECONDS  # refresca en el primer ciclo real
    while True:
        await asyncio.sleep(DASHBOARD_CURATION_CHECK_INTERVAL_SECONDS)
        elapsed_since_refresh += DASHBOARD_CURATION_CHECK_INTERVAL_SECONDS
        signal = _dashboard_curation_signal()
        signal_changed = last_signal is not None and signal != last_signal
        if elapsed_since_refresh >= DASHBOARD_CURATION_INTERVAL_SECONDS or signal_changed:
            dashboard_curating_in_progress = True
            try:
                dashboard_curator.refresh()
            finally:
                dashboard_curating_in_progress = False
            elapsed_since_refresh = 0
        last_signal = signal


@app.on_event("startup")
async def warmup():
    orchestrator.warmup()
    # PYTEST_CURRENT_TEST lo setea pytest automáticamente durante cada test —
    # evita que cada TestClient() de la suite dispare un backup real sobre
    # data/ (irían cientos por corrida) y una tarea de fondo que nunca se
    # cancela entre tests.
    if not os.environ.get("PYTEST_CURRENT_TEST"):
        data_backup.backup_now()
        asyncio.create_task(_periodic_backup_loop())
        audio_store.purge_older_than(AUDIO_PURGE_MAX_AGE_SECONDS)
        asyncio.create_task(_periodic_audio_purge_loop())
        asyncio.create_task(_periodic_dashboard_curation_loop())


class SendRequest(BaseModel):
    text: str
    conversation_id: str | None = None
    input_audio_id: str | None = None


class SendResponse(BaseModel):
    response: str
    speech: str
    deliverable: str | None = None
    thinking: str | None = None


class TTSRequest(BaseModel):
    text: str
    # None = tier 'local' (default de toda conversación, ver voice/config.yaml).
    # Explícito ('premium', etc.) solo cuando se pide voz de verdad o un asset
    # publicable — el router nunca escala de tier por su cuenta.
    tier: str | None = None


class TTSResponse(BaseModel):
    audio_base64: str | None = None
    audio_id: str | None = None


class LoginRequest(BaseModel):
    password: str


class DashboardPreferences(BaseModel):
    visible_widgets: dict[str, bool] = {}
    panel_order: list[str] = []
    widget_options: dict[str, dict] = {}
    # Vista HUD del dashboard (rediseño radial) — campos aditivos, nunca
    # tocan los tres de arriba (Vista clásica sigue funcionando igual que
    # siempre, sin cambios, mismo criterio de reversibilidad real).
    dashboard_view: str = "classic"
    hud_widget_state: dict[str, str] = {}
    hud_widget_options: dict[str, dict] = {}
    # v2 del rediseño HUD: posición del chat y si el drawer de
    # conversaciones/proyectos queda fijo abierto — también aditivos.
    hud_chat_position: str = "left"
    hud_sidebar_pinned: bool = False
    show_message_timestamps: bool = False


class PersonalityPreferences(BaseModel):
    sarcasm_level: float = 7.5


class ProfileRequest(BaseModel):
    name: str


class ProjectCreateRequest(BaseModel):
    name: str


class ProjectPromptRequest(BaseModel):
    prompt: str


class ProjectTextRequest(BaseModel):
    text: str


class ConversationProjectRequest(BaseModel):
    project_id: str


@app.get("/")
def index(snarf_session: str | None = Cookie(default=None)):
    if not is_authenticated(snarf_session):
        return RedirectResponse("/login")
    return FileResponse("web/index.html")


@app.get("/login")
def login_page():
    return FileResponse("web/login.html")


@app.post("/login")
def login(payload: LoginRequest):
    if not os.environ.get("SESSION_SECRET"):
        raise HTTPException(503, "SESSION_SECRET no configurada en el servidor")
    if not password_matches(payload.password):
        raise HTTPException(401, "contraseña incorrecta")
    token = create_session_token(os.environ["SESSION_SECRET"], DEFAULT_USER_ID)
    response = JSONResponse({"status": "ok"})
    response.set_cookie(
        SESSION_COOKIE_NAME, token, max_age=SESSION_MAX_AGE_SECONDS, httponly=True, samesite="lax", secure=True
    )
    return response


@app.post("/logout")
def logout():
    response = JSONResponse({"status": "ok"})
    response.delete_cookie(SESSION_COOKIE_NAME)
    return response


@app.get("/status")
def status():
    return {
        "stt_available": voice_router.stt_available,
        "tts_available": voice_router.tts_status()["available"],
        "llm_available": orchestrator.llm_available,
    }


@app.post("/transcribe")
async def transcribe(file: UploadFile, user_id: str = Depends(require_user)):
    if not voice_router.stt_available:
        return {"transcript": ""}
    audio_bytes = await file.read()
    if len(audio_bytes) < 2000:
        return {"transcript": ""}
    input_log.record("voice")
    # Se guarda la nota de voz real ANTES de intentar transcribir — así el
    # audio sigue existiendo (reproducible como nota de voz en el chat, con
    # su transcripción como desplegable) incluso si el STT falla o devuelve
    # vacío; se purga solo a los 7 días si nunca termina en un mensaje real.
    ext = (file.filename or "audio.webm").rsplit(".", 1)[-1] if "." in (file.filename or "") else "webm"
    audio_id = audio_store.save(audio_bytes, ext)
    try:
        text = voice_router.transcribe(audio_bytes, filename=file.filename or "audio.webm")
    except Exception as exc:
        print(f"[transcribe] fallo de STT, degradando a transcript vacío: {exc}")
        # Distinto de "no se detectó voz" (audio corto, o Scribe transcribió
        # silencio real): acá el servicio en sí falló (cuota agotada, red,
        # etc.) — sin este campo, la interfaz no puede distinguir ambos casos
        # y termina diciéndole al usuario "no se escuchó nada" cuando en
        # realidad el micrófono funcionó perfecto.
        return {"transcript": "", "error": "no se pudo transcribir: el servicio de voz no está disponible ahora", "audio_id": audio_id}
    return {"transcript": text, "audio_id": audio_id}


@app.post("/send", response_model=SendResponse)
def send(payload: SendRequest, background_tasks: BackgroundTasks, user_id: str = Depends(require_user)):
    input_log.record("text", detalle=detail.truncate_detalle(payload.text))
    # Se chequea ANTES de handle() (que ya va a agregar la entrada de este
    # turno) si esta conversación todavía no tenía ningún mensaje — así se
    # sabe si este es el primer intercambio real, sin ambigüedad.
    is_first_turn = bool(payload.conversation_id) and not orchestrator.memory.get_conversation(payload.conversation_id)
    # El proyecto de la conversación (si tiene uno asignado) se resuelve solo
    # dentro de orchestrator.handle() por conversation_id — ver Proyectos
    # Mark II. Ya no viaja como parámetro por mensaje.
    result = orchestrator.handle(
        "visual", payload.text, conversation_id=payload.conversation_id, input_audio_id=payload.input_audio_id
    )
    if is_first_turn:
        # En background: nombrar la conversación es un nice-to-have, no debe
        # sumarle latencia a la respuesta que el fundador está esperando.
        background_tasks.add_task(orchestrator.generate_conversation_title, payload.conversation_id)
    return SendResponse(response=result.text, speech=result.speech, deliverable=result.deliverable, thinking=result.thinking)


@app.post("/tts", response_model=TTSResponse)
def synthesize_speech(payload: TTSRequest, user_id: str = Depends(require_user)):
    # Caché por contenido: la misma respuesta ya sintetizada antes (con el
    # mismo tier) no vuelve a pagar una llamada real al proveedor — escuchar
    # varias veces la misma respuesta reusa siempre el mismo archivo. audio_id
    # se devuelve además de audio_base64 para que el frontend arme una
    # burbuja de nota de voz real (GET /audio/{id}), no solo un data-URI de
    # un solo uso. La clave de caché incluye el tier para no confundir el
    # audio local (gratis) con el premium (pago) de la misma frase.
    cache_key = f"{payload.tier or 'local'}:{payload.text}"
    audio_bytes = audio_store.get_cached_tts(cache_key)
    if audio_bytes is None:
        try:
            # Sin `tier` explícito, voice_router.speak() SOLO intenta el tier
            # 'local' — nunca escala solo a 'premium'/'hosted' (esos cuestan
            # plata real). Si local está caído, esto tira TierUnavailable en
            # vez de gastar en silencio.
            audio_bytes = voice_router.speak(payload.text, tier=payload.tier)
        except TierUnavailable:
            return TTSResponse(audio_base64=None)
        audio_store.save_tts(cache_key, audio_bytes)
    audio_id = audio_store.tts_cache_id(cache_key)
    return TTSResponse(audio_base64=base64.b64encode(audio_bytes).decode("ascii"), audio_id=audio_id)


@app.get("/audio/{audio_id}")
def get_audio(audio_id: str, user_id: str = Depends(require_user)):
    path = audio_store.path_for(audio_id)
    if path is None:
        raise HTTPException(404, "audio no encontrado (puede haber sido purgado ya)")
    ext = audio_id.rsplit(".", 1)[-1].lower()
    return FileResponse(path, media_type=MIME_BY_EXT.get(ext, "application/octet-stream"))


@app.post("/files/upload")
async def upload_file(file: UploadFile, project_id: str | None = Form(None), user_id: str = Depends(require_user)):
    if not _google_connected(user_id):
        raise HTTPException(400, "Google no conectado")
    content = await file.read()
    mime_type = file.content_type or "application/octet-stream"
    input_log.record("file", category=categorize_mime(mime_type), detalle=detail.truncate_detalle(file.filename))
    try:
        # Con project_id: sube a la carpeta real de ESE proyecto e indexa
        # etiquetado con su id, para que search_within() no quede siempre
        # vacío. Sin project_id: comportamiento de siempre (carpeta
        # "Snarf/Archivos" genérica).
        extra_metadata = None
        if project_id:
            project = orchestrator.projects.get(project_id)
            if project is None:
                raise HTTPException(404, "proyecto no encontrado")
            folder_id = project["drive_folder_id"]
            extra_metadata = {"project_id": project_id}
        else:
            folder_id = orchestrator.document_publisher.folder_id()
        created = orchestrator.drive.upload_file(file.filename or "archivo", content, mime_type, parent_id=folder_id)
        index_result = orchestrator.drive_indexer.index_file(created, extra_metadata=extra_metadata)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"no se pudo subir/indexar el archivo: {exc}")

    indexed = index_result.get("status") == "indexed"
    response = {
        "id": created["id"],
        "name": created["name"],
        "webViewLink": created.get("webViewLink"),
        "indexed": indexed,
    }
    # Devolvemos la descripción/análisis de la imagen de inmediato, sin
    # volver a pagar la extracción — ya quedó guardada al indexar.
    if mime_type.startswith("image/") and indexed:
        response["analysis"] = orchestrator.drive_indexer.get_indexed_text(created["id"])
    return response


@app.get("/files/local/{owner_user_id}/{filename}")
def download_local_file(owner_user_id: str, filename: str, user_id: str = Depends(require_user)):
    # Un usuario solo puede descargar sus propios archivos locales (hoy hay
    # un único user_id real, pero el chequeo ya queda listo para cuando haya
    # más de uno). Path(filename).name descarta cualquier componente de
    # directorio (ej. "../../.env") antes de tocar el filesystem.
    if owner_user_id != user_id:
        raise HTTPException(403, "no autorizado")
    safe_name = Path(filename).name
    path = LOCAL_FILES_DATA_DIR / user_id / safe_name
    if not path.is_file():
        raise HTTPException(404, "archivo no encontrado")
    return FileResponse(path, filename=safe_name)


@app.get("/dashboard/summary")
def dashboard_summary(user_id: str = Depends(require_user)):
    return {
        "user_id": user_id,
        "capabilities": {
            "llm": orchestrator.llm_available,
            "stt": voice_router.stt_available,
            "tts": voice_router.tts_status()["available"],
            "google_connected": _google_connected(user_id),
        },
        "memory": orchestrator.memory.stats(),
        "cost": usage_tracker.summarize(),
    }


@app.get("/dashboard/activity")
def dashboard_activity(user_id: str = Depends(require_user)):
    # Registro real de qué herramienta ejecuta el Orchestrator y cuándo —
    # base para una futura visualización tipo "cerebro" de Snarf (ver
    # Roadmaps en MASTER_MAP.md). Todavía sin widget visual, solo el dato.
    return {"stats": activity_log.stats(), "recent": activity_log.recent(50)}


@app.get("/dashboard/brain")
def dashboard_brain(since: float | None = None, user_id: str = Depends(require_user)):
    # Grafo del "cerebro de Snarf": combina activity_log (herramientas
    # despachadas por el Orchestrator), usage_log (llamadas a Anthropic/
    # ElevenLabs/Voyage, que no tienen tool_name propio), input_log (texto/
    # voz/archivo entrando por /send, /transcribe, /files/upload) y el
    # manifiesto de indexación ya persistido. `since` es siempre el
    # `server_time` de la respuesta anterior, no un timestamp de evento —
    # así el filtro > nunca pierde ni duplica eventos entre polls.
    manifest_summary = orchestrator.drive_indexer.manifest_summary()
    snap = brain.snapshot(
        activity_log.recent(n=10000),
        usage_tracker.recent(n=10000),
        input_log.recent(n=10000),
        manifest_summary,
        since=since,
    )
    return {"server_time": time.time(), **snap}


# Fase 4-b del plan de HUD (Vista HUD del cerebro, ver SESSION_STATE.md):
# recorte mecánico de texto ya real (nunca una llamada nueva al modelo, ver
# TELEMETRY_SCHEMA.md, sección "Resumen truncado de input/output").
TELEMETRY_FEED_SUMMARY_MAX_CHARS = 80


@app.get("/dashboard/telemetry_feed")
def dashboard_telemetry_feed(since: float | None = None, user_id: str = Depends(require_user)):
    # Vista HUD del cerebro (Fase 4-b): mismo evento unificado real de Fase 1
    # (data/telemetry_events.jsonl), ya anotado acá con el verbo temático
    # determinístico (snarf/telemetry/verbs.py — nunca generado por el LLM)
    # y un resumen recortado mecánicamente de `skill`, para que el frontend
    # no tenga que duplicar ninguna de las dos tablas. Vista clásica sigue
    # leyendo /dashboard/brain sin tocar — ambas vistas parten de los mismos
    # tres logs reales que emiten el evento unificado (Fase 1), solo que la
    # Vista HUD lo consume directo en vez de a través de brain.snapshot().
    all_events = events.all_events()
    if since is not None:
        all_events = [e for e in all_events if e["timestamp"] > since]
    feed = [
        {
            **e,
            "verbo": verbs.verbo_tematico(e["nodo"], e["agente"], e["estado"], skill=e["skill"]),
            "resumen": (
                verbs.resumen_llm(e.get("modelo"))
                if e["nodo"] == "llm"
                else (e["skill"] or "")[:TELEMETRY_FEED_SUMMARY_MAX_CHARS]
            ),
        }
        for e in all_events[-100:]
    ]
    return {"server_time": time.time(), "events": feed}


@app.get("/dashboard/dock_priority")
def dashboard_dock_priority(user_id: str = Depends(require_user)):
    # Fase 5 del plan de HUD: ranking real de nodos para el dock radial
    # (Fase 2) — actividad reciente + alertas (errores) + gasto del día
    # sobre el umbral (Fase 3), nunca datos mock. Ver
    # snarf/telemetry/relevance.py.
    all_events = events.all_events()
    today_key = datetime.now(ZoneInfo(cost_history.FOUNDER_TIMEZONE)).strftime("%Y-%m-%d")
    day_summary = cost_history.by_day(all_events)
    ranking = relevance.dock_priority(all_events, relevance.DOCK_NODE_IDS, day_summary, today_key=today_key)
    return {"server_time": time.time(), "ranking": ranking}


@app.get("/dashboard/widget_summaries")
def dashboard_widget_summaries(user_id: str = Depends(require_user)):
    # Vista HUD del dashboard (rediseño radial): fuente única de qué widget
    # se ve en el tablero nuevo — mismo motor de datos que ya usa el dock de
    # globos contextuales del panel Cerebro (relevance.dock_priority), solo
    # que acá se expone TODO nodo real con actividad relevante, no un top-N
    # fijo. `curator_caption`/`curator_template` son opcionales: `None`
    # significa "el Especialista todavía no lo curó" (nodos chicos, fuera
    # del top-N curado) — en ese caso `template` cae a la plantilla default
    # mecánica de su `size_tier`, nunca un placeholder inventado.
    all_events = events.all_events()
    today_key = datetime.now(ZoneInfo(cost_history.FOUNDER_TIMEZONE)).strftime("%Y-%m-%d")
    day_summary = cost_history.by_day(all_events)
    summaries = widget_summary.all_widget_summaries(all_events, day_summary, today_key=today_key)
    curation = dashboard_curator.cached_curation() or {}
    captions = curation.get("node_captions", {})
    curated_templates = curation.get("node_templates", {})
    for s in summaries:
        # Bug real encontrado con Playwright: el template cacheado se elige
        # para el size_tier que el nodo TENÍA en el momento de curarlo — si
        # su relevancia bajó entre esa curación y este poll (el ranking se
        # recalcula en cada request, la curación no), puede haber quedado
        # con un size_tier más chico ahora. Usar el template viejo sin
        # validar metía una card de 320px en el espacio angular angosto
        # reservado para el tier "small", superponiéndose con vecinos.
        curator_template = curated_templates.get(s["node_id"])
        valid_for_current_tier = set(widget_templates.templates_for_tier(s["size_tier"]).keys())
        s["curator_caption"] = captions.get(s["node_id"])
        s["template"] = (
            curator_template if curator_template in valid_for_current_tier
            else widget_templates.DEFAULT_TEMPLATE_BY_TIER[s["size_tier"]]
        )
    return {"server_time": time.time(), "widgets": summaries}


@app.get("/dashboard/widget_templates")
def dashboard_widget_templates(user_id: str = Depends(require_user)):
    # Estática — el frontend la pide una vez al entrar a Vista HUD y la
    # cachea, en vez de duplicar a mano las 24 plantillas en JS.
    return {"templates": widget_templates.WIDGET_TEMPLATES}


@app.get("/dashboard/template_proposals")
def dashboard_template_proposals(user_id: str = Depends(require_user)):
    # Solo lectura — cola de propuestas del curador para que el fundador las
    # revise (Track A del plan v2: nunca se aplican solas, ver
    # snarf/specialists/dashboard_curator.py).
    return {"proposals": dashboard_curator_module._load_template_proposals()}


@app.get("/skill_proposals")
def skill_proposals(user_id: str = Depends(require_user)):
    # Registro de auditoría real de la Skill Factory (ver ADR 0095/0102) —
    # cada intento de construir una skill (construida/activada/abortada/
    # fallida), nunca una cola de acciones pendientes de aplicar.
    return {"proposals": orchestrator.skill_factory.list_proposals()}


@app.get("/skill_proposals/{proposal_id}")
def skill_proposal_detail(proposal_id: str, user_id: str = Depends(require_user)):
    manifest = orchestrator.skill_factory.load_manifest(proposal_id)
    if manifest is None:
        return {"error": f"proposal '{proposal_id}' no existe."}
    return manifest


@app.get("/dashboard/curation")
def dashboard_curation(user_id: str = Depends(require_user)):
    curation = dashboard_curator.cached_curation()
    return {
        "server_time": time.time(),
        "curating": dashboard_curating_in_progress,
        "headline": curation["headline"] if curation else None,
        "generated_at": curation["generated_at"] if curation else None,
    }


@app.get("/dashboard/node_activity/{node_id}")
def dashboard_node_activity(node_id: str, since: float | None = None, user_id: str = Depends(require_user)):
    # Drill-down genérico (ver plan del rediseño radial): mismos datos reales
    # que /dashboard/telemetry_feed, filtrados a un solo nodo — funciona
    # automáticamente para cualquier nodo real, incluida cualquier capacidad
    # futura que todavía no tenga un panel de detalle propio como los que ya
    # existen para drive/gmail/calendar/youtube.
    all_events = [e for e in events.all_events() if e["nodo"] == node_id]
    if since is not None:
        all_events = [e for e in all_events if e["timestamp"] > since]
    feed = [
        {**e, "verbo": verbs.verbo_tematico(e["nodo"], e["agente"], e["estado"], skill=e["skill"])}
        for e in all_events[-100:]
    ]
    return {"server_time": time.time(), "events": feed}


@app.get("/dashboard/input_efficiency")
def dashboard_input_efficiency(user_id: str = Depends(require_user)):
    # Fase 6 del plan de HUD: auditoría real de cuánto contexto viaja
    # alrededor de lo que el fundador efectivamente escribió, turno a
    # turno. Ver snarf/telemetry/input_preprocessing.py.
    return {"recent": input_preprocessing.recent(30), "summary": input_preprocessing.summary()}


@app.get("/dashboard/preferences")
def get_dashboard_preferences(user_id: str = Depends(require_user)):
    return load_prefs(user_id)


@app.put("/dashboard/preferences")
def put_dashboard_preferences(payload: DashboardPreferences, user_id: str = Depends(require_user)):
    # Bug real encontrado en vivo (2026-08-05, mismo patrón que el fix de
    # PUT /llm-routing de esta misma ronda): DashboardPreferences declara un
    # default propio en cada campo (visible_widgets={}, widget_options={},
    # etc.) — un PUT parcial (cualquier cliente que no mande TODOS los
    # campos) pisaba en silencio cada campo omitido con ese default vacío,
    # perdiendo customización real ya guardada (tamaños/orden de widgets,
    # estado y posición de nodos HUD). El frontend real siempre manda el
    # objeto completo (persistPrefs() hace JSON.stringify(dashboardPrefs) tal
    # cual se cargó), así que este merge no le cambia el comportamiento —
    # solo protege contra un PUT parcial de cualquier otro cliente.
    merged = {**load_prefs(user_id), **payload.model_dump(exclude_unset=True)}
    return save_prefs(user_id, merged)


@app.get("/personality/preferences")
def get_personality_preferences(user_id: str = Depends(require_user)):
    return load_personality_prefs(user_id)


@app.put("/personality/preferences")
def put_personality_preferences(payload: PersonalityPreferences, user_id: str = Depends(require_user)):
    return save_personality_prefs(user_id, payload.model_dump())


@app.get("/llm-routing")
def get_llm_routing(user_id: str = Depends(require_user)):
    return {"routing": llm_routing.load_routing(), "available_providers": llm_routing.available_providers()}


@app.put("/llm-routing")
def put_llm_routing(payload: dict[str, dict], user_id: str = Depends(require_user)):
    # Bug real encontrado en vivo (2026-08-05): save_routing() completa
    # cualquier rol ausente del payload con DEFAULT_ROUTING, no con lo que ya
    # estaba guardado — el frontend manda un solo rol por PUT
    # (persistLlmRouting en web/index.html), así que sin este merge, elegir
    # UN proveedor nuevo para UN rol desde Configuración reseteaba en
    # silencio TODOS los demás roles a los defaults del código. attempt_fallback
    # (llm_routing.py) ya mergeaba así — el endpoint era la única ruta rota.
    routing = llm_routing.save_routing({**llm_routing.load_routing(), **payload})
    # Sin esto, cambiar un rol acá no tenía ningún efecto hasta el próximo
    # reinicio del servidor — self._llm/self._title_llm quedaban resueltos
    # una sola vez al construir el Orchestrator (bug real encontrado
    # probando esta misma ronda). Los otros 3 roles ya son dinámicos por sí
    # solos (factory), no necesitan este refresh.
    orchestrator.refresh_llm_routing()
    return {"routing": routing, "available_providers": llm_routing.available_providers()}


@app.get("/llm-routing/fallback_events")
def get_llm_fallback_events(since: float | None = None, user_id: str = Depends(require_user)):
    # Registro trazable real de cada vez que un rol cambió de proveedor solo
    # (ver llm_routing.generate_with_fallback) — el frontend lo poll-ea para
    # avisar en el chat apenas pasa algo nuevo, `since` (server_time del
    # último visto) evita re-mostrar lo mismo en cada carga.
    return {"events": llm_routing.recent_fallback_events(since=since), "server_time": time.time()}


@app.get("/profile")
def get_profile(user_id: str = Depends(require_user)):
    return load_user_profile(user_id)


@app.put("/profile")
def put_profile(payload: ProfileRequest, user_id: str = Depends(require_user)):
    return save_user_profile(user_id, payload.model_dump())


@app.get("/dashboard/widgets/usage")
def dashboard_widget_usage(user_id: str = Depends(require_user)):
    metrics = usage_tracker.usage_metrics()
    cost_by_vendor = usage_tracker.summarize()["by_vendor_usd"]
    result = {
        vendor: {**data, "cost_usd": cost_by_vendor.get(vendor)}
        for vendor, data in metrics.items()
    }
    if _elevenlabs_for_dashboard.available:
        try:
            result.setdefault("elevenlabs", {})["subscription"] = _elevenlabs_for_dashboard.subscription_info()
        except Exception as exc:
            result.setdefault("elevenlabs", {})["subscription_error"] = str(exc)
    return {"vendors": result}


@app.get("/dashboard/cost_history")
def dashboard_cost_history(user_id: str = Depends(require_user)):
    # Fase 3 del plan de HUD (ver SESSION_STATE.md): agrega el evento
    # unificado de telemetría (Fase 1) por día/agente/sesión — todos los
    # eventos reales guardados hasta ahora, no solo los últimos N (una
    # agregación histórica recortada mentiría el total).
    return cost_history.summary(events.all_events())


@app.get("/dashboard/widgets/drive")
def dashboard_widget_drive(user_id: str = Depends(require_user)):
    if not _google_connected(user_id):
        return {"connected": False}
    try:
        files = orchestrator.drive.list_files(page_size=10)
        files.sort(key=lambda f: f.get("modifiedTime", ""), reverse=True)
        return {"connected": True, "files": files[:5]}
    except Exception as exc:
        return {"connected": True, "error": str(exc)}


@app.get("/dashboard/widgets/gmail")
def dashboard_widget_gmail(max_results: int = 5, user_id: str = Depends(require_user)):
    if not _google_connected(user_id):
        return {"connected": False}
    max_results = min(max(max_results, 1), 20)
    try:
        messages = orchestrator.gmail.list_messages(max_results=max_results)
        return {"connected": True, "messages": messages}
    except Exception as exc:
        return {"connected": True, "error": str(exc)}


@app.get("/dashboard/widgets/gmail/digest")
def dashboard_gmail_digest(user_id: str = Depends(require_user)):
    if not _google_connected(user_id):
        return {"connected": False}
    return {"connected": True, "digest": orchestrator.gmail_digest.cached_digest()}


@app.post("/dashboard/widgets/gmail/digest/refresh")
def dashboard_gmail_digest_refresh(user_id: str = Depends(require_user)):
    if not _google_connected(user_id):
        return {"connected": False}
    try:
        return {"connected": True, "digest": orchestrator.gmail_digest.refresh()}
    except Exception as exc:
        return {"connected": True, "error": str(exc)}


@app.get("/dashboard/widgets/calendar/brief")
def dashboard_calendar_brief(user_id: str = Depends(require_user)):
    if not _google_connected(user_id):
        return {"connected": False}
    return {"connected": True, "brief": orchestrator.calendar_brief.cached_brief()}


@app.post("/dashboard/widgets/calendar/brief/refresh")
def dashboard_calendar_brief_refresh(user_id: str = Depends(require_user)):
    if not _google_connected(user_id):
        return {"connected": False}
    try:
        return {"connected": True, "brief": orchestrator.calendar_brief.refresh()}
    except Exception as exc:
        return {"connected": True, "error": str(exc)}


@app.get("/dashboard/widgets/executive_board")
def dashboard_executive_board(user_id: str = Depends(require_user)):
    # Muestra la última consulta real cacheada (ver ADR 0094/0098) — nunca
    # dispara una consulta nueva desde un GET de poll del navegador, mismo
    # criterio que el resto de los widgets cache-first.
    return {"consult": orchestrator.executive_board.cached_consult()}


@app.post("/dashboard/widgets/executive_board/consult")
def dashboard_executive_board_consult(payload: dict, user_id: str = Depends(require_user)):
    question = payload.get("question", "")
    if not question:
        return {"error": "Falta 'question'."}
    try:
        return orchestrator.executive_board.consult(question, roles=payload.get("roles"))
    except Exception as exc:
        return {"error": str(exc)}


@app.get("/dashboard/widgets/calendar")
def dashboard_widget_calendar(user_id: str = Depends(require_user)):
    if not _google_connected(user_id):
        return {"connected": False}
    try:
        events = orchestrator.calendar.list_upcoming_events(max_results=5)
        return {"connected": True, "events": events}
    except Exception as exc:
        return {"connected": True, "error": str(exc)}


@app.get("/dashboard/widgets/youtube")
def dashboard_widget_youtube(user_id: str = Depends(require_user)):
    if not _google_connected(user_id):
        return {"connected": False}
    try:
        subscriptions = orchestrator.youtube.list_subscriptions(max_results=5)
        return {"connected": True, "subscriptions": subscriptions}
    except Exception as exc:
        return {"connected": True, "error": str(exc)}


@app.get("/conversations")
def list_conversations(user_id: str = Depends(require_user)):
    # La lista general de la barra lateral son las conversaciones SIN
    # proyecto asignado — las que sí tienen uno viven en la lista propia de
    # ese proyecto (GET /projects/{id}/conversations). El uso conversacional
    # (tool list_conversations, para que Snarf recuerde todo) no pasa por
    # acá y sigue viendo el historial completo.
    return orchestrator.memory.list_conversations(unassigned_only=True)


# Tamaño de página al abrir/paginar una conversación desde el chat (ver
# loadConversation() en web/index.html) — la tool conversacional
# get_conversation y generate_conversation_title siguen pidiendo la
# conversación entera (sin limit) directo contra EpisodicMemory, esto solo
# aplica a esta ruta HTTP.
CONVERSATION_PAGE_SIZE = 30


@app.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: str, limit: int = CONVERSATION_PAGE_SIZE, before: float | None = None, user_id: str = Depends(require_user)
):
    # Pide un elemento de más para saber si queda más historial antes del
    # tramo devuelto, sin un segundo query — se descarta antes de responder.
    page = orchestrator.memory.get_conversation(conversation_id, limit=limit + 1, before_timestamp=before)
    has_more = len(page) > limit
    return {"entries": page[-limit:] if has_more else page, "has_more": has_more}


@app.put("/conversations/{conversation_id}/project")
def assign_conversation_to_project(
    conversation_id: str, payload: ConversationProjectRequest, user_id: str = Depends(require_user)
):
    if orchestrator.projects.get(payload.project_id) is None:
        raise HTTPException(404, "proyecto no encontrado")
    return orchestrator.memory.assign_conversation(conversation_id, payload.project_id)


@app.delete("/conversations/{conversation_id}/project")
def unassign_conversation_from_project(conversation_id: str, user_id: str = Depends(require_user)):
    return orchestrator.memory.unassign_conversation(conversation_id)


# Igual que /dashboard/widgets/gmail/digest/refresh: estas rutas llaman
# directo a ProjectManager, sin pasar por _handle_tool — no generan pulso en
# el cerebro de Snarf (sí lo genera el camino conversacional, project_create
# etc. dichas en el chat). Misma asimetría ya aceptada para el digest de
# Gmail, no un problema nuevo.
@app.get("/projects")
def list_projects(user_id: str = Depends(require_user)):
    return orchestrator.projects.list_projects()


@app.post("/projects")
def create_project(payload: ProjectCreateRequest, user_id: str = Depends(require_user)):
    if not _google_connected(user_id):
        raise HTTPException(400, "Google no conectado")
    try:
        return orchestrator.projects.create(payload.name)
    except Exception as exc:
        raise HTTPException(502, f"no se pudo crear el proyecto: {exc}")


@app.get("/projects/{project_id}")
def get_project(project_id: str, user_id: str = Depends(require_user)):
    # cached_summary genera el resumen la primera vez que se pide (mismo
    # patrón que GmailDigestSpecialist.cached_digest() or refresh()) — así el
    # "home" de un proyecto recién creado no llega vacío a la primera vista.
    project = orchestrator.projects.cached_summary(project_id)
    if project is None:
        raise HTTPException(404, "proyecto no encontrado")
    project["file_count"] = orchestrator.projects.file_count(project_id)
    project["pending_task_count"] = sum(1 for t in project["tasks"] if not t["done"])
    project["conversations"] = orchestrator.memory.list_conversations(project_id=project_id)
    return project


@app.get("/projects/{project_id}/conversations")
def list_project_conversations(project_id: str, user_id: str = Depends(require_user)):
    if orchestrator.projects.get(project_id) is None:
        raise HTTPException(404, "proyecto no encontrado")
    return orchestrator.memory.list_conversations(project_id=project_id)


@app.post("/projects/{project_id}/summary/refresh")
def refresh_project_summary(project_id: str, user_id: str = Depends(require_user)):
    project = orchestrator.projects.generate_summary(project_id)
    if project is None:
        raise HTTPException(404, "proyecto no encontrado")
    return project


@app.put("/projects/{project_id}/prompt")
def set_project_prompt(project_id: str, payload: ProjectPromptRequest, user_id: str = Depends(require_user)):
    project = orchestrator.projects.set_prompt(project_id, payload.prompt)
    if project is None:
        raise HTTPException(404, "proyecto no encontrado")
    return project


@app.post("/projects/{project_id}/tasks")
def add_project_task(project_id: str, payload: ProjectTextRequest, user_id: str = Depends(require_user)):
    project = orchestrator.projects.add_task(project_id, payload.text)
    if project is None:
        raise HTTPException(404, "proyecto no encontrado")
    return project


@app.patch("/projects/{project_id}/tasks/{task_id}")
def toggle_project_task(project_id: str, task_id: str, user_id: str = Depends(require_user)):
    project = orchestrator.projects.complete_task(project_id, task_id)
    if project is None:
        raise HTTPException(404, "proyecto no encontrado")
    return project


@app.delete("/projects/{project_id}/tasks/{task_id}")
def delete_project_task(project_id: str, task_id: str, user_id: str = Depends(require_user)):
    project = orchestrator.projects.delete_task(project_id, task_id)
    if project is None:
        raise HTTPException(404, "proyecto no encontrado")
    return project


@app.post("/projects/{project_id}/notes")
def add_project_note(project_id: str, payload: ProjectTextRequest, user_id: str = Depends(require_user)):
    project = orchestrator.projects.add_note(project_id, payload.text)
    if project is None:
        raise HTTPException(404, "proyecto no encontrado")
    return project


@app.delete("/projects/{project_id}/notes/{note_id}")
def delete_project_note(project_id: str, note_id: str, user_id: str = Depends(require_user)):
    project = orchestrator.projects.delete_note(project_id, note_id)
    if project is None:
        raise HTTPException(404, "proyecto no encontrado")
    return project


@app.delete("/projects/{project_id}")
def delete_project(project_id: str, confirmed: bool = False, user_id: str = Depends(require_user)):
    # El camino conversacional muestra una vista previa y espera el próximo
    # turno antes de confirmar — una request HTTP no puede replicar eso. El
    # frontend es responsable de pedir una confirmación real (window.confirm)
    # antes de mandar ?confirmed=true; sin el flag, se rechaza en vez de
    # borrar en silencio.
    if not confirmed:
        raise HTTPException(400, "falta confirmar (?confirmed=true)")
    if orchestrator.projects.get(project_id) is None:
        raise HTTPException(404, "proyecto no encontrado")
    return orchestrator.projects.delete(project_id)


def _lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


if __name__ == "__main__":
    import uvicorn

    print(f"Local:  http://127.0.0.1:8000")
    print(f"Red:    http://{_lan_ip()}:8000  (mismo Wi-Fi; el micrófono puede requerir HTTPS, ver README)")
    uvicorn.run(app, host="0.0.0.0", port=8000)
