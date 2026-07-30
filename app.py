import asyncio
import base64
import os
import socket
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import Cookie, Depends, FastAPI, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

from snarf.capabilities.elevenlabs_stt import ElevenLabsSTT
from snarf.capabilities.elevenlabs_tts import ElevenLabsTTS
from snarf.capabilities.google_auth import TOKENS_DIR as GOOGLE_TOKENS_DIR
from snarf.core.orchestrator import DEFAULT_USER_ID, LOCAL_FILES_DATA_DIR, Orchestrator
from snarf.runtime.dashboard_prefs import load_prefs, save_prefs
from snarf.runtime.personality_prefs import load_prefs as load_personality_prefs, save_prefs as save_personality_prefs
from snarf.runtime import data_backup
from snarf.knowledge.extraction import categorize_mime
from snarf.telemetry import activity_log, brain, input_log, usage_tracker
from snarf.runtime.web_auth import (
    SESSION_COOKIE_NAME,
    SESSION_MAX_AGE_SECONDS,
    create_session_token,
    is_authenticated,
    password_matches,
    require_user,
)

app = FastAPI()
stt = ElevenLabsSTT()
tts = ElevenLabsTTS()
orchestrator = Orchestrator(user_id=DEFAULT_USER_ID)

def _google_connected(user_id: str) -> bool:
    return (GOOGLE_TOKENS_DIR / f"{user_id}.json").exists()


BACKUP_INTERVAL_SECONDS = 6 * 3600


async def _periodic_backup_loop():
    while True:
        await asyncio.sleep(BACKUP_INTERVAL_SECONDS)
        data_backup.backup_now()


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


class SendRequest(BaseModel):
    text: str
    conversation_id: str | None = None


class SendResponse(BaseModel):
    response: str


class TTSRequest(BaseModel):
    text: str


class TTSResponse(BaseModel):
    audio_base64: str | None = None


class LoginRequest(BaseModel):
    password: str


class DashboardPreferences(BaseModel):
    visible_widgets: dict[str, bool] = {}
    panel_order: list[str] = []
    widget_options: dict[str, dict] = {}


class PersonalityPreferences(BaseModel):
    sarcasm_level: float = 7.5


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
        "stt_available": stt.available,
        "tts_available": tts.available,
        "llm_available": orchestrator.llm_available,
    }


@app.post("/transcribe")
async def transcribe(file: UploadFile, user_id: str = Depends(require_user)):
    if not stt.available:
        return {"transcript": ""}
    audio_bytes = await file.read()
    if len(audio_bytes) < 2000:
        return {"transcript": ""}
    input_log.record("voice")
    try:
        text = stt.transcribe(audio_bytes, filename=file.filename or "audio.webm")
    except Exception as exc:
        print(f"[transcribe] fallo de STT, degradando a transcript vacío: {exc}")
        # Distinto de "no se detectó voz" (audio corto, o Scribe transcribió
        # silencio real): acá el servicio en sí falló (cuota agotada, red,
        # etc.) — sin este campo, la interfaz no puede distinguir ambos casos
        # y termina diciéndole al usuario "no se escuchó nada" cuando en
        # realidad el micrófono funcionó perfecto.
        return {"transcript": "", "error": "no se pudo transcribir: el servicio de voz no está disponible ahora"}
    return {"transcript": text}


@app.post("/send", response_model=SendResponse)
def send(payload: SendRequest, user_id: str = Depends(require_user)):
    input_log.record("text")
    # El proyecto de la conversación (si tiene uno asignado) se resuelve solo
    # dentro de orchestrator.handle() por conversation_id — ver Proyectos
    # Mark II. Ya no viaja como parámetro por mensaje.
    response_text = orchestrator.handle("visual", payload.text, conversation_id=payload.conversation_id)
    return SendResponse(response=response_text)


@app.post("/tts", response_model=TTSResponse)
def synthesize_speech(payload: TTSRequest, user_id: str = Depends(require_user)):
    if not tts.available:
        return TTSResponse(audio_base64=None)
    audio_bytes = tts.synthesize(payload.text)
    return TTSResponse(audio_base64=base64.b64encode(audio_bytes).decode("ascii"))


@app.post("/files/upload")
async def upload_file(file: UploadFile, project_id: str | None = Form(None), user_id: str = Depends(require_user)):
    if not _google_connected(user_id):
        raise HTTPException(400, "Google no conectado")
    content = await file.read()
    mime_type = file.content_type or "application/octet-stream"
    input_log.record("file", category=categorize_mime(mime_type))
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
            "stt": stt.available,
            "tts": tts.available,
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


@app.get("/dashboard/preferences")
def get_dashboard_preferences(user_id: str = Depends(require_user)):
    return load_prefs(user_id)


@app.put("/dashboard/preferences")
def put_dashboard_preferences(payload: DashboardPreferences, user_id: str = Depends(require_user)):
    return save_prefs(user_id, payload.model_dump())


@app.get("/personality/preferences")
def get_personality_preferences(user_id: str = Depends(require_user)):
    return load_personality_prefs(user_id)


@app.put("/personality/preferences")
def put_personality_preferences(payload: PersonalityPreferences, user_id: str = Depends(require_user)):
    return save_personality_prefs(user_id, payload.model_dump())


@app.get("/dashboard/widgets/usage")
def dashboard_widget_usage(user_id: str = Depends(require_user)):
    metrics = usage_tracker.usage_metrics()
    cost_by_vendor = usage_tracker.summarize()["by_vendor_usd"]
    result = {
        vendor: {**data, "cost_usd": cost_by_vendor.get(vendor)}
        for vendor, data in metrics.items()
    }
    if tts.available:
        try:
            result.setdefault("elevenlabs", {})["subscription"] = tts.subscription_info()
        except Exception as exc:
            result.setdefault("elevenlabs", {})["subscription_error"] = str(exc)
    return {"vendors": result}


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


@app.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str, user_id: str = Depends(require_user)):
    return orchestrator.memory.get_conversation(conversation_id)


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
