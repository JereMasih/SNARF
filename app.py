import base64
import socket

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from snarf.capabilities.elevenlabs_stt import ElevenLabsSTT
from snarf.capabilities.elevenlabs_tts import ElevenLabsTTS
from snarf.core.orchestrator import Orchestrator

app = FastAPI()
stt = ElevenLabsSTT()
tts = ElevenLabsTTS()
orchestrator = Orchestrator()


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


@app.get("/")
def index():
    return FileResponse("web/index.html")


@app.get("/status")
def status():
    return {
        "stt_available": stt.available,
        "tts_available": tts.available,
        "llm_available": orchestrator.llm_available,
    }


@app.post("/transcribe")
async def transcribe(file: UploadFile):
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
def send(payload: SendRequest):
    response_text = orchestrator.handle("visual", payload.text, conversation_id=payload.conversation_id)
    return SendResponse(response=response_text)


@app.post("/tts", response_model=TTSResponse)
def synthesize_speech(payload: TTSRequest):
    if not tts.available:
        return TTSResponse(audio_base64=None)
    audio_bytes = tts.synthesize(payload.text)
    return TTSResponse(audio_base64=base64.b64encode(audio_bytes).decode("ascii"))


@app.get("/conversations")
def list_conversations():
    return orchestrator.memory.list_conversations()


@app.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str):
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
