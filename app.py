import base64
import os
import socket
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import Cookie, Depends, FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

from snarf.capabilities.elevenlabs_stt import ElevenLabsSTT
from snarf.capabilities.elevenlabs_tts import ElevenLabsTTS
from snarf.capabilities.google_auth import TOKENS_DIR as GOOGLE_TOKENS_DIR
from snarf.core.orchestrator import DEFAULT_USER_ID, LOCAL_FILES_DATA_DIR, Orchestrator
from snarf.runtime.dashboard_prefs import load_prefs, save_prefs
from snarf.telemetry import activity_log, usage_tracker
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


@app.on_event("startup")
def warmup():
    orchestrator.warmup()


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
        SESSION_COOKIE_NAME, token, max_age=SESSION_MAX_AGE_SECONDS, httponly=True, samesite="lax"
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
    try:
        text = stt.transcribe(audio_bytes, filename=file.filename or "audio.webm")
    except Exception as exc:
        print(f"[transcribe] fallo de STT, degradando a transcript vacío: {exc}")
        return {"transcript": ""}
    return {"transcript": text}


@app.post("/send", response_model=SendResponse)
def send(payload: SendRequest, user_id: str = Depends(require_user)):
    response_text = orchestrator.handle("visual", payload.text, conversation_id=payload.conversation_id)
    return SendResponse(response=response_text)


@app.post("/tts", response_model=TTSResponse)
def synthesize_speech(payload: TTSRequest, user_id: str = Depends(require_user)):
    if not tts.available:
        return TTSResponse(audio_base64=None)
    audio_bytes = tts.synthesize(payload.text)
    return TTSResponse(audio_base64=base64.b64encode(audio_bytes).decode("ascii"))


@app.post("/files/upload")
async def upload_file(file: UploadFile, user_id: str = Depends(require_user)):
    if not _google_connected(user_id):
        raise HTTPException(400, "Google no conectado")
    content = await file.read()
    mime_type = file.content_type or "application/octet-stream"
    try:
        folder_id = orchestrator.document_publisher.folder_id()
        created = orchestrator.drive.upload_file(file.filename or "archivo", content, mime_type, parent_id=folder_id)
        index_result = orchestrator.drive_indexer.index_file(created)
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


@app.get("/dashboard/preferences")
def get_dashboard_preferences(user_id: str = Depends(require_user)):
    return load_prefs(user_id)


@app.put("/dashboard/preferences")
def put_dashboard_preferences(payload: DashboardPreferences, user_id: str = Depends(require_user)):
    return save_prefs(user_id, payload.model_dump())


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
    return orchestrator.memory.list_conversations()


@app.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str, user_id: str = Depends(require_user)):
    return orchestrator.memory.get_conversation(conversation_id)


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
